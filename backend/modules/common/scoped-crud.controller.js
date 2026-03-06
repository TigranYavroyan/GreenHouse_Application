class ScopedCrudController {
  constructor(service) {
    this.service = service;
  }

  create = async (req, res) => {
    try {
      const item = await this.service.create(req.contextUserId, req.body);
      return res.status(201).json(item);
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };

  list = async (req, res) => {
    try {
      const items = await this.service.listByUser(req.contextUserId);
      return res.json({ count: items.length, data: items });
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };

  getById = async (req, res) => {
    try {
      const item = await this.service.getByIdForUser(req.params.id, req.contextUserId);
      return res.json(item);
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };

  update = async (req, res) => {
    try {
      const item = await this.service.updateForUser(req.params.id, req.contextUserId, req.body);
      return res.json(item);
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };

  delete = async (req, res) => {
    try {
      const result = await this.service.deleteForUser(req.params.id, req.contextUserId);
      return res.json(result);
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };
}

export default ScopedCrudController;
