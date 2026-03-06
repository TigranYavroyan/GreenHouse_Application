import { serviceError } from '../common/service-error.js';

class SensorReadingsService {
  constructor({ sensorReadingsRepository, sensorsRepository }) {
    this.sensorReadingsRepository = sensorReadingsRepository;
    this.sensorsRepository = sensorsRepository;
  }

  async create(userId, payload) {
    if (!payload?.sensorId) {
      throw serviceError('sensorId is required', 400);
    }
    if (payload?.value === undefined || payload?.value === null) {
      throw serviceError('value is required', 400);
    }

    const sensor = await this.sensorsRepository.findByIdForUser(payload.sensorId, userId);
    if (!sensor) {
      throw serviceError('Sensor not found for current user', 404);
    }

    return this.sensorReadingsRepository.create(payload.sensorId, payload);
  }

  async listByUser(userId) {
    return this.sensorReadingsRepository.findAllByUser(userId);
  }

  async getByIdForUser(id, userId) {
    const reading = await this.sensorReadingsRepository.findByIdForUser(id, userId);
    if (!reading) {
      throw serviceError('Sensor reading not found', 404);
    }
    return reading;
  }

  async updateForUser(id, userId, payload) {
    if (payload?.sensorId) {
      const sensor = await this.sensorsRepository.findByIdForUser(payload.sensorId, userId);
      if (!sensor) {
        throw serviceError('Target sensor not found for current user', 404);
      }
    }

    const updated = await this.sensorReadingsRepository.updateByIdForUser(id, userId, payload);
    if (!updated) {
      throw serviceError('Sensor reading not found', 404);
    }
    return updated;
  }

  async deleteForUser(id, userId) {
    const deleted = await this.sensorReadingsRepository.deleteByIdForUser(id, userId);
    if (!deleted) {
      throw serviceError('Sensor reading not found', 404);
    }
    return { success: true };
  }
}

export default SensorReadingsService;
