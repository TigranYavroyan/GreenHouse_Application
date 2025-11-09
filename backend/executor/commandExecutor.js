// executor/commandExecutor.js
import { exec as childExec } from 'child_process';
import util from 'util';
import config from '../config/index.js';

const execPromise = util.promisify(childExec);

class CommandExecutor {
  constructor(systemLogger) {
    this.systemLogger = systemLogger;
    this.defaultTimeout = config.exec.timeout;
  }

  /**
   * Execute a shell command in the provided cwd.
   * Returns { output, command, executionTime } or throws an object { error, code, stderr, command }.
   */
  async executeInSession(command, workingDirectory, session, opts = {}) {
    const timeout = opts.timeout || this.defaultTimeout;
    const options = {
      cwd: workingDirectory,
      shell: true,
      timeout,
      encoding: 'utf8',
      maxBuffer: 10 * 1024 * 1024
    };

    session.logger.debug(`Executing: ${command} (cwd: ${workingDirectory})`);
    const start = Date.now();

    try {
      const { stdout, stderr } = await execPromise(command, options);
      const took = Date.now() - start;
      session.logger.debug(`Command succeeded in ${took}ms: ${command}`);
      return { output: stdout ? stdout.trim() : '', stderr: stderr ? stderr.trim() : '', command, executionTime: took };
    } catch (err) {
      const took = Date.now() - start;
      if (err.killed || err.signal === 'SIGTERM') {
        session.logger.error(`Command timeout after ${timeout}ms: ${command}`);
        throw { error: `Command timed out after ${timeout}ms`, code: 'TIMEOUT', command };
      }
      session.logger.error(`Command failed (${err.code || 'ERR'}): ${command} - ${err.message}`);
      throw { error: err.message, code: err.code, stderr: err.stderr, command };
    }
  }

  // Expose higher-level commands here; keep it small and extensible.
  async runCommand(commandName, parameters = {}, session) {
    switch (commandName) {
      case 'list_directory':
        return this.executeInSession(`ls -la`, parameters.path || session.currentPath, session);
      case 'navigate':
        return this.executeInSession(`cd "${parameters.path}" && pwd`, session.currentPath, session);
      case 'change_directory':
        return this.executeInSession(`cd "${parameters.path}" && pwd`, session.currentPath, session);
      case 'get_current_path':
        return { output: session.currentPath };
      case 'system_status':
        return this.executeInSession('ps aux | head -10', session.currentPath, session);
      case 'execute_raw':
        return this.executeInSession(parameters.raw_command, session.currentPath, session);
      case 'read_sensor':
        // simulator
        {
          const sensorData = {
            temperature: Math.random() * 30 + 10,
            humidity: Math.random() * 100,
            light: Math.random() * 1000,
            timestamp: new Date().toISOString()
          };
          session.logger.info(`Sensor data: ${JSON.stringify(sensorData)}`);
          return sensorData;
        }
      default:
        // Return error in result object instead of throwing
        return { error: `Unknown command: ${commandName}`, command: commandName };
    }
  }
}

export default CommandExecutor;
