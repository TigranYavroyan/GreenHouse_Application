"""
Configuration module for Greenhouse Frontend.
Loads variables from the repository root `.env` (same directory as `docker-compose.yml`).
Docker Compose injects environment variables for containers; this file supports local runs.
"""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _resolve_project_env_path() -> Optional[Path]:
    """Return repo-root `.env` if it sits next to `docker-compose.yml`."""
    here = Path(__file__).resolve().parent
    for start in (here, Path.cwd()):
        base = start.resolve()
        for _ in range(12):
            env_file = base / ".env"
            compose = base / "docker-compose.yml"
            if env_file.is_file() and compose.is_file():
                return env_file
            if base.parent == base:
                break
            base = base.parent
    return None


_env_path = _resolve_project_env_path()
if _env_path is not None:
    load_dotenv(_env_path)


# Determine environment (defaults to development)
ENVIRONMENT = os.getenv('ENVIRONMENT', os.getenv('NODE_ENV', 'development')).lower()


# Configuration values with defaults
class Config:
    """Application configuration"""

    # Backend API URL
    BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:3000')

    # RabbitMQ Configuration
    RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
    RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))
    RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
    RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')

    # Redis Configuration (for edge caching)
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
    REDIS_DB = int(os.getenv('REDIS_DB', '0'))

    # Environment
    ENVIRONMENT = ENVIRONMENT

    @classmethod
    def get_rabbitmq_url(cls):
        """Get RabbitMQ connection URL"""
        return f"amqp://{cls.RABBITMQ_USER}:{cls.RABBITMQ_PASS}@{cls.RABBITMQ_HOST}:{cls.RABBITMQ_PORT}"

    @classmethod
    def print_config(cls):
        """Print current configuration (for debugging)"""
        print(f"Environment: {cls.ENVIRONMENT}")
        print(f"Backend URL: {cls.BACKEND_URL}")
        print(f"RabbitMQ: {cls.RABBITMQ_HOST}:{cls.RABBITMQ_PORT}")
        print(f"RabbitMQ User: {cls.RABBITMQ_USER}")


# Export config instance
config = Config()
