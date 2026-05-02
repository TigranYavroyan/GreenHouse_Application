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
- Logic Builder supports undo/redo: **Ctrl+Z** / **Ctrl+Y** (and **Ctrl+Shift+Z** where the platform maps redo); moving nodes records a single undo step per completed drag; loading or rebuilding logic from core clears the undo stack.

---

## Step-by-Step Implementation Plan (Application Side)

This section is the execution checklist for implementing the feature in this repository.

### Step 0: Define delivery boundaries
- Keep transport path as: Desktop -> Backend API -> GreenHouse core.
- Do not add RabbitMQ calls for this tab.
- Keep existing routes and message contracts untouched.
- Implement in phases, with phase gates (working end-to-end before moving forward).

### Step 1: Backend pass-through for logic API

Purpose:
- Expose core logic endpoints through existing backend so desktop uses one API origin.

Required routes to add:
- `GET /api/json/logic/tree`
- `GET /api/json/logic/runtime`
- `GET /api/json/logic/full`
- `POST /api/json/logic/upload`
- `POST /api/json/logic/reload`

Likely files to update:
- `backend/clients/greenhouseCoreClient.js`
- `backend/modules/core/core.service.js`
- `backend/modules/core/core.controller.js`
- `backend/routers/core.js`

Implementation notes:
- Use existing `requestJson()` pattern in `greenhouseCoreClient`.
- For upload, forward exact JSON body without shape rewriting.
- Keep error style consistent: `{ "error": "<message>" }`.
- Keep routes thin (controller -> service -> client), no business logic in routes.

Definition of done:
- Can curl backend route and receive core response for all 5 endpoints.
- Error codes/messages propagate correctly.

### Step 2: Desktop HTTP client extension

Purpose:
- Add typed client methods for logic operations.

Likely files:
- `frontend/modules/core_api_client.py`
- `frontend/modules/core_dtos.py` (only if introducing DTOs for logic response wrappers)

Required methods:
- `get_logic_tree()`
- `get_logic_runtime()`
- `get_logic_full()`
- `upload_logic(payload: dict)`
- `reload_logic()`

Implementation notes:
- Reuse `_request()` helper and auth behavior.
- Preserve pass-through JSON for logic payloads (no lossy conversion).
- Keep upload body as user/model generated dict.

Definition of done:
- Existing UI can call methods directly and print/inspect returned JSON.

### Step 3: Add new Logic tab in desktop UI

Purpose:
- Provide user-visible place for logic management.

Likely files:
- `frontend/front.ui`
- `frontend/modules/greenhouse.py`
- new mixin file recommended: `frontend/modules/greenhouse_logic_mixin.py`

Suggested tab blocks:
1. Logic summary/status row
2. Tree/runtime viewer panel
3. Raw JSON editor panel
4. Action buttons: Load, Validate, Upload, Reload

Implementation notes:
- Keep tab responsibilities isolated in a new mixin (same pattern as scheduling/statistics/server mixins).
- Wire tab initialization from `GreenhouseDesktop.__init__`.
- Add `tabWidget.currentChanged` behavior only if needed for auto-refresh optimization.

Definition of done:
- Tab renders.
- Buttons invoke API methods.
- Success/error shown with existing dialog/status style.

### Step 4: Implement raw JSON workflow first (mandatory foundation)

Purpose:
- Ensure full functionality before block editor complexity.

Flow:
1. Load current (`logic/full`) into editor.
2. Validate JSON locally.
3. Upload via `logic/upload`.
4. Reload from file via `logic/reload`.
5. Refresh viewer and status indicators.

Validation baseline (phase 1):
- JSON parse success.
- root exists.
- node fields are arrays/strings where required.

Definition of done:
- User can round-trip logic JSON end-to-end from desktop.

### Step 5: Internal frontend logic model for block editor

Purpose:
- Establish stable in-memory model independent of widget implementation.

Recommended canonical model:
- `LogicDocument { root: LogicNode }`
- `LogicNode { id, title, condition, args, actions, children }`
- `LogicAction { id, target, valueType, value, trigger, enabled }`

Rules:
- Keep `id` frontend-only (not sent to server).
- Serializer strips runtime/frontend-only fields.
- Deserializer tolerates runtime fields in incoming payload.

