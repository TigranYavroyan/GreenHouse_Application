import bcrypt from 'bcryptjs';

const TRIVIAL_PASSWORDS = new Set([
  'password',
  '12345678',
  'admin',
  'admin123',
  'qwerty',
  'letmein',
]);

function parseBool(value, defaultValue = false) {
  if (value === undefined || value === null || value === '') return defaultValue;
  return String(value).toLowerCase() === 'true';
}

export default async function ensureDefaultUser({ usersRepository, logger }) {
  const enabled = parseBool(process.env.DEFAULT_USER_ENABLED, false);
  if (!enabled) return null;

  const username = process.env.DEFAULT_USER_USERNAME;
  const password = process.env.DEFAULT_USER_PASSWORD;
  const email = process.env.DEFAULT_USER_EMAIL || null;

  if (!username || !password) {
    throw new Error('DEFAULT_USER_USERNAME and DEFAULT_USER_PASSWORD are required when DEFAULT_USER_ENABLED=true');
  }

  if (password.length < 8 || TRIVIAL_PASSWORDS.has(password.toLowerCase())) {
    throw new Error('DEFAULT_USER_PASSWORD is too weak; use at least 8 chars and avoid common passwords');
  }

  const existing = await usersRepository.findByUsername(username);
  if (existing) {
    logger?.info(`Default user "${username}" already exists.`);
    return existing;
  }

  const hashedPassword = await bcrypt.hash(password, 10);
  const created = await usersRepository.create({
    username,
    password: hashedPassword,
    email,
  });

  logger?.info(`Default user "${username}" created.`);
  return created;
}
