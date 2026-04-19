// sessions/sessionManager.js
import createSessionLogger from '../logger/sessionLogger.js';
import SystemLogger from '../logger/systemLogger.js';
import config from '../config/index.js';

class SessionManager {
  constructor() {
    this.sessions = new Map();
    this.counter = 1;
  }

  createSession(sessionId) {
    if (this.sessions.has(sessionId)) return this.sessions.get(sessionId);
    const sessionNumber = this.counter++;
    const logger = createSessionLogger(sessionId, sessionNumber);

    const session = {
      sessionId,
      logger,
      sessionNumber,
      currentPath: process.cwd(),
      previousPath: process.cwd(),
      createdAt: new Date().toISOString(),
      lastActivity: new Date().toISOString(),
      commandQueue: Promise.resolve(),
      isProcessing: false
    };

    this.sessions.set(sessionId, session);
    return session;
  }

  getSession(sessionId) {
    return this.sessions.get(sessionId);
  }

  getOrCreate(sessionId) {
    let s = this.getSession(sessionId);
    if (!s) s = this.createSession(sessionId);
    s.lastActivity = new Date().toISOString();
    return s;
  }

  deleteSession(sessionId) {
    const s = this.sessions.get(sessionId);
    if (s) {
      s.logger.info('Session terminated');
      this.sessions.delete(sessionId);
      SystemLogger.info(`Session deleted: ${sessionId}`);
    }
  }

  listSessions() {
    return Array.from(this.sessions.values()).map(s => ({
      id: s.sessionId,
      sessionNumber: s.sessionNumber,
      logFile: s.logger.logFile,
      currentPath: s.currentPath,
      createdAt: s.createdAt,
      lastActivity: s.lastActivity
    }));
  }

  cleanupOldSessions(maxAgeMs = config.sessions.inactivityTtlMs) {
    const now = Date.now();
    for (const [id, s] of this.sessions.entries()) {
      if (now - new Date(s.lastActivity).getTime() > maxAgeMs) {
        s.logger.info(`Session terminated due to inactivity (${maxAgeMs / 60000} minutes)`);
        this.sessions.delete(id);
        SystemLogger.info(`Cleaned up old session: ${id}`);
      }
    }
  }
}

export default SessionManager;
