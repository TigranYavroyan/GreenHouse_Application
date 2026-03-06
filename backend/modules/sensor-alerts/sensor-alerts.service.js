import { serviceError } from '../common/service-error.js';

class SensorAlertsService {
  constructor({ sensorAlertsRepository, sensorAlertRulesRepository }) {
    this.sensorAlertsRepository = sensorAlertsRepository;
    this.sensorAlertRulesRepository = sensorAlertRulesRepository;
  }

  async create(userId, payload) {
    if (!payload?.sensorAlertRuleId) {
      throw serviceError('sensorAlertRuleId is required', 400);
    }
    if (payload?.value === undefined || payload?.value === null || !payload?.message) {
      throw serviceError('value and message are required', 400);
    }

    const rule = await this.sensorAlertRulesRepository.findByIdForUser(payload.sensorAlertRuleId, userId);
    if (!rule) {
      throw serviceError('Sensor alert rule not found for current user', 404);
    }

    return this.sensorAlertsRepository.create(payload.sensorAlertRuleId, payload);
  }

  async listByUser(userId) {
    return this.sensorAlertsRepository.findAllByUser(userId);
  }

  async getByIdForUser(id, userId) {
    const alert = await this.sensorAlertsRepository.findByIdForUser(id, userId);
    if (!alert) {
      throw serviceError('Sensor alert not found', 404);
    }
    return alert;
  }

  async updateForUser(id, userId, payload) {
    if (payload?.sensorAlertRuleId) {
      const rule = await this.sensorAlertRulesRepository.findByIdForUser(payload.sensorAlertRuleId, userId);
      if (!rule) {
        throw serviceError('Target alert rule not found for current user', 404);
      }
    }

    const updated = await this.sensorAlertsRepository.updateByIdForUser(id, userId, payload);
    if (!updated) {
      throw serviceError('Sensor alert not found', 404);
    }
    return updated;
  }

  async deleteForUser(id, userId) {
    const deleted = await this.sensorAlertsRepository.deleteByIdForUser(id, userId);
    if (!deleted) {
      throw serviceError('Sensor alert not found', 404);
    }
    return { success: true };
  }
}

export default SensorAlertsService;
