import { Router } from 'express';
import SensorAlertRulesController from '../modules/sensor-alert-rules/sensor-alert-rules.controller.js';

export default function createSensorAlertRulesRouter({ sensorAlertRulesService, userContextMiddleware }) {
  const router = Router();
  const controller = new SensorAlertRulesController(sensorAlertRulesService);

  router.use(userContextMiddleware);
  router.post('/', controller.create);
  router.get('/', controller.list);
  router.get('/:id', controller.getById);
  router.patch('/:id', controller.update);
  router.delete('/:id', controller.delete);

  return router;
}
