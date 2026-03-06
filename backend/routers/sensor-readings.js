import { Router } from 'express';
import SensorReadingsController from '../modules/sensor-readings/sensor-readings.controller.js';

export default function createSensorReadingsRouter({ sensorReadingsService, userContextMiddleware }) {
  const router = Router();
  const controller = new SensorReadingsController(sensorReadingsService);

  router.use(userContextMiddleware);
  router.post('/', controller.create);
  router.get('/', controller.list);
  router.get('/:id', controller.getById);
  router.patch('/:id', controller.update);
  router.delete('/:id', controller.delete);

  return router;
}
