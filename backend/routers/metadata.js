import { Router } from 'express';
import MetadataService from '../modules/metadata/metadata.service.js';
import MetadataController from '../modules/metadata/metadata.controller.js';

export default function createMetadataRouter(deps) {
  const router = Router();

  const service = new MetadataService(deps);
  const controller = new MetadataController(service);

  router.get('/health/', controller.health);
  router.get('/stats/', controller.stats);
  router.get('/queues/', controller.queues);
  router.get('/', controller.root);

  return router;
}