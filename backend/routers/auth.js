import { Router } from 'express';
import AuthService from '../modules/auth/auth.service.js';
import AuthController from '../modules/auth/auth.controller.js';

export default function createAuthRouter({ userRepository }) {
  const router = Router();

  const authService = new AuthService({
    userRepository,
    jwtSecret: process.env.JWT_SECRET,
  });

  const authController = new AuthController(authService);

  router.post('/', authController.register);
  router.post('/', authController.login);

  return router;
}