import { Router } from 'express';
import AuthService from '../modules/auth/auth.service.js';
import AuthController from '../modules/auth/auth.controller.js';

export default function createAuthRouter({ userRepository }) {
  const router = Router();

  const authService = new AuthService({
    userRepository,
    jwtSecret: process.env.JWT_SECRET,
    jwtExpiresIn: process.env.JWT_EXPIRES_IN || '1h',
  });

  const authController = new AuthController(authService);

  router.post('/register', authController.register);
  router.post('/login', authController.login);

  return router;
}