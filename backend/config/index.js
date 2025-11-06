// config/index.js
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default {
  redis: {
    host: process.env.REDIS_HOST || 'redis',
    port: process.env.REDIS_PORT ? Number(process.env.REDIS_PORT) : 6379
  },
  rabbitmq: {
    host: process.env.RABBITMQ_HOST || 'rabbitmq',
    port: process.env.RABBITMQ_PORT ? Number(process.env.RABBITMQ_PORT) : 5672
  },
  logsDir: path.join(__dirname, '..', 'logs'),
  server: {
    port: process.env.PORT ? Number(process.env.PORT) : 3000
  },
  exec: {
    timeout: Number(process.env.EXEC_TIMEOUT_MS) || 15000
  }
};
