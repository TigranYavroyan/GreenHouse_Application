import { serviceError } from '../common/service-error.js';

class UserLogsService {
  constructor({ userLogsRepository }) {
    this.userLogsRepository = userLogsRepository;
  }

  async create(userId, payload) {
    const title = String(payload?.title || '').trim();
    if (!title) {
      throw serviceError('title is required', 400);
    }

    return this.userLogsRepository.create(userId, {
      category: String(payload?.category || 'control').trim() || 'control',
      title,
      payload: payload?.payload && typeof payload.payload === 'object' ? payload.payload : {},
      metadata: payload?.metadata && typeof payload.metadata === 'object' ? payload.metadata : {},
    });
  }

  async listByUser(userId) {
    return this.userLogsRepository.findAllByUser(userId);
  }

  async getByIdForUser(id, userId) {
    const entry = await this.userLogsRepository.findByIdForUser(id, userId);
    if (!entry) {
      throw serviceError('User log not found', 404);
    }
    return entry;
  }

  async updateForUser(id, userId, payload) {
    const updates = {};
    if (payload?.title !== undefined) {
      updates.title = String(payload.title || '').trim();
      if (!updates.title) {
        throw serviceError('title cannot be empty', 400);
      }
    }
    if (payload?.category !== undefined) {
      updates.category = String(payload.category || '').trim() || 'control';
    }
    if (payload?.payload !== undefined) {
      updates.payload = payload.payload && typeof payload.payload === 'object' ? payload.payload : {};
    }
    if (payload?.metadata !== undefined) {
      updates.metadata = payload.metadata && typeof payload.metadata === 'object' ? payload.metadata : {};
    }

    const updated = await this.userLogsRepository.updateByIdForUser(id, userId, updates);
    if (!updated) {
      throw serviceError('User log not found', 404);
    }
    return updated;
  }

  async deleteForUser(id, userId) {
    const deleted = await this.userLogsRepository.deleteByIdForUser(id, userId);
    if (!deleted) {
      throw serviceError('User log not found', 404);
    }
    return { success: true };
  }
}

export default UserLogsService;
