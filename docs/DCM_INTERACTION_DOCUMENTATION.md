# Device Control Module (DCM) Interaction Documentation

This document is implementation-aligned to the current core replacement files in this repository:

- `backend/routers/core.js`
- `backend/modules/core/core.controller.js`
- `backend/modules/core/core.service.js`
- `backend/clients/greenhouseCoreClient.js`
- `backend/app.js`
- `frontend/modules/core_api_client.py`
- `frontend/modules/core_dtos.py`
- `frontend/modules/greenhouse_server.py`
- `frontend/modules/greenhouse.py`
- `frontend/modules/table_renderers.py`

Important source constraint:
- The requested `demo/*` files are not present in this repository.
- All low-level DCM serial/CRC/config-map details that require `DeviceControlModule`/`DG_EXE_CONFIG` are therefore marked as **unknown from code**.

---

## 1) HTTP API (getters + setters/commands)

There are two API layers:

- **Backend HTTP API** exposed by this project (mounted in `backend/app.js`).
- **Greenhouse Core native API** called by backend client (same route shapes on core host).

### 1.1 Route map

#### A) Backend routes (external clients should call these)

Base URL example: `http://localhost:3000`

| Method | Path | Purpose |
|---|---|---|
| GET | `/status` | Health/status |
| GET | `/schema/getters` | Getter schema |
| GET | `/schema/executors` | Executor schema |
| GET | `/getters` | All getter snapshots |
| GET | `/getters/:key` | One getter snapshot |
| GET | `/executors` | All executor snapshots |
| GET | `/sensor-readings` | User-scoped persisted sensor readings (supports filters) |
| POST | `/api/executors/:name/:action` | Generic executor command route (`mode`, `on`, `off`, `set`) |

Compatibility aliases:
- none (removed; use canonical root routes listed above)

#### B) Core native routes (backend talks to these on core server)

