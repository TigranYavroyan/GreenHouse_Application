// routes/routes.js
import authMiddleware from '../middleware/authMiddleware.js';
import express from 'express';
import bcrypt from 'bcryptjs';
import path from 'path';


function createRoutes() {
  const router = express.Router();

  // root
  router.get('/', (req, res) => {
    res.json({
      message: 'Greenhouse Automation Backend',
      version: '1.0.0',
      logsDirectory: path.join(process.cwd(), 'logs'),
      endpoints: [
        'GET  /metadata/health/',
        'GET  /sessions',
        'GET  /sessions/:sessionId/log',
        'GET  /logs',
        'GET  /logs/system',
        'DELETE /sessions/:sessionId',
        'GET  /cache/keys',
        'DELETE /cache/clear',
        'GET  /metadata/stats/',
        'GET  /metadata/queues/',
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
