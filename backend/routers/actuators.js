import { Router } from 'express';
import ActuatorsController from '../modules/actuators/actuators.controller.js';

export default function createActuatorsRouter({ actuatorsService, userContextMiddleware }) {
  const router = Router();
  const controller = new ActuatorsController(actuatorsService);

  router.use(userContextMiddleware);
  router.post('/', controller.create);
  router.get('/', controller.list);
  router.get('/:id', controller.getById);
  router.patch('/:id', controller.update);
  router.delete('/:id', controller.delete);

  return router;
}
