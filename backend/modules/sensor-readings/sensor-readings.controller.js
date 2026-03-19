import ScopedCrudController from '../common/scoped-crud.controller.js';

class SensorReadingsController extends ScopedCrudController {
  list = async (req, res) => {
    try {
      const items = await this.service.listByUser(req.contextUserId, req.query || {});
      return res.json({ count: items.length, data: items });
    } catch (err) {
      return res.status(err.status || 400).json({ error: err.message });
    }
  };
}

export default SensorReadingsController;
