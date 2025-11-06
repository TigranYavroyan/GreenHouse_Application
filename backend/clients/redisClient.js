// clients/redisClient.js
import redis from 'redis';
import SystemLogger from '../logger/systemLogger.js';
import config from '../config/index.js';

class RedisClientWrapper {
  constructor() {
    this.client = redis.createClient({
      socket: {
        host: config.redis.host,
        port: config.redis.port
      }
    });
    this._isOpen = false;

    this.client.on('error', (err) => {
      SystemLogger.error(`Redis Client Error: ${err.message}`);
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
      await this.client.connect();
    }
  }

  get isOpen() {
    return this.client && this.client.isOpen;
  }

  async get(key) {
    return await this.client.get(key);
  }

  async setEx(key, ttlSeconds, value) {
    return await this.client.setEx(key, ttlSeconds, value);
  }

  async keys(pattern) {
    return await this.client.keys(pattern);
  }

  async del(keys) {
    if (!keys || keys.length === 0) return 0;
    return await this.client.del(keys);
  }
}

export default RedisClientWrapper;
