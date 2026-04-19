// clients/redisClient.js
import redis from 'redis';
import SystemLogger from '../logger/systemLogger.js';
import config from '../config/index.js';

class RedisClientWrapper {
  constructor() {
    this._isOpen = false;
    this._lastRedisErrorLogAt = 0;
    this._errorLogIntervalMs = config.redis.errorLogIntervalMs;

    const { reconnectBackoffBaseMs, reconnectBackoffMaxMs } = config.redis;
    this.client = redis.createClient({
      socket: {
        host: config.redis.host,
        port: config.redis.port,
        reconnectStrategy: (retries) => {
          const cappedRetries = Math.min(retries, 10);
          return Math.min(
            reconnectBackoffBaseMs * (2 ** cappedRetries),
            reconnectBackoffMaxMs
          );
        },
      }
    });

    this.client.on('error', (err) => {
      const now = Date.now();
      if (now - this._lastRedisErrorLogAt >= this._errorLogIntervalMs) {
        SystemLogger.error(`Redis Client Error: ${err.message}`);
        this._lastRedisErrorLogAt = now;
      }
      this._isOpen = false;
    });
    this.client.on('connect', () => {
      SystemLogger.info('Redis Client Connected');
    });
    this.client.on('ready', () => {
      SystemLogger.info('Redis Client Ready');
      this._isOpen = true;
    });
    this.client.on('end', () => {
      SystemLogger.warn('Redis client ended');
      this._isOpen = false;
    });
  }

  async connect() {
    if (!this.client.isOpen) {
      try {
        await this.client.connect();
      } catch (error) {
        this._isOpen = false;
        SystemLogger.warn(`Redis connect failed; running in degraded mode: ${error.message}`);
      }
    }
  }

  get isOpen() {
    return this.client && this.client.isOpen;
  }

  async get(key) {
    if (!this.isOpen) return null;
    return await this.client.get(key);
  }

  async setEx(key, ttlSeconds, value) {
    if (!this.isOpen) return null;
    return await this.client.setEx(key, ttlSeconds, value);
  }

  async keys(pattern) {
    if (!this.isOpen) return [];
    return await this.client.keys(pattern);
  }

  async del(keys) {
    if (!this.isOpen) return 0;
    if (!keys || keys.length === 0) return 0;
    return await this.client.del(keys);
  }

  async mGet(keys) {
    if (!this.isOpen) return [];
    if (!keys || keys.length === 0) return [];
    return await this.client.mGet(keys);
  }

  scanIterator(options = {}) {
    if (!this.isOpen) {
      return (async function* emptyIterator() {})();
    }
    return this.client.scanIterator(options);
  }

  async lPush(key, value) {
    if (!this.isOpen) return null;
    return await this.client.lPush(key, value);
  }

  async lTrim(key, start, stop) {
    if (!this.isOpen) return null;
    return await this.client.lTrim(key, start, stop);
  }

  async lRange(key, start, stop) {
    if (!this.isOpen) return [];
    return await this.client.lRange(key, start, stop);
  }

  async expire(key, ttlSeconds) {
    if (!this.isOpen) return null;
    return await this.client.expire(key, ttlSeconds);
  }
}

export default RedisClientWrapper;
