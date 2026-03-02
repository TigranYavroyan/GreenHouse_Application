class SessionController {
  constructor(sessionService) {
    this.sessionService = sessionService;
  }

  list = (req, res) => {
    res.json({ sessions: this.sessionService.listSessions() });
  };

  log = (req, res) => {
    try {
      const data = this.sessionService.getSessionLog(req.params.sessionId);
      res.json(data);
    } catch (err) {
      res.status(404).json({ error: err.message });
    }
  };

  delete = (req, res) => {
    try {
      const data = this.sessionService.deleteSession(req.params.sessionId);
      res.json(data);
    } catch (err) {
      res.status(404).json({ error: err.message });
    }
  };
}

export default SessionController;