// logger/simulatorLogger.js
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

class SimulatorLogger {
  constructor() {
    // Create logs directory if it doesn't exist
    // __dirname is sim/logger, so we go up one level to sim, then into logs
    const logsDir = path.join(__dirname, '..', 'logs');
    if (!fs.existsSync(logsDir)) {
      fs.mkdirSync(logsDir, { recursive: true });
      console.log(`Created logs directory: ${logsDir}`);
    }

    this.logFile = path.join(logsDir, 'simulator.log');
    this.maxFileSize = 10 * 1024 * 1024; // 10MB
    this.maxBackups = 5;
    
    // Log initialization with file path
    console.log(`Simulator logger initialized. Log file: ${this.logFile}`);
    
    // Write initial log entry
    this.writeLog('info', 'Simulator logger initialized', {
      logFile: this.logFile,
      logsDirectory: logsDir,
      maxFileSize: `${this.maxFileSize / 1024 / 1024}MB`,
      maxBackups: this.maxBackups
    });
  }

  /**
   * Format log message with timestamp
   */
  formatMessage(level, message, data = null) {
    const timestamp = new Date().toISOString();
    let logLine = `[${timestamp}] [${level.toUpperCase()}] ${message}`;
    
    if (data) {
      logLine += ` | Data: ${JSON.stringify(data)}`;
    }
    
    return logLine + '\n';
  }

  /**
   * Write to log file
   */
  writeLog(level, message, data = null) {
    const logLine = this.formatMessage(level, message, data);
    
    try {
      // Ensure logs directory exists (in case it was deleted)
      const logsDir = path.dirname(this.logFile);
      if (!fs.existsSync(logsDir)) {
        fs.mkdirSync(logsDir, { recursive: true });
      }

      // Check file size and rotate if needed
      if (fs.existsSync(this.logFile)) {
        const stats = fs.statSync(this.logFile);
        if (stats.size > this.maxFileSize) {
          this.rotateLog();
        }
      }

      // Append to log file (creates file if it doesn't exist)
      fs.appendFileSync(this.logFile, logLine, 'utf8');
      
      // Also output to console
      const consoleMethod = level === 'error' ? console.error : 
                           level === 'warn' ? console.warn : 
                           level === 'debug' ? console.debug : console.log;
      consoleMethod(logLine.trim());
    } catch (error) {
      // Fallback: always log errors to console even if file write fails
      console.error(`Failed to write to log file (${this.logFile}): ${error.message}`);
      console.error(`Error details: ${error.stack}`);
      // Still output the original log to console
      const consoleMethod = level === 'error' ? console.error : 
                           level === 'warn' ? console.warn : 
                           level === 'debug' ? console.debug : console.log;
      consoleMethod(logLine.trim());
    }
  }

  /**
   * Rotate log files
   */
  rotateLog() {
    try {
      // Move current log to backup
      for (let i = this.maxBackups - 1; i >= 1; i--) {
        const oldFile = `${this.logFile}.${i}`;
        const newFile = `${this.logFile}.${i + 1}`;
        if (fs.existsSync(oldFile)) {
          if (fs.existsSync(newFile)) {
            fs.unlinkSync(newFile);
          }
          fs.renameSync(oldFile, newFile);
        }
      }
      
      // Move current log to .1
      if (fs.existsSync(this.logFile)) {
        fs.renameSync(this.logFile, `${this.logFile}.1`);
      }
    } catch (error) {
      console.error(`Failed to rotate log file: ${error.message}`);
    }
  }

  /**
   * Log info message
   */
  info(message, data = null) {
    this.writeLog('info', message, data);
  }

  /**
   * Log error message
   */
  error(message, data = null) {
    this.writeLog('error', message, data);
  }

  /**
   * Log warning message
   */
  warn(message, data = null) {
    this.writeLog('warn', message, data);
  }

  /**
   * Log debug message
   */
  debug(message, data = null) {
    this.writeLog('debug', message, data);
  }

  /**
   * Log command received
   */
  commandReceived(command, parameters, commandId, sessionId) {
    this.info(`Command received: ${command}`, {
      commandId,
      sessionId,
      command,
      parameters
    });
  }

  /**
   * Log command executed
   */
  commandExecuted(command, result, commandId, executionTime = null) {
    const logData = {
      commandId,
      command,
      success: result.success,
      executionTime
    };
    
    if (result.success) {
      this.info(`Command executed successfully: ${command}`, logData);
    } else {
      this.error(`Command execution failed: ${command}`, {
        ...logData,
        error: result.error
      });
    }
  }

  /**
   * Log data sent to client
   */
  dataSent(endpoint, payload, responseStatus) {
    this.info(`Data sent to client`, {
      endpoint,
      payload,
      responseStatus
    });
  }

  /**
   * Log device state change
   */
  deviceStateChanged(deviceType, deviceId, oldState, newState) {
    this.info(`Device state changed: ${deviceType}/${deviceId}`, {
      deviceType,
      deviceId,
      oldState,
      newState
    });
  }

  /**
   * Log sensor reading
   */
  sensorReading(sensorType, value, unit, deviceId) {
    this.debug(`Sensor reading: ${sensorType}`, {
      sensorType,
      value,
      unit,
      deviceId
    });
  }
}

// Export singleton instance
const simulatorLogger = new SimulatorLogger();
export default simulatorLogger;

