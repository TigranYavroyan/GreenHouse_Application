// app.js
import express from 'express';
import SystemLogger from './logger/systemLogger.js';
import RedisClientWrapper from './clients/redisClient.js';
import RabbitMQClient from './clients/rabbitmqClient.js';
import GreenhouseCoreClient from './clients/greenhouseCoreClient.js';
import SessionManager from './sessions/sessionManager.js';
import CommandExecutor from './executor/commandExecutor.js';
import CommandProcessor from './processor/commandProcessor.js';
import createRoutes from './router/routes.js';
import config from './config/index.js';

class App {
  constructor() {
    this.app = express();
    this.config = config;
    this.systemLogger = SystemLogger;

    // clients
    this.redisClient = new RedisClientWrapper();
    this.rabbitClient = new RabbitMQClient();
    this.greenhouseCoreClient = new GreenhouseCoreClient();

    // core services
    this.sessionManager = new SessionManager();
    this.commandExecutor = new CommandExecutor(SystemLogger, this.greenhouseCoreClient);
    this.commandProcessor = new CommandProcessor({
      redisClient: this.redisClient,
      sessionManager: this.sessionManager,
      rabbitClient: this.rabbitClient,
      commandExecutor: this.commandExecutor
    });

    this.setupMiddleware();
    this.setupRoutes();
  }

  setupMiddleware() {
    this.app.use(express.json());
    this.app.use((req, res, next) => {
      res.header('Access-Control-Allow-Origin', '*');
      res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
      next();
    });
  }

  setupRoutes() {
    const router = createRoutes({
      sessionManager: this.sessionManager,
      redisClient: this.redisClient,
      rabbitClient: this.rabbitClient,
      commandStats: this.commandProcessor.commandStats,
      systemLogger: this.systemLogger
    });
    this.app.use('/', router);
  }

  async setupRabbitAndConsumer() {
    try {
      await this.rabbitClient.connect();
      await this.rabbitClient.assertQueue('greenhouse_commands', { durable: true });
      await this.rabbitClient.assertQueue('command_responses', { durable: true });
      await this.rabbitClient.prefetch(5);

      // consumer
      await this.rabbitClient.consume('greenhouse_commands', async (msg) => {
        if (!msg) return;
        let commandData = null;
        try {
          commandData = JSON.parse(msg.content.toString());
          this.systemLogger.debug(`Processing command: ${commandData.commandId}`);
          const result = await this.commandProcessor.processCommand(commandData);

          // send response
          this.rabbitClient.sendToQueue('command_responses', Buffer.from(JSON.stringify(result)), { persistent: true });
          this.rabbitClient.ack(msg);
        } catch (err) {
          this.commandProcessor.commandStats.errors++;
          this.systemLogger.error(`Command processing failed: ${err && err.message ? err.message : JSON.stringify(err)}`);
          const errorResponse = {
            commandId: commandData ? commandData.commandId : 'unknown',
            error: err && err.message ? err.message : JSON.stringify(err),
            timestamp: new Date().toISOString(),
            sessionId: commandData ? commandData.sessionId : 'unknown'
          };
          try {
            this.rabbitClient.sendToQueue('command_responses', Buffer.from(JSON.stringify(errorResponse)));
          } catch (e) {
            this.systemLogger.error(`Failed to send error response: ${e.message}`);
          }
          if (msg) this.rabbitClient.ack(msg);
        }
      }, { noAck: false });

      this.systemLogger.info('RabbitMQ connected and consumer started');
    } catch (err) {
      this.systemLogger.error(`RabbitMQ setup failed: ${err.message}`);
      setTimeout(() => this.setupRabbitAndConsumer().catch(() => {}), 5000);
    }
  }

  async start(port = this.config.server.port) {
    try {
      await this.redisClient.connect();
      this.systemLogger.info('Redis connected');

      // Connect to greenhouse core
      await this.greenhouseCoreClient.connect();
      if (this.greenhouseCoreClient.connected) {
        this.systemLogger.info('Greenhouse Core Client connected');
      } else {
        this.systemLogger.warn('Greenhouse Core Client connection failed - will retry on command execution');
      }

      // start rabbit
      this.setupRabbitAndConsumer().catch((e) => this.systemLogger.error(`Rabbit setup error: ${e.message}`));

      // session cleanup
      setInterval(() => this.sessionManager.cleanupOldSessions(), 5 * 60 * 1000);

      this.app.listen(port, () => {
        this.systemLogger.info(`Greenhouse backend running on port ${port}`);
        this.systemLogger.info(`Logs directory: ${this.config.logsDir}`);
        this.systemLogger.info(`API docs available at http://localhost:${port}`);
      });

    } catch (err) {
      this.systemLogger.error(`Failed to start server: ${err.message}`);
      process.exit(1);
    }
  }
}

export default App;
