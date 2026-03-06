import { Actuator, Device } from '../../entity/index.js';

class ActuatorsRepository {
  async create(deviceId, payload) {
    return Actuator.create({
      ...payload,
      deviceId,
    });
  }

  async findAllByUser(userId) {
    return Actuator.findAll({
      include: [
        {
          model: Device,
          as: 'device',
          where: { userId },
          required: true,
        },
      ],
      order: [['created_at', 'DESC']],
    });
  }

  async findByIdForUser(id, userId) {
    return Actuator.findOne({
      where: { id },
      include: [
        {
          model: Device,
          as: 'device',
          where: { userId },
          required: true,
        },
      ],
    });
  }

  async updateByIdForUser(id, userId, payload) {
    const actuator = await this.findByIdForUser(id, userId);
    if (!actuator) return null;

    await actuator.update(payload);
    return actuator;
  }

  async deleteByIdForUser(id, userId) {
    const actuator = await this.findByIdForUser(id, userId);
    if (!actuator) return false;

    await actuator.destroy();
    return true;
  }
}

export default ActuatorsRepository;
