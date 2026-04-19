// config/index.js
import fs from 'node:fs';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import ConfigPostgres from './configPostgres.js';


const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/** Repository root `.env` (next to docker-compose.yml), for local monorepo runs. */
function resolveProjectEnvPath() {
  const seeds = new Set();
  const addSeed = (p) => {
    const resolved = path.resolve(p);
    if (resolved) seeds.add(resolved);
  };
  addSeed(__dirname);
  addSeed(process.cwd());

  for (const seed of seeds) {
    let dir = seed;
    for (let i = 0; i < 12; i += 1) {
      const envPath = path.join(dir, '.env');
      const composePath = path.join(dir, 'docker-compose.yml');
      if (fs.existsSync(composePath) && fs.existsSync(envPath)) {
        return envPath;
      }
      const parent = path.dirname(dir);
      if (parent === dir) break;
      dir = parent;
    }
  }
  return null;
}

const config = {
  ConfigPostgres,
  configEnv: () => {
    const envPath = resolveProjectEnvPath();
    if (envPath) {
      dotenv.config({ path: envPath });
    }
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
  get smtp() {
    return {
      host: process.env.SMTP_HOST || 'smtp.gmail.com',
      port: process.env.SMTP_PORT ? Number(process.env.SMTP_PORT) : 587,
      secure: String(process.env.SMTP_SECURE || 'false').toLowerCase() === 'true',
      user: process.env.SMTP_USER || '',
      pass: process.env.SMTP_PASS || '',
    };
  },
  get mail() {
    return {
      from: process.env.MAIL_FROM || 'no-reply@greenhouse.local',
    };
  },
  get notification() {
    return {
      maxRetries: process.env.NOTIFICATION_MAX_RETRIES ? Number(process.env.NOTIFICATION_MAX_RETRIES) : 5,
      retryDelayMs: process.env.NOTIFICATION_RETRY_DELAY_MS ? Number(process.env.NOTIFICATION_RETRY_DELAY_MS) : 30000,
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
