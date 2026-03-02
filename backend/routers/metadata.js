import { Router } from 'express';
import MetadataService from '../modules/metadata/metadata.service.js';
import MetadataController from '../modules/metadata/metadata.controller.js';
import authMiddleware from '../middleware/authMiddleware.js';

export default function createMetadataRouter(deps) {
  const router = Router();

  const service = new MetadataService(deps);
  const controller = new MetadataController(service);

  router.get('/metadata/health/', authMiddleware, controller.health);
  router.get('/metadata/stats/', controller.stats);
  router.get('/metadata/queues/', controller.queues);
  router.get('/', controller.root);

  return router;
}