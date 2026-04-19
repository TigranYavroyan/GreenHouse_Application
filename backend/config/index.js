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

const projectEnvPath = resolveProjectEnvPath();
if (projectEnvPath) {
  dotenv.config({ path: projectEnvPath });
}

function envNumber(name, fallback) {
  const raw = process.env[name];
  if (raw === undefined || raw === '') return fallback;
  const n = Number(raw);
  return Number.isFinite(n) ? n : fallback;
}

const config = {
  ConfigPostgres,
  configEnv: () => {
    if (projectEnvPath) {
      dotenv.config({ path: projectEnvPath });
    }
  },
  logsDir: path.join(__dirname, '..', 'logs'),
  get httpListenHost() {
    return process.env.HTTP_LISTEN_HOST || '0.0.0.0';
  },
  get redis() {
    return {
      host: process.env.REDIS_HOST || 'localhost',
      port: envNumber('REDIS_PORT', 6379),
      errorLogIntervalMs: envNumber('REDIS_ERROR_LOG_INTERVAL_MS', 10000),
      reconnectBackoffBaseMs: envNumber('REDIS_RECONNECT_BACKOFF_BASE_MS', 500),
      reconnectBackoffMaxMs: envNumber('REDIS_RECONNECT_BACKOFF_MAX_MS', 10000),
    };
  },
  get rabbitmq() {
    return {
      host: process.env.RABBITMQ_HOST || 'localhost',
      port: envNumber('RABBITMQ_PORT', 5672),
      reconnectDelayMs: envNumber('RABBITMQ_RECONNECT_DELAY_MS', 5000),
      bootstrapRetryDelayMs: envNumber('RABBITMQ_BOOTSTRAP_RETRY_DELAY_MS', 5000),
      consumerPrefetch: envNumber('RABBITMQ_CONSUMER_PREFETCH', 5),
    };
  },
  get server() {
    return {
      port: envNumber('PORT', 3000),
    };
  },
  get smtp() {
    return {
      host: process.env.SMTP_HOST || 'smtp.gmail.com',
      port: envNumber('SMTP_PORT', 587),
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
      maxRetries: envNumber('NOTIFICATION_MAX_RETRIES', 5),
      retryDelayMs: envNumber('NOTIFICATION_RETRY_DELAY_MS', 30000),
    };
  },
  get greenhouseCore() {
    return {
      url: process.env.GREENHOUSE_CORE_URL || 'http://127.0.0.1:3001',
      timeout: envNumber('GREENHOUSE_CORE_TIMEOUT', 10000),
      retries: envNumber('GREENHOUSE_CORE_RETRIES', 2),
      retryBackoffBaseMs: envNumber('GREENHOUSE_CORE_RETRY_BACKOFF_BASE_MS', 100),
    };
  },
  get sessions() {
    return {
      cleanupIntervalMs: envNumber('SESSION_CLEANUP_INTERVAL_MS', 300000),
      inactivityTtlMs: envNumber('SESSION_INACTIVITY_TTL_MS', 1800000),
    };
  },
  get metrics() {
    return {
      defaultCollectTimeoutMs: envNumber('PROM_DEFAULT_METRICS_TIMEOUT_MS', 5000),
    };
  },
  get sensorReadings() {
    return {
      maxListLimit: envNumber('SENSOR_READINGS_MAX_LIMIT', 5000),
    };
  },
  get fog() {
    return {
      redisScanCount: envNumber('FOG_REDIS_SCAN_COUNT', 100),
      anomalyTtlSec: envNumber('FOG_ANOMALY_TTL_SEC', 86400),
      anomalyRecentMaxIndex: envNumber('FOG_ANOMALY_RECENT_LIST_MAX_INDEX', 99),
    };
  },
  get commands() {
    return {
      execTimeoutMs: envNumber('EXEC_TIMEOUT_MS', 15000),
    };
  },
};

export default config;
