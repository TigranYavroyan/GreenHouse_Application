# GreenHouse Application Documentation

This folder documents the **current implementation state** of the GreenHouse project (PyQt5 desktop + Node.js backend + RabbitMQ + Redis + PostgreSQL + external greenhouse core API).

## What Is Canonical

- API behavior is defined by backend source in `backend/`.
- Desktop behavior is defined by frontend source in `frontend/`.
- Message contracts are defined by code + project rules:
  - Command envelope must include `commandId`, `command`, `type`, `parameters`, `sessionId`.
  - Backend responses include `commandId`, `result`, `cached`, `sessionId`, `timestamp`, with top-level `error` on failure.

## Document Map

- `overall_architecture_description.txt` - end-to-end architecture and runtime flow.
- `DCM_INTERACTION_DOCUMENTATION.md` - HTTP executor/getter integration contract and examples.
- `AUTH_EMAIL_VERIFICATION_PROTOCOL.md` - auth and verification event protocol.
- `ERD_DATABASE.md` - relational model and Redis keyspace.
- `EDGE_TO_EDGE_FOG_AGGREGATION.md` - edge/fog design and backend fog APIs.
- `EDGE_FOG_INTEGRATION_SUMMARY.md` - concise implementation status for fog integration.
- `BLOCK_SCHEME_IMPLEMENTATION_CONTEXT.md` - current logic-tab status and roadmap context.
- `TABLE_INTEGRATION_SUMMARY.md` / `TABLE_FIXES.md` - table UI integration notes.
- `UML_CLASS_DIAGRAM.mermaid` - high-level class/module relationships.
- `HOW_TO_USE_DIPLOMA_WORK.md` - helper notes for external diploma document workflow.

## Current Highlights

- RabbitMQ command consumer uses manual ack (`noAck: false`) and prefetch from config (default `5`).
- Command processor supports per-session sequencing and best-effort Redis cache/idempotency.
- For built-in greenhouse commands, command TTL is currently `0`, so response cache/idempotency is effectively bypassed.
- Desktop sends AMQP commands with `replyTo=command_responses.<sessionId>` and backend publishes to `replyTo` when present.
- Backend exposes greenhouse core passthrough APIs at root routes (`/status`, `/schema/*`, `/getters`, `/executors`, `/api/executors/:name/:action`).
- Desktop includes a Logic tab with local canvas editing and JSON generation; backend passthrough routes for `/api/json/logic/*` are not implemented yet.

## Quick Start (Local)

1. Create env file: `cp .env.example .env`
2. Start stack: `docker compose up -d`
3. Backend API: `http://localhost:3000`
4. Run desktop locally from `frontend/` with `python main.py`

## Notes

- `--nogui` mode in frontend is intentionally unsupported and exits.
- Keep this folder synced with implementation whenever contracts/routes/data models change.