Core base URL from config: `GREENHOUSE_CORE_URL` (default `http://192.168.27.16:8080`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/status` | Core status |
| GET | `/schema/getters` | Getter schema |
| GET | `/schema/executors` | Executor schema |
| GET | `/getters` | Getter snapshots |
| GET | `/getters/:key` | One getter snapshot |
| GET | `/executors` | Executor snapshots |
| POST | `/api/executors/:name/mode` | Set mode |
| POST | `/api/executors/:name/on` | ON action |
| POST | `/api/executors/:name/off` | OFF action |
| POST | `/api/executors/:name/set` | SET action |
| POST | `/api/v1/commands/execute` | Queue-consumed command execution endpoint used by backend processor |

---

### 1.2 Endpoint-by-endpoint contract (backend external API)

#### GET `/status`
- **Purpose**: returns upstream core status payload.
- **Required body**: none.
- **Optional body**: none.
- **Success response schema**:
  - object, at minimum observed/expected key: `status` (string).
- **Status codes**:
  - `200` on success.
  - upstream HTTP status is preserved on upstream/core errors when available.
  - `502` on network/core connectivity failures.
- **Example**:
```json
{
  "status": "ok"
}
```

#### GET `/schema/getters`
- **Purpose**: returns getter schema map.
- **Required body**: none.
- **Success response schema**:
  - object map: `{ "<getterName>": "<type>" }`.
- **Status codes**: `200`, upstream status passthrough, or `502` for connectivity failures.
- **Example**:
```json
{
  "air_temp": "float",
  "humidity": "float"
}
```

#### GET `/schema/executors`
- **Purpose**: returns executor schema map.
- **Required body**: none.
- **Success response schema**:
  - object map: `{ "<executorName>": "<type>" }`.
- **Status codes**: `200`, upstream status passthrough, or `502` for connectivity failures.
- **Example**:
```json
{
  "fan_1": "bool",
  "pump_pwm_1": "int"
}
```

#### GET `/getters`
- **Purpose**: returns current snapshot of all getters.
- **Required body**: none.
- **Success response schema**:
  - object map by getter key:
    - `valid` (boolean)
    - `stampMs` (number)
    - `data` object:
      - `type` (string)
      - `value` (any)
- **Status codes**: `200`, upstream status passthrough, or `502` for connectivity failures.
- **Example**:
```json
{
  "air_temp": {
    "valid": true,
    "stampMs": 1741380000000,
    "data": {
      "type": "float",
      "value": 24.3
    }
  }
}
```

#### GET `/getters/<key>`
- **Purpose**: returns one getter snapshot.
- **Required body**: none.
- **Path param**: `key` (string; backend client requires non-empty after trim).
- **Success response schema**:
  - same entry shape as a single getter value in `/getters`.
- **Status codes**:
  - `200` success.
  - upstream status passthrough (for example `404` for unknown key).
  - `502` on network/core connectivity failures.
- **Example**:
```json
{
  "key": "air_temp",
  "valid": true,
  "stampMs": 1741380000000,
  "data": {
    "type": "float",
    "value": 24.3
  }
}
```

#### GET `/executors`
- **Purpose**: returns executor snapshots.
- **Required body**: none.
- **Success response schema**:
  - array of executor objects:
    - `id` (number)
    - `name` (string)
    - `valid` (boolean)
    - `stampMs` (number)
    - `mode` (string, examples in code paths: `MANUAL` / `AUTO`)
    - `data` object:
      - `type` (string)
      - `value` (any)
- **Status codes**: `200`, upstream status passthrough, or `502` for connectivity failures.
- **Example**:
```json
[
  {
    "id": 2,
    "name": "fan_1",
    "valid": true,
    "stampMs": 1741380000000,
    "mode": "AUTO",
    "data": {
      "type": "bool",
      "value": false
    }
  }
]
```

#### GET `/sensor-readings`
- **Purpose**: returns authenticated user sensor readings persisted in database.
- **Required body**: none.
- **Optional query params**:
  - `deviceId` (UUID string) -- filter by device ID
  - `deviceName` (string) -- filter by exact device name (alternative to `deviceId`)
  - `sensorId` (UUID string)
  - `from` (ISO datetime string)
  - `to` (ISO datetime string)
  - `limit` (positive integer, max 5000)
  - `order` (`ASC` or `DESC`)
- **Success response schema**:
  - object wrapper:
    - `count` (number)
    - `data` (array of reading objects)
  - each reading includes at least:
    - `id` (UUID)
    - `value` (number)
    - `timestamp` (ISO datetime)
    - `sensor` object with nested `device`
- **Status codes**:
  - `200` on success
  - `400` on invalid query params (for example invalid dates, invalid order, invalid limit)
  - `401/403` on auth/user-context failures
- **Example**:
```json
{
  "count": 2,
  "data": [
    {
      "id": "6e9f6f60-bb2b-4f6a-a1ef-3f3f6cbda290",
      "value": 24.7,
      "timestamp": "2026-03-19T09:15:00.000Z",
      "sensor": {
        "id": "3e1476a8-c6d1-43a4-b934-44c2383bd2c0",
        "name": "Temp Sensor A",
        "type": "temperature",
        "device": {
          "id": "0fbc1f72-286f-46da-9cf2-b0177fce9a1c",
          "name": "Greenhouse Device 1"
        }
      }
    }
  ]
}
```

#### POST `/api/executors/<name>/mode`
- **Purpose**: set executor mode.
- **Required body**:
```json
{ "value": "manual|auto|0|1" }
```
- **Optional body fields**: none in code.
- **Status codes**:
  - `200` success.
  - `400` if body `value` is missing/blank in controller or mode is invalid.
  - upstream status passthrough for upstream non-2xx.
  - `502` on network/core connectivity failures.
- **Example request**:
```json
{ "value": "manual" }
```
- **Example success** (pass-through from core, shape may vary by core):
```json
{
  "ok": true,
  "name": "fan_1",
  "action": "mode",
  "value": "manual"
}
```

#### POST `/api/executors/<name>/on`
- **Purpose**: send ON action.
- **Required body**: none.
- **Optional body**: ignored by current backend route.
- **Status codes**:
  - `200` success.
  - upstream status passthrough for upstream non-2xx.
  - `502` on network/core connectivity failures.
- **Example success**:
```json
{
  "ok": true,
  "name": "fan_1",
  "action": "on"
}
```

#### POST `/api/executors/<name>/off`
- **Purpose**: send OFF action.
- **Required body**: none.
- **Optional body**: ignored by current backend route.
- **Status codes**:
  - `200` success.
  - upstream status passthrough for upstream non-2xx.
  - `502` on network/core connectivity failures.
- **Example success**:
```json
{
  "ok": true,
  "name": "fan_1",
  "action": "off"
}
```

#### POST `/api/executors/<name>/set`
- **Purpose**: set executor value payload.
- **Required body**:
```json
{ "value": "<non-empty>" }
```
- **Status codes**:
  - `200` success.
  - `400` if `value` is `undefined`, `null`, or empty string.
  - upstream status passthrough for upstream non-2xx.
  - `502` on network/core connectivity failures.
- **Example request**:
```json
{ "value": "120" }
```
- **Example success**:
```json
{
  "ok": true,
  "name": "pump_pwm_1",
  "action": "set",
  "value": "120"
}
```

#### POST `/api/v1/commands/execute`
- **Purpose**: execute command payload forwarded from backend queue consumer.
- **Required body**:
```json
{
  "command": "read_temperature_data",
  "parameters": {},
  "commandId": "uuid",
  "sessionId": "session-uuid"
}
```
- **Body rules**:
  - `command` must be string.
  - `parameters` must be object (backend defaults to `{}` when omitted).
  - `commandId` and `sessionId` must be strings.
- **Success response schema**:
```json
{
  "success": true,
  "result": {},
  "error": null,
  "commandId": "uuid",
  "command": "read_temperature_data",
  "timestamp": "2026-03-08T12:00:00.000Z"
}
```
- **Failure behavior**:
  - HTTP transport errors are surfaced by backend as top-level `error` in `command_responses`.
  - Application-level command failure is represented by `success: false` with `error` message.

---

### 1.3 POST action list for `/api/executors/<name>/<action>`

Allowed actions in current code path:
- `mode`
- `on`
- `off`
- `set`

Value rules:
- `mode`: accepts `manual|MANUAL|0` and `auto|AUTO|1` (normalized to lowercase canonical form before send).
- `on`: no request body required.
- `off`: no request body required.
- `set`: requires non-empty `value`; backend forwards as string to core.

---

## 2) Command/value rules and validation

### 2.1 Exact accepted `value` formats by action

#### `mode`
- Accepted by backend client normalization:
  - `"manual"`, `"MANUAL"`, `"0"`
  - `"auto"`, `"AUTO"`, `"1"`
- Rejected values trigger:
  - `Mode value must be one of: manual, auto, 0, 1`

#### `on` / `off`
- No `value` required or consumed in controller route.
- Action identity is encoded in URL segment.

#### `set`
- Controller requires `value` to be present and non-empty (`undefined`/`null`/`""` are rejected).
- Backend client sends `body: { value: String(value) }`.
- Numeric/integer constraints are **not enforced in these backend/frontend files**.

### 2.2 Preconditions

From frontend logic (`ServerPanelMixin`):
- UI requires MANUAL mode before calling `on`, `off`, or `set`:
  - Reads executors.
  - ON/OFF/SET buttons are disabled when no eligible MANUAL executor exists.
  - If selected executor is `AUTO`, action is blocked and user is asked to switch mode explicitly.
- For kind selection:
  - Executor schema type `bool` => treated as `digital` (`on`/`off` UI flows).
  - Any other type => treated as `value` (`set` flow).

Backend proxy itself does **not** enforce MANUAL precondition; it forwards action to core.

### 2.3 Error conditions and messages (exact/near-exact)

Observed in code:

- Missing mode value (controller):
  - HTTP `400`
  - `{"error":"Body field \"value\" is required"}`

- Missing set value (controller):
  - HTTP `400`
  - `{"error":"Body field \"value\" is required"}`

- Invalid mode value (backend client normalizer):
  - HTTP `400`
  - `{"error":"Mode value must be one of: manual, auto, 0, 1"}`

- Missing getter key in backend client helper (if called internally with empty key):
  - throws `Getter key is required`

- Missing executor name in backend client helper (internal guard):
  - throws `Executor name is required`

- Upstream non-2xx from core:
  - backend extracts `payload.error` if present, else `HTTP <status>: <statusText>`
  - backend returns same HTTP status with `{ "error": "<message>" }`

- Network/timeout failure to core:
  - propagated as `502` `{ "error": "<fetch/abort message>" }`
  - exact text depends on runtime/fetch error.

---

## 3) Response values and payload schemas

### 3.1 General proxy response wrapper behavior

- Success: route returns upstream payload as-is (`200` default).
- Error: proxy returns object:
```json
{
  "error": "..."
}
```

### 3.2 `getters` entry structure

From DTO and renderers:

```json
{
  "<getterKey>": {
    "valid": true,
    "stampMs": 1741380000000,
    "data": {
      "type": "float",
      "value": 24.3
    }
  }
}
```

Fields:
- `valid`: boolean
- `stampMs`: integer milliseconds
- `data.type`: string
- `data.value`: any JSON value

### 3.3 `executors` entry structure

From DTO and renderers:

```json
[
  {
    "id": 2,
    "name": "fan_1",
    "valid": true,
    "stampMs": 1741380000000,
    "mode": "AUTO",
    "data": {
      "type": "bool",
      "value": false
    }
  }
]
```

Fields:
- `id`: integer
- `name`: string
- `valid`: boolean
- `stampMs`: integer milliseconds
- `mode`: string
- `data.type`: string
- `data.value`: any JSON value

### 3.4 Action success payload (`mode` / `on` / `off` / `set`)

Current backend is pass-through for action responses; schema is determined by core server.

Observed/expected fields used by this project and request context:
- commonly expected: `ok`, `name`, `action`, `value` (depending on action)

Because backend does not re-shape these payloads, any additional fields from core can appear unchanged.

### 3.5 Error response format and HTTP codes

Proxy error body:
```json
{
  "error": "<message>"
}
```

Proxy status code behavior:
- `400` for missing required body `value` and invalid mode values.
- `502` for upstream/core failures.

---

## 4) DCM low-level protocol (serial)

Status: **unknown from code in this repository**.

The requested items below are not present in the available replacement files:
- serial frame format (`data/crc`)
- packet forms (`tableId,index,value`, `;` batches)
- table IDs and ranges (digital/pwm/index/value constraints)
- queue semantics and retry/timeout at serial layer
- feedback mask bit layout (error bits, packet count bits, keyword bit)
- MCU reply success/failure parsing criteria

What is available:
- HTTP-level retries from backend to core:
  - exponential backoff (`100ms * 2^attempt`)
  - retry on timeout (`AbortError`) and some fetch-connectivity failures
  - retries count configured by `GREENHOUSE_CORE_RETRIES`
- This is **HTTP client behavior**, not serial protocol behavior.

Where to check next:
- Original missing sources referenced in your request:
  - `demo/Tools/DeviceControlModule.hpp`
  - `demo/Executor/EX_DeviceControlModule.hpp`
  - `demo/DG_EXE_CONFIG.txt`
  - `demo/API/HttpServer.hpp`
  - `demo/main.cpp`
  - `demo/GlobalState.hpp`

---

## 5) Mapping: logical executor names -> DCM channels

### 5.1 Project-specific mapping in current repository

Static DCM channel mapping (`tableId/index`) is **unknown from code** in current files.

What is available dynamically at runtime:
- Executor schema map (`/schema/executors`): `name -> type`
- Executor snapshot list (`/executors`): includes `id`, `name`, `mode`, `data`

Therefore this repository currently supports:
- **Logical mapping**: `name -> type` from schema
- **Runtime identity mapping**: `name -> id` from executor snapshots
- **No visible mapping** to DCM `tableId/index` in available files

### 5.2 Generic protocol behavior vs project mapping

- **Generic behavior (documented from current code)**:
  - Bool executors are treated as digital controls in frontend (`on/off`).
  - Non-bool executors are treated as value controls (`set`).
  - MANUAL mode is required by frontend before control actions.

- **Project-specific DCM channel map (`[dcm_map]`, `[schema_executors]`, `[executors]`)**:
  - **unknown from code** (missing requested config/source files).

### 5.3 Mapping table (best available from current code)

| Executor name | Executor id | Type | Mode default | DCM tableId/index |
|---|---|---|---|---|
| runtime from `/executors` | runtime from `/executors` | runtime from `/schema/executors` or `executors[].data.type` | not fixed in this repo; snapshot field `mode` reflects current state | unknown from code |

---

## 6) Practical usage

Assume backend proxy base URL:
- `BASE=http://localhost:3000`

### 6.1 Switch executor to MANUAL

```bash
curl -sS -X POST "$BASE/api/executors/fan_1/mode" \
  -H "Content-Type: application/json" \
  -d '{"value":"manual"}'
```

### 6.2 Turn channel ON/OFF (digital executor)

```bash
curl -sS -X POST "$BASE/api/executors/fan_1/on"
curl -sS -X POST "$BASE/api/executors/fan_1/off"
```

### 6.3 Set numeric value (PWM-like/value executor)

```bash
curl -sS -X POST "$BASE/api/executors/pump_pwm_1/set" \
  -H "Content-Type: application/json" \
  -d '{"value":"120"}'
```

### 6.4 Read current executor/getter states

```bash
curl -sS "$BASE/status"
curl -sS "$BASE/schema/getters"
curl -sS "$BASE/schema/executors"
curl -sS "$BASE/getters"
curl -sS "$BASE/getters/air_temp"
curl -sS "$BASE/executors"
```

### 6.5 Failure examples and recovery

#### Example: missing `value` for mode/set

```bash
curl -sS -X POST "$BASE/api/executors/fan_1/mode" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Expected proxy result:
```json
{
  "error": "Body field \"value\" is required"
}
```

Recovery:
- Send a valid payload (`{"value":"manual"}` or `{"value":"auto"}` for mode).
- For `set`, provide non-empty `value`.

#### Example: invalid mode value

```bash
curl -sS -X POST "$BASE/api/executors/fan_1/mode" \
  -H "Content-Type: application/json" \
  -d '{"value":"invalid_mode"}'
```

Expected error (from backend mode normalizer):
```json
{
  "error": "Mode value must be one of: manual, auto, 0, 1"
}
```

Recovery:
- Use `"manual"`, `"auto"`, `"0"`, or `"1"`.

#### Example: upstream unavailable

- If core is down/unreachable, proxy returns `502` with fetch/HTTP error text in `error`.

Recovery:
- Verify backend env `GREENHOUSE_CORE_URL`.
- Verify core service availability.
- Retry after connectivity is restored.

### 6.6 RabbitMQ command envelope and response contract

Command payload sent to `greenhouse_commands`:

```json
{
  "commandId": "uuid",
  "command": "read_temperature_data",
  "type": "user",
  "parameters": {},
  "sessionId": "session-uuid"
}
```

AMQP publish properties used by frontend:
- `replyTo`: `command_responses.<sessionId>` (dedicated response queue per desktop session)
- `correlationId`: `commandId`

Backend response routing:
- If incoming command message has `replyTo`, backend publishes response there.
- Otherwise backend falls back to shared `command_responses`.

Success response payload from `command_responses`:

```json
{
  "commandId": "uuid",
  "result": {},
  "cached": false,
  "sessionId": "session-uuid",
  "currentPath": "/",
  "timestamp": "2026-03-08T12:00:00.000Z"
}
```

Failure response payload from `command_responses`:

```json
{
  "commandId": "uuid",
  "result": null,
  "cached": false,
  "error": "Error message",
  "sessionId": "session-uuid",
  "currentPath": null,
  "timestamp": "2026-03-08T12:00:00.000Z"
}
```

---

## 7) Gaps / ambiguities (explicit)

### Unknown from code

1. **Low-level DCM serial protocol** details:
   - frame bytes, CRC algorithm, parsing masks, packet semantics.
2. **Static map from executor to DCM channel**:
   - no visible `dcm_map`, `tableId`, `index` definitions.
3. **Core-native action response strict schema**:
   - backend passes through core response; exact final schema is defined by core service implementation, not by this repository.
4. **Whether core accepts aliases like `mode=0|1` natively**:
   - backend normalizes these aliases to `manual|auto` before forwarding.
5. **Strict numeric constraints for `set`**:
   - not validated in this backend/frontend layer.

### Next places to inspect

- The missing `demo/*` sources requested originally.
- The real greenhouse core service repository/code running at `GREENHOUSE_CORE_URL`.
- Any protocol/design doc that defines DCM serial framing and mapping tables.

---

## Frontend buttons and setup for DCM consistency

This section is derived from current UI wiring and intended to keep the frontend user friendly and consistent with DCM logic.

### Connected buttons (current)

From `frontend/modules/greenhouse.py`:

- Connected server-tab actions:
  - `healthButton` -> `view_core_status` (`System Health`)
  - `refreshButton` -> `refresh_all_status` (`Refresh All Data`)
  - `statsButton` -> `view_getter_schema` (`Available Sensor Types`)
  - `sessionsButton` -> `view_executor_schema` (`Available Device Controls`)
  - `cacheKeysButton` -> `view_getters` (`All Sensor Readings`)
  - `queuesButton` -> `view_executors` (`All Device States`)
  - `clearCacheButton` -> `prompt_switch_executor_mode` (`Change Device Mode`)
  - `testCommandButton` -> `prompt_executor_on` (`Turn Device ON`)
  - `logFilesButton` -> `prompt_executor_off` (`Turn Device OFF`)
  - `viewLogButton` -> `prompt_executor_set` (`Set Device Value`)
- Connected control-tab actions (RabbitMQ command flow, not executor HTTP API):
  - sensor reads and toggle controls for water/fan/heater/actuator
  - sensor read responses are additionally persisted (best effort) into authenticated REST entities:
    - ensure/create device (`/devices`)
    - ensure/create sensor (`/sensors`)
    - append time-series row (`/sensor-readings`)
- Connected scheduling-tab actions:
  - `scheduleTaskButton` -> `schedule_selected_task` (create backend one-time schedule from delay presets)
  - `cancelScheduledButton` -> `cancel_selected_schedule` (cancel selected backend schedule by disabling it)
  - `clearScheduledButton` -> `clear_all_schedules` (cancel all pending backend schedules for current user)
- Connected statistics-tab actions:
  - `statisticsDeviceCombo` is populated with concrete sensor names from `GET /sensors` (user-scoped); each item stores the sensor ID, name, and type
  - On plot load, readings are fetched via `GET /sensor-readings?sensorId=<id>&order=ASC` with optional `from`/`to` time filters; plot title shows sensor name and type
  - `statisticsLoadButton` -> explicit fetch + plot render
  - `statisticsDeviceCombo` / time controls / `statisticsAllDataCheck` -> debounced auto-reload of plot data
  - tab switch to `statisticsTab` -> refresh executor names + auto-load latest plot
  - if `/sensor-readings` is empty/incomplete, statistics plotting falls back to persisted `/user-logs` sensor-read command history
- Hidden/removed from active UI (not connected to core action flow):
  - legacy `statusButton` (`📊 System Status`)

### Button behavior details

- ON/OFF/SET buttons are enabled only when matching MANUAL executors exist.
- Mode switching remains explicit (`Set Mode` button).
- ON/OFF/SET flows do not auto-switch from `AUTO` to `MANUAL`.

### User-friendly DCM button set (implemented)

Server tab now uses end-user naming and one-action-per-button behavior:
- `System Health`
- `Refresh All Data`
- `Available Sensor Types`
- `Available Device Controls`
- `All Sensor Readings`
- `All Device States`
- `Change Device Mode`
- `Turn Device ON`
- `Turn Device OFF`
- `Set Device Value`

This keeps:
- one clear place for DCM state/actions
- explicit mode-first flow
- consistent digital vs value action paths
- reduced user confusion from developer-oriented naming

### Scheduling dispatch and waiting boundaries

- Scheduling is persisted with backend `/schedules` records and supports `scheduleMode` values:
  - `one_time` => dispatch once, then disable.
  - `recurring` => dispatch on each cron tick while enabled.
- At schedule trigger time, runtime dispatches command envelope to `greenhouse_commands`.
- Schedule execution status is dispatch-based:
  - one-time:
    - `completed` => command was successfully published and schedule was finalized.
    - `not_done` => publish failed and `metadata.lastDispatchError` is populated.
  - recurring:
    - `pending` remains active between dispatches.
    - `metadata.lastDispatchStatus` tracks latest dispatch result (`completed` or `failed`).
  - `canceled` => schedule was canceled by user before dispatch.
- Core waiting logic (`timeout`, `retry`, `backoff`) occurs later inside command execution path (`GreenhouseCoreClient.executeCommand`) after queue consumption.
- Therefore schedule completion is intentionally decoupled from final core response completion.

### User log restore flow

- On login/re-login the desktop asks whether to load previously saved user data.
- If user confirms, control/server table rows are restored from backend `/user-logs` (database-backed, user-scoped).
- If user chooses fresh start, old rows are not loaded for the current session view.

