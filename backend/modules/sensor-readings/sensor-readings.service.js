import { serviceError } from '../common/service-error.js';
import config from '../../config/index.js';

class SensorReadingsService {
  constructor({ sensorReadingsRepository, sensorsRepository }) {
    this.sensorReadingsRepository = sensorReadingsRepository;
    this.sensorsRepository = sensorsRepository;
  }

  _parseNumericValue(rawValue) {
    const parsed = Number(rawValue);
    if (!Number.isFinite(parsed)) {
      throw serviceError('value must be a finite number', 400);
    }
    return parsed;
  }

  _parseTimestamp(rawTimestamp) {
    if (rawTimestamp === undefined || rawTimestamp === null || rawTimestamp === '') {
      return undefined;
    }
    const parsedTimestamp = new Date(String(rawTimestamp).trim());
    if (Number.isNaN(parsedTimestamp.getTime())) {
      throw serviceError('timestamp must be a valid ISO datetime string', 400);
    }
    return parsedTimestamp.toISOString();
  }

  _extractAdditionalMetadata(payload = {}) {
    const ignoredFields = new Set(['id', 'sensorId', 'value', 'timestamp', 'metadata', 'createdAt', 'updatedAt']);
    return Object.entries(payload || {}).reduce((acc, [key, value]) => {
      if (ignoredFields.has(key)) {
        return acc;
      }
      acc[key] = value;
      return acc;
    }, {});
  }

  _normalizeWritePayload(payload = {}, { requireSensorId = false, requireValue = false } = {}) {
    const normalizedPayload = payload || {};
    const normalized = {};

    const normalizedSensorId = normalizedPayload.sensorId !== undefined
      ? String(normalizedPayload.sensorId || '').trim()
      : '';
    if (requireSensorId && !normalizedSensorId) {
      throw serviceError('sensorId is required', 400);
    }
    if (normalizedSensorId) {
      normalized.sensorId = normalizedSensorId;
    }

    if (requireValue && (normalizedPayload.value === undefined || normalizedPayload.value === null || normalizedPayload.value === '')) {
      throw serviceError('value is required', 400);
    }
    if (normalizedPayload.value !== undefined && normalizedPayload.value !== null && normalizedPayload.value !== '') {
      normalized.value = this._parseNumericValue(normalizedPayload.value);
    }

    if (normalizedPayload.timestamp !== undefined) {
      normalized.timestamp = this._parseTimestamp(normalizedPayload.timestamp);
    }

    const sourceMetadata = normalizedPayload.metadata && typeof normalizedPayload.metadata === 'object'
      ? normalizedPayload.metadata
      : {};
    if (normalizedPayload.metadata !== undefined && (typeof normalizedPayload.metadata !== 'object' || Array.isArray(normalizedPayload.metadata))) {
      throw serviceError('metadata must be an object', 400);
    }

    const additionalMetadata = this._extractAdditionalMetadata(normalizedPayload);
    normalized.metadata = {
      ...sourceMetadata,
      ...(Object.keys(additionalMetadata).length > 0 ? { additionalPayload: additionalMetadata } : {}),
    };

    return normalized;
  }

  async create(userId, payload) {
    const normalizedPayload = this._normalizeWritePayload(payload, {
      requireSensorId: true,
      requireValue: true,
    });

    const sensor = await this.sensorsRepository.findByIdForUser(normalizedPayload.sensorId, userId);
    if (!sensor) {
      throw serviceError('Sensor not found for current user', 404);
    }

    return this.sensorReadingsRepository.create(normalizedPayload.sensorId, normalizedPayload);
  }

  _normalizeListFilters(rawFilters = {}) {
    const filters = rawFilters || {};
    const normalized = {
      deviceId: '',
      deviceName: '',
      sensorId: '',
      from: null,
      to: null,
      limit: null,
      order: 'DESC',
    };

    if (filters.deviceId !== undefined) {
      normalized.deviceId = String(filters.deviceId || '').trim();
    }
    if (filters.deviceName !== undefined) {
      normalized.deviceName = String(filters.deviceName || '').trim();
    }
    if (filters.sensorId !== undefined) {
      normalized.sensorId = String(filters.sensorId || '').trim();
    }

    if (filters.from !== undefined && String(filters.from).trim()) {
      const fromDate = new Date(String(filters.from).trim());
      if (Number.isNaN(fromDate.getTime())) {
        throw serviceError('Invalid "from" query parameter', 400);
      }
      normalized.from = fromDate;
    }

    if (filters.to !== undefined && String(filters.to).trim()) {
      const toDate = new Date(String(filters.to).trim());
      if (Number.isNaN(toDate.getTime())) {
        throw serviceError('Invalid "to" query parameter', 400);
      }
      normalized.to = toDate;
    }

    if (normalized.from && normalized.to && normalized.from > normalized.to) {
      throw serviceError('"from" must be less than or equal to "to"', 400);
    }

    if (filters.limit !== undefined && String(filters.limit).trim()) {
      const parsedLimit = Number.parseInt(String(filters.limit), 10);
      if (!Number.isInteger(parsedLimit) || parsedLimit <= 0) {
        throw serviceError('Invalid "limit" query parameter', 400);
      }
      normalized.limit = Math.min(parsedLimit, config.sensorReadings.maxListLimit);
    }

    if (filters.order !== undefined && String(filters.order).trim()) {
      const normalizedOrder = String(filters.order).trim().toUpperCase();
      if (normalizedOrder !== 'ASC' && normalizedOrder !== 'DESC') {
        throw serviceError('Invalid "order" query parameter; use ASC or DESC', 400);
      }
      normalized.order = normalizedOrder;
    }

    return normalized;
  }

  async listByUser(userId, filters = {}) {
    const normalizedFilters = this._normalizeListFilters(filters);
    return this.sensorReadingsRepository.findAllByUser(userId, normalizedFilters);
  }

  async getByIdForUser(id, userId) {
    const reading = await this.sensorReadingsRepository.findByIdForUser(id, userId);
    if (!reading) {
      throw serviceError('Sensor reading not found', 404);
    }
    return reading;
  }

  async updateForUser(id, userId, payload) {
    const normalizedPayload = this._normalizeWritePayload(payload || {}, {
      requireSensorId: false,
      requireValue: false,
    });
    if (Object.keys(normalizedPayload).length === 0) {
      throw serviceError('No valid fields provided for update', 400);
    }

    if (normalizedPayload?.sensorId) {
      const sensor = await this.sensorsRepository.findByIdForUser(normalizedPayload.sensorId, userId);
      if (!sensor) {
        throw serviceError('Target sensor not found for current user', 404);
      }
    }

    const updated = await this.sensorReadingsRepository.updateByIdForUser(id, userId, normalizedPayload);
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
