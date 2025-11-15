// config/index.js
import path from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';
import dotenv from 'dotenv';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load environment variables based on NODE_ENV
const nodeEnv = process.env.NODE_ENV || 'development';

if (nodeEnv === 'production') {
  // Production: load .env file
  dotenv.config({ path: path.join(__dirname, '..', '.env') });
} else if (nodeEnv === 'development') {
  // Development: try .env_dev first, then .env.local, then .env
  const envDevPath = path.join(__dirname, '..', '.env_dev');
  const envLocalPath = path.join(__dirname, '..', '.env.local');
  const envPath = path.join(__dirname, '..', '.env');
  
  if (existsSync(envDevPath)) {
    dotenv.config({ path: envDevPath });
  } else if (existsSync(envLocalPath)) {
    dotenv.config({ path: envLocalPath });
  } else {
    dotenv.config({ path: envPath });
  }
} else {
  // Fallback: load .env
  dotenv.config({ path: path.join(__dirname, '..', '.env') });
}

export default {
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
