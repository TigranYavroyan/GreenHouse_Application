// processor/commandProcessor.js
import SystemLogger from '../logger/systemLogger.js';

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
      errors: 0
    };
  }

  generateCacheKey(command, parameters, currentPath, sessionId) {
    // Ensure parameters are sorted for consistent cache keys
    const sortedParams = parameters ? Object.keys(parameters).sort().reduce((obj, key) => {
      obj[key] = parameters[key];
      return obj;
    }, {}) : {};
    return `cmd:${sessionId}:${command}:${currentPath}:${JSON.stringify(sortedParams)}`;
  }

  getTTLForCommand(command) {
    const ttlConfig = {
      list_directory: 15,
      system_status: 8,
      read_sensor: 5,
      get_current_path: 15,
      execute_raw: 0
    };
    return ttlConfig[command] || 8;
  }

  isStateful(command) {
    return command === 'navigate' || command === 'change_directory' || command === 'execute_raw';
  }

  /**
   * Main entry to process a commandData object. Returns a result object.
   */
  async processCommand(commandData) {
    const { commandId, command, parameters = {}, sessionId } = commandData;
    this.commandStats.totalProcessed++;
    if (!sessionId) throw new Error('Session ID is required');

    const session = this.sessions.getOrCreate(sessionId);
    session.lastActivity = new Date().toISOString();
    session.logger.command(commandId, 'RECEIVED', `command: ${command}`);

    // queue per-session sequential execution
    session.commandQueue = session.commandQueue.then(async () => {
      try {
        // cache lookup for non-stateful commands
        if (!this.isStateful(command) && this.redis && this.redis.isOpen) {
          const cacheKey = this.generateCacheKey(command, parameters, session.currentPath, session.sessionId);
          const cached = await this.redis.get(cacheKey);
          if (cached) {
            try {
              const cachedResult = JSON.parse(cached);
              this.commandStats.cacheHits++;
              session.logger.command(commandId, 'CACHE_HIT');
              return {
                commandId,
                result: cachedResult,
                cached: true,
                sessionId: session.sessionId,
                currentPath: session.currentPath,
                timestamp: new Date().toISOString()
              };
            } catch (parseError) {
              // If we can't parse the cached value, delete it and continue
              SystemLogger.warn(`Failed to parse cached result for ${command}, deleting corrupted cache entry: ${cacheKey}`);
              try {
                await this.redis.del([cacheKey]);
              } catch (e) {
                SystemLogger.warn(`Failed to delete corrupted cache entry: ${e.message}`);
              }
              // Continue with fresh execution
            }
          }
        }

        this.commandStats.cacheMisses++;
        session.logger.command(commandId, 'EXECUTING');
        const result = await this.executor.runCommand(command, parameters, session);

        // update session path if navigate/change_directory succeeded and returned output pwd
        if ((command === 'navigate' || command === 'change_directory') && result.output && !result.error) {
          const newPath = (result.output || '').trim();
          if (newPath) {
            session.previousPath = session.currentPath;
            session.currentPath = newPath;
          }
        }

        // caching - only cache successful results (no errors)
        if (!this.isStateful(command) && !result.error && this.redis && this.redis.isOpen) {
          const cacheKey = this.generateCacheKey(command, parameters, session.currentPath, session.sessionId);
          const ttl = this.getTTLForCommand(command);
          try {
            await this.redis.setEx(cacheKey, ttl, JSON.stringify(result));
            session.logger.command(commandId, 'CACHED', `TTL:${ttl}s`);
          } catch (e) {
            SystemLogger.warn(`Failed to cache result: ${e.message}`);
          }
        }

        session.logger.command(commandId, 'COMPLETED');
        
        // If result contains an error, move it to top level for consistent error handling
        const response = {
          commandId,
          result,
          cached: false,
          sessionId: session.sessionId,
          currentPath: session.currentPath,
          timestamp: new Date().toISOString()
        };
        
        // Move error from result.error to top-level error if present
        if (result && result.error) {
          response.error = result.error;
          // Optionally keep error in result for backward compatibility
        }
        
        return response;

      } catch (err) {
        this.commandStats.errors++;
        session.logger.error(`Command processing failed: ${err && err.message ? err.message : JSON.stringify(err)}`);
        throw err;
      }
    });

    // return the promise result (the queued job)
    return session.commandQueue;
  }
}

export default CommandProcessor;
