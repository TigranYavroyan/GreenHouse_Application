// config/index.js
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import ConfigPostgres from './configPostgres.js';


const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const normalizeNodeEnv = () => (
  process.env.NODE_ENV === 'production' ? 'production' : 'development'
);

const config = {
  ConfigPostgres,
  configEnv: () => {
    const normalizedEnv = normalizeNodeEnv();
    dotenv.config({
      path: `.env.${normalizedEnv}`,
    });
  },
  logsDir: path.join(__dirname, '..', 'logs'),
  get redis() {
    return {
      host: process.env.REDIS_HOST || 'localhost',
      port: process.env.REDIS_PORT ? Number(process.env.REDIS_PORT) : 6379,
    };
  },
  get rabbitmq() {
    return {
      host: process.env.RABBITMQ_HOST || 'localhost',
      port: process.env.RABBITMQ_PORT ? Number(process.env.RABBITMQ_PORT) : 5672,
    };
  },
  get server() {
    return {
      port: process.env.PORT ? Number(process.env.PORT) : 3000,
    };
  },
  get greenhouseCore() {
    return {
      url: process.env.GREENHOUSE_CORE_URL || 'http://192.168.27.16:8080',
      timeout: Number(process.env.GREENHOUSE_CORE_TIMEOUT) || 10000,
      retries: Number(process.env.GREENHOUSE_CORE_RETRIES) || 2,
    };
  },
};

export default config;
