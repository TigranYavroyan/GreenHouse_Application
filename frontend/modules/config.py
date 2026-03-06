"""
Configuration module for Greenhouse Frontend
Loads environment variables from .env files based on ENVIRONMENT variable
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Get the base directory (frontend/)
BASE_DIR = Path(__file__).resolve().parent.parent
DOCKER_ENV_FILE = Path('/.dockerenv')


def is_running_in_docker() -> bool:
    """Detect Docker runtime to choose proper hostnames."""
    return DOCKER_ENV_FILE.exists()


def load_first_existing(*paths: Path) -> None:
    """Load the first env file that exists."""
    for path in paths:
        if path.exists():
            load_dotenv(path)
            return

# Determine environment (defaults to development)
ENVIRONMENT = os.getenv('ENVIRONMENT', os.getenv('NODE_ENV', 'development')).lower()
IS_DOCKER = is_running_in_docker()

env_path = BASE_DIR / '.env'
env_dev_path = BASE_DIR / '.env_dev'
env_local_path = BASE_DIR / '.env.local'

# Load environment variables based on ENVIRONMENT
if ENVIRONMENT == 'production':
    # Production in Docker should use service names from .env.
    # Production outside Docker should prefer localhost-friendly values.
    if IS_DOCKER:
        load_first_existing(env_path)
    else:
        load_first_existing(env_local_path, env_dev_path, env_path)
elif ENVIRONMENT == 'development':
    # Development: try .env_dev first, then .env.local, then .env
    load_first_existing(env_dev_path, env_local_path, env_path)
else:
    # Fallback: load .env
    load_first_existing(env_path)

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

