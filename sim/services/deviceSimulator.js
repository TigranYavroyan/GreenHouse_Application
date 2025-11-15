// services/deviceSimulator.js
import simulatorLogger from '../logger/simulatorLogger.js';

class DeviceSimulator {
  constructor() {
    // Simulated device states
    this.deviceStates = {
      waterCanal: {
        id: 'water_canal_1',
        status: 'off',
        lastChanged: new Date().toISOString()
      },
      actuators: {
        // Generic actuator registry
        'actuator_1': { status: 'off', lastChanged: new Date().toISOString() },
        'actuator_2': { status: 'off', lastChanged: new Date().toISOString() }
      },
      fans: {
        'fan_1': { status: 'off', speed: 0, lastChanged: new Date().toISOString() },
        'fan_2': { status: 'off', speed: 0, lastChanged: new Date().toISOString() }
      },
      heaters: {
        'heater_1': { status: 'off', temperature: 0, lastChanged: new Date().toISOString() },
        'heater_2': { status: 'off', temperature: 0, lastChanged: new Date().toISOString() }
      }
    };

    // Simulated sensor data with realistic base values
    this.sensorData = {
      temperature: {
        value: 22.5,
        unit: 'celsius',
        lastUpdated: new Date().toISOString(),
        sensorId: 'temp_sensor_1',
        location: 'greenhouse_main'
      },
      humidity: {
        value: 65.0,
        unit: 'percent',
        lastUpdated: new Date().toISOString(),
        sensorId: 'humidity_sensor_1',
        location: 'greenhouse_main'
      },
      light: {
        value: 750,
        unit: 'lux',
        lastUpdated: new Date().toISOString(),
        sensorId: 'light_sensor_1',
        location: 'greenhouse_main'
      },
      co2: {
        value: 400,
        unit: 'ppm',
        lastUpdated: new Date().toISOString(),
        sensorId: 'co2_sensor_1',
        location: 'greenhouse_main'
      },
      soilMoisture: {
        value: 50.0,
        unit: 'percent',
        lastUpdated: new Date().toISOString(),
        sensorId: 'soil_moisture_sensor_1',
        location: 'greenhouse_main'
      },
      soilPH: {
        value: 6.5,
        unit: 'pH',
        lastUpdated: new Date().toISOString(),
        sensorId: 'soil_ph_sensor_1',
        location: 'greenhouse_main'
      }
    };

    simulatorLogger.info('DeviceSimulator initialized', {
      deviceCount: Object.keys(this.deviceStates).length,
      sensorCount: Object.keys(this.sensorData).length
    });
  }

  /**
   * Simulate reading temperature data
   */
  readTemperatureData() {
    // Simulate slight variations in temperature
    // Temperature affected by heater status
    const heaterOn = Object.values(this.deviceStates.heaters).some(h => h.status === 'on');
    const baseTemp = heaterOn ? 25.0 : 22.5;
    const variation = (Math.random() - 0.5) * 4; // ±2 degrees
    const temperature = baseTemp + variation;

    this.sensorData.temperature = {
      value: Math.round(temperature * 10) / 10,
      unit: 'celsius',
      lastUpdated: new Date().toISOString(),
      sensorId: 'temp_sensor_1',
      location: 'greenhouse_main'
    };

    simulatorLogger.sensorReading('temperature', this.sensorData.temperature.value, 'celsius', 'temp_sensor_1');

    return {
      success: true,
      data: {
        temperature: this.sensorData.temperature.value,
        unit: this.sensorData.temperature.unit,
        timestamp: this.sensorData.temperature.lastUpdated,
        sensorId: this.sensorData.temperature.sensorId,
        location: this.sensorData.temperature.location
      }
    };
  }

  /**
   * Simulate reading humidity data
   */
  readHumidityData() {
    // Humidity affected by water canal and fans
    const waterOn = this.deviceStates.waterCanal.status === 'on';
    const fansOn = Object.values(this.deviceStates.fans).some(f => f.status === 'on');
    const baseHumidity = waterOn ? 75.0 : 65.0;
    const adjustment = fansOn ? -5.0 : 0; // Fans reduce humidity
    const variation = (Math.random() - 0.5) * 10; // ±5 percent
    const humidity = Math.max(0, Math.min(100, baseHumidity + adjustment + variation));

    this.sensorData.humidity = {
      value: Math.round(humidity * 10) / 10,
      unit: 'percent',
      lastUpdated: new Date().toISOString(),
      sensorId: 'humidity_sensor_1',
      location: 'greenhouse_main'
    };

    simulatorLogger.sensorReading('humidity', this.sensorData.humidity.value, 'percent', 'humidity_sensor_1');

    return {
      success: true,
      data: {
        humidity: this.sensorData.humidity.value,
        unit: this.sensorData.humidity.unit,
        timestamp: this.sensorData.humidity.lastUpdated,
        sensorId: this.sensorData.humidity.sensorId,
        location: this.sensorData.humidity.location
      }
    };
  }

