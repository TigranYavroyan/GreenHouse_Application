// executor/commandExecutor.js

class CommandExecutor {
  constructor(systemLogger, greenhouseCoreClient = null) {
    this.systemLogger = systemLogger;
    this.greenhouseCoreClient = greenhouseCoreClient;
  }

  /**
   * Check if command is a greenhouse-specific command
   */
  isGreenhouseCommand(commandName) {
    const greenhouseCommands = [
      // Sensor reading commands
      'read_temperature_data',
      'read_humidity_data',
      'read_light_data',
      'read_co2_data',
      'read_soil_moisture_data',
      'read_soil_ph_data',
      'read_sensor', // Legacy command, routes to appropriate sensor based on parameters
      // Device control commands
      'switch_water_canal',
      'switch_actuator',
      'switch_fan',
      'switch_heater'
    ];
    return greenhouseCommands.includes(commandName);
  }

  /**
   * Execute greenhouse command via core client
   */
  async executeGreenhouseCommand(commandName, parameters = {}, session) {
    if (!this.greenhouseCoreClient) {
      session.logger.error(`Greenhouse core client not available for command: ${commandName}`);
      return { error: 'Greenhouse core client not configured', command: commandName };
    }

    // Map legacy read_sensor to appropriate command based on parameters
    let actualCommand = commandName;
    if (commandName === 'read_sensor') {
      const sensorType = parameters.sensor || 'temperature';
      if (sensorType === 'temperature') {
        actualCommand = 'read_temperature_data';
      } else if (sensorType === 'humidity') {
        actualCommand = 'read_humidity_data';
      } else if (sensorType === 'light') {
        actualCommand = 'read_light_data';
      } else if (sensorType === 'co2') {
        actualCommand = 'read_co2_data';
      } else if (sensorType === 'soil_moisture') {
        actualCommand = 'read_soil_moisture_data';
      } else if (sensorType === 'soil_ph') {
        actualCommand = 'read_soil_ph_data';
      } else {
        actualCommand = 'read_temperature_data'; // Default fallback
      }
    }

    const start = Date.now();
    session.logger.debug(`Executing greenhouse command: ${actualCommand}`);

    try {
      const metadata = {
        commandId: session.lastCommandId || 'unknown',
        sessionId: session.sessionId
      };

      const result = await this.greenhouseCoreClient.executeCommand(
        actualCommand,
        parameters,
        metadata
      );

      const executionTime = Date.now() - start;

      if (result.success) {
        session.logger.info(`Greenhouse command ${actualCommand} succeeded in ${executionTime}ms`);
        // Normalize response to match existing structure
        return {
          output: JSON.stringify(result.data),
          data: result.data,
          executionTime,
          command: commandName
        };
      } else {
        session.logger.error(`Greenhouse command ${actualCommand} failed: ${result.error}`);
        return {
          error: result.error || 'Command execution failed',
          command: commandName,
          executionTime
        };
      }
    } catch (err) {
      const executionTime = Date.now() - start;
      session.logger.error(`Greenhouse command ${actualCommand} exception: ${err.message}`);
      return {
        error: err.message || 'Command execution exception',
        command: commandName,
        executionTime
      };
    }
  }

  /**
   * Execute command - routes to greenhouse core client
   */
  async runCommand(commandName, parameters = {}, session) {
    // All commands are routed to greenhouse core client
    if (this.isGreenhouseCommand(commandName)) {
      return this.executeGreenhouseCommand(commandName, parameters, session);
    }

    // Unknown command - return error
    return {
      error: `Unknown command: ${commandName}. Only greenhouse commands are supported.`,
      command: commandName
    };
  }
}

export default CommandExecutor;
