# Environment Configuration Guide

This backend supports three different environment configurations:

## Environment Files

- **`.env`** - Production environment (used in Docker)
- **`.env_dev`** - Development environment (used with `npm run dev`)
- **`.env.local`** - Local development environment (used with `npm run local`)

## Running the Backend

### Production (Docker)
```bash
# Uses .env file automatically via docker-compose
docker-compose up backend
```

### Development (with nodemon)
```bash
# Uses .env_dev file
npm run dev
```

### Local (without Docker, localhost services)
```bash
# Uses .env.local file
# Make sure Redis and RabbitMQ are running locally
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
EXEC_TIMEOUT_MS=15000
```

## Configuration Loading Logic

The `config/index.js` file automatically loads the appropriate `.env` file based on `NODE_ENV`:

- `NODE_ENV=production` → loads `.env`
- `NODE_ENV=development` → tries `.env_dev`, then `.env.local`, then `.env`

## Notes

- Environment variables in `.env` files are loaded using `dotenv`
- Docker Compose uses `env_file` directive to load `.env` from the backend directory
- For local development, ensure Redis and RabbitMQ are running on localhost