  /**
   * Simulate reading light data
   */
  readLightData() {
    // Light varies based on time of day simulation
    const hour = new Date().getHours();
    const isDaytime = hour >= 6 && hour < 20;
    const baseLight = isDaytime ? 750 : 50;
    const variation = (Math.random() - 0.5) * 200; // ±100 lux
    const light = Math.max(0, baseLight + variation);

    this.sensorData.light = {
      value: Math.round(light),
      unit: 'lux',
      lastUpdated: new Date().toISOString(),
      sensorId: 'light_sensor_1',
      location: 'greenhouse_main'
    };

    simulatorLogger.sensorReading('light', this.sensorData.light.value, 'lux', 'light_sensor_1');

    return {
      success: true,
      data: {
        light: this.sensorData.light.value,
        unit: this.sensorData.light.unit,
        timestamp: this.sensorData.light.lastUpdated,
        sensorId: this.sensorData.light.sensorId,
        location: this.sensorData.light.location
      }
    };
  }

  /**
   * Simulate reading CO2 data
   */
  readCO2Data() {
    // CO2 levels affected by ventilation (fans)
    const fansOn = Object.values(this.deviceStates.fans).some(f => f.status === 'on');
    const baseCO2 = fansOn ? 350 : 400; // Fans reduce CO2
    const variation = (Math.random() - 0.5) * 100; // ±50 ppm
    const co2 = Math.max(300, Math.min(1000, baseCO2 + variation));

    this.sensorData.co2 = {
      value: Math.round(co2),
      unit: 'ppm',
      lastUpdated: new Date().toISOString(),
      sensorId: 'co2_sensor_1',
      location: 'greenhouse_main'
    };

    simulatorLogger.sensorReading('co2', this.sensorData.co2.value, 'ppm', 'co2_sensor_1');

    return {
      success: true,
      data: {
        co2: this.sensorData.co2.value,
        unit: this.sensorData.co2.unit,
        timestamp: this.sensorData.co2.lastUpdated,
        sensorId: this.sensorData.co2.sensorId,
        location: this.sensorData.co2.location
      }
    };
  }

  /**
   * Simulate reading soil moisture data
   */
  readSoilMoistureData() {
    // Soil moisture affected by water canal
    const waterOn = this.deviceStates.waterCanal.status === 'on';
    const baseMoisture = waterOn ? 70.0 : 50.0;
    const variation = (Math.random() - 0.5) * 20; // ±10 percent
    const moisture = Math.max(0, Math.min(100, baseMoisture + variation));

    this.sensorData.soilMoisture = {
      value: Math.round(moisture * 10) / 10,
      unit: 'percent',
      lastUpdated: new Date().toISOString(),
      sensorId: 'soil_moisture_sensor_1',
      location: 'greenhouse_main'
    };

    simulatorLogger.sensorReading('soil_moisture', this.sensorData.soilMoisture.value, 'percent', 'soil_moisture_sensor_1');

    return {
      success: true,
      data: {
        soilMoisture: this.sensorData.soilMoisture.value,
        unit: this.sensorData.soilMoisture.unit,
        timestamp: this.sensorData.soilMoisture.lastUpdated,
        sensorId: this.sensorData.soilMoisture.sensorId,
        location: this.sensorData.soilMoisture.location
      }
    };
  }

  /**
   * Simulate reading soil pH data
   */
  readSoilPHData() {
    // pH is relatively stable but can vary slightly
    const basePH = 6.5;
    const variation = (Math.random() - 0.5) * 0.5; // ±0.25 pH
    const ph = Math.max(4.0, Math.min(9.0, basePH + variation));

    this.sensorData.soilPH = {
      value: Math.round(ph * 100) / 100,
      unit: 'pH',
      lastUpdated: new Date().toISOString(),
      sensorId: 'soil_ph_sensor_1',
      location: 'greenhouse_main'
    };

    simulatorLogger.sensorReading('soil_ph', this.sensorData.soilPH.value, 'pH', 'soil_ph_sensor_1');

    return {
      success: true,
      data: {
        soilPH: this.sensorData.soilPH.value,
        unit: this.sensorData.soilPH.unit,
        timestamp: this.sensorData.soilPH.lastUpdated,
        sensorId: this.sensorData.soilPH.sensorId,
        location: this.sensorData.soilPH.location
      }
    };
  }

