import { Router } from 'express';
import UserLogsController from '../modules/user-logs/user-logs.controller.js';

export default function createUserLogsRouter({ userLogsService, userContextMiddleware }) {
  const router = Router();
  const controller = new UserLogsController(userLogsService);

  router.use(userContextMiddleware);
  router.post('/', controller.create);
  router.get('/', controller.list);
  router.get('/:id', controller.getById);
  router.patch('/:id', controller.update);
  router.delete('/:id', controller.delete);

  return router;
}
