// processor/commandProcessor.js
import config from '../config/index.js';
import { resolveCachePlan } from './command/commandCachePolicy.js';
import {
  persistIdempotentResponse,
  tryReadCachedResult,
  tryReplayFromIdempotency,
  writeCachedResult,
} from './command/redisCommandCache.js';

class CommandProcessor {
  constructor({ redisClient, sessionManager, rabbitClient, commandExecutor }) {
    this.redis = redisClient;
    this.sessions = sessionManager;
    this.rabbit = rabbitClient;
    this.executor = commandExecutor;

    this.commandStats = {
      totalProcessed: 0,
      cacheHits: 0,
      cacheMisses: 0,
      errors: 0,
    };
  }

  /**
   * Main entry to process a commandData object. Returns a result object.
   */
  async processCommand(commandData) {
    const { commandId, command, parameters = {}, sessionId } = commandData;
    this.commandStats.totalProcessed += 1;
    if (!sessionId) throw new Error('Session ID is required');

    const session = this.sessions.getOrCreate(sessionId);
    session.lastActivity = new Date().toISOString();
    session.logger.command(commandId, 'RECEIVED', `command: ${command}`);

    session.commandQueue = session.commandQueue
      .catch((queueError) => {
        session.logger.error(
          `Previous command in queue failed, continuing with next command: ${
            queueError && queueError.message ? queueError.message : String(queueError)
          }`,
        );
      })
      .then(async () => {
      try {
        const { ttl, shouldCache } = resolveCachePlan(command, parameters);
        const redis = this.redis && this.redis.isOpen ? this.redis : null;

        if (shouldCache && redis) {
          const idemHit = await tryReplayFromIdempotency({
            redis,
            commandId,
            session,
            commandStats: this.commandStats,
          });
          if (idemHit) return idemHit;

          const cacheHit = await tryReadCachedResult({
            redis,
            command,
            parameters,
            session,
            commandId,
            commandStats: this.commandStats,
          });
          if (cacheHit) return cacheHit;
        }

        this.commandStats.cacheMisses += 1;
        session.logger.command(commandId, 'EXECUTING');
        session.lastCommandId = commandId;

        const execTimeoutMs = config.commands.execTimeoutMs;
        let result;
        if (execTimeoutMs > 0) {
          result = await Promise.race([
            this.executor.runCommand(command, parameters, session),
            new Promise((resolve) => {
              setTimeout(() => {
                resolve({
                  error: 'Command execution timeout',
                  command,
                  executionTime: execTimeoutMs,
                });
              }, execTimeoutMs);
            }),
          ]);
        } else {
          result = await this.executor.runCommand(command, parameters, session);
        }

        if (shouldCache && !result.error && redis) {
          await writeCachedResult({
            redis,
            command,
            parameters,
            session,
            ttl,
            result,
            commandId,
          });
        }

        session.logger.command(commandId, 'COMPLETED');

        const response = {
          commandId,
          result,
          cached: false,
          sessionId: session.sessionId,
          currentPath: session.currentPath,
          timestamp: new Date().toISOString(),
        };

        if (result && result.error) {
          response.error = result.error;
        }

        if (shouldCache && !response.error && redis) {
          await persistIdempotentResponse({
            redis,
            commandId,
            ttl,
            response,
            session,
          });
        }

        return response;
      } catch (err) {
        this.commandStats.errors += 1;
        session.logger.error(
          `Command processing failed: ${err && err.message ? err.message : JSON.stringify(err)}`,
        );
        throw err;
      }
      });

    return session.commandQueue;
  }
}

export default CommandProcessor;
