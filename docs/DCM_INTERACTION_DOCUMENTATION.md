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
  - `healthButton` -> `view_core_status` (retitled to `Core Status`)
  - `refreshButton` -> `refresh_all_status` (retitled to `Refresh Snapshot`)
  - `statsButton` -> `view_getter_schema` (`Getter Schema`)
  - `sessionsButton` -> `view_executor_schema` (`Executor Schema`)
  - `cacheKeysButton` -> `view_getters` (`Getters`)
  - `queuesButton` -> `view_executors` (`Executors`)
  - `clearCacheButton` -> `prompt_switch_executor_mode` (`Set Mode`)
  - `testCommandButton` -> `prompt_executor_on` (`Executor ON`)
  - `logFilesButton` -> `prompt_executor_off` (`Executor OFF`)
  - `viewLogButton` -> `prompt_executor_set` (`Executor SET`)
- Connected control-tab actions (RabbitMQ command flow, not executor HTTP API):
  - sensor reads and toggle controls for water/fan/heater/actuator
- Hidden/removed from active UI (not connected to core action flow):
  - legacy `statusButton` (`📊 System Status`)
  - scheduling local-only buttons `cancelScheduledButton` and `clearScheduledButton`
  - local table-level `Clear Table` button

### Button behavior details

- ON/OFF/SET buttons are enabled only when matching MANUAL executors exist.
- Mode switching remains explicit (`Set Mode` button).
- ON/OFF/SET flows do not auto-switch from `AUTO` to `MANUAL`.

### Recommended user-friendly DCM button set (spec)

To align UI with actual DCM logic exposed by root backend API routes, keep server tab focused on:
- `Core Status`
- `Refresh Snapshot`
- `Set Executor Mode`
- `Executor ON`
- `Executor OFF`
- `Executor SET Value`

This keeps:
- one clear place for DCM state/actions
- explicit mode-first flow
- consistent digital vs value action paths
- reduced user confusion from non-connected controls

