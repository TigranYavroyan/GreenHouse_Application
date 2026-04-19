/**
 * Redis-backed idempotency (idem:commandId) and per-session command result cache (cmd:...).
 */
import SystemLogger from '../../logger/systemLogger.js';
import { generateCacheKey } from './commandCachePolicy.js';

export async function tryReplayFromIdempotency({
  redis,
  commandId,
  session,
  commandStats,
}) {
  const idemKey = `idem:${commandId}`;
  const idemRaw = await redis.get(idemKey);
  if (!idemRaw) return null;

  try {
    const prior = JSON.parse(idemRaw);
    if (prior && prior.commandId === commandId) {
      commandStats.cacheHits += 1;
      session.logger.command(commandId, 'IDEMPOTENCY_HIT');
      return {
        ...prior,
        cached: true,
        sessionId: session.sessionId,
        currentPath: session.currentPath,
        timestamp: new Date().toISOString(),
      };
    }
  } catch {
    SystemLogger.warn(`Corrupted idempotency entry for ${commandId}, deleting: ${idemKey}`);
    try {
      await redis.del([idemKey]);
    } catch (delErr) {
      SystemLogger.warn(`Failed to delete corrupted idempotency key: ${delErr.message}`);
    }
  }
  return null;
}

export async function tryReadCachedResult({
  redis,
  command,
  parameters,
  session,
  commandId,
  commandStats,
}) {
  const cacheKey = generateCacheKey(command, parameters, session.currentPath, session.sessionId);
  const cached = await redis.get(cacheKey);
  if (!cached) return null;

  try {
    const cachedResult = JSON.parse(cached);
    commandStats.cacheHits += 1;
    session.logger.command(commandId, 'CACHE_HIT');
    return {
      commandId,
      result: cachedResult,
      cached: true,
      sessionId: session.sessionId,
      currentPath: session.currentPath,
      timestamp: new Date().toISOString(),
    };
  } catch {
    SystemLogger.warn(
      `Failed to parse cached result for ${command}, deleting corrupted cache entry: ${cacheKey}`,
    );
    try {
      await redis.del([cacheKey]);
    } catch (e) {
      SystemLogger.warn(`Failed to delete corrupted cache entry: ${e.message}`);
    }
  }
  return null;
}

export async function writeCachedResult({
  redis,
  command,
  parameters,
  session,
  ttl,
  result,
  commandId,
}) {
  const cacheKey = generateCacheKey(command, parameters, session.currentPath, session.sessionId);
  try {
    await redis.setEx(cacheKey, ttl, JSON.stringify(result));
    session.logger.command(commandId, 'CACHED', `TTL:${ttl}s`);
  } catch (e) {
    SystemLogger.warn(`Failed to cache result: ${e.message}`);
  }
}

export async function persistIdempotentResponse({
  redis,
  commandId,
  ttl,
  response,
  session,
}) {
  const idemKey = `idem:${commandId}`;
  const idemTtl = Math.max(ttl, 60);
  try {
    await redis.setEx(idemKey, idemTtl, JSON.stringify(response));
    session.logger.command(commandId, 'IDEMPOTENCY_STORED', `TTL:${idemTtl}s`);
  } catch (e) {
    SystemLogger.warn(`Failed to store idempotency key: ${e.message}`);
  }
}
