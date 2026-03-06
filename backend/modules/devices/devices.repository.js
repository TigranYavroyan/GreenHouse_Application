import { Device } from '../../entity/index.js';

class DevicesRepository {
  async create(userId, payload) {
    return Device.create({
      ...payload,
      userId,
    });
  }

  async findAllByUser(userId) {
    return Device.findAll({
      where: { userId },
      order: [['created_at', 'DESC']],
    });
  }

  async findByIdForUser(id, userId) {
    return Device.findOne({
      where: { id, userId },
    });
  }

  async updateByIdForUser(id, userId, payload) {
    const device = await this.findByIdForUser(id, userId);
    if (!device) return null;

    await device.update(payload);
    return device;
  }

  async deleteByIdForUser(id, userId) {
    const device = await this.findByIdForUser(id, userId);
    if (!device) return false;

    await device.destroy();
    return true;
  }
}

export default DevicesRepository;
