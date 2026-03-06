class UsersController {
  constructor(usersService) {
    this.usersService = usersService;
  }

  create = async (req, res) => {
    try {
      const user = await this.usersService.create(req.body);
      return res.status(201).json(user);
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };

  list = async (req, res) => {
    try {
      const users = await this.usersService.list();
      return res.json({ count: users.length, data: users });
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };

  getById = async (req, res) => {
    try {
      const user = await this.usersService.getById(req.params.id);
      return res.json(user);
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };

  update = async (req, res) => {
    try {
      const user = await this.usersService.update(req.params.id, req.body);
      return res.json(user);
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };

  delete = async (req, res) => {
    try {
      const result = await this.usersService.delete(req.params.id);
      return res.json(result);
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };
}

export default UsersController;
