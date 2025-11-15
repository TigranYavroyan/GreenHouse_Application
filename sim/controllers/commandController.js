// controllers/commandController.js
import DeviceSimulator from '../services/deviceSimulator.js';
import simulatorLogger from '../logger/simulatorLogger.js';

class CommandController {
  constructor() {
    this.deviceSimulator = new DeviceSimulator();
    simulatorLogger.info('CommandController initialized');
  }

  /**
   * Handle command execution
   */
  async executeCommand(req, res) {
    const startTime = Date.now();
    try {
      const { command, parameters = {}, commandId, sessionId } = req.body;

      // Log received command
      simulatorLogger.commandReceived(command, parameters, commandId, sessionId);

      if (!command) {
        const errorResponse = {
          success: false,
          error: 'Command is required',
          commandId: commandId || null
        };
        simulatorLogger.warn('Command execution rejected: missing command', { commandId, sessionId });
        return res.status(400).json(errorResponse);
      }

      let result;

      switch (command) {
        case 'read_temperature_data':
          result = this.deviceSimulator.readTemperatureData();
          break;

        case 'read_humidity_data':
          result = this.deviceSimulator.readHumidityData();
          break;

        case 'read_light_data':
          result = this.deviceSimulator.readLightData();
          break;

        case 'read_co2_data':
          result = this.deviceSimulator.readCO2Data();
          break;

        case 'read_soil_moisture_data':
          result = this.deviceSimulator.readSoilMoistureData();
          break;

        case 'read_soil_ph_data':
          result = this.deviceSimulator.readSoilPHData();
          break;

        case 'switch_water_canal':
          const canalAction = parameters.action || 'toggle';
          result = this.deviceSimulator.switchWaterCanal(canalAction);
          break;

        case 'switch_actuator':
          const actuatorId = parameters.actuatorId || 'actuator_1';
          const actuatorAction = parameters.action || 'toggle';
          result = this.deviceSimulator.switchActuator(actuatorId, actuatorAction);
          break;

        case 'switch_fan':
          const fanId = parameters.fanId || 'fan_1';
          const fanAction = parameters.action || 'toggle';
          result = this.deviceSimulator.switchFan(fanId, fanAction);
          break;

        case 'switch_heater':
          const heaterId = parameters.heaterId || 'heater_1';
          const heaterAction = parameters.action || 'toggle';
          result = this.deviceSimulator.switchHeater(heaterId, heaterAction);
          break;

        case 'read_sensor':
          // Legacy command - route to appropriate sensor based on parameters
          const sensorType = parameters.sensor || 'temperature';
          if (sensorType === 'temperature') {
            result = this.deviceSimulator.readTemperatureData();
          } else if (sensorType === 'humidity') {
            result = this.deviceSimulator.readHumidityData();
          } else if (sensorType === 'light') {
            result = this.deviceSimulator.readLightData();
          } else if (sensorType === 'co2') {
            result = this.deviceSimulator.readCO2Data();
          } else if (sensorType === 'soil_moisture') {
            result = this.deviceSimulator.readSoilMoistureData();
          } else if (sensorType === 'soil_ph') {
            result = this.deviceSimulator.readSoilPHData();
          } else {
            result = { success: false, error: `Unknown sensor type: ${sensorType}` };
          }
          break;

        default:
          const errorResponse = {
            success: false,
            error: `Unknown command: ${command}`,
            commandId: commandId || null
          };
          simulatorLogger.warn(`Unknown command received: ${command}`, { commandId, sessionId });
          return res.status(400).json(errorResponse);
      }

      const executionTime = Date.now() - startTime;

      // Return standardized response
      const response = {
        success: result.success,
        result: result.data || null,
        error: result.error || null,
        commandId: commandId || null,
        command: command,
        timestamp: new Date().toISOString()
      };

      // Log command execution result
      simulatorLogger.commandExecuted(command, result, commandId, executionTime);
      
      // Log data sent to client
      simulatorLogger.dataSent('/api/v1/commands/execute', response, result.success ? 200 : 400);

      if (result.success) {
        res.status(200).json(response);
      } else {
        res.status(400).json(response);
      }

    } catch (error) {
      const executionTime = Date.now() - startTime;
      const errorResponse = {
        success: false,
        error: error.message || 'Internal server error',
        commandId: req.body.commandId || null,
        timestamp: new Date().toISOString()
      };
      
      simulatorLogger.error('Command execution exception', {
        command: req.body.command,
        commandId: req.body.commandId,
        error: error.message,
        stack: error.stack,
        executionTime
      });
      
      res.status(500).json(errorResponse);
    }
  }

  /**
   * Health check endpoint
   */
  healthCheck(req, res) {
    const healthData = {
      status: 'ok',
      service: 'greenhouse-core-simulator',
      timestamp: new Date().toISOString(),
      version: '1.0.0'
    };
    simulatorLogger.debug('Health check requested', healthData);
    res.json(healthData);
  }

  /**
   * Get device states (for debugging/monitoring)
   */
  getDeviceStates(req, res) {
    try {
      const states = this.deviceSimulator.getDeviceStates();
      const sensors = this.deviceSimulator.getSensorData();
      
      const response = {
        success: true,
        devices: states,
        sensors: sensors,
        timestamp: new Date().toISOString()
      };
      
      simulatorLogger.debug('Device states requested', { deviceCount: Object.keys(states).length });
      res.json(response);
    } catch (error) {
      simulatorLogger.error('Failed to get device states', { error: error.message });
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  }
}

export default CommandController;

