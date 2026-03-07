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

  async findAllEnabled() {
    return Schedule.findAll({
      where: { enabled: true },
      include: [
        {
          model: Device,
          as: 'device',
          required: true,
        },
      ],
      order: [['created_at', 'DESC']],
    });
  }

  async findEnabledById(id) {
    return Schedule.findOne({
      where: { id, enabled: true },
      include: [
        {
          model: Device,
          as: 'device',
          required: true,
        },
      ],
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

  async updateMetadataById(id, metadataPatch) {
    const schedule = await Schedule.findByPk(id);
    if (!schedule) return null;

    const mergedMetadata = {
      ...(schedule.metadata || {}),
      ...(metadataPatch || {}),
    };
    await schedule.update({ metadata: mergedMetadata });
    return schedule;
  }
}

export default SchedulesRepository;
