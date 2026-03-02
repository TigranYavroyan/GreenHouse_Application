class AuthController {
  constructor(authService) {
    this.authService = authService;
  }

  register = async (req, res) => {
    try {
      const { username, password } = req.body;

      if (!username || !password) {
        return res.status(400).json({
          error: 'Missing username or password',
        });
      }

      const user = await this.authService.register(username, password);

      res.status(201).json({
        message: 'User registered successfully',
        user,
      });
    } catch (err) {
      res.status(400).json({ error: err.message });
    }
  };

  login = async (req, res) => {
    try {
      const { username, password } = req.body;

      if (!username || !password) {
        return res.status(400).json({
          error: 'Missing username or password',
        });
      }

      const result = await this.authService.login(username, password);

      res.json(result);
    } catch (err) {
      res.status(401).json({ error: err.message });
    }
  };
}

export default AuthController;