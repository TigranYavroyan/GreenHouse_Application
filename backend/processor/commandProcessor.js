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

  getTTLForCommand(command, parameters = {}) {
    const ttlConfig = {
      // Greenhouse core sensor readings: always live for sync correctness.
      read_temperature_data: 0,
      read_humidity_data: 0,
      read_light_data: 0,
      read_co2_data: 0,
      read_soil_moisture_data: 0,
      read_soil_ph_data: 0,
      read_sensor: 0, // Legacy sensor read command
      // Device control commands (stateful - don't cache)
      switch_water_canal: 0,
      switch_actuator: 0,
      switch_fan: 0,
      switch_heater: 0
    };

    if (Object.prototype.hasOwnProperty.call(ttlConfig, command)) {
      return ttlConfig[command];
    }
    return 8;
  }

  isStateful(command) {
    // Commands that change state and should not be cached
    const statefulCommands = [
      'switch_water_canal',
      'switch_actuator',
      'switch_fan',
      'switch_heater'
    ];
    return statefulCommands.includes(command);
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
        const ttl = this.getTTLForCommand(command, parameters);
        const shouldCache = !this.isStateful(command) && ttl > 0;

        // cache lookup for cacheable commands
        if (shouldCache && this.redis && this.redis.isOpen) {
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
        // Store commandId in session temporarily for executor to use
        session.lastCommandId = commandId;
        const result = await this.executor.runCommand(command, parameters, session);

        // Cache only successful results for commands with positive TTL.
        if (shouldCache && !result.error && this.redis && this.redis.isOpen) {
          const cacheKey = this.generateCacheKey(command, parameters, session.currentPath, session.sessionId);
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
