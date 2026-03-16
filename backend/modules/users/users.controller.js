class UsersController {
  constructor(usersService) {
    this.usersService = usersService;
  }

  getAuthenticatedUserId(req) {
    return req.user?.id || null;
  }

  ensureSelfAccess(req) {
    const authUserId = this.getAuthenticatedUserId(req);
    if (!authUserId) {
      const error = new Error('Unauthorized');
      error.status = 401;
      throw error;
    }
    if (req.params?.id && req.params.id !== authUserId) {
      const error = new Error('Forbidden');
      error.status = 403;
      throw error;
    }
    return authUserId;
  }

  create = async (req, res) => {
    return res.status(405).json({
      error: 'Use POST /auth/register for signup',
    });
  };

  list = async (req, res) => {
    try {
      const authUserId = this.ensureSelfAccess(req);
      const user = await this.usersService.getById(authUserId);
      return res.json({ count: 1, data: [user] });
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };

  getById = async (req, res) => {
    try {
      const authUserId = this.ensureSelfAccess(req);
      const user = await this.usersService.getById(authUserId);
      return res.json(user);
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };

  update = async (req, res) => {
    try {
      const authUserId = this.ensureSelfAccess(req);
      const user = await this.usersService.update(authUserId, req.body);
      return res.json(user);
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };

  delete = async (req, res) => {
    try {
      const authUserId = this.ensureSelfAccess(req);
      const result = await this.usersService.delete(authUserId);
      return res.json(result);
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };
}

export default UsersController;
