import { Router } from 'express';
import UsersController from '../modules/users/users.controller.js';

export default function createUsersRouter({ usersService }) {
  const router = Router();
  const controller = new UsersController(usersService);

  router.post('/', controller.create);
  router.get('/', controller.list);
  router.get('/:id', controller.getById);
  router.patch('/:id', controller.update);
  router.delete('/:id', controller.delete);

  return router;
}
