// logger/systemLogger.js
import fs from 'fs';
import os from 'os';
import path from 'path';
import config from '../config/index.js';

function ensureLogsDir() {
  if (!fs.existsSync(config.logsDir)) {
    fs.mkdirSync(config.logsDir, { recursive: true });
  }
}
ensureLogsDir();

const logFilePath = path.join(config.logsDir, 'backend_system.log');

function writeLine(line) {
  fs.appendFileSync(logFilePath, line);
}

const header = `=== Greenhouse Backend System Log ===
Started: ${new Date().toISOString()}
Node.js: ${process.version}
Platform: ${os.platform()}/${os.arch()}
Logs Directory: ${config.logsDir}
==============================================

`;

if (!fs.existsSync(logFilePath)) {
  fs.writeFileSync(logFilePath, header);
} else {
  fs.appendFileSync(logFilePath, `\n\n=== Backend Restarted: ${new Date().toISOString()} ===\n\n`);
}

const SystemLogger = {
  info: (msg) => {
    const ts = new Date().toISOString();
    const line = `[${ts}] INFO: ${msg}\n`;
    writeLine(line);
    console.log(`[System] ${msg}`);
  },
  error: (msg) => {
    const ts = new Date().toISOString();
    const line = `[${ts}] ERROR: ${msg}\n`;
    writeLine(line);
    console.error(`[System] ${msg}`);
  },
  warn: (msg) => {
    const ts = new Date().toISOString();
    const line = `[${ts}] WARN: ${msg}\n`;
    writeLine(line);
    console.warn(`[System] ${msg}`);
  },
  debug: (msg) => {
    const ts = new Date().toISOString();
    const line = `[${ts}] DEBUG: ${msg}\n`;
    writeLine(line);
  },
  getLogPath: () => logFilePath
};

export default SystemLogger;
