import { Router } from 'express';
import AuthService from '../modules/auth/auth.service.js';
import AuthController from '../modules/auth/auth.controller.js';
import AuthEventsPublisher from '../modules/auth/events/auth-events.publisher.js';

export default function createAuthRouter({ userRepository, rabbitClient }) {
  const router = Router();
  const authEventsPublisher = new AuthEventsPublisher({ rabbitClient });

  const authService = new AuthService({
    userRepository,
    authEventsPublisher,
    jwtSecret: process.env.JWT_SECRET,
    jwtExpiresIn: process.env.JWT_EXPIRES_IN || '1h',
    emailVerificationJwtSecret: process.env.EMAIL_VERIFICATION_JWT_SECRET || process.env.JWT_SECRET,
    emailVerificationExpiresIn: process.env.EMAIL_VERIFICATION_EXPIRES_IN || '1h',
    publicBackendUrl: process.env.PUBLIC_BACKEND_URL,
  });

  const authController = new AuthController(authService);

  router.post('/register', authController.register);
  router.post('/login', authController.login);
  router.get('/verification/styles.css', authController.verificationStyles);
  router.get('/verify-email', authController.verifyEmail);

  return router;
}