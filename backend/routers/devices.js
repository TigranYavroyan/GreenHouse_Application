import { Router } from 'express';
import DevicesController from '../modules/devices/devices.controller.js';

export default function createDevicesRouter({ devicesService, userContextMiddleware }) {
  const router = Router();
  const controller = new DevicesController(devicesService);

  router.use(userContextMiddleware);
  router.post('/', controller.create);
  router.get('/', controller.list);
  router.get('/:id', controller.getById);
  router.patch('/:id', controller.update);
  router.delete('/:id', controller.delete);

  return router;
}
