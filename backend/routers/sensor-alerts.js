import { Router } from 'express';
import SensorAlertsController from '../modules/sensor-alerts/sensor-alerts.controller.js';

export default function createSensorAlertsRouter({ sensorAlertsService, userContextMiddleware }) {
  const router = Router();
  const controller = new SensorAlertsController(sensorAlertsService);

  router.use(userContextMiddleware);
  router.post('/', controller.create);
  router.get('/', controller.list);
  router.get('/:id', controller.getById);
  router.patch('/:id', controller.update);
  router.delete('/:id', controller.delete);

  return router;
}
