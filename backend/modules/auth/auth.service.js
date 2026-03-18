import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { randomUUID } from 'crypto';

class AuthService {
  constructor({
    userRepository,
    authEventsPublisher,
    jwtSecret,
    jwtExpiresIn = '1h',
    emailVerificationJwtSecret,
    emailVerificationExpiresIn = '1h',
    publicBackendUrl,
  }) {
    this.userRepository = userRepository; // abstraction for DB
    this.authEventsPublisher = authEventsPublisher;
    this.jwtSecret = jwtSecret;
    this.jwtExpiresIn = jwtExpiresIn;
    this.emailVerificationJwtSecret = emailVerificationJwtSecret || jwtSecret;
    this.emailVerificationExpiresIn = emailVerificationExpiresIn;
    this.publicBackendUrl = publicBackendUrl;
  }

  throwAuthError(message, statusCode) {
    const error = new Error(message);
    error.statusCode = statusCode;
    throw error;
  }

  buildVerificationUrl(token) {
    const baseUrl = String(this.publicBackendUrl || '').replace(/\/+$/, '');
    return `${baseUrl}/auth/verify-email?token=${encodeURIComponent(token)}`;
  }

  async register(username, password, email) {
    if (!this.emailVerificationJwtSecret) {
      this.throwAuthError('Email verification secret is not configured', 500);
    }
    if (!this.publicBackendUrl) {
      this.throwAuthError('Public backend URL is not configured', 500);
    }

    const normalizedUsername = String(username || '').trim();
    const normalizedEmail = String(email || '').trim().toLowerCase();
    const normalizedPassword = String(password || '');
    if (!normalizedUsername || !normalizedPassword || !normalizedEmail) {
      this.throwAuthError('username, password and email are required', 400);
    }

    const existingUser = await this.userRepository.findByUsername(normalizedUsername);
    if (existingUser) {
      this.throwAuthError('User already exists', 409);
    }

    const existingEmail = await this.userRepository.findByEmail(normalizedEmail);
    if (existingEmail) {
      this.throwAuthError('Email is already registered', 409);
    }

    const hashedPassword = await bcrypt.hash(normalizedPassword, 10);

    const user = await this.userRepository.create({
      username: normalizedUsername,
      password: hashedPassword,
      email: normalizedEmail,
      verified: false,
    });

    const verificationToken = jwt.sign(
      {
        sub: user.id,
        email: normalizedEmail,
        type: 'email_verification',
        jti: randomUUID(),
      },
      this.emailVerificationJwtSecret,
      { expiresIn: this.emailVerificationExpiresIn }
    );

    const verificationUrl = this.buildVerificationUrl(verificationToken);

    try {
      this.authEventsPublisher.publishVerificationEmailRequested({
        userId: user.id,
        email: normalizedEmail,
        username: user.username,
        verificationToken,
        verificationUrl,
      });
    } catch (publishError) {
      await this.userRepository.deleteById(user.id);
      this.throwAuthError(`Registration failed: ${publishError.message}`, 503);
    }

    return {
      id: user.id,
      username: user.username,
      email: user.email,
      verified: user.verified,
    };
  }

  async login(username, password) {
    if (!this.jwtSecret) {
      this.throwAuthError('JWT secret is not configured', 500);
    }

    const user = await this.userRepository.findAuthByUsername(username);
    if (!user) {
      this.throwAuthError('Invalid username or password', 401);
    }

    const isValid = await bcrypt.compare(password, user.password);
    if (!isValid) {
      this.throwAuthError('Invalid username or password', 401);
    }

    if (!user.verified) {
      this.throwAuthError('Email is not verified yet', 403);
    }

    const token = jwt.sign(
      { id: user.id, username: user.username, verified: user.verified },
      this.jwtSecret,
      { expiresIn: this.jwtExpiresIn }
    );

    return { token };
  }

  async verifyEmailToken(token) {
    if (!this.emailVerificationJwtSecret) {
      this.throwAuthError('Email verification secret is not configured', 500);
    }

    const normalizedToken = String(token || '').trim();
    if (!normalizedToken) {
      this.throwAuthError('Verification token is required', 400);
    }

    let payload;
    try {
      payload = jwt.verify(normalizedToken, this.emailVerificationJwtSecret);
    } catch (error) {
      this.throwAuthError('Verification token is invalid or expired', 400);
    }

    if (payload?.type !== 'email_verification' || !payload?.sub) {
      this.throwAuthError('Verification token type is invalid', 400);
    }

    const user = await this.userRepository.findAuthById(payload.sub);
    if (!user) {
      this.throwAuthError('User not found for verification token', 404);
    }

    if (user.email !== payload.email) {
      this.throwAuthError('Verification token does not match user email', 400);
    }

    const verifiedUser = await this.userRepository.markVerifiedById(user.id);
    return {
      id: verifiedUser.id,
      username: verifiedUser.username,
      email: verifiedUser.email,
      verified: verifiedUser.verified,
    };
  }
}

export default AuthService;