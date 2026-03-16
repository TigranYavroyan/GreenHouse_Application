class FogController {
  constructor(fogService) {
    this.service = fogService;
  }

  storeAggregated = async (req, res) => {
    try {
      const key = await this.service.storeAggregated(req.body);
      res.json({ success: true, key });
    } catch (error) {
      res.status(error.status || 500).json({ error: error.message || 'Failed to store aggregated data' });
    }
  };

  getAggregated = async (req, res) => {
    try {
      const data = await this.service.getAggregated(req.query);
      res.json({ count: data.length, data });
    } catch (error) {
      res.status(error.status || 500).json({ error: error.message || 'Failed to fetch aggregated data' });
    }
  };

  getDevices = async (req, res) => {
    try {
      const devices = await this.service.getDevices();
      res.json({ count: devices.length, devices });
    } catch (error) {
      res.status(error.status || 500).json({ error: error.message || 'Failed to fetch devices' });
    }
  };

  storeAnomaly = async (req, res) => {
    try {
      const key = await this.service.storeAnomaly(req.body);
      res.json({ success: true, key });
    } catch (error) {
      res.status(error.status || 500).json({ error: error.message || 'Failed to store anomaly' });
    }
  };

  getAnomalies = async (req, res) => {
    try {
      const limit = parseInt(req.query.limit, 10) || 10;
      const anomalies = await this.service.getRecentAnomalies(limit);
      res.json({ count: anomalies.length, anomalies });
    } catch (error) {
      res.status(error.status || 500).json({ error: error.message || 'Failed to fetch anomalies' });
    }
  };
}

export default FogController;