Definition of done:
- `json -> model -> json` round-trip is stable and server-compatible.

### Step 6: Build block-scheme UI editor

Purpose:
- Visual editing of rule tree and actions.

Pragmatic approach:
- Start with tree-form editor (hierarchical list with add/remove/reorder) as phase 2a.
- Move to node-graph canvas (library-based) as phase 2b if needed.

Minimum operations:
- add/remove node
- nest/un-nest (parent/child)
- edit condition and args
- add/remove/edit action
- duplicate node/action

Strong recommendation:
- Keep raw JSON editor available as fallback and debug path.

Definition of done:
- User can create non-trivial tree visually and upload successfully.

### Step 7: Advanced validation engine (before production use)

Purpose:
- Prevent invalid logic from being uploaded.

Validation levels:
1. Structural: required fields/array types.
2. Semantic:
   - condition key exists in supported list
   - args count aligns with selected condition
   - trigger in supported set
   - valueType in supported set
3. Environment-aware:
   - action target exists in `/schema/executors`
   - optional type compatibility with executor schema

UX behavior:
- Show inline validation errors on blocks and in summary panel.
- Disable Upload when blocking errors exist.

Definition of done:
- Invalid configs are blocked locally with clear messages.

### Step 8: Runtime observability in UI

Purpose:
- Help users understand what logic is doing live.

Display from `logic/full` and/or `logic/runtime`:
- per-node active/inactive state
- local/effective result
- resolved args
- last error
- last fire/eval times

Definition of done:
- User can visually debug rule behavior without opening external tools.

### Step 9: Safe rollout and backward compatibility

Release order:
1. backend pass-through + client support
2. raw JSON tab workflow
3. tree-form/block editor
4. advanced validation and polish

Compatibility constraints:
- Keep existing Server/Scheduling/Control tabs unchanged.
- Keep existing core/executor flows intact.
- Keep API auth and error patterns consistent.

### Step 10: Testing checklist

Backend tests:
- logic routes proxy success and error codes
- upload forwards body intact

Frontend/manual tests:
- load/upload/reload success
- malformed JSON rejected
- unsupported condition rejected
- missing root rejected
- manual mode logic guard observed in runtime
- nested tree behavior (parent false disables child actions)

End-to-end tests:
- upload blink-style sample logic
- verify executor desired/actual updates through existing server views

---

## Concrete File-Level Task Breakdown

### Backend
- `backend/clients/greenhouseCoreClient.js`
  - add methods for logic get/upload/reload via `/api/json/*`
- `backend/modules/core/core.service.js`
  - expose new service methods
- `backend/modules/core/core.controller.js`
  - add handler methods for logic routes
- `backend/routers/core.js`
  - register logic routes

### Frontend
- `frontend/modules/core_api_client.py`
  - add logic API methods
- `frontend/front.ui`
  - add new tab with controls and containers
- `frontend/modules/greenhouse.py`
  - initialize/wire logic tab setup
- `frontend/modules/greenhouse_logic_mixin.py` (new)
  - tab behavior, API calls, validation, rendering

Optional helper modules (recommended):
- `frontend/modules/logic_models.py`
- `frontend/modules/logic_serializer.py`
- `frontend/modules/logic_validator.py`

---

## UI/UX Implementation Approach

### Primary interaction model
- Left: block/tree editor
- Right: selected node/action properties
- Bottom: validation panel + upload status
- Secondary panel: raw JSON preview/editor

### Commands
- `Load from server`
- `Validate`
- `Upload`
- `Reload from file`
- `Discard local changes`

### Guardrails
- unsaved changes indicator
- confirmation before reload/discard
- upload disabled on blocking errors

---

## Definition of Fully Complete Feature

The feature is considered fully complete when:
- backend exposes logic pass-through endpoints,
- desktop has a dedicated logic tab,
- user can visually build full Composite trees,
- generated JSON matches core parser contract,
- validations prevent common config mistakes,
- runtime panel helps debug active/inactive branches,
- behavior in greenhouse core matches expected Composite semantics.

---

## Modularity and SOLID Requirements (must follow)

This feature must preserve strong modularity and SOLID design across backend and frontend.

### S: Single Responsibility Principle
- Each class/module should do one thing:
  - API transport (HTTP calls),
  - data mapping/serialization,
  - validation,
  - UI rendering,
  - interaction orchestration.
