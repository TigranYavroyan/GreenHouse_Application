import { serviceError } from '../common/service-error.js';
import cron from 'node-cron';

class SchedulesService {
  constructor({ schedulesRepository, devicesRepository, schedulesRuntime = null }) {
    this.schedulesRepository = schedulesRepository;
    this.devicesRepository = devicesRepository;
    this.schedulesRuntime = schedulesRuntime;
  }

  validateCronExpression(cronExpression) {
    const normalized = String(cronExpression || '').trim();
    if (!normalized) {
      throw serviceError('cronExpression is required', 400);
    }
    if (!cron.validate(normalized)) {
      throw serviceError('cronExpression is invalid', 400);
    }
  }

  async create(userId, payload) {
    if (!payload?.deviceId) {
      throw serviceError('deviceId is required', 400);
    }
    if (!payload?.name || !payload?.cronExpression || !payload?.action) {
      throw serviceError('name, cronExpression and action are required', 400);
    }
    this.validateCronExpression(payload.cronExpression);

    const device = await this.devicesRepository.findByIdForUser(payload.deviceId, userId);
    if (!device) {
      throw serviceError('Device not found for current user', 404);
    }

    const created = await this.schedulesRepository.create(payload.deviceId, payload);
    if (this.schedulesRuntime) {
      await this.schedulesRuntime.upsert(created);
    }
    return created;
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
    if (payload?.cronExpression !== undefined) {
      this.validateCronExpression(payload.cronExpression);
    }
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
    if (this.schedulesRuntime) {
      await this.schedulesRuntime.upsert(updated);
    }
    return updated;
  }

  async deleteForUser(id, userId) {
    const deleted = await this.schedulesRepository.deleteByIdForUser(id, userId);
    if (!deleted) {
      throw serviceError('Schedule not found', 404);
    }
    if (this.schedulesRuntime) {
      await this.schedulesRuntime.remove(id);
    }
    return { success: true };
  }
}

export default SchedulesService;
