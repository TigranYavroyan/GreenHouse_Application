class MetadataController {
  constructor(metadataService) {
    this.metadataService = metadataService;
  }

  health = (req, res) => {
    try {
      const data = this.metadataService.getHealth();
      res.json(data);
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  };

  stats = (req, res) => {
    res.json(this.metadataService.getStats());
  };

  queues = async (req, res) => {
    try {
      const data = await this.metadataService.getQueues();
      res.json(data);
    } catch (err) {
      res.status(503).json({ error: err.message });
    }
  };

  root = (req, res) => {
    res.json(this.metadataService.getRootInfo());
  };
}

export default MetadataController;