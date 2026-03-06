import { serviceError } from '../common/service-error.js';

class ActuatorsService {
  constructor({ actuatorsRepository, devicesRepository }) {
    this.actuatorsRepository = actuatorsRepository;
    this.devicesRepository = devicesRepository;
  }

  async create(userId, payload) {
    if (!payload?.deviceId) {
      throw serviceError('deviceId is required', 400);
    }
    if (!payload?.name || !payload?.type) {
      throw serviceError('Actuator name and type are required', 400);
    }

    const device = await this.devicesRepository.findByIdForUser(payload.deviceId, userId);
    if (!device) {
      throw serviceError('Device not found for current user', 404);
    }

    return this.actuatorsRepository.create(payload.deviceId, payload);
  }

  async listByUser(userId) {
    return this.actuatorsRepository.findAllByUser(userId);
  }

  async getByIdForUser(id, userId) {
    const actuator = await this.actuatorsRepository.findByIdForUser(id, userId);
    if (!actuator) {
      throw serviceError('Actuator not found', 404);
    }
    return actuator;
  }

  async updateForUser(id, userId, payload) {
    if (payload?.deviceId) {
      const device = await this.devicesRepository.findByIdForUser(payload.deviceId, userId);
      if (!device) {
        throw serviceError('Target device not found for current user', 404);
      }
    }

    const updated = await this.actuatorsRepository.updateByIdForUser(id, userId, payload);
    if (!updated) {
      throw serviceError('Actuator not found', 404);
    }
    return updated;
  }

  async deleteForUser(id, userId) {
    const deleted = await this.actuatorsRepository.deleteByIdForUser(id, userId);
    if (!deleted) {
      throw serviceError('Actuator not found', 404);
    }
    return { success: true };
  }
}

export default ActuatorsService;
