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

  // Clear only error entries from cache
  router.delete('/cache/clear-errors', async (req, res) => {
    try {
      if (!redisClient) return res.status(503).json({ error: 'Redis not available' });
      const keys = await redisClient.keys('cmd:*');
      let deletedCount = 0;
      
      for (const key of keys) {
        try {
          const cached = await redisClient.get(key);
          if (cached) {
            const result = JSON.parse(cached);
            if (result && result.error) {
              await redisClient.del([key]);
              deletedCount++;
            }
          }
        } catch (e) {
          // If we can't parse it, delete it as it's likely corrupted
          await redisClient.del([key]);
          deletedCount++;
        }
      }
      
      res.json({ message: `Cleared ${deletedCount} error cache entries` });
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

  // Aggregated data endpoints (Edge-to-Fog sync)
  router.post('/fog/aggregated', async (req, res) => {
    try {
      if (!redisClient || !redisClient.isOpen) {
        return res.status(503).json({ error: 'Redis not available' });
      }
      
      const { sensorType, location, timeframe, data } = req.body;
      if (!sensorType || !location || !timeframe || !data) {
        return res.status(400).json({ error: 'Missing required fields: sensorType, location, timeframe, data' });
      }
      
      // Store aggregated data in Redis with namespace
      const cacheKey = `fog:agg:${sensorType}:${location}:${timeframe}`;
      const ttl = timeframe === '1min' ? 300 : timeframe === '5min' ? 600 : timeframe === '15min' ? 1800 : 3600;
      
      await redisClient.setEx(cacheKey, ttl, JSON.stringify({
        ...data,
        sensorType,
        location,
        timeframe,
        receivedAt: new Date().toISOString()
      }));
      
      systemLogger.info(`Stored aggregated data: ${cacheKey}`);
      res.json({ success: true, key: cacheKey });
    } catch (err) {
      systemLogger.error(`Failed to store aggregated data: ${err.message}`);
      res.status(500).json({ error: err.message });
    }
  });

  router.get('/fog/aggregated', async (req, res) => {
    try {
      if (!redisClient || !redisClient.isOpen) {
        return res.status(503).json({ error: 'Redis not available' });
      }
      
      const { sensorType, location, timeframe } = req.query;
      let pattern = 'fog:agg:*';
      
      if (sensorType && location && timeframe) {
        pattern = `fog:agg:${sensorType}:${location}:${timeframe}`;
      } else if (sensorType && location) {
        pattern = `fog:agg:${sensorType}:${location}:*`;
      } else if (sensorType) {
        pattern = `fog:agg:${sensorType}:*`;
      }
      
      const keys = await redisClient.keys(pattern);
      const results = [];
      
      for (const key of keys) {
        const value = await redisClient.get(key);
        if (value) {
          try {
            const data = JSON.parse(value);
            results.push(data);
          } catch (e) {
            systemLogger.warn(`Failed to parse aggregated data for key: ${key}`);
          }
        }
      }
      
      res.json({ count: results.length, data: results });
    } catch (err) {
      systemLogger.error(`Failed to get aggregated data: ${err.message}`);
      res.status(500).json({ error: err.message });
    }
  });

  router.get('/fog/devices', async (req, res) => {
    try {
      if (!redisClient || !redisClient.isOpen) {
        return res.status(503).json({ error: 'Redis not available' });
      }
      
      const keys = await redisClient.keys('fog:device:*');
      const devices = [];
      
      for (const key of keys) {
        const value = await redisClient.get(key);
        if (value) {
          try {
            const device = JSON.parse(value);
            devices.push(device);
          } catch (e) {
            systemLogger.warn(`Failed to parse device data for key: ${key}`);
          }
        }
      }
      
      res.json({ count: devices.length, devices });
    } catch (err) {
      systemLogger.error(`Failed to get devices: ${err.message}`);
      res.status(500).json({ error: err.message });
    }
  });

  router.post('/fog/anomalies', async (req, res) => {
    try {
      if (!redisClient || !redisClient.isOpen) {
        return res.status(503).json({ error: 'Redis not available' });
      }
      
      const anomaly = req.body;
      if (!anomaly.anomaly_id || !anomaly.sensor_type || !anomaly.location) {
        return res.status(400).json({ error: 'Missing required fields' });
      }
      
      // Store anomaly in Redis
      const cacheKey = `fog:anomaly:${anomaly.anomaly_id}`;
      await redisClient.setEx(cacheKey, 86400, JSON.stringify({
        ...anomaly,
        receivedAt: new Date().toISOString()
      }));
      
      // Also add to list of recent anomalies
      const listKey = 'fog:anomalies:recent';
      const recentAnomalies = await redisClient.get(listKey);
      let anomalies = recentAnomalies ? JSON.parse(recentAnomalies) : [];
      anomalies.unshift(anomaly);
      anomalies = anomalies.slice(0, 100); // Keep only last 100
      await redisClient.setEx(listKey, 86400, JSON.stringify(anomalies));
      
      systemLogger.warn(`Anomaly received: ${anomaly.message}`);
      res.json({ success: true, key: cacheKey });
    } catch (err) {
      systemLogger.error(`Failed to store anomaly: ${err.message}`);
      res.status(500).json({ error: err.message });
    }
  });

  router.get('/fog/anomalies', async (req, res) => {
    try {
      if (!redisClient || !redisClient.isOpen) {
        return res.status(503).json({ error: 'Redis not available' });
      }
      
      const limit = parseInt(req.query.limit) || 10;
      const listKey = 'fog:anomalies:recent';
      const recentAnomalies = await redisClient.get(listKey);
      
      if (recentAnomalies) {
        const anomalies = JSON.parse(recentAnomalies);
        res.json({ count: Math.min(limit, anomalies.length), anomalies: anomalies.slice(0, limit) });
      } else {
        res.json({ count: 0, anomalies: [] });
      }
    } catch (err) {
      systemLogger.error(`Failed to get anomalies: ${err.message}`);
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


  // try to fix


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