- Do not mix UI widget code with HTTP request logic.
- Do not place business/validation rules inside route files or Qt event handlers.

### O: Open/Closed Principle
- Add logic features by extending modules, not modifying unrelated code paths.
- Conditions/triggers/value types should be represented as registries/constants so new types can be added with minimal code changes.
- Keep validator rule sets extensible (rule table pattern preferred over deeply nested conditionals).

### L: Liskov Substitution Principle
- If abstractions are introduced (e.g., validator interfaces, serializer interfaces), implementations must remain substitutable without changing calling code.
- Avoid special-case behavior that breaks shared interfaces.

### I: Interface Segregation Principle
- Keep small focused interfaces/services:
  - logic read/write API interface,
  - validation interface,
  - serialization interface.
- UI mixin should consume narrow methods (`load`, `upload`, `reload`) rather than broad generic service contracts.

### D: Dependency Inversion Principle
- UI layer depends on abstractions/helpers, not concrete transport internals.
- Inject API client dependency through existing app initialization path (`setup_core_panel` style).
- Keep core model/validator independent from widget toolkit where possible.

---

## Layered Module Boundaries (recommended)

### Backend layering
- Router layer: route declarations only.
- Controller layer: request parsing + HTTP response mapping only.
- Service layer: use-case orchestration only.
- Client layer: outbound HTTP transport to greenhouse core.

No cross-layer shortcuts:
- router -> client directly (avoid),
- controller with embedded HTTP transport (avoid).

### Frontend layering
- UI layer: tab widgets, dialogs, signals/slots.
- Application layer: logic tab coordinator/mixin (workflow orchestration).
- Domain/model layer: logic node/action document model.
- Infrastructure layer: HTTP client (`CoreApiClient`), serialization helpers.

No cross-layer shortcuts:
- raw network calls directly from button handlers (avoid),
- widget state used as source of truth for model persistence (avoid).

---

## Likely Files by Responsibility (modular map)

### Backend
- `backend/routers/core.js`
  - add route declarations for logic endpoints only.
- `backend/modules/core/core.controller.js`
  - add request handlers; no transport logic.
- `backend/modules/core/core.service.js`
  - add use-case methods; no HTTP details.
- `backend/clients/greenhouseCoreClient.js`
  - add concrete core HTTP methods for logic endpoints.

### Frontend transport
- `frontend/modules/core_api_client.py`
  - add typed logic methods for load/upload/reload.

### Frontend logic domain (new, recommended)
- `frontend/modules/logic_models.py`
  - `LogicDocument`, `LogicNode`, `LogicAction` dataclasses.
- `frontend/modules/logic_serializer.py`
  - json <-> model conversion, payload normalization.
- `frontend/modules/logic_validator.py`
  - structural + semantic + environment-aware validation.
- `frontend/modules/logic_constants.py`
  - condition list, trigger list, value type list, arg specs.

### Frontend UI/application
- `frontend/modules/greenhouse_logic_mixin.py` (new)
  - tab orchestration, load/validate/upload/reload actions.
- `frontend/front.ui`
  - logic tab widgets/layout.
- `frontend/modules/greenhouse.py`
  - mixin wiring and setup invocation.

---

## Design Patterns to Apply

### Recommended
- Strategy pattern for validation rules (per rule family).
- Mapper/Adapter for dto/model/json conversion.
- Facade service in mixin for UI actions (`load_logic`, `validate_logic`, `upload_logic`, `reload_logic`).
- Immutable-ish domain model updates where practical (reduce side effects).

### Avoid
- God mixin containing transport + validation + rendering + model mutation in one class.
- Duplicated serialization logic in UI event handlers.
- Hidden implicit conversions on upload path.

---

## Dependency and coupling rules

- UI must depend on `CoreApiClient` methods, not backend route strings spread across many files.
- Validation must work independently from UI widgets (callable in tests/headless mode).
- Serializer must not read widget state directly; it takes model input only.
- Keep new logic modules free of RabbitMQ dependencies.

---

## Refactoring safety rules during implementation

- Keep existing tabs/features behavior unchanged unless explicitly required.
- Keep each phase mergeable and testable independently.
- Prefer additive changes; avoid broad rewrites.
- If introducing shared helpers, move carefully and avoid breaking existing imports.
