# Environment Configuration Guide

This backend supports environment-specific configuration files:

## Environment Files

- **`.env.development`** - Development (`npm run dev` / `npm run local`)
- **`.env.production`** - Production (`npm start` / Docker)
- **`.env.example`** - Template for creating environment files

## Running the Backend

### Production (Docker)
```bash
# Uses .env.production via docker-compose
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
EMAIL_VERIFICATION_JWT_SECRET=replace_with_dedicated_secret
EMAIL_VERIFICATION_EXPIRES_IN=1h
PUBLIC_BACKEND_URL=http://localhost:3000
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURE=false
SMTP_USER=example@gmail.com
SMTP_PASS=app_password
MAIL_FROM=Greenhouse Automation <example@gmail.com>
NOTIFICATION_MAX_RETRIES=5
NOTIFICATION_RETRY_DELAY_MS=30000
EXEC_TIMEOUT_MS=15000
```

## Configuration Loading Logic

The `config/index.js` file loads:

- `NODE_ENV=production` → `.env.production`
- `NODE_ENV=development` → `.env.development`

## Notes

- Environment variables are loaded using `dotenv`
- Docker Compose uses `env_file` directive with `.env.production`/`.env.development`
- `PUBLIC_BACKEND_URL` is used to generate `/auth/verify-email` links sent over SMTP
- Gmail SMTP typically requires an app password in `SMTP_PASS` (do not use your main account password)
- Notification retry policy uses `NOTIFICATION_MAX_RETRIES` and `NOTIFICATION_RETRY_DELAY_MS`
- Never use weak default passwords in production
- For local development, ensure Redis, RabbitMQ, and PostgreSQL are running on localhost

