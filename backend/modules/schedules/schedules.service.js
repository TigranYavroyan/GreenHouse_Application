import { serviceError } from '../common/service-error.js';
import cron from 'node-cron';

class SchedulesService {
  constructor({ schedulesRepository, devicesRepository, schedulesRuntime = null }) {
    this.schedulesRepository = schedulesRepository;
    this.devicesRepository = devicesRepository;
    this.schedulesRuntime = schedulesRuntime;
  }

  _normalizeScheduleMode(rawMode) {
    const normalized = String(rawMode || '').trim().toLowerCase();
    if (!normalized || normalized === 'one-time' || normalized === 'one_time' || normalized === 'onetime') {
      return 'one_time';
    }
    if (normalized === 'recurring') {
      return 'recurring';
    }
    throw serviceError('scheduleMode must be one_time or recurring', 400);
  }

  _normalizeMetadata(payload = {}, existingMetadata = {}) {
    const payloadMetadata = payload?.metadata;
    if (payloadMetadata !== undefined && (typeof payloadMetadata !== 'object' || Array.isArray(payloadMetadata))) {
      throw serviceError('metadata must be an object', 400);
    }

    const metadata = {
      ...(existingMetadata || {}),
      ...(payloadMetadata || {}),
    };

    const modeCandidate = payload?.scheduleMode !== undefined
      ? payload.scheduleMode
      : metadata.scheduleMode;
    metadata.scheduleMode = this._normalizeScheduleMode(modeCandidate);
    return metadata;
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

    const normalizedPayload = {
      ...payload,
      metadata: this._normalizeMetadata(payload, {}),
    };

    const created = await this.schedulesRepository.create(payload.deviceId, normalizedPayload);
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

    const existing = await this.schedulesRepository.findByIdForUser(id, userId);
    if (!existing) {
      throw serviceError('Schedule not found', 404);
    }

    const normalizedPayload = { ...payload };
    if (payload?.metadata !== undefined || payload?.scheduleMode !== undefined) {
      normalizedPayload.metadata = this._normalizeMetadata(payload, existing.metadata || {});
    }

    const updated = await this.schedulesRepository.updateByIdForUser(id, userId, normalizedPayload);
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
