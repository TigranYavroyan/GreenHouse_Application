// config/index.js
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import ConfigPostgres from './configPostgres.js';


const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default {
  ConfigPostgres,
  configEnv: () => {
    dotenv.config({
      path: `.env.${process.env.NODE_ENV}`,
    });
  },
  redis: {
    host: process.env.REDIS_HOST || 'localhost',
    port: process.env.REDIS_PORT ? Number(process.env.REDIS_PORT) : 6379
  },
  rabbitmq: {
    host: process.env.RABBITMQ_HOST || 'localhost',
    port: process.env.RABBITMQ_PORT ? Number(process.env.RABBITMQ_PORT) : 5672
  },
  logsDir: path.join(__dirname, '..', 'logs'),
  server: {
    port: process.env.PORT ? Number(process.env.PORT) : 3000
  },
  greenhouseCore: {
    url: process.env.GREENHOUSE_CORE_URL || 'http://localhost:3001',
    timeout: Number(process.env.GREENHOUSE_CORE_TIMEOUT) || 10000,
    retries: Number(process.env.GREENHOUSE_CORE_RETRIES) || 2
  }
};
