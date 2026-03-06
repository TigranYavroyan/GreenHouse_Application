# Environment Configuration Guide

This backend supports environment-specific configuration files:

## Environment Files

- **`.env`** - Production/default
- **`.env.development`** - Development (`npm run dev` / `npm run local`)
- **`.env.production`** - Explicit production profile (optional)

## Running the Backend

### Production (Docker)
```bash
# Uses .env file automatically via docker-compose
docker-compose up backend
```

### Development (with nodemon)
```bash
# Uses .env.development file
npm run dev
```

### Local (without Docker, localhost services)
```bash
# Uses .env.development file
# Make sure Redis, RabbitMQ, and PostgreSQL are running locally
npm run local
```

## Environment Variables

All environment files should contain:

```env
NODE_ENV=production|development
PORT=3000
REDIS_HOST=localhost|redis
REDIS_PORT=6379
RABBITMQ_HOST=localhost|rabbitmq
RABBITMQ_PORT=5672
POSTGRES_HOST=localhost|postgres
POSTGRES_PORT=5432
POSTGRES_DB=greenhouse
POSTGRES_USER=greenhouse
POSTGRES_PASSWORD=greenhouse
JWT_SECRET=replace_with_secure_secret
JWT_EXPIRES_IN=1h
DEFAULT_USER_ENABLED=false
DEFAULT_USER_USERNAME=desktop_default_user
DEFAULT_USER_PASSWORD=replace_with_strong_password
DEFAULT_USER_EMAIL=
EXEC_TIMEOUT_MS=15000
```

## Configuration Loading Logic

The `config/index.js` file loads:

- `NODE_ENV=production` → `.env.production` (if present) via `dotenv` + Docker env file
- `NODE_ENV=development` → `.env.development`

## Notes

- Environment variables in `.env` files are loaded using `dotenv`
- Docker Compose uses `env_file` directive to load `.env` from the backend directory
- `DEFAULT_USER_ENABLED=true` will bootstrap a default user on startup (idempotent)
- Never use weak default passwords in production
- For local development, ensure Redis, RabbitMQ, and PostgreSQL are running on localhost

