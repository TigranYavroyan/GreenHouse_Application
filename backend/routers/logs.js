import { Router } from 'express';
import LogsService from '../modules/logs/logs.service.js';
import LogsController from '../modules/logs/logs.controller.js';

export default function createLogsRouter() {
  const router = Router();

  const service = new LogsService();
  const controller = new LogsController(service);

  router.get('/', controller.list);
  router.get('/system', controller.system);

  return router;
}