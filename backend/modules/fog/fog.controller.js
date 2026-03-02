class FogController {
  constructor(fogService) {
    this.service = fogService;
  }

  storeAggregated = async (req, res) => {
    const key = await this.service.storeAggregated(req.body);
    res.json({ success: true, key });
  };

  getAggregated = async (req, res) => {
    const data = await this.service.getAggregated(req.query);
    res.json({ count: data.length, data });
  };

  getDevices = async (req, res) => {
    const devices = await this.service.getDevices();
    res.json({ count: devices.length, devices });
  };

  storeAnomaly = async (req, res) => {
    const key = await this.service.storeAnomaly(req.body);
    res.json({ success: true, key });
  };

  getAnomalies = async (req, res) => {
    const limit = parseInt(req.query.limit) || 10;
    const anomalies = await this.service.getRecentAnomalies(limit);
    res.json({ count: anomalies.length, anomalies });
  };
}

export default FogController;