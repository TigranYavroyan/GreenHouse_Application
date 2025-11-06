// logger/sessionLogger.js
import fs from 'fs';
import path from 'path';
import config from '../config/index.js';
import SystemLogger from './systemLogger.js';

export default function createSessionLogger(sessionId, sessionNumber) {
  const logsDir = config.logsDir;
  if (!fs.existsSync(logsDir)) fs.mkdirSync(logsDir, { recursive: true });

  const fileName = `session_${sessionNumber}.log`;
  const filePath = path.join(logsDir, fileName);

  const header = `=== Session Log ===
Session ID: ${sessionId}
Session Number: ${sessionNumber}
Created: ${new Date().toISOString()}
Log File: ${fileName}
========================================

`;
  fs.writeFileSync(filePath, header);

  const logger = {
    sessionId,
    sessionNumber,
    logFile: filePath,
    info: (message) => {
      const ts = new Date().toISOString();
      fs.appendFileSync(filePath, `[${ts}] INFO: ${message}\n`);
      SystemLogger.debug(`[Session ${sessionNumber}] ${message}`);
    },
    error: (message) => {
      const ts = new Date().toISOString();
      fs.appendFileSync(filePath, `[${ts}] ERROR: ${message}\n`);
      SystemLogger.error(`[Session ${sessionNumber}] ${message}`);
    },
    debug: (message) => {
      const ts = new Date().toISOString();
      fs.appendFileSync(filePath, `[${ts}] DEBUG: ${message}\n`);
    },
    command: (commandId, action, details = '') => {
      const ts = new Date().toISOString();
      fs.appendFileSync(filePath, `[${ts}] COMMAND: ${commandId} - ${action} ${details}\n`);
    },
    getSessionInfo: () => ({
      sessionId,
      sessionNumber,
      logFile: fileName,
      createdAt: new Date().toISOString()
    })
  };

  logger.info(`Session started - ID: ${sessionId}`);
  SystemLogger.info(`Created new session: ${sessionId} (${fileName})`);
  return logger;
}
