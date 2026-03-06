import { serviceError } from '../common/service-error.js';

class SensorAlertRulesService {
  constructor({ sensorAlertRulesRepository, sensorsRepository }) {
    this.sensorAlertRulesRepository = sensorAlertRulesRepository;
    this.sensorsRepository = sensorsRepository;
  }

  async create(userId, payload) {
    if (!payload?.sensorId) {
      throw serviceError('sensorId is required', 400);
    }
    if (!payload?.name) {
      throw serviceError('Rule name is required', 400);
    }

    const sensor = await this.sensorsRepository.findByIdForUser(payload.sensorId, userId);
    if (!sensor) {
      throw serviceError('Sensor not found for current user', 404);
    }

    return this.sensorAlertRulesRepository.create(payload.sensorId, payload);
  }

  async listByUser(userId) {
    return this.sensorAlertRulesRepository.findAllByUser(userId);
  }

  async getByIdForUser(id, userId) {
    const rule = await this.sensorAlertRulesRepository.findByIdForUser(id, userId);
    if (!rule) {
      throw serviceError('Sensor alert rule not found', 404);
    }
    return rule;
  }

  async updateForUser(id, userId, payload) {
    if (payload?.sensorId) {
      const sensor = await this.sensorsRepository.findByIdForUser(payload.sensorId, userId);
      if (!sensor) {
        throw serviceError('Target sensor not found for current user', 404);
      }
    }

    const updated = await this.sensorAlertRulesRepository.updateByIdForUser(id, userId, payload);
    if (!updated) {
      throw serviceError('Sensor alert rule not found', 404);
    }
    return updated;
  }

  async deleteForUser(id, userId) {
    const deleted = await this.sensorAlertRulesRepository.deleteByIdForUser(id, userId);
    if (!deleted) {
      throw serviceError('Sensor alert rule not found', 404);
    }
    return { success: true };
  }
}

export default SensorAlertRulesService;
