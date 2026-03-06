import { SensorReading, Sensor, Device } from '../../entity/index.js';

class SensorReadingsRepository {
  async create(sensorId, payload) {
    return SensorReading.create({
      ...payload,
      sensorId,
    });
  }

  async findAllByUser(userId) {
    return SensorReading.findAll({
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
      order: [['timestamp', 'DESC']],
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

    await reading.update(payload);
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
