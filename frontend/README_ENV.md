# Frontend Environment Configuration Guide

This frontend supports environment-specific configuration files:

## Environment Files

- **`.env.development`** - Development environment
- **`.env.production`** - Production environment
- **`.env.example`** - Template for creating environment files

## Running the Frontend

### Production (Docker)
```bash
# Uses .env.production via docker-compose
# Set ENVIRONMENT=production in docker-compose.yml
docker-compose up frontend
```

### Development
```bash
# Uses .env.development file
export ENVIRONMENT=development
python3 main.py
```

## Environment Variables

All environment files should contain:

```env
BACKEND_URL=http://localhost:3000|http://backend:3000
RABBITMQ_HOST=localhost|rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASS=guest
```

## Configuration Loading Logic

The `modules/config.py` file automatically loads:

- `ENVIRONMENT=production` or `NODE_ENV=production` → `.env.production`
- `ENVIRONMENT=development` or `NODE_ENV=development` → `.env.development`

## Configuration Module

The frontend uses a centralized configuration module (`modules/config.py`) that:
- Loads environment variables from `.env` files
- Provides a `Config` class with all configuration values
- Can be imported in any module: `from modules.config import config`

## Usage in Code

```python
from modules.config import config

# Access configuration values
backend_url = config.BACKEND_URL
rabbitmq_host = config.RABBITMQ_HOST
rabbitmq_port = config.RABBITMQ_PORT
```

## Notes

- Environment variables in `.env` files are loaded using `python-dotenv`
- Docker Compose uses `env_file` directive with `.env.production`/`.env.development`
- For local development, ensure Redis and RabbitMQ are running on localhost
- The `ENVIRONMENT` variable can be set as an environment variable or in docker-compose.yml

