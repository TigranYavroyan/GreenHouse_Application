import { UserLog } from '../../entity/index.js';

class UserLogsRepository {
  async create(userId, payload) {
    return UserLog.create({
      ...payload,
      userId,
    });
  }

  async findAllByUser(userId) {
    return UserLog.findAll({
      where: { userId },
      order: [['created_at', 'DESC']],
    });
  }

  async findByIdForUser(id, userId) {
    return UserLog.findOne({
      where: { id, userId },
    });
  }

  async updateByIdForUser(id, userId, payload) {
    const entry = await this.findByIdForUser(id, userId);
    if (!entry) return null;

    await entry.update(payload);
    return entry;
  }

  async deleteByIdForUser(id, userId) {
    const entry = await this.findByIdForUser(id, userId);
    if (!entry) return false;

    await entry.destroy();
    return true;
  }
}

export default UserLogsRepository;
