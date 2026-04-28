# Device/Core Interaction Contract

This document describes the current executor/getter integration contract between desktop -> backend -> greenhouse core.

## 1) Route Surface (backend API)

Base URL example: `http://localhost:3000`

### Read routes

- `GET /status`
- `GET /schema/getters`
- `GET /schema/executors`
- `GET /getters`
- `GET /getters/:key`
- `GET /executors`

### Write routes

- `POST /api/executors/:name/:action` where action is:
  - `mode`
  - `on`
  - `off`
  - `set`

No compatibility aliases are used.

## 2) Executor Action Rules

### `mode`

- Body required: `{ "value": "manual|auto|0|1" }`
- Backend normalizes `0 -> manual`, `1 -> auto`.
- Missing value -> `400` with `{"error":"Body field \"value\" is required"}`
- Invalid value -> `400` with `{"error":"Mode value must be one of: manual, auto, 0, 1"}`

### `on` / `off`

- No body required.
- Backend forwards action to core.

### `set`

- Body required: `{ "value": "<non-empty>" }`
- Backend forwards as string to core.
- Missing/empty value -> `400`.

## 3) Response/Error Behavior

- Backend mostly passes upstream core payload as-is for successful calls.
- Proxy/network/core errors are normalized to:

```json
{
  "error": "message"
}
```

- Upstream HTTP status is preserved when available.
- Connectivity failures are typically returned as `502`.

## 4) Queue Command Contract (desktop -> backend)

Command envelope to `greenhouse_commands`:

```json
{
  "commandId": "uuid",
  "command": "read_temperature_data",
  "type": "user",
  "parameters": {},
  "sessionId": "session-uuid"
}
```

Desktop publish properties:

- `replyTo: command_responses.<sessionId>`
- `correlationId: commandId`

Backend response payload:

```json
{
  "commandId": "uuid",
  "result": {},
  "cached": false,
  "sessionId": "session-uuid",
  "currentPath": "/",
  "timestamp": "2026-01-01T00:00:00.000Z"
}
```

On failure, backend adds top-level `error`.

## 4.1) Logic JSON API (GreenHouse2/demo passthrough)

The backend proxies demo logic endpoints to the configured core host:

- `GET /api/json/logic/full`
- `POST /api/json/logic/upload`
- `POST /api/json/logic/reload`

Upload expects a logic payload with top-level `root` compatible with demo logic JSON.

## 5) Practical cURL Examples

```bash
BASE="http://localhost:3000"

curl -sS "$BASE/status"
curl -sS "$BASE/schema/getters"
curl -sS "$BASE/schema/executors"
curl -sS "$BASE/getters"
curl -sS "$BASE/executors"

curl -sS -X POST "$BASE/api/executors/fan_1/mode" \
  -H "Content-Type: application/json" \
  -d '{"value":"manual"}'

curl -sS -X POST "$BASE/api/executors/fan_1/on"
curl -sS -X POST "$BASE/api/executors/fan_1/off"

curl -sS -X POST "$BASE/api/executors/pump_pwm_1/set" \
  -H "Content-Type: application/json" \
  -d '{"value":"120"}'
```

## 6) Scope Boundary

- This repository documents HTTP and AMQP contracts.
- Low-level DCM serial/table mapping details are not implemented here and must be sourced from the greenhouse core/DCM project.

