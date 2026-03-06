import { SensorAlertRule, Sensor, Device } from '../../entity/index.js';

class SensorAlertRulesRepository {
  async create(sensorId, payload) {
    return SensorAlertRule.create({
      ...payload,
      sensorId,
    });
  }

  async findAllByUser(userId) {
    return SensorAlertRule.findAll({
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
      order: [['created_at', 'DESC']],
    });
  }

  async findByIdForUser(id, userId) {
    return SensorAlertRule.findOne({
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
    const rule = await this.findByIdForUser(id, userId);
    if (!rule) return null;

    await rule.update(payload);
    return rule;
  }

  async deleteByIdForUser(id, userId) {
    const rule = await this.findByIdForUser(id, userId);
    if (!rule) return false;

    await rule.destroy();
    return true;
  }
}

export default SensorAlertRulesRepository;
