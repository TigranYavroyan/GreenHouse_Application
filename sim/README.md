# Greenhouse Core Python Simulator

This simulator emulates the Greenhouse Core HTTP contract used by the backend.

## Run Locally

```bash
cd sim
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 3001
```

## Run With Docker

From workspace root:

```bash
docker compose up -d greenhouse-core-sim
```

## Contract Endpoints

These paths match `backend/clients/greenhouseCoreClient.js` (what the Node backend calls on `GREENHOUSE_CORE_URL`):

- `GET /status`
- `GET /schema/getters`
- `GET /schema/executors`
- `GET /getters`
- `GET /getters/{key}`
- `GET /executors`
- `POST /api/executors/{name}/{action}` where action is `mode|on|off|set`
- `GET /api/json/logic/full`
- `POST /api/json/logic/upload`
- `POST /api/json/logic/reload`
- `POST /api/v1/commands/execute` (direct HTTP command channel; backend normally uses getters/executors instead)

If `GREENHOUSE_CORE_URL` includes an `/api/v1` base (e.g. `http://core:3001/api/v1`), the same routes are also mounted under that prefix (so `GET /api/v1/status` + `GET /status` both work). Disable the duplicate tree with:

```bash
CORE_DUPLICATE_ROUTES_UNDER_API_V1=false
```

Health aliases:

- `GET /health`
- `GET /api/v1/health`
- `GET /metadata/health/`
- `GET /api/v1/metadata/health/`

## Supported Commands

- `read_temperature_data`
- `read_humidity_data`
- `read_light_data`
- `read_co2_data`
- `read_soil_moisture_data`
- `read_soil_ph_data`
- `read_sensor` (`sensor` parameter: `temperature|humidity|light|co2|soil_moisture|soil_ph`)
- `switch_water_canal` (`action`: `on|off|toggle`)
- `switch_actuator` (`actuatorId`, `action`)
- `switch_fan` (`fanId`, `action`)
- `switch_heater` (`heaterId`, `action`)

## Smoke Checks

```bash
curl -sS http://localhost:3001/status
curl -sS http://localhost:3001/getters
curl -sS http://localhost:3001/executors
curl -sS -X POST http://localhost:3001/api/v1/commands/execute -H "Content-Type: application/json" -d '{"command":"read_temperature_data","parameters":{"sensor":"temperature"},"commandId":"test-command-id","sessionId":"test-session-id"}'
```
