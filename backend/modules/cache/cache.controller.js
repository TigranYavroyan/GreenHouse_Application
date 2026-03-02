class CacheController {
  constructor(cacheService) {
    this.cacheService = cacheService;
  }

  getCacheKeys = async (req, res) => {
    try {
      const keys = await this.cacheService.getKeys();
      res.json({ keys });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  }

  clearCache = async (req, res) => {
    try {
      await this.cacheService.clear();
      res.json({ message: 'Cache cleared' });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  }

  clearErrorCache = async (req, res) => {
    try {
      await this.cacheService.clearErrors();
      res.json({ message: 'Error cache cleared' });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  }
}

export default CacheController;
