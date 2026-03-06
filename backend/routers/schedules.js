import { Router } from 'express';
import SchedulesController from '../modules/schedules/schedules.controller.js';

export default function createSchedulesRouter({ schedulesService, userContextMiddleware }) {
  const router = Router();
  const controller = new SchedulesController(schedulesService);

  router.use(userContextMiddleware);
  router.post('/', controller.create);
  router.get('/', controller.list);
  router.get('/:id', controller.getById);
  router.patch('/:id', controller.update);
  router.delete('/:id', controller.delete);

  return router;
}
