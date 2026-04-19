# Frontend environment

Configuration lives in the **repository root** only:

- **`.env.example`** — copy to **`.env`** at the repo root (next to `docker-compose.yml`).
- **`modules/config.py`** loads that `.env` when it sits beside `docker-compose.yml`. In Docker, variables come from Compose (`env_file: ./.env` plus per-service `environment` overrides).

See the root `.env.example` for all variables (`BACKEND_URL`, `RABBITMQ_*`, `REDIS_*`, etc.).
