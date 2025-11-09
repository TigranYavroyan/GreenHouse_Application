# Frontend Environment Configuration Guide

This frontend supports three different environment configurations:

## Environment Files

- **`.env`** - Production environment (used in Docker)
- **`.env_dev`** - Development environment
- **`.env.local`** - Local development environment (without Docker)

## Running the Frontend

### Production (Docker)
```bash
# Uses .env file automatically via docker-compose
# Set ENVIRONMENT=production in docker-compose.yml
docker-compose up frontend
```

### Development
```bash
# Uses .env_dev file
export ENVIRONMENT=development
python3 main.py
```

### Local (without Docker, localhost services)
```bash
# Uses .env.local file
export ENVIRONMENT=development
python3 main.py
# Make sure Redis and RabbitMQ are running locally
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

The `modules/config.py` file automatically loads the appropriate `.env` file based on `ENVIRONMENT` or `NODE_ENV`:

- `ENVIRONMENT=production` or `NODE_ENV=production` → loads `.env`
- `ENVIRONMENT=development` or `NODE_ENV=development` → tries `.env_dev`, then `.env.local`, then `.env`

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
- Docker Compose uses `env_file` directive to load `.env` from the frontend directory
- For local development, ensure Redis and RabbitMQ are running on localhost
- The `ENVIRONMENT` variable can be set as an environment variable or in docker-compose.yml

