// clients/greenhouseCoreClient.js
import SystemLogger from '../logger/systemLogger.js';
import config from '../config/index.js';

class GreenhouseCoreClient {
  constructor() {
    this.baseUrl = config.greenhouseCore.url;
    this.timeout = config.greenhouseCore.timeout;
    this.maxRetries = config.greenhouseCore.retries;
    this.retryBackoffBaseMs = config.greenhouseCore.retryBackoffBaseMs;
    this.isConnected = false;
  }

  /**
   * Initialize connection (for future use if needed)
   */
  async connect() {
    try {
      const healthCheck = await this.healthCheck();
      this.isConnected = healthCheck.success;
      if (this.isConnected) {
        SystemLogger.info('Greenhouse Core Client connected');
      }
      return this.isConnected;
    } catch (error) {
      SystemLogger.error(`Failed to connect to greenhouse core: ${error.message}`);
      this.isConnected = false;
      return false;
    }
  }

  /**
   * Disconnect (cleanup if needed)
   */
  async disconnect() {
    this.isConnected = false;
    SystemLogger.info('Greenhouse Core Client disconnected');
  }

  normalizeError(error, fallbackMessage = 'Request failed') {
    if (!error) return fallbackMessage;
    if (typeof error === 'string') return error;
    if (error.message) return error.message;
    return fallbackMessage;
  }

  toErrorWithMetadata(sourceError, fallbackMessage = 'Request failed') {
    if (sourceError instanceof Error) {
      return sourceError;
    }

    const error = new Error(this.normalizeError(sourceError, fallbackMessage));
    if (sourceError && typeof sourceError === 'object') {
      if (Number.isInteger(sourceError.statusCode)) {
        error.statusCode = sourceError.statusCode;
      }
      if (sourceError.payload !== undefined) {
        error.payload = sourceError.payload;
      }
    }
    return error;
  }

  normalizeMode(modeValue) {
    const normalized = String(modeValue || '').trim().toLowerCase();
    if (normalized === 'manual' || normalized === '0') return 'manual';
    if (normalized === 'auto' || normalized === '1') return 'auto';
    const error = new Error('Mode value must be one of: manual, auto, 0, 1');
    error.statusCode = 400;
    throw error;
  }

  sensorUnitsByType(sensorType) {
    const units = {
      temperature: 'C',
      humidity: '%',
      light: 'lux',
      co2: 'ppm',
      soil_moisture: '%',
      soil_ph: 'pH',
    };
    return units[sensorType] || '';
  }

  sensorTypeFromCommand(command, parameters = {}) {
    const normalized = String(command || '').trim().toLowerCase();
    if (normalized === 'read_sensor') {
      return String(parameters.sensor || 'temperature').trim().toLowerCase() || 'temperature';
    }
    if (normalized.startsWith('read_') && normalized.endsWith('_data')) {
      return normalized.slice(5, -5) || 'temperature';
    }
    return 'temperature';
  }

  sensorOutputKey(sensorType) {
    const keys = {
      temperature: 'temperature',
      humidity: 'humidity',
      light: 'light',
      co2: 'co2',
      soil_moisture: 'soilMoisture',
      soil_ph: 'soilPH',
    };
    return keys[sensorType] || sensorType;
  }

  sensorGetterAliases(sensorType) {
    const byType = {
      temperature: ['temperature', 'temp', 'air_temp', 'temp1', 'inside_temp'],
      humidity: ['humidity', 'hum', 'air_humidity'],
      light: ['light', 'lux', 'luminosity'],
      co2: ['co2', 'co2_ppm'],
      soil_moisture: ['soil_moisture', 'soilMoisture', 'soil_moist', 'moisture'],
      soil_ph: ['soil_ph', 'soilPH', 'ph', 'soilPh'],
    };
    return byType[sensorType] || [sensorType];
  }

