import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const verificationPagePath = path.resolve(__dirname, '../../public/email-verification/index.html');
const verificationStylesPath = path.resolve(__dirname, '../../public/email-verification/styles.css');

class AuthController {
  constructor(authService) {
    this.authService = authService;
  }

  register = async (req, res) => {
    try {
      const { username, password, email } = req.body;

      if (!username || !password || !email) {
        return res.status(400).json({
          error: 'Missing username, password or email',
        });
      }

      const user = await this.authService.register(username, password, email);

      res.status(201).json({
        message: 'User registered successfully',
        user,
      });
    } catch (err) {
      res.status(err.statusCode || 400).json({ error: err.message });
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
      res.status(err.statusCode || 401).json({ error: err.message });
    }
  };

  verifyEmail = async (req, res) => {
    const wantsJson = String(req.query.format || '').toLowerCase() === 'json'
      || String(req.headers.accept || '').includes('application/json');

    try {
      const { token } = req.query;
      const user = await this.authService.verifyEmailToken(token);

      if (wantsJson) {
        res.json({
          message: 'Email verified successfully',
          user,
        });
        return;
      }

      res.sendFile(verificationPagePath);
    } catch (err) {
      if (wantsJson) {
        res.status(err.statusCode || 400).json({ error: err.message });
        return;
      }

      const safeMessage = String(err.message || 'Verification failed').replace(/[<>]/g, '');
      res.status(err.statusCode || 400).send(
        `<!doctype html><html><head><meta charset="utf-8"><title>Email Verification Failed</title></head><body><h2>Email verification failed</h2><p>${safeMessage}</p></body></html>`
      );
    }
  };

  verificationStyles = (req, res) => {
    res.sendFile(verificationStylesPath);
  };
}

export default AuthController;