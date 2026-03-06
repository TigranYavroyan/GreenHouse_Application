import { User } from '../../entity/index.js';

class UsersRepository {
  async create(payload) {
    return User.create(payload);
  }

  async findAll() {
    return User.findAll({
      order: [['created_at', 'DESC']],
    });
  }

  async findById(id) {
    return User.findByPk(id);
  }

  async findByUsername(username) {
    return User.findOne({ where: { username } });
  }

  async updateById(id, payload) {
    const user = await this.findById(id);
    if (!user) return null;

    await user.update(payload);
    return user;
  }

  async deleteById(id) {
    const user = await this.findById(id);
    if (!user) return false;

    await user.destroy();
    return true;
  }
}

export default UsersRepository;
