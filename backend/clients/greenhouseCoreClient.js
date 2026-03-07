// clients/greenhouseCoreClient.js
import SystemLogger from '../logger/systemLogger.js';
import config from '../config/index.js';

class GreenhouseCoreClient {
  constructor() {
    this.baseUrl = config.greenhouseCore.url;
    this.timeout = config.greenhouseCore.timeout;
    this.maxRetries = config.greenhouseCore.retries;
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

  normalizeMode(modeValue) {
    const normalized = String(modeValue || '').trim().toLowerCase();
    if (normalized === 'manual' || normalized === '0') return 'manual';
    if (normalized === 'auto' || normalized === '1') return 'auto';
    const error = new Error('Mode value must be one of: manual, auto, 0, 1');
    error.statusCode = 400;
    throw error;
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
          await new Promise((resolve) => setTimeout(resolve, 100 * Math.pow(2, attempt)));
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

    throw new Error(this.normalizeError(lastError));
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

        const payload = {
          command,
          parameters,
          commandId,
          sessionId
        };

        // Log data being sent to core server
        SystemLogger.info(`Sending command to greenhouse core server`, {
          commandId,
          sessionId,
          command,
          parameters,
          attempt: attempt + 1,
          url: `${this.baseUrl}/api/v1/commands/execute`,
          payload: JSON.stringify(payload)
        });

        const response = await this.requestJson('/api/v1/commands/execute', {
          method: 'POST',
          body: payload,
          retries: 0
        });

        const result = response || {};

        // Log response received from core server
        SystemLogger.info(`Received response from greenhouse core server`, {
          commandId,
          sessionId,
          command,
          status: 200,
          success: result.success,
          hasError: !!result.error,
          responseData: JSON.stringify(result)
        });

        // Check if the result indicates success
        if (result.success === false) {
          SystemLogger.warn(`Command ${command} failed in core server`, {
            commandId,
            error: result.error
          });
          throw new Error(result.error || 'Command execution failed');
        }

        // Update connection status on success
        this.isConnected = true;

        SystemLogger.debug(`Command ${command} executed successfully (commandId: ${commandId})`);

        // Return normalized result
        return {
          success: true,
          data: result.result || result.data,
          commandId: result.commandId || commandId,
          timestamp: result.timestamp || new Date().toISOString()
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

