# Backend environment

Configuration lives in the **repository root** only:

- **`.env.example`** — copy to **`.env`** at the repo root (next to `docker-compose.yml`).
- **`config/index.js`** loads that `.env` when it sits beside `docker-compose.yml`. In Docker, variables are injected by Compose (`env_file: ./.env`); service hostnames (`REDIS_HOST`, `RABBITMQ_HOST`, `POSTGRES_HOST`, etc.) are overridden per service where needed.

See the root `.env.example` for the full list of variables.
