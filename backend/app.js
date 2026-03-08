import express from 'express';
import SystemLogger from './logger/systemLogger.js';
import RedisClientWrapper from './clients/redisClient.js';
import RabbitMQClient from './clients/rabbitmqClient.js';
import GreenhouseCoreClient from './clients/greenhouseCoreClient.js';
import SessionManager from './sessions/sessionManager.js';
import CommandExecutor from './executor/commandExecutor.js';
import CommandProcessor from './processor/commandProcessor.js';
import config from './config/index.js';
import createCacheRouter from './routers/cache.js';
import createFogRouter from './routers/fog.js';
import createSessionRouter from './routers/session.js';
import createLogsRouter from './routers/logs.js';
import createMetadataRouter from './routers/metadata.js';
import createAuthRouter from './routers/auth.js';
import createUsersRouter from './routers/users.js';
import createDevicesRouter from './routers/devices.js';
import createSensorsRouter from './routers/sensors.js';
import createSensorReadingsRouter from './routers/sensor-readings.js';
import createActuatorsRouter from './routers/actuators.js';
import createSchedulesRouter from './routers/schedules.js';
import createSensorAlertRulesRouter from './routers/sensor-alert-rules.js';
import createSensorAlertsRouter from './routers/sensor-alerts.js';
import createCoreRouter from './routers/core.js';
import { metricsRouter } from './clients/promClient.js';
import './entity/index.js';
import createUserContextMiddleware from './middleware/userContextMiddleware.js';
import UsersRepository from './modules/users/users.repository.js';
import DevicesRepository from './modules/devices/devices.repository.js';
import SensorsRepository from './modules/sensors/sensors.repository.js';
import SensorReadingsRepository from './modules/sensor-readings/sensor-readings.repository.js';
import ActuatorsRepository from './modules/actuators/actuators.repository.js';
import SchedulesRepository from './modules/schedules/schedules.repository.js';
import SensorAlertRulesRepository from './modules/sensor-alert-rules/sensor-alert-rules.repository.js';
import SensorAlertsRepository from './modules/sensor-alerts/sensor-alerts.repository.js';
import UsersService from './modules/users/users.service.js';
import DevicesService from './modules/devices/devices.service.js';
import SensorsService from './modules/sensors/sensors.service.js';
import SensorReadingsService from './modules/sensor-readings/sensor-readings.service.js';
import ActuatorsService from './modules/actuators/actuators.service.js';
import SchedulesService from './modules/schedules/schedules.service.js';
import SchedulesRuntime from './modules/schedules/schedules.runtime.js';
import SensorAlertRulesService from './modules/sensor-alert-rules/sensor-alert-rules.service.js';
import SensorAlertsService from './modules/sensor-alerts/sensor-alerts.service.js';
import ensureDefaultUser from './modules/users/default-user.bootstrap.js';

class App {
  constructor() {
    this.app = express();
    this.config = config;
    this.config.configEnv();
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
    this.defaultUserId = null;

    // repositories
    this.usersRepository = new UsersRepository();
    this.devicesRepository = new DevicesRepository();
    this.sensorsRepository = new SensorsRepository();
    this.sensorReadingsRepository = new SensorReadingsRepository();
    this.actuatorsRepository = new ActuatorsRepository();
    this.schedulesRepository = new SchedulesRepository();
    this.sensorAlertRulesRepository = new SensorAlertRulesRepository();
    this.sensorAlertsRepository = new SensorAlertsRepository();

    this.schedulesRuntime = new SchedulesRuntime({
      schedulesRepository: this.schedulesRepository,
      rabbitClient: this.rabbitClient,
      logger: this.systemLogger,
    });
    this.rabbitConsumerReady = false;
    this.rabbitReconnectHandlerAttached = false;

    // services
    this.usersService = new UsersService(this.usersRepository);
    this.devicesService = new DevicesService({
      devicesRepository: this.devicesRepository,
      usersRepository: this.usersRepository,
    });
    this.sensorsService = new SensorsService({
      sensorsRepository: this.sensorsRepository,
      devicesRepository: this.devicesRepository,
    });
    this.sensorReadingsService = new SensorReadingsService({
      sensorReadingsRepository: this.sensorReadingsRepository,
      sensorsRepository: this.sensorsRepository,
    });
    this.actuatorsService = new ActuatorsService({
      actuatorsRepository: this.actuatorsRepository,
      devicesRepository: this.devicesRepository,
    });
    this.schedulesService = new SchedulesService({
      schedulesRepository: this.schedulesRepository,
      devicesRepository: this.devicesRepository,
      schedulesRuntime: this.schedulesRuntime,
    });
    this.sensorAlertRulesService = new SensorAlertRulesService({
      sensorAlertRulesRepository: this.sensorAlertRulesRepository,
      sensorsRepository: this.sensorsRepository,
    });
    this.sensorAlertsService = new SensorAlertsService({
      sensorAlertsRepository: this.sensorAlertsRepository,
      sensorAlertRulesRepository: this.sensorAlertRulesRepository,
    });

    this.setupMiddleware();
    this.userContextMiddleware = createUserContextMiddleware({
      getDefaultUserId: () => this.defaultUserId,
    });
    this.setupRoutes();
  }

