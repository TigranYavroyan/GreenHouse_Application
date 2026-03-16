class CacheService {
  constructor(redisClient) {
    this.redisClient = redisClient;
  }

  ensureRedis() {
    if (!this.redisClient || !this.redisClient.isOpen) {
      const error = new Error('Redis not available');
      error.status = 503;
      throw error;
    }
  }

  async getKeys() {
    try {
      this.ensureRedis();
      const keys = await this.redisClient.keys('cmd:*');
      return keys;
    } catch (err) {
      if (err.status) throw err;
      throw new Error(`Failed to get cache keys: ${err.message}`);
    }
  }

  async clear() {
    try {
      const keys = await this.getKeys();
      if (keys.length > 0) {
        await this.redisClient.del(keys);
      }
    } catch (err) {
      throw new Error(`Failed to clear cache: ${err.message}`);
    }
  }

  async clearErrors() {
    try {
      const keys = await this.getKeys();
      for (const key of keys) {
        const cached = await this.redisClient.get(key);
        if (cached) {
          const result = JSON.parse(cached);
          if (result && result.error) {
            await this.redisClient.del([key]);
          }
        }
      }
    } catch (err) {
      throw new Error(`Failed to clear error cache: ${err.message}`);
    }
  }
}

export default CacheService;
