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

  /**
   * Health check
   */
  async healthCheck() {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeout);

      const response = await fetch(`${this.baseUrl}/api/v1/health`, {
        method: 'GET',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json'
        }
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        return { success: true, data };
      } else {
        return { success: false, error: `Health check failed with status ${response.status}` };
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        return { success: false, error: 'Health check timeout' };
      }
      return { success: false, error: error.message || 'Health check failed' };
    }
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

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        const payload = {
          command,
          parameters,
          commandId,
          sessionId
        };

        // Log data being sent to simulator
        SystemLogger.info(`Sending command to greenhouse core simulator`, {
          commandId,
          sessionId,
          command,
          parameters,
          attempt: attempt + 1,
          url: `${this.baseUrl}/api/v1/commands/execute`,
          payload: JSON.stringify(payload)
        });

        const response = await fetch(`${this.baseUrl}/api/v1/commands/execute`, {
          method: 'POST',
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();

        // Log response received from simulator
        SystemLogger.info(`Received response from greenhouse core simulator`, {
          commandId,
          sessionId,
          command,
          status: response.status,
          success: result.success,
          hasError: !!result.error,
          responseData: JSON.stringify(result)
        });

        // Check if the result indicates success
        if (result.success === false) {
          SystemLogger.warn(`Command ${command} failed in simulator`, {
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
        SystemLogger.error(`Error sending command to simulator`, {
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

