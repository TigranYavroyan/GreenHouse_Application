import { serviceError } from '../common/service-error.js';

class SensorsService {
  constructor({ sensorsRepository, devicesRepository }) {
    this.sensorsRepository = sensorsRepository;
    this.devicesRepository = devicesRepository;
  }

  async create(userId, payload) {
    if (!payload?.deviceId) {
      throw serviceError('deviceId is required', 400);
    }
    if (!payload?.name || !payload?.type) {
      throw serviceError('Sensor name and type are required', 400);
    }

    const device = await this.devicesRepository.findByIdForUser(payload.deviceId, userId);
    if (!device) {
      throw serviceError('Device not found for current user', 404);
    }

    return this.sensorsRepository.create(payload.deviceId, payload);
  }

  async listByUser(userId) {
    return this.sensorsRepository.findAllByUser(userId);
  }

  async getByIdForUser(id, userId) {
    const sensor = await this.sensorsRepository.findByIdForUser(id, userId);
    if (!sensor) {
      throw serviceError('Sensor not found', 404);
    }
    return sensor;
  }

  async updateForUser(id, userId, payload) {
    if (payload?.deviceId) {
      const device = await this.devicesRepository.findByIdForUser(payload.deviceId, userId);
      if (!device) {
        throw serviceError('Target device not found for current user', 404);
      }
    }

    const updated = await this.sensorsRepository.updateByIdForUser(id, userId, payload);
    if (!updated) {
      throw serviceError('Sensor not found', 404);
    }
    return updated;
  }

  async deleteForUser(id, userId) {
    const deleted = await this.sensorsRepository.deleteByIdForUser(id, userId);
    if (!deleted) {
      throw serviceError('Sensor not found', 404);
    }
    return { success: true };
  }
}

export default SensorsService;
