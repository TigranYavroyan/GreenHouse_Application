import { Router } from 'express';
import CoreService from '../modules/core/core.service.js';
import CoreController from '../modules/core/core.controller.js';

export default function createCoreRouter({ greenhouseCoreClient }) {
  const router = Router();
  const service = new CoreService({ greenhouseCoreClient });
  const controller = new CoreController(service);

  router.get('/status', controller.status);
  router.get('/schema/getters', controller.getterSchema);
  router.get('/schema/executors', controller.executorSchema);
  router.get('/getters', controller.getters);
  router.get('/getters/:key', controller.getterByKey);
  router.get('/executors', controller.executors);

  router.post('/api/executors/:name/:action', controller.executorAction);

  return router;
}
