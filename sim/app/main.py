import logging
import os
import random
from copy import deepcopy
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("greenhouse-core-simulator")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logs_dir = os.getenv("LOGS_DIR", "/app/logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, "simulator.log")

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s"
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.info("Simulator logger initialized")
    return logger


class CommandRequest(BaseModel):
    command: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    commandId: str
    sessionId: str


def default_logic_document() -> Dict[str, Any]:
    """Minimal tree matching frontend `normalize_existing_logic_payload` / upload shape."""
    return {
        "root": {
            "title": "root",
            "condition": "always",
            "args": [],
            "actions": [],
            "children": [],
        }
    }


class CoreSimulator:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.rng = random.Random(42)
        self._logic_document: Dict[str, Any] = deepcopy(default_logic_document())

        self.getter_schema = {
            "air_temp": "float",
            "humidity": "float",
            "light": "int",
            "co2": "int",
            "soil_moisture": "float",
            "soil_ph": "float",
        }

        self.executor_schema = {
            "fan_1": "bool",
            "heater_1": "bool",
            "actuator_1": "bool",
            "water_canal_1": "bool",
            "pump_pwm_1": "int",
        }

        self.sensor_units = {
            "temperature": "celsius",
            "humidity": "percent",
            "light": "lux",
            "co2": "ppm",
            "soil_moisture": "percent",
            "soil_ph": "pH",
        }

        self.sensor_id_map = {
            "temperature": "temp_sensor_1",
            "humidity": "humidity_sensor_1",
            "light": "light_sensor_1",
            "co2": "co2_sensor_1",
            "soil_moisture": "soil_moisture_sensor_1",
            "soil_ph": "soil_ph_sensor_1",
        }

        self.sensor_state = {
            "temperature": 22.0,
            "humidity": 58.0,
            "light": 750,
            "co2": 410,
            "soil_moisture": 52.0,
            "soil_ph": 6.5,
        }

        self.executor_state: Dict[str, Dict[str, Any]] = {
            "fan_1": {"id": 1, "mode": "AUTO", "type": "bool", "value": False},
            "heater_1": {"id": 2, "mode": "AUTO", "type": "bool", "value": False},
            "actuator_1": {"id": 3, "mode": "MANUAL", "type": "bool", "value": False},
            "water_canal_1": {"id": 4, "mode": "MANUAL", "type": "bool", "value": False},
            "pump_pwm_1": {"id": 5, "mode": "MANUAL", "type": "int", "value": 0},
        }

    def _sample_sensor(self, sensor: str) -> Any:
        if sensor == "temperature":
            self.sensor_state[sensor] = round(self.sensor_state[sensor] + self.rng.uniform(-0.6, 0.6), 1)
        elif sensor == "humidity":
            self.sensor_state[sensor] = round(max(0.0, min(100.0, self.sensor_state[sensor] + self.rng.uniform(-2.5, 2.5))), 1)
        elif sensor == "light":
            self.sensor_state[sensor] = int(max(0, min(2000, self.sensor_state[sensor] + self.rng.randint(-80, 80))))
        elif sensor == "co2":
            self.sensor_state[sensor] = int(max(250, min(2000, self.sensor_state[sensor] + self.rng.randint(-25, 25))))
        elif sensor == "soil_moisture":
            self.sensor_state[sensor] = round(max(0.0, min(100.0, self.sensor_state[sensor] + self.rng.uniform(-2.0, 2.0))), 1)
        elif sensor == "soil_ph":
            self.sensor_state[sensor] = round(max(0.0, min(14.0, self.sensor_state[sensor] + self.rng.uniform(-0.15, 0.15))), 2)
        return self.sensor_state[sensor]

    def _getter_snapshot(self, getter_key: str) -> Dict[str, Any]:
        sensor_map = {
            "air_temp": "temperature",
            "humidity": "humidity",
            "light": "light",
            "co2": "co2",
            "soil_moisture": "soil_moisture",
            "soil_ph": "soil_ph",
        }
        sensor = sensor_map.get(getter_key)
        if not sensor:
            raise KeyError(getter_key)
        value = self._sample_sensor(sensor)
        return {
            "valid": True,
            "stampMs": now_ms(),
            "data": {
                "type": self.getter_schema[getter_key],
                "value": value,
            },
        }

    def all_getters(self) -> Dict[str, Any]:
        return {key: self._getter_snapshot(key) for key in self.getter_schema.keys()}

    def one_getter(self, key: str) -> Dict[str, Any]:
        snapshot = self._getter_snapshot(key)
        with_key = deepcopy(snapshot)
        with_key["key"] = key
        return with_key

    def all_executors(self) -> Any:
        stamp = now_ms()
        rows = []
        for name, info in self.executor_state.items():
            rows.append(
                {
                    "id": info["id"],
                    "name": name,
                    "valid": True,
                    "stampMs": stamp,
                    "mode": info["mode"],
                    "data": {
                        "type": info["type"],
                        "value": info["value"],
                    },
                }
            )
        return rows

    def executor_action(self, name: str, action: str, body: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        normalized_action = action.strip().lower()
        if name not in self.executor_state:
            raise HTTPException(status_code=404, detail=f"Unknown executor: {name}")

        record = self.executor_state[name]
        body = body or {}
        value = body.get("value")

        if normalized_action == "mode":
            if value is None or str(value).strip() == "":
                raise HTTPException(status_code=400, detail='Body field "value" is required')
            mode_text = str(value).strip().lower()
            if mode_text in ("manual", "0"):
                record["mode"] = "MANUAL"
            elif mode_text in ("auto", "1"):
                record["mode"] = "AUTO"
            else:
                raise HTTPException(status_code=400, detail='Mode value must be one of: manual, auto, 0, 1')
            return {"ok": True, "name": name, "action": "mode", "value": record["mode"].lower()}

        if normalized_action == "on":
            if record["type"] == "bool":
                record["value"] = True
            return {"ok": True, "name": name, "action": "on"}

        if normalized_action == "off":
            if record["type"] == "bool":
                record["value"] = False
            return {"ok": True, "name": name, "action": "off"}

        if normalized_action == "set":
            if value is None or str(value).strip() == "":
                raise HTTPException(status_code=400, detail='Body field "value" is required')
            if record["type"] == "int":
                try:
                    parsed = int(float(str(value)))
                except ValueError as error:
                    raise HTTPException(status_code=400, detail="Value must be numeric for int executors") from error
                record["value"] = parsed
            else:
                lowered = str(value).strip().lower()
                if lowered in ("1", "true", "on"):
                    record["value"] = True
                elif lowered in ("0", "false", "off"):
                    record["value"] = False
                else:
                    raise HTTPException(status_code=400, detail="Value must be boolean-like for bool executors")
            return {"ok": True, "name": name, "action": "set", "value": record["value"]}

        raise HTTPException(status_code=400, detail=f"Unsupported executor action: {action}")

    def get_logic_full(self) -> Dict[str, Any]:
        return deepcopy(self._logic_document)

    def upload_logic(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Logic upload body must be a JSON object")
        root = payload.get("root")
        if not isinstance(root, dict):
            raise HTTPException(status_code=400, detail='Logic payload must contain an object "root"')
        self._logic_document = deepcopy(payload)
        self.logger.info("Logic configuration uploaded (root title=%s)", root.get("title", ""))
        return {"ok": True}

    def reload_logic(self) -> Dict[str, Any]:
        self.logger.info("Logic reload requested (simulator uses in-memory config)")
        return {"ok": True, "reloadedAt": now_iso()}

    def execute_command(self, payload: CommandRequest) -> Dict[str, Any]:
        command = payload.command
        params = payload.parameters or {}
        result = None
        error = None
        success = True

        if command == "read_temperature_data":
            result = self._read_sensor_payload("temperature", "temperature")
        elif command == "read_humidity_data":
            result = self._read_sensor_payload("humidity", "humidity")
        elif command == "read_light_data":
            result = self._read_sensor_payload("light", "light")
        elif command == "read_co2_data":
            result = self._read_sensor_payload("co2", "co2")
        elif command == "read_soil_moisture_data":
            result = self._read_sensor_payload("soil_moisture", "soilMoisture")
        elif command == "read_soil_ph_data":
            result = self._read_sensor_payload("soil_ph", "soilPH")
        elif command == "read_sensor":
            sensor_name = str(params.get("sensor", "temperature")).strip().lower()
            remap = {
                "temperature": ("temperature", "temperature"),
                "humidity": ("humidity", "humidity"),
                "light": ("light", "light"),
                "co2": ("co2", "co2"),
                "soil_moisture": ("soil_moisture", "soilMoisture"),
                "soil_ph": ("soil_ph", "soilPH"),
            }
            if sensor_name not in remap:
                success = False
                error = f"Unsupported sensor: {sensor_name}"
            else:
                sensor_key, output_key = remap[sensor_name]
                result = self._read_sensor_payload(sensor_key, output_key)
        elif command == "switch_fan":
            result = self._switch_device("fan_1", params.get("fanId", "fan_1"), params.get("action", "toggle"), include_speed=True)
        elif command == "switch_heater":
            result = self._switch_device("heater_1", params.get("heaterId", "heater_1"), params.get("action", "toggle"), include_temp=True)
        elif command == "switch_actuator":
            result = self._switch_device("actuator_1", params.get("actuatorId", "actuator_1"), params.get("action", "toggle"))
        elif command == "switch_water_canal":
            result = self._switch_device("water_canal_1", "water_canal_1", params.get("action", "toggle"), response_key="deviceId")
        else:
            success = False
            error = f"Unknown command: {command}"

        response = {
            "success": success,
            "result": result if success else None,
            "error": error,
            "commandId": payload.commandId,
            "command": command,
            "timestamp": now_iso(),
        }
        return response

    def _read_sensor_payload(self, sensor_name: str, output_key: str) -> Dict[str, Any]:
        value = self._sample_sensor(sensor_name)
        return {
            output_key: value,
            "unit": self.sensor_units[sensor_name],
            "timestamp": now_iso(),
            "sensorId": self.sensor_id_map[sensor_name],
            "location": "greenhouse_main",
        }

    def _switch_device(
        self,
        state_key: str,
        device_id: str,
        action: Any,
        include_speed: bool = False,
        include_temp: bool = False,
        response_key: str = "actuatorId",
    ) -> Dict[str, Any]:
        record = self.executor_state[state_key]
        previous = "on" if record["value"] else "off"
        action_text = str(action or "toggle").strip().lower()
        if action_text == "toggle":
            record["value"] = not record["value"]
        elif action_text == "on":
            record["value"] = True
        elif action_text == "off":
            record["value"] = False
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported action: {action_text}")

        status = "on" if record["value"] else "off"
        payload = {
            response_key: str(device_id),
            "status": status,
            "previousStatus": previous,
            "timestamp": now_iso(),
        }
        if include_speed:
            payload["speed"] = 50 if status == "on" else 0
        if include_temp:
            payload["temperature"] = 24 if status == "on" else 0
        return payload


logger = setup_logger()
app = FastAPI(title="Greenhouse Core Simulator", version="1.0.0")
sim = CoreSimulator(logger=logger)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_log_middleware(request, call_next):
    logger.debug("Incoming request: %s %s", request.method, request.url.path)
    response = await call_next(request)
    return response


@app.get("/health")
@app.get("/api/v1/health")
@app.get("/metadata/health/")
@app.get("/api/v1/metadata/health/")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "greenhouse-core-simulator",
        "timestamp": now_iso(),
        "version": "1.0.0",
    }


@app.get("/status")
def status() -> Dict[str, Any]:
    return {"status": "ok"}


@app.get("/schema/getters")
def getter_schema() -> Dict[str, str]:
    return sim.getter_schema


@app.get("/schema/executors")
def executor_schema() -> Dict[str, str]:
    return sim.executor_schema


@app.get("/getters")
def getters() -> Dict[str, Any]:
    return sim.all_getters()


@app.get("/getters/{key}")
def getter_by_key(key: str) -> Dict[str, Any]:
    try:
        return sim.one_getter(key)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Unknown getter key: {key}") from error


@app.get("/executors")
def executors() -> Any:
    return sim.all_executors()


@app.post("/api/executors/{name}/{action}")
def executor_action(
    name: str,
    action: str,
    payload: Optional[Dict[str, Any]] = Body(default=None),
) -> Dict[str, Any]:
    return sim.executor_action(name=name, action=action, body=payload)


@app.get("/api/json/logic/full")
def logic_full() -> Dict[str, Any]:
    return sim.get_logic_full()


@app.post("/api/json/logic/upload")
def logic_upload(body: Dict[str, Any]) -> Dict[str, Any]:
    return sim.upload_logic(body)


@app.post("/api/json/logic/reload")
def logic_reload() -> Dict[str, Any]:
    return sim.reload_logic()


@app.post("/api/v1/commands/execute")
def execute_command(payload: CommandRequest) -> Dict[str, Any]:
    logger.info(
        "Command received: %s",
        payload.command,
        extra={
            "commandId": payload.commandId,
            "sessionId": payload.sessionId,
            "command": payload.command,
            "parameters": payload.parameters,
        },
    )
    response = sim.execute_command(payload)
    return response