  /**
   * Simulate switching water canal on/off
   */
  switchWaterCanal(action) {
    const validActions = ['on', 'off', 'toggle'];
    
    if (!validActions.includes(action)) {
      return {
        success: false,
        error: `Invalid action: ${action}. Must be one of: ${validActions.join(', ')}`
      };
    }

    const currentState = this.deviceStates.waterCanal.status;
    let newState;

    if (action === 'toggle') {
      newState = currentState === 'on' ? 'off' : 'on';
    } else {
      newState = action;
    }

    this.deviceStates.waterCanal.status = newState;
    this.deviceStates.waterCanal.lastChanged = new Date().toISOString();

    simulatorLogger.deviceStateChanged('waterCanal', this.deviceStates.waterCanal.id, currentState, newState);

    return {
      success: true,
      data: {
        deviceId: this.deviceStates.waterCanal.id,
        status: newState,
        previousStatus: currentState,
        timestamp: this.deviceStates.waterCanal.lastChanged
      }
    };
  }

  /**
   * Simulate switching actuator on/off
   */
  switchActuator(actuatorId, action) {
    const validActions = ['on', 'off', 'toggle'];
    
    if (!validActions.includes(action)) {
      return {
        success: false,
        error: `Invalid action: ${action}. Must be one of: ${validActions.join(', ')}`
      };
    }

    // Initialize actuator if it doesn't exist
    if (!this.deviceStates.actuators[actuatorId]) {
      this.deviceStates.actuators[actuatorId] = {
        status: 'off',
        lastChanged: new Date().toISOString()
      };
    }

    const actuator = this.deviceStates.actuators[actuatorId];
    const currentState = actuator.status;
    let newState;

    if (action === 'toggle') {
      newState = currentState === 'on' ? 'off' : 'on';
    } else {
      newState = action;
    }

    actuator.status = newState;
    actuator.lastChanged = new Date().toISOString();

    simulatorLogger.deviceStateChanged('actuator', actuatorId, currentState, newState);

    return {
      success: true,
      data: {
        actuatorId: actuatorId,
        status: newState,
        previousStatus: currentState,
        timestamp: actuator.lastChanged
      }
    };
  }

  /**
   * Simulate switching fan on/off
   */
  switchFan(fanId, action) {
    const validActions = ['on', 'off', 'toggle'];
    
    if (!validActions.includes(action)) {
      return {
        success: false,
        error: `Invalid action: ${action}. Must be one of: ${validActions.join(', ')}`
      };
    }

    // Initialize fan if it doesn't exist
    if (!this.deviceStates.fans[fanId]) {
      this.deviceStates.fans[fanId] = {
        status: 'off',
        speed: 0,
        lastChanged: new Date().toISOString()
      };
    }

    const fan = this.deviceStates.fans[fanId];
    const currentState = fan.status;
    let newState;

    if (action === 'toggle') {
      newState = currentState === 'on' ? 'off' : 'on';
    } else {
      newState = action;
    }

    fan.status = newState;
    fan.speed = newState === 'on' ? 50 : 0; // Default speed when on
    fan.lastChanged = new Date().toISOString();

    simulatorLogger.deviceStateChanged('fan', fanId, currentState, newState);

    return {
      success: true,
      data: {
        fanId: fanId,
        status: newState,
        speed: fan.speed,
        previousStatus: currentState,
        timestamp: fan.lastChanged
      }
    };
  }

  /**
   * Simulate switching heater on/off
   */
  switchHeater(heaterId, action) {
    const validActions = ['on', 'off', 'toggle'];
    
    if (!validActions.includes(action)) {
      return {
        success: false,
        error: `Invalid action: ${action}. Must be one of: ${validActions.join(', ')}`
      };
    }

    // Initialize heater if it doesn't exist
    if (!this.deviceStates.heaters[heaterId]) {
      this.deviceStates.heaters[heaterId] = {
        status: 'off',
        temperature: 0,
        lastChanged: new Date().toISOString()
      };
    }

    const heater = this.deviceStates.heaters[heaterId];
    const currentState = heater.status;
    let newState;

    if (action === 'toggle') {
      newState = currentState === 'on' ? 'off' : 'on';
    } else {
      newState = action;
    }

    heater.status = newState;
    heater.temperature = newState === 'on' ? 30 : 0; // Default temperature when on
    heater.lastChanged = new Date().toISOString();

    simulatorLogger.deviceStateChanged('heater', heaterId, currentState, newState);

    return {
      success: true,
      data: {
        heaterId: heaterId,
        status: newState,
        temperature: heater.temperature,
        previousStatus: currentState,
        timestamp: heater.lastChanged
      }
    };
  }

  /**
   * Get current state of all devices
   */
  getDeviceStates() {
    return {
      waterCanal: { ...this.deviceStates.waterCanal },
      actuators: { ...this.deviceStates.actuators },
      fans: { ...this.deviceStates.fans },
      heaters: { ...this.deviceStates.heaters }
    };
  }

  /**
   * Get current sensor readings
   */
  getSensorData() {
    return { ...this.sensorData };
  }
}

export default DeviceSimulator;

