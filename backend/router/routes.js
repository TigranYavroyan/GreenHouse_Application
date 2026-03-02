// routes/routes.js
import authMiddleware from '../middleware/authMiddleware.js';
import express from 'express';
import bcrypt from 'bcryptjs';
import path from 'path';
import fs from 'fs';


function createRoutes({ sessionManager, redisClient, rabbitClient, commandStats, systemLogger }) {
  const router = express.Router();

  // Health
  router.get('/health', authMiddleware, (req, res) => {
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
        'GET  /queues',
        'POST /fog/aggregated',
        'GET  /fog/aggregated',
        'GET  /fog/devices',
        'POST /fog/anomalies',
        'GET  /fog/anomalies'
      ]
    });
  });

  router.post('/registration', (req, res) => {
    const { username, password } = req.body;
    if (!username || !password) {
      return res.status(400).json({ error: 'Missing username or password' });
    }

    // Hash password and store user in database
    const hashedPassword = bcrypt.hashSync(password, 8);
    const user = { username, password: hashedPassword };
    // Save user to database (omitted for brevity)

    res.status(201).json({ message: 'User registered successfully' });
  });

  router.post('/login', (req, res) => {
    const { username, password } = req.body;
    if (!username || !password) {
      return res.status(400).json({ error: 'Missing username or password' });
    }

    // Find user in database (omitted for brevity)

    // Compare passwords
    const isValid = bcrypt.compareSync(password, user.password);
    if (!isValid) {
      return res.status(401).json({ error: 'Invalid username or password' });
    }

    // Generate JWT token
    const token = jwt.sign({ id: user.id }, process.env.JWT_SECRET, { expiresIn: '1h' });
    res.json({ token });
  });

  return router;
}

export default createRoutes;
