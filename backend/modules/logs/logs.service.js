import fs from 'fs';
import path from 'path';

class LogsService {
  constructor() {
    this.logsDir = path.join(process.cwd(), 'logs');
  }

  listLogs() {
    const files = fs.readdirSync(this.logsDir)
      .filter(f => f.endsWith('.log'))
      .map(file => {
        const fullPath = path.join(this.logsDir, file);
        const stat = fs.statSync(fullPath);

        return {
          name: file,
          size: stat.size,
          modified: stat.mtime,
          type: file.startsWith('session_') ? 'session' : 'system',
        };
      })
      .sort((a, b) => b.modified - a.modified);

    return files;
  }

  getSystemLog() {
    const systemLog = path.join(this.logsDir, 'backend_system.log');

    if (!fs.existsSync(systemLog)) {
      throw new Error('System log not found');
    }

    return {
      name: 'backend_system.log',
      content: fs.readFileSync(systemLog, 'utf8'),
    };
  }
}

export default LogsService;