  normalizeExecutorAlias(value) {
    return String(value || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_');
  }

  executorAliases(executorName) {
    const original = String(executorName || '').trim();
    const normalized = this.normalizeExecutorAlias(original);
    return new Set([
      original,
      normalized,
      normalized.replace(/_/g, ''),
    ]);
  }

  resolveGetterValue(entry) {
    if (!entry || typeof entry !== 'object') return null;
    if (entry.data && typeof entry.data === 'object' && entry.data.value !== undefined) {
      return entry.data.value;
    }
    if (entry.value !== undefined) return entry.value;
    return null;
  }

  resolveGetterByAliases(getters, aliases = []) {
    if (!getters || typeof getters !== 'object') {
      return { key: '', entry: null };
    }

    const aliasSet = new Set(aliases.map((x) => String(x || '').trim().toLowerCase()).filter(Boolean));
    const keys = Object.keys(getters);

    for (const key of keys) {
      if (aliasSet.has(String(key).toLowerCase())) {
        return { key, entry: getters[key] };
      }
    }

    const normalizedAliasSet = new Set(
      [...aliasSet].map((x) => x.replace(/[^a-z0-9]+/g, '_'))
    );

    for (const key of keys) {
      const normalizedKey = String(key).toLowerCase().replace(/[^a-z0-9]+/g, '_');
      if (normalizedAliasSet.has(normalizedKey)) {
        return { key, entry: getters[key] };
      }
    }

    return { key: '', entry: null };
  }

  resolveExecutorByAliases(executors, aliases = []) {
    const list = Array.isArray(executors) ? executors : [];
    if (!list.length) return null;

    const aliasSet = new Set();
    for (const alias of aliases) {
      for (const token of this.executorAliases(alias)) {
        aliasSet.add(token);
      }
    }

    for (const executor of list) {
      const name = String(executor?.name || '').trim();
      if (!name) continue;
      const tokens = this.executorAliases(name);
      for (const token of tokens) {
        if (aliasSet.has(token)) {
          return executor;
        }
      }
    }
    return null;
  }

  async executeReadCommand(command, parameters = {}) {
    const sensorType = this.sensorTypeFromCommand(command, parameters);
    const outputKey = this.sensorOutputKey(sensorType);
    const getters = await this.getGetters();
    const { key, entry } = this.resolveGetterByAliases(getters, this.sensorGetterAliases(sensorType));
    if (!entry) {
      throw new Error(`Getter not found for sensor type: ${sensorType}`);
    }

    const value = this.resolveGetterValue(entry);
    if (value === null || value === undefined) {
      throw new Error(`Getter value is missing for key: ${key}`);
    }

    const stampMs = Number(entry?.stampMs || Date.now());
    const timestamp = Number.isFinite(stampMs) ? new Date(stampMs).toISOString() : new Date().toISOString();
    return {
      [outputKey]: value,
      unit: this.sensorUnitsByType(sensorType),
      timestamp,
      sensorId: key,
    };
  }

  async executeSwitchCommand(command, parameters = {}) {
    const executors = await this.getExecutors();
    const defaultsByCommand = {
      switch_fan: ['LOW_DCM_D_0', 'fan_1', 'fan', 'dcm_d_0'],
      switch_heater: ['LOW_DCM_D_1', 'heater_1', 'heater', 'dcm_d_1'],
      switch_actuator: ['LOW_DCM_D_2', 'actuator_1', 'actuator', 'dcm_d_2'],
      switch_water_canal: ['LOW_DCM_D_3', 'water_canal_1', 'water_canal', 'dcm_d_3'],
    };
    const idAliasByCommand = {
      switch_fan: String(parameters.fanId || '').trim(),
      switch_heater: String(parameters.heaterId || '').trim(),
      switch_actuator: String(parameters.actuatorId || '').trim(),
      switch_water_canal: String(parameters.canalId || parameters.waterCanalId || '').trim(),
    };

    const aliases = [...(defaultsByCommand[command] || [])];
    if (idAliasByCommand[command]) {
      aliases.unshift(idAliasByCommand[command]);
    }

    const executor = this.resolveExecutorByAliases(executors, aliases);
    if (!executor || !executor.name) {
      throw new Error(`Executor not found for command: ${command}`);
    }

    const executorName = String(executor.name);
    const currentMode = String(executor.mode || '').toUpperCase();
    if (currentMode !== 'MANUAL') {
      await this.setExecutorMode(executorName, 'manual');
    }

    const requestedAction = String(parameters.action || 'toggle').trim().toLowerCase();
    let action = requestedAction;
    if (requestedAction === 'toggle') {
      const currentValue = Boolean(executor?.data?.value);
      action = currentValue ? 'off' : 'on';
    }

    if (action === 'set') {
      const setValue = parameters.value !== undefined ? parameters.value : 1;
      await this.executorSet(executorName, setValue);
      return {
        actuatorId: executorName,
        status: String(setValue),
        timestamp: new Date().toISOString(),
      };
    }

    if (action === 'on') {
      await this.executorOn(executorName);
      return {
        actuatorId: executorName,
        status: 'on',
        timestamp: new Date().toISOString(),
      };
    }

    if (action === 'off') {
      await this.executorOff(executorName);
      return {
        actuatorId: executorName,
        status: 'off',
        timestamp: new Date().toISOString(),
      };
    }

    throw new Error(`Unsupported switch action: ${requestedAction}`);
  }

  async requestJson(path, options = {}) {
    const {
      method = 'GET',
      body = null,
      retries = this.maxRetries,
      timeout = this.timeout
    } = options;

    let lastError = null;

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        if (attempt > 0) {
          await new Promise((resolve) => setTimeout(
            resolve,
            this.retryBackoffBaseMs * Math.pow(2, attempt)
          ));
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);
        const requestInit = {
          method,
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json'
          }
        };

        if (body !== null && body !== undefined) {
          requestInit.body = JSON.stringify(body);
        }

        const response = await fetch(`${this.baseUrl}${path}`, requestInit);
        clearTimeout(timeoutId);

        let payload = null;
        try {
          payload = await response.json();
        } catch (parseError) {
          payload = null;
        }

        if (!response.ok) {
          const message = payload?.error || `HTTP ${response.status}: ${response.statusText}`;
          const error = new Error(message);
          error.statusCode = response.status;
          error.payload = payload;
          throw error;
        }

        this.isConnected = true;
        return payload;
      } catch (error) {
        lastError = error;
        this.isConnected = false;

        const isRetryable =
          error?.name === 'AbortError' ||
          (error?.message && error.message.includes('fetch failed'));

        if (!isRetryable || attempt >= retries) {
          break;
        }
      }
    }

    const normalizedError = this.toErrorWithMetadata(lastError);
    if (!normalizedError.message) {
      normalizedError.message = this.normalizeError(lastError);
    }
    throw normalizedError;
  }

  /**
   * Health check
   */
  async healthCheck() {
    try {
      const data = await this.requestJson('/status', {
        method: 'GET',
        retries: 0
      });
      return { success: true, data };
    } catch (error) {
      return { success: false, error: this.normalizeError(error, 'Health check failed') };
    }
  }

  /**
   * Core schema/state APIs
   */
  async getStatus() {
    return this.requestJson('/status');
  }

  async getGetterSchema() {
    return this.requestJson('/schema/getters');
  }

  async getExecutorSchema() {
    return this.requestJson('/schema/executors');
  }

  async getGetters() {
    return this.requestJson('/getters');
  }

  async getGetter(key) {
    const safeKey = encodeURIComponent(String(key || '').trim());
    if (!safeKey) {
      throw new Error('Getter key is required');
    }
    return this.requestJson(`/getters/${safeKey}`);
  }

  async getExecutors() {
    return this.requestJson('/executors');
  }

  async setExecutorMode(name, value) {
    const safeName = encodeURIComponent(String(name || '').trim());
    if (!safeName) {
      throw new Error('Executor name is required');
    }

    const mode = this.normalizeMode(value);
    return this.requestJson(`/api/executors/${safeName}/mode`, {
      method: 'POST',
      body: { value: mode }
    });
  }

  async executorOn(name) {
    const safeName = encodeURIComponent(String(name || '').trim());
    if (!safeName) {
      throw new Error('Executor name is required');
    }

    return this.requestJson(`/api/executors/${safeName}/on`, {
      method: 'POST'
    });
  }

  async executorOff(name) {
    const safeName = encodeURIComponent(String(name || '').trim());
    if (!safeName) {
      throw new Error('Executor name is required');
    }

    return this.requestJson(`/api/executors/${safeName}/off`, {
      method: 'POST'
    });
  }

  async executorSet(name, value) {
    const safeName = encodeURIComponent(String(name || '').trim());
    if (!safeName) {
      throw new Error('Executor name is required');
    }

    return this.requestJson(`/api/executors/${safeName}/set`, {
      method: 'POST',
      body: { value: String(value) }
    });
  }

  async getLogicFull() {
    return this.requestJson('/api/json/logic/full');
  }

  async uploadLogic(payload = {}) {
    return this.requestJson('/api/json/logic/upload', {
      method: 'POST',
      body: payload || {},
    });
  }

  async reloadLogic() {
    return this.requestJson('/api/json/logic/reload', {
      method: 'POST',
      body: {},
    });
  }

  /**
   * Execute command with retry logic
   */
  async executeCommand(command, parameters = {}, metadata = {}) {
    const { commandId, sessionId } = metadata;
    let lastError = null;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        if (attempt > 0) {
          SystemLogger.warn(`Retrying command ${command} (attempt ${attempt + 1}/${this.maxRetries + 1})`);
          // Exponential backoff: wait 100ms * 2^attempt
          await new Promise(resolve => setTimeout(resolve, 100 * Math.pow(2, attempt)));
        }

        SystemLogger.info('Dispatching command via GreenHouse2 demo HTTP API', {
          commandId,
          sessionId,
          command,
          parameters,
          attempt: attempt + 1,
          baseUrl: this.baseUrl,
        });

        let data = null;
        const normalizedCommand = String(command || '').trim().toLowerCase();
        if (normalizedCommand === 'read_sensor' || normalizedCommand.startsWith('read_')) {
          data = await this.executeReadCommand(normalizedCommand, parameters);
        } else if (normalizedCommand.startsWith('switch_')) {
          data = await this.executeSwitchCommand(normalizedCommand, parameters);
        } else {
          throw new Error(`Unsupported greenhouse command: ${command}`);
        }

        // Log response received from core server
        SystemLogger.info('Received response from greenhouse core server', {
          commandId,
          sessionId,
          command,
          status: 200,
          success: true,
          hasError: false,
          responseData: JSON.stringify(data),
        });

        // Update connection status on success
        this.isConnected = true;

        SystemLogger.debug(`Command ${command} executed successfully (commandId: ${commandId})`);

        // Return normalized result
        return {
          success: true,
          data,
          commandId: commandId || 'unknown',
          timestamp: new Date().toISOString(),
        };

      } catch (error) {
        lastError = error;

        // Log error details
        SystemLogger.error(`Error sending command to core server`, {
          commandId,
          sessionId,
          command,
          attempt: attempt + 1,
          error: error.message,
          errorType: error.name,
          willRetry: attempt < this.maxRetries
        });

        if (error.name === 'AbortError') {
          SystemLogger.warn(`Command ${command} timed out (attempt ${attempt + 1})`);
          if (attempt < this.maxRetries) {
            continue; // Retry on timeout
          }
        } else if (error.message && error.message.includes('fetch failed')) {
          SystemLogger.warn(`Connection error for command ${command} (attempt ${attempt + 1}): ${error.message}`);
          this.isConnected = false;
          if (attempt < this.maxRetries) {
            continue; // Retry on connection error
          }
        } else {
          // For other errors (like 4xx), don't retry
          SystemLogger.error(`Command ${command} failed: ${error.message}`);
          break;
        }
      }
    }

    // All retries exhausted
    this.isConnected = false;
    SystemLogger.error(`Command ${command} failed after ${this.maxRetries + 1} attempts: ${lastError?.message || 'Unknown error'}`);

    return {
      success: false,
      error: lastError?.message || 'Command execution failed after retries',
      commandId,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Check if client is connected
   */
  get connected() {
    return this.isConnected;
  }
}

export default GreenhouseCoreClient;

