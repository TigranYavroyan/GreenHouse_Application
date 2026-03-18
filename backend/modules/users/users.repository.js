import { User } from '../../entity/index.js';

function sanitizeUser(user) {
  if (!user) return null;
  const plain = typeof user.toJSON === 'function' ? user.toJSON() : { ...user };
  delete plain.password;
  return plain;
}

class UsersRepository {
  async create(payload) {
    const user = await User.create(payload);
    return sanitizeUser(user);
  }

  async findAll() {
    const users = await User.findAll({
      order: [['created_at', 'DESC']],
    });
    return users.map((user) => sanitizeUser(user));
  }

  async findById(id) {
    const user = await User.findByPk(id);
    return sanitizeUser(user);
  }

  async findByUsername(username) {
    const user = await User.findOne({ where: { username } });
    return sanitizeUser(user);
  }

  async findByEmail(email) {
    const user = await User.findOne({ where: { email } });
    return sanitizeUser(user);
  }

  async findAuthByUsername(username) {
    return User.findOne({ where: { username } });
  }

  async findAuthById(id) {
    return User.findByPk(id);
  }

  async markVerifiedById(id) {
    const user = await User.findByPk(id);
    if (!user) return null;
    if (!user.verified) {
      await user.update({ verified: true });
    }
    return sanitizeUser(user);
  }

  async updateById(id, payload) {
    const user = await User.findByPk(id);
    if (!user) return null;

    await user.update(payload);
    return sanitizeUser(user);
  }

  async deleteById(id) {
    const user = await User.findByPk(id);
    if (!user) return false;

    await user.destroy();
    return true;
  }
}

export default UsersRepository;
