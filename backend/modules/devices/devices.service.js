import { serviceError } from '../common/service-error.js';

class DevicesService {
  constructor({ devicesRepository, usersRepository }) {
    this.devicesRepository = devicesRepository;
    this.usersRepository = usersRepository;
  }

  async create(userId, payload) {
    if (!payload?.name) {
      throw serviceError('Device name is required', 400);
    }

    const user = await this.usersRepository.findById(userId);
    if (!user) {
      throw serviceError('User not found', 404);
    }

    return this.devicesRepository.create(userId, payload);
  }

  async listByUser(userId) {
    return this.devicesRepository.findAllByUser(userId);
  }

  async getByIdForUser(id, userId) {
    const device = await this.devicesRepository.findByIdForUser(id, userId);
    if (!device) {
      throw serviceError('Device not found', 404);
    }
    return device;
  }

  async updateForUser(id, userId, payload) {
    const updated = await this.devicesRepository.updateByIdForUser(id, userId, payload);
    if (!updated) {
      throw serviceError('Device not found', 404);
    }
    return updated;
  }

  async deleteForUser(id, userId) {
    const deleted = await this.devicesRepository.deleteByIdForUser(id, userId);
    if (!deleted) {
      throw serviceError('Device not found', 404);
    }
    return { success: true };
  }
}

export default DevicesService;
