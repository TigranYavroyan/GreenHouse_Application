import { Router } from 'express';
import SensorsController from '../modules/sensors/sensors.controller.js';

export default function createSensorsRouter({ sensorsService, userContextMiddleware }) {
  const router = Router();
  const controller = new SensorsController(sensorsService);

  router.use(userContextMiddleware);
  router.post('/', controller.create);
  router.get('/', controller.list);
  router.get('/:id', controller.getById);
  router.patch('/:id', controller.update);
  router.delete('/:id', controller.delete);

  return router;
}
