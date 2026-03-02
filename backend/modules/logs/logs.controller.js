class LogsController {
  constructor(logsService) {
    this.logsService = logsService;
  }

  list = (req, res) => {
    try {
      res.json({ logs: this.logsService.listLogs() });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  };

  system = (req, res) => {
    try {
      res.json(this.logsService.getSystemLog());
    } catch (err) {
      res.status(404).json({ error: err.message });
    }
  };
}

export default LogsController;