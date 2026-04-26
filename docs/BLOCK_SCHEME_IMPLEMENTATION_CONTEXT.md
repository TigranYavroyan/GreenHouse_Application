# Block-Scheme Logic Implementation Context

Use this file as reusable context for new chats about implementing the greenhouse logic block-scheme tab in the desktop app.

## Reusable Prompt (copy/paste to new chat)

```md
Use `docs/BLOCK_SCHEME_IMPLEMENTATION_CONTEXT.md` as the source of truth for this task.

Goal:
- Implement the frontend block-scheme (visual rule builder) for greenhouse logic.
- Ensure full compatibility with GreenHouse2 Composite logic model and API contract.
- Keep architecture clean and consistent with existing project boundaries.

Before coding:
- Read and follow the context file fully.
- Reuse existing API/client modules where possible.
- Preserve current message/API contracts.
```

---

## Task Goal

Implement a new desktop tab for building and managing greenhouse logic as a block-scheme (visual flow), fully compatible with the `GreenHouse2/demo` Composite logic engine and JSON contract.

The tab must allow:
- loading current logic from API,
- editing visually (and optionally raw JSON),
- validating,
- uploading to server,
- reloading from server-side file.

---

## Source of Truth (Core Side)

Core logic lives in:
- `GreenHouse2/demo/Logic/RuleTree.hpp`
- `GreenHouse2/demo/Logic/RuleNode.hpp`
- `GreenHouse2/demo/Logic/RuleEngine.hpp`
- `GreenHouse2/demo/Logic/ConditionContext.hpp`
- `GreenHouse2/demo/Logic/ArgumentResolver.hpp`
- `GreenHouse2/demo/Logic/LogicJsonController.hpp`
- `GreenHouse2/demo/Logic/ActionModel.hpp`
- `GreenHouse2/demo/logic.json`
- `GreenHouse2/demo/main.cpp` (wiring)

HTTP/API layer lives in:
- `GreenHouse2/demo/API/HttpServer.hpp`
- `GreenHouse2/demo/API/JsonAPI.hpp`
- `GreenHouse2/demo/API/web/index.html`
- `GreenHouse2/demo/API/web/app.js`
- `GreenHouse2/demo/API/HTTP_API.md`

---

## Composite Logic Model (must match)

### Tree structure
- `RuleTree` has one `root`.
- Each `RuleNode` has:
  - `title: string`
  - `condition: string`
  - `args: string[]`
  - `actions: ActionModel[]`
  - `children: RuleNode[]`
  - runtime state (computed by engine, not required for upload)

### Evaluation model
- Engine traverses tree top-down every tick.
- For each node:
  - resolve args,
  - evaluate local condition,
  - compute `effectiveResult = parentEffective && localResult`,
  - process actions based on trigger mode.
- Child nodes are evaluated with parent `effectiveResult` (Composite gating).

### Runtime behavior
- Tracks per-node runtime:
  - `localResult`
  - `effectiveResult`
  - `prevEffectiveResult`
  - `lastEvalMs`
  - `lastFireMs`
  - `lastError`
  - `resolvedArgs`

---

## Action Model (must match)

Each action has:
- `target: string` (executor name)
- `valueType: "bool" | "int" | "double" | "string"`
- `value: string` (literal, parsed later)
- `trigger: "on_enter" | "on_exit" | "while_true" | "while_false"`
- `enabled: boolean`

### Trigger semantics
- `on_enter`: fire on false->true transition
- `on_exit`: fire on true->false transition
- `while_true`: fire each tick while effective true
- `while_false`: fire each tick while effective false

---

## Condition Strategies (currently supported)

### Double-like
- `gt`, `lt`, `eq`, `neq`, `gte`, `lte`, `in_range`, `out_of_range`, `always`, `never`

### Int64-like
- `gt_i64`, `lt_i64`, `eq_i64`, `neq_i64`, `gte_i64`, `lte_i64`, `in_range_i64`, `out_of_range_i64`, `always_i64`, `never_i64`

### Modulo family
- `mod_part`, `mod_lt`, `mod_lte`, `mod_gt`, `mod_gte`, `mod_eq`, `mod_neq`, `mod_in_range`, `mod_out_of_range`

### Bool
- `is_true`, `is_false`, `always_bool`, `never_bool`

---

## Argument Resolution Rules

Resolver order per arg token:
1. Built-in time token (if matched),
2. getter key from GlobalState,
3. raw literal string.

Known time helpers:
- `time.unix_ms`
- `time.hour`
- `time.minute`
- `time.second`
- `time.daily_hhmmss`

Then `ConditionContext` converts args to target type.

---

## Mode / Override Rules (critical)

Logic must **not** overwrite manual operator control:
- if executor actual mode is `MANUAL` or desired mode is `MANUAL`, logic action is skipped.

So block-scheme UI must represent/assume:
- logic writes desired AUTO state,
- manual mode has priority.

---

## Execution Pipeline (full path)

1. `LogicJsonController` loads/uploads JSON tree.
2. `RuleEngine.tick()` evaluates conditions and writes desired executor state.
3. `ExecutorStateBridge.tick()`:
   - syncs modes,
   - deduplicates desired vs actual,
   - maps executor names to DCM binding,
   - enqueues hardware commands,
   - updates actual/pending/error state.
4. `Executor.tick()` executes queued commands.

---

## JSON Contract for Logic Upload

### Minimal upload shape

```json
{
  "root": {
    "title": "root_name",
    "condition": "always",
    "args": [],
    "actions": [],
    "children": []
  }
}
```

### Node shape
- required for parse:
  - `title` (fallback exists but should be sent),
  - `condition` (fallback exists but should be sent),
  - `args` array,
  - `actions` array,
  - `children` array.
- runtime fields may exist in read payload but are not required in upload payload.

---

## Core Logic API Endpoints (already implemented in GreenHouse2)

Via generic JSON API:
- `GET /api/json/logic/tree`
- `GET /api/json/logic/runtime`
- `GET /api/json/logic/full`
- `POST /api/json/logic/upload`
- `POST /api/json/logic/reload`

Also available:
- `GET /api/json` (route discovery)

---

## Current Project Integration Status

### Desktop side
- Desktop already uses `CoreApiClient` (`frontend/modules/core_api_client.py`) for core HTTP operations.
- Server tab already integrates status/getters/executors actions.

### Backend side
- Backend currently proxies:
  - `/status`, `/schema/getters`, `/schema/executors`, `/getters`, `/getters/:key`, `/executors`, `/api/executors/:name/:action`
- Backend does **not yet** expose `/api/json/logic/*` pass-through routes.

---

## Recommended Implementation Strategy

### Phase 1 (fast + safe)
- Add logic tab with:
  - load current logic JSON,
  - validate JSON,
  - upload,
  - reload from file,
  - show runtime tree/summary.
- Reuse existing HTTP client/service patterns.

### Phase 2
- Add visual block-scheme editor that serializes/deserializes to the exact JSON contract.
- Keep raw JSON editor as fallback/debug mode.

### Phase 3
- Add rich validation:
  - condition key validity,
  - arg count/type checks per condition,
  - executor target existence/type checks,
  - trigger/valueType/value consistency.

---

## Architecture Constraints for This Project

- Desktop UI logic stays in frontend modules/mixins.
- Do not add RabbitMQ logic to the new block-scheme tab flow.
- Use existing backend/core HTTP path for this feature.
- Reuse existing `CoreApiClient` patterns and DTO style.
- Keep code SOLID/KISS and avoid duplicate transport logic.

---

## Acceptance Criteria for Final Feature

- User can fetch current logic (`logic/full`).
- User can edit logic via blocks and/or JSON.
- User can validate before send.
- User can upload valid logic and receive clear success/error feedback.
- User can reload logic from file via API.
- Generated JSON is accepted by `LogicJsonController` without manual patching.
- Behavior in runtime matches Composite semantics (parent gating, triggers, manual override guard).

