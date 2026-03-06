import { Schedule, Device } from '../../entity/index.js';

class SchedulesRepository {
  async create(deviceId, payload) {
    return Schedule.create({
      ...payload,
      deviceId,
    });
  }

  async findAllByUser(userId) {
    return Schedule.findAll({
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
    return Schedule.findOne({
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
    const schedule = await this.findByIdForUser(id, userId);
    if (!schedule) return null;

    await schedule.update(payload);
    return schedule;
  }

  async deleteByIdForUser(id, userId) {
    const schedule = await this.findByIdForUser(id, userId);
    if (!schedule) return false;

    await schedule.destroy();
    return true;
  }
}

export default SchedulesRepository;
