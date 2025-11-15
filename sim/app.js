// app.js
import express from 'express';
import CommandController from './controllers/commandController.js';
import simulatorLogger from './logger/simulatorLogger.js';

const app = express();
const PORT = process.env.PORT || 3001;

simulatorLogger.info('Starting Greenhouse Core Simulator', { port: PORT });

// Middleware
app.use(express.json());
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
  
  // Log all incoming requests
  simulatorLogger.debug(`Incoming request: ${req.method} ${req.path}`, {
    method: req.method,
    path: req.path,
    query: req.query,
    body: req.body
  });
  
  next();
});

// Initialize controller
const commandController = new CommandController();

// Routes
app.get('/health', (req, res) => commandController.healthCheck(req, res));
app.get('/api/v1/health', (req, res) => commandController.healthCheck(req, res));

// Command execution endpoint
app.post('/api/v1/commands/execute', (req, res) => commandController.executeCommand(req, res));

// Alternative endpoint format for specific commands (for backward compatibility)
app.post('/api/v1/commands/read_temperature_data', (req, res) => {
  req.body.command = 'read_temperature_data';
  commandController.executeCommand(req, res);
});

app.post('/api/v1/commands/switch_water_canal', (req, res) => {
  req.body.command = 'switch_water_canal';
  commandController.executeCommand(req, res);
});

app.post('/api/v1/commands/switch_actuator', (req, res) => {
  req.body.command = 'switch_actuator';
  commandController.executeCommand(req, res);
});

// Debug/monitoring endpoint
app.get('/api/v1/devices', (req, res) => commandController.getDeviceStates(req, res));

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    message: 'Greenhouse Core Simulator',
    version: '1.0.0',
    endpoints: [
      'GET  /health',
      'GET  /api/v1/health',
      'POST /api/v1/commands/execute',
      'POST /api/v1/commands/read_temperature_data',
      'POST /api/v1/commands/switch_water_canal',
      'POST /api/v1/commands/switch_actuator',
      'GET  /api/v1/devices'
    ]
  });
});

// Error handling middleware
app.use((err, req, res, next) => {
  simulatorLogger.error('Request error', {
    error: err.message,
    stack: err.stack,
    path: req.path,
    method: req.method
  });
  res.status(500).json({
    success: false,
    error: err.message || 'Internal server error',
    timestamp: new Date().toISOString()
  });
});

// Start server
app.listen(PORT, () => {
  simulatorLogger.info(`Greenhouse Core Simulator running on port ${PORT}`);
  simulatorLogger.info(`Health check: http://localhost:${PORT}/health`);
  console.log(`Greenhouse Core Simulator running on port ${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/health`);
  console.log(`Logs directory: sim/logs/`);
  console.log(`Log file: sim/logs/simulator.log`);
  console.log(`All simulator operations are being logged to: sim/logs/simulator.log`);
});

