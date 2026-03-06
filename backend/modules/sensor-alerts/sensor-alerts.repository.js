import { SensorAlert, SensorAlertRule, Sensor, Device } from '../../entity/index.js';

class SensorAlertsRepository {
  async create(sensorAlertRuleId, payload) {
    return SensorAlert.create({
      ...payload,
      sensorAlertRuleId,
    });
  }

  async findAllByUser(userId) {
    return SensorAlert.findAll({
      include: [
        {
          model: SensorAlertRule,
          as: 'alertRule',
          required: true,
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
        },
      ],
      order: [['triggered_at', 'DESC']],
    });
  }

  async findByIdForUser(id, userId) {
    return SensorAlert.findOne({
      where: { id },
      include: [
        {
          model: SensorAlertRule,
          as: 'alertRule',
          required: true,
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
        },
      ],
    });
  }

  async updateByIdForUser(id, userId, payload) {
    const alert = await this.findByIdForUser(id, userId);
    if (!alert) return null;

    await alert.update(payload);
    return alert;
  }

  async deleteByIdForUser(id, userId) {
    const alert = await this.findByIdForUser(id, userId);
    if (!alert) return false;

    await alert.destroy();
    return true;
  }
}

export default SensorAlertsRepository;
