import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';

class AuthService {
  constructor({ userRepository, jwtSecret, jwtExpiresIn = '1h' }) {
    this.userRepository = userRepository; // abstraction for DB
    this.jwtSecret = jwtSecret;
    this.jwtExpiresIn = jwtExpiresIn;
  }

  async register(username, password, email = null) {
    const existingUser = await this.userRepository.findByUsername(username);
    if (existingUser) {
      throw new Error('User already exists');
    }

    const hashedPassword = await bcrypt.hash(password, 10);

    const user = await this.userRepository.create({
      username,
      password: hashedPassword,
      email,
    });

    return { id: user.id, username: user.username };
  }

  async login(username, password) {
    if (!this.jwtSecret) {
      throw new Error('JWT secret is not configured');
    }

    const user = await this.userRepository.findByUsername(username);
    if (!user) {
      throw new Error('Invalid username or password');
    }

    const isValid = await bcrypt.compare(password, user.password);
    if (!isValid) {
      throw new Error('Invalid username or password');
    }

    const token = jwt.sign(
      { id: user.id, username: user.username },
      this.jwtSecret,
      { expiresIn: this.jwtExpiresIn }
    );

    return { token };
  }
}

export default AuthService;