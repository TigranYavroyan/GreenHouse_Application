// routes/routes.js
import express from 'express';
import path from 'path';
import fs from 'fs';

function createRoutes({ sessionManager, redisClient, rabbitClient, commandStats, systemLogger }) {
  const router = express.Router();

  // Health
  router.get('/health', (req, res) => {
    const sessionInfo = sessionManager.listSessions().map(s => ({
      id: s.id,
      sessionNumber: s.sessionNumber,
      logFile: path.basename(s.logFile || s.logFile),
      currentPath: s.currentPath,
      createdAt: s.createdAt,
      lastActivity: s.lastActivity
    }));

    res.json({
      status: 'ok',
      timestamp: new Date().toISOString(),
      redis: redisClient && redisClient.isOpen ? 'connected' : 'disconnected',
      rabbitmq: rabbitClient && rabbitClient.channel ? 'connected' : 'disconnected',
      sessions: sessionManager.listSessions(),
      platform: process.platform,
      logsDirectory: path.join(process.cwd(), 'logs'),
      totalSessions: sessionManager.counter ? sessionManager.counter - 1 : 0,
      stats: commandStats,
    });
  });

  // Sessions list
  router.get('/sessions', (req, res) => {
    res.json({ sessions: sessionManager.listSessions() });
  });

  // Session log content
  router.get('/sessions/:sessionId/log', (req, res) => {
    const sid = req.params.sessionId;
    const s = sessionManager.getSession(sid);
    if (!s) return res.status(404).json({ error: 'Session not found' });
    try {
      const content = fs.readFileSync(s.logger.logFile, 'utf8');
      res.json({
        sessionId: sid,
        sessionNumber: s.sessionNumber,
        logFile: path.basename(s.logger.logFile),
        content
      });
    } catch (err) {
      res.status(500).json({ error: 'Failed to read log file' });
    }
  });

  // Delete session
  router.delete('/sessions/:sessionId', (req, res) => {
    const sid = req.params.sessionId;
    const s = sessionManager.getSession(sid);
    if (!s) return res.status(404).json({ error: 'Session not found' });
    s.logger.info('Session terminated via API');
    sessionManager.deleteSession(sid);
    res.json({ message: `Session ${sid} deleted`, logFile: path.basename(s.logger.logFile) });
  });

  // List logs
  router.get('/logs', (req, res) => {
    try {
      const logsDir = path.join(process.cwd(), 'logs');
      const files = fs.readdirSync(logsDir)
        .filter(f => f.endsWith('.log'))
        .map(file => {
          const fp = path.join(logsDir, file);
          const st = fs.statSync(fp);
          return { name: file, size: st.size, modified: st.mtime, path: fp, type: file.startsWith('session_') ? 'session' : 'system' };
        })
        .sort((a,b) => b.modified - a.modified);
      res.json({ logs: files });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  router.get('/logs/system', (req, res) => {
    try {
      const systemLog = path.join(process.cwd(), 'logs', 'backend_system.log');
      if (!fs.existsSync(systemLog)) return res.status(404).json({ error: 'System log not found' });
      const content = fs.readFileSync(systemLog, 'utf8');
      res.json({ name: 'backend_system.log', content });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Cache keys & clear
  router.get('/cache/keys', async (req, res) => {
    try {
      if (!redisClient) return res.status(503).json({ error: 'Redis not available' });
      const keys = await redisClient.keys('cmd:*');
      res.json({ keys });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  router.delete('/cache/clear', async (req, res) => {
    try {
      if (!redisClient) return res.status(503).json({ error: 'Redis not available' });
      const keys = await redisClient.keys('cmd:*');
      if (keys.length > 0) {
        await redisClient.del(keys);
      }
      res.json({ message: `Cleared ${keys.length} cache entries` });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // Stats
  router.get('/stats', (req, res) => {
    res.json(commandStats);
  });

  // Queues
  router.get('/queues', async (req, res) => {
    try {
      if (!rabbitClient || !rabbitClient.channel) return res.status(503).json({ error: 'RabbitMQ channel not available' });
      const commandQueue = await rabbitClient.checkQueue('greenhouse_commands');
      const responseQueue = await rabbitClient.checkQueue('command_responses');
      res.json({
        commandQueue: { messageCount: commandQueue.messageCount, consumerCount: commandQueue.consumerCount },
        responseQueue: { messageCount: responseQueue.messageCount, consumerCount: responseQueue.consumerCount }
      });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  // root
  router.get('/', (req, res) => {
    res.json({
      message: 'Greenhouse Automation Backend',
      version: '1.0.0',
      logsDirectory: path.join(process.cwd(), 'logs'),
      endpoints: [
        'GET  /health',
        'GET  /sessions',
        'GET  /sessions/:sessionId/log',
        'GET  /logs',
        'GET  /logs/system',
        'DELETE /sessions/:sessionId',
        'GET  /cache/keys',
        'DELETE /cache/clear',
        'GET  /stats',
        'GET  /queues'
      ]
    });
  });

  return router;
}

export default createRoutes;