  setupMiddleware() {
    this.app.use(express.json());
    this.app.use((req, res, next) => {
      res.header('Access-Control-Allow-Origin', '*');
      res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization, X-User-Id');
      next();
    });
  }

  setupRoutes() {
    this.app.get('/', (req, res) => {
      res.json({
        message: 'Greenhouse Automation Backend',
        version: '1.0.0',
        endpoints: [
          'POST /auth/register',
          'POST /auth/login',
          'GET  /users',
          'GET  /devices',
          'GET  /sensors',
          'GET  /sensor-readings',
          'GET  /actuators',
          'GET  /schedules',
          'GET  /sensor-alert-rules',
          'GET  /sensor-alerts',
          'GET  /metadata/health/',
          'GET  /status',
        ],
      });
    });

    this.app.use('/auth', createAuthRouter({ userRepository: this.usersRepository }));
    this.app.use('/users', createUsersRouter({ usersService: this.usersService }));
    this.app.use('/devices', createDevicesRouter({
      devicesService: this.devicesService,
      userContextMiddleware: this.userContextMiddleware,
    }));
    this.app.use('/sensors', createSensorsRouter({
      sensorsService: this.sensorsService,
      userContextMiddleware: this.userContextMiddleware,
    }));
    this.app.use('/sensor-readings', createSensorReadingsRouter({
      sensorReadingsService: this.sensorReadingsService,
      userContextMiddleware: this.userContextMiddleware,
    }));
    this.app.use('/actuators', createActuatorsRouter({
      actuatorsService: this.actuatorsService,
      userContextMiddleware: this.userContextMiddleware,
    }));
    this.app.use('/schedules', createSchedulesRouter({
      schedulesService: this.schedulesService,
      userContextMiddleware: this.userContextMiddleware,
    }));
    this.app.use('/sensor-alert-rules', createSensorAlertRulesRouter({
      sensorAlertRulesService: this.sensorAlertRulesService,
      userContextMiddleware: this.userContextMiddleware,
    }));
    this.app.use('/sensor-alerts', createSensorAlertsRouter({
      sensorAlertsService: this.sensorAlertsService,
      userContextMiddleware: this.userContextMiddleware,
    }));
    this.app.use('/', createCoreRouter({
      greenhouseCoreClient: this.greenhouseCoreClient
    }));
    this.app.use('/cache', createCacheRouter(this.redisClient));
    this.app.use('/fog', createFogRouter(this.redisClient, this.systemLogger));
    this.app.use('/sessions', createSessionRouter({ sessionManager: this.sessionManager }));
    this.app.use('/logs', createLogsRouter());
    this.app.use('/metadata', createMetadataRouter({
      sessionManager: this.sessionManager,
      redisClient: this.redisClient,
      rabbitClient: this.rabbitClient,
      commandStats: this.commandProcessor.commandStats,
    }));
    this.app.use(metricsRouter);
  }

  async setupRabbitAndConsumer() {
    try {
      if (!this.rabbitReconnectHandlerAttached) {
        this.rabbitClient.addOnConnectHandler(async () => {
          await this.configureRabbitConsumer();
        });
        this.rabbitReconnectHandlerAttached = true;
      }

      await this.rabbitClient.connect();
      await this.schedulesRuntime.start();
      this.systemLogger.info('RabbitMQ connected and consumer bootstrap complete');
    } catch (err) {
      this.systemLogger.error(`RabbitMQ setup failed: ${err.message}`);
      setTimeout(() => this.setupRabbitAndConsumer().catch(() => {}), 5000);
    }
  }

