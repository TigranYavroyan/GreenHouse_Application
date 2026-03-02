class FogService {
  constructor(redisClient, systemLogger) {
    this.redis = redisClient;
    this.logger = systemLogger;
  }

  async ensureRedis() {
    if (!this.redis || !this.redis.isOpen) {
      const err = new Error('Redis not available');
      err.status = 503;
      throw err;
    }
  }

  getTTL(timeframe) {
    const map = {
      '1min': 300,
      '5min': 600,
      '15min': 1800
    };
    return map[timeframe] || 3600;
  }

  async storeAggregated({ sensorType, location, timeframe, data }) {
    await this.ensureRedis();

    if (!sensorType || !location || !timeframe || !data) {
      const err = new Error('Missing required fields');
      err.status = 400;
      throw err;
    }

    const key = `fog:agg:${sensorType}:${location}:${timeframe}`;
    const ttl = this.getTTL(timeframe);

    await this.redis.setEx(
      key,
      ttl,
      JSON.stringify({
        ...data,
        sensorType,
        location,
        timeframe,
        receivedAt: new Date().toISOString()
      })
    );

    this.logger?.info(`Stored aggregated data: ${key}`);

    return key;
  }

  async getAggregated(filters) {
    await this.ensureRedis();

    let pattern = 'fog:agg:*';

    if (filters.sensorType && filters.location && filters.timeframe) {
      pattern = `fog:agg:${filters.sensorType}:${filters.location}:${filters.timeframe}`;
    } else if (filters.sensorType && filters.location) {
      pattern = `fog:agg:${filters.sensorType}:${filters.location}:*`;
    } else if (filters.sensorType) {
      pattern = `fog:agg:${filters.sensorType}:*`;
    }

    const keys = [];
    for await (const key of this.redis.scanIterator({
      MATCH: pattern,
      COUNT: 100
    })) {
      keys.push(key);
    }

    if (!keys.length) return [];

    const values = await this.redis.mGet(keys);

    return values
      .filter(Boolean)
      .map(v => {
        try {
          return JSON.parse(v);
        } catch {
          return null;
        }
      })
      .filter(Boolean);
  }

  async getDevices() {
    await this.ensureRedis();

    const keys = [];
    for await (const key of this.redis.scanIterator({
      MATCH: 'fog:device:*',
      COUNT: 100
    })) {
      keys.push(key);
    }

    if (!keys.length) return [];

    const values = await this.redis.mGet(keys);

    return values
      .filter(Boolean)
      .map(v => JSON.parse(v));
  }

  async storeAnomaly(anomaly) {
    await this.ensureRedis();

    if (!anomaly.anomaly_id || !anomaly.sensor_type || !anomaly.location) {
      const err = new Error('Missing required fields');
      err.status = 400;
      throw err;
    }

    const key = `fog:anomaly:${anomaly.anomaly_id}`;

    await this.redis.setEx(
      key,
      86400,
      JSON.stringify({
        ...anomaly,
        receivedAt: new Date().toISOString()
      })
    );

    // Use Redis list instead of storing JSON array
    await this.redis.lPush('fog:anomalies:recent', JSON.stringify(anomaly));
    await this.redis.lTrim('fog:anomalies:recent', 0, 99);
    await this.redis.expire('fog:anomalies:recent', 86400);

    this.logger?.warn(`Anomaly received: ${anomaly.message}`);

    return key;
  }

  async getRecentAnomalies(limit = 10) {
    await this.ensureRedis();

    const items = await this.redis.lRange(
      'fog:anomalies:recent',
      0,
      limit - 1
    );

    return items.map(i => JSON.parse(i));
  }
}

export default FogService;