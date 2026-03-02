import fs from 'fs';

class SessionService {
  constructor(sessionManager) {
    this.sessionManager = sessionManager;
  }

  listSessions() {
    return this.sessionManager.listSessions();
  }

  getSessionLog(sessionId) {
    const session = this.sessionManager.getSession(sessionId);
    if (!session) throw new Error('Session not found');

    const content = fs.readFileSync(session.logger.logFile, 'utf8');

    return {
      sessionId,
      sessionNumber: session.sessionNumber,
      logFile: session.logger.logFile,
      content,
    };
  }

  deleteSession(sessionId) {
    const session = this.sessionManager.getSession(sessionId);
    if (!session) throw new Error('Session not found');

    session.logger.info('Session terminated via API');
    this.sessionManager.deleteSession(sessionId);

    return { message: `Session ${sessionId} deleted` };
  }
}

export default SessionService;