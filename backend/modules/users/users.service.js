import { serviceError } from '../common/service-error.js';

class UsersService {
  constructor(usersRepository) {
    this.usersRepository = usersRepository;
  }

  async create(payload) {
    if (!payload?.username || !payload?.password) {
      throw serviceError('username and password are required', 400);
    }

    const existing = await this.usersRepository.findByUsername(payload.username);
    if (existing) {
      throw serviceError('User already exists', 409);
    }

    return this.usersRepository.create(payload);
  }

  async list() {
    return this.usersRepository.findAll();
  }

  async getById(id) {
    const user = await this.usersRepository.findById(id);
    if (!user) {
      throw serviceError('User not found', 404);
    }
    return user;
  }

  async update(id, payload) {
    if (payload?.username) {
      const existing = await this.usersRepository.findByUsername(payload.username);
      if (existing && existing.id !== id) {
        throw serviceError('Username is already taken', 409);
      }
    }

    const updated = await this.usersRepository.updateById(id, payload);
    if (!updated) {
      throw serviceError('User not found', 404);
    }

    return updated;
  }

  async delete(id) {
    const deleted = await this.usersRepository.deleteById(id);
    if (!deleted) {
      throw serviceError('User not found', 404);
    }
    return { success: true };
  }
}

export default UsersService;
