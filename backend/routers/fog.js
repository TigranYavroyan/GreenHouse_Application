import { Router } from 'express';
import FogService from '../modules/fog/fog.service.js';
import FogController from '../modules/fog/fog.controller.js';

export default function createFogRouter(redisClient, systemLogger) {
  const router = Router();

  const service = new FogService(redisClient, systemLogger);
  const controller = new FogController(service);

  router.post('/aggregated', controller.storeAggregated);
  router.get('/aggregated', controller.getAggregated);
  router.get('/devices', controller.getDevices);
  router.post('/anomalies', controller.storeAnomaly);
  router.get('/anomalies', controller.getAnomalies);

  return router;
}