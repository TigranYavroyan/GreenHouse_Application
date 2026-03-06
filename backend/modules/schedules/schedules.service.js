import { serviceError } from '../common/service-error.js';

class SchedulesService {
  constructor({ schedulesRepository, devicesRepository }) {
    this.schedulesRepository = schedulesRepository;
    this.devicesRepository = devicesRepository;
  }

  async create(userId, payload) {
    if (!payload?.deviceId) {
      throw serviceError('deviceId is required', 400);
    }
    if (!payload?.name || !payload?.cronExpression || !payload?.action) {
      throw serviceError('name, cronExpression and action are required', 400);
    }

    const device = await this.devicesRepository.findByIdForUser(payload.deviceId, userId);
    if (!device) {
      throw serviceError('Device not found for current user', 404);
    }

    return this.schedulesRepository.create(payload.deviceId, payload);
  }

  async listByUser(userId) {
    return this.schedulesRepository.findAllByUser(userId);
  }

  async getByIdForUser(id, userId) {
    const schedule = await this.schedulesRepository.findByIdForUser(id, userId);
    if (!schedule) {
      throw serviceError('Schedule not found', 404);
    }
    return schedule;
  }

  async updateForUser(id, userId, payload) {
    if (payload?.deviceId) {
      const device = await this.devicesRepository.findByIdForUser(payload.deviceId, userId);
      if (!device) {
        throw serviceError('Target device not found for current user', 404);
      }
    }

    const updated = await this.schedulesRepository.updateByIdForUser(id, userId, payload);
    if (!updated) {
      throw serviceError('Schedule not found', 404);
    }
    return updated;
  }

  async deleteForUser(id, userId) {
    const deleted = await this.schedulesRepository.deleteByIdForUser(id, userId);
    if (!deleted) {
      throw serviceError('Schedule not found', 404);
    }
    return { success: true };
  }
}

export default SchedulesService;
