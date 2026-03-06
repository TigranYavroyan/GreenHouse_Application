import { Sensor, Device } from '../../entity/index.js';

const OWNED_DEVICE_INCLUDE = {
  model: Device,
  as: 'device',
  where: {},
  required: true,
};

class SensorsRepository {
  async create(deviceId, payload) {
    return Sensor.create({
      ...payload,
      deviceId,
    });
  }

  async findAllByUser(userId) {
    return Sensor.findAll({
      include: [
        {
          ...OWNED_DEVICE_INCLUDE,
          where: { userId },
        },
      ],
      order: [['created_at', 'DESC']],
    });
  }

  async findByIdForUser(id, userId) {
    return Sensor.findOne({
      where: { id },
      include: [
        {
          ...OWNED_DEVICE_INCLUDE,
          where: { userId },
        },
      ],
    });
  }

  async updateByIdForUser(id, userId, payload) {
    const sensor = await this.findByIdForUser(id, userId);
    if (!sensor) return null;

    await sensor.update(payload);
    return sensor;
  }

  async deleteByIdForUser(id, userId) {
    const sensor = await this.findByIdForUser(id, userId);
    if (!sensor) return false;

    await sensor.destroy();
    return true;
  }
}

export default SensorsRepository;
