import { Router } from 'express';
import SessionService from '../modules/sessions/sessions.service.js';
import SessionController from '../modules/sessions/sessions.controller.js';

export default function createSessionRouter({ sessionManager }) {
  const router = Router();

  const service = new SessionService(sessionManager);
  const controller = new SessionController(service);

  router.get('/', controller.list);
  router.get('/:sessionId/log', controller.log);
  router.delete('/:sessionId', controller.delete);

  return router;
}