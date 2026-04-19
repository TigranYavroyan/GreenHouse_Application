// metrics.js
import client from 'prom-client';
import express from 'express';
import config from '../config/index.js';

const collectDefaultMetrics = client.collectDefaultMetrics;
collectDefaultMetrics({ timeout: config.metrics.defaultCollectTimeoutMs });

const register = client.register;

export const metricsRouter = express.Router();

metricsRouter.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});

export { register, client };