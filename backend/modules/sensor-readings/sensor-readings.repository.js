import { Op } from 'sequelize';
import { SensorReading, Sensor, Device } from '../../entity/index.js';

class SensorReadingsRepository {
  async create(sensorId, payload) {
    const metadata = payload && typeof payload.metadata === 'object' && payload.metadata !== null
      ? payload.metadata
      : {};

    return SensorReading.create({
      sensorId,
      value: payload.value,
      ...(payload.timestamp ? { timestamp: payload.timestamp } : {}),
      metadata,
    });
  }

  async findAllByUser(userId, filters = {}) {
    const {
      deviceId = null,
      deviceName = null,
      sensorId = null,
      from = null,
      to = null,
      limit = null,
      order = 'DESC',
    } = filters || {};

    const readingWhere = {};
    if (sensorId) {
      readingWhere.sensorId = sensorId;
    }

    if (from || to) {
      readingWhere.timestamp = {};
      if (from) {
        readingWhere.timestamp[Op.gte] = from;
      }
      if (to) {
        readingWhere.timestamp[Op.lte] = to;
      }
    }

    const sensorInclude = {
      model: Sensor,
      as: 'sensor',
      required: true,
      include: [
        {
          model: Device,
          as: 'device',
          where: { userId },
          required: true,
        },
      ],
    };

    if (deviceId) {
      sensorInclude.include[0].where.id = deviceId;
    }
    if (deviceName) {
      sensorInclude.include[0].where.name = deviceName;
    }

    const queryOptions = {
      include: [sensorInclude],
      order: [['timestamp', String(order || 'DESC').toUpperCase() === 'ASC' ? 'ASC' : 'DESC']],
    };

    if (Object.keys(readingWhere).length > 0) {
      queryOptions.where = readingWhere;
    }
    if (Number.isInteger(limit) && limit > 0) {
      queryOptions.limit = limit;
    }

    return SensorReading.findAll({
      ...queryOptions,
    });
  }

  async findByIdForUser(id, userId) {
    return SensorReading.findOne({
      where: { id },
      include: [
        {
          model: Sensor,
          as: 'sensor',
          required: true,
          include: [
            {
              model: Device,
              as: 'device',
              where: { userId },
              required: true,
            },
          ],
        },
      ],
    });
  }

  async updateByIdForUser(id, userId, payload) {
    const reading = await this.findByIdForUser(id, userId);
    if (!reading) return null;

    const updates = {};
    if (payload.sensorId !== undefined) {
      updates.sensorId = payload.sensorId;
    }
    if (payload.value !== undefined) {
      updates.value = payload.value;
    }
    if (payload.timestamp !== undefined) {
      updates.timestamp = payload.timestamp;
    }
    if (payload.metadata !== undefined) {
      updates.metadata = {
        ...(reading.metadata || {}),
        ...(payload.metadata || {}),
      };
    }

    await reading.update(updates);
    return reading;
  }

  async deleteByIdForUser(id, userId) {
    const reading = await this.findByIdForUser(id, userId);
    if (!reading) return false;

    await reading.destroy();
    return true;
  }
}

export default SensorReadingsRepository;