  buildErrorResponse(commandData, error) {
    return {
      commandId: commandData && commandData.commandId ? commandData.commandId : 'unknown',
      result: null,
      cached: false,
      error: error && error.message ? error.message : JSON.stringify(error),
      timestamp: new Date().toISOString(),
      sessionId: commandData && commandData.sessionId ? commandData.sessionId : 'unknown',
      currentPath: null
    };
  }

  validateCommandMessage(commandData) {
    if (!commandData || typeof commandData !== 'object') {
      const error = new Error('Invalid command message: payload must be an object');
      error.isValidationError = true;
      throw error;
    }

    if (!commandData.commandId || typeof commandData.commandId !== 'string') {
      const error = new Error('Invalid command message: commandId is required');
      error.isValidationError = true;
      throw error;
    }

    if (!commandData.command || typeof commandData.command !== 'string') {
      const error = new Error('Invalid command message: command is required');
      error.isValidationError = true;
      throw error;
    }

    if (!commandData.type || typeof commandData.type !== 'string') {
      const error = new Error('Invalid command message: type is required');
      error.isValidationError = true;
      throw error;
    }

    if (commandData.parameters === undefined || commandData.parameters === null) {
      commandData.parameters = {};
    }

    if (typeof commandData.parameters !== 'object' || Array.isArray(commandData.parameters)) {
      const error = new Error('Invalid command message: parameters must be an object');
      error.isValidationError = true;
      throw error;
    }

    if (!commandData.sessionId || typeof commandData.sessionId !== 'string') {
      const error = new Error('Invalid command message: sessionId is required');
      error.isValidationError = true;
      throw error;
    }
  }

  publishCommandResponse(payload) {
    const published = this.rabbitClient.sendToQueue(
      'command_responses',
      Buffer.from(JSON.stringify(payload)),
      { persistent: true }
    );

    if (!published) {
      throw new Error('Failed to publish response to command_responses');
    }
  }

  async configureRabbitConsumer() {
    await this.rabbitClient.assertQueue('greenhouse_commands', { durable: true });
    await this.rabbitClient.assertQueue('command_responses', { durable: true });
    await this.rabbitClient.prefetch(5);

    if (this.rabbitConsumerReady) {
      this.rabbitConsumerReady = false;
    }

    await this.rabbitClient.consume('greenhouse_commands', async (msg) => {
      if (!msg) return;

      let commandData = null;

      try {
        commandData = JSON.parse(msg.content.toString());
      } catch (parseError) {
        const errorResponse = this.buildErrorResponse(commandData, new Error('Invalid JSON command payload'));
        try {
          this.publishCommandResponse(errorResponse);
          this.rabbitClient.ack(msg);
        } catch (publishError) {
          this.systemLogger.error(`Failed to publish parse error response: ${publishError.message}`);
          this.rabbitClient.nack(msg, true);
        }
        return;
      }

      try {
        this.validateCommandMessage(commandData);
        this.systemLogger.debug(`Processing command: ${commandData.commandId}`);
        const result = await this.commandProcessor.processCommand(commandData);
        this.publishCommandResponse(result);
        this.rabbitClient.ack(msg);
      } catch (err) {
        this.commandProcessor.commandStats.errors++;
        this.systemLogger.error(`Command processing failed: ${err && err.message ? err.message : JSON.stringify(err)}`);
        const errorResponse = this.buildErrorResponse(commandData, err);
        try {
          this.publishCommandResponse(errorResponse);
          this.rabbitClient.ack(msg);
        } catch (publishError) {
          this.systemLogger.error(`Failed to publish error response: ${publishError.message}`);
          if (err && err.isValidationError) {
            this.rabbitClient.nack(msg, false);
            return;
          }
          this.rabbitClient.nack(msg, true);
        }
      }
    }, { noAck: false });

    this.rabbitConsumerReady = true;
    this.systemLogger.info('RabbitMQ consumer configured');
  }

  async start(port = this.config.server.port) {
    try {
      await this.config.ConfigPostgres.init();
      const defaultUser = await ensureDefaultUser({
        usersRepository: this.usersRepository,
        logger: this.systemLogger,
      });
      this.defaultUserId = defaultUser?.id || null;

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

      const stopRuntime = () => {
        try {
          this.schedulesRuntime.stop();
        } catch (error) {
          this.systemLogger.warn(`Failed to stop schedules runtime: ${error.message}`);
        }
      };
      process.on('SIGINT', stopRuntime);
      process.on('SIGTERM', stopRuntime);

    } catch (err) {
      this.systemLogger.error(`Failed to start server: ${err.message}`);
      process.exit(1);
    }
  }
}

export default App;
