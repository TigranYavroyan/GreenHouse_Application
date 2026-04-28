import requests
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote, urlencode

from modules.core_dtos import (
    CoreStatusDto,
    ExecutorSnapshotDto,
    GetterSnapshotDto,
    SetExecutorModeRequestDto,
    SetExecutorValueRequestDto,
    parse_executor_schema,
    parse_executor_snapshots,
    parse_getter_schema,
    parse_getter_snapshots,
)


class ApiRequestError(RuntimeError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class UnauthorizedError(ApiRequestError):
    pass


class CoreApiClient:
    def __init__(
        self,
        backend_url: str,
        timeout_seconds: int = 5,
        auth_token_provider: Optional[Callable[[], Optional[str]]] = None,
    ):
        self.backend_url = backend_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.auth_token_provider = auth_token_provider

    def _build_headers(self, requires_auth: bool = True) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if not requires_auth:
            return headers

        if not callable(self.auth_token_provider):
            return headers

        token = str(self.auth_token_provider() or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _request(
        self,
        path: str,
        method: str = "GET",
        data: Dict[str, Any] = None,
        requires_auth: bool = True,
        query_params: Dict[str, Any] = None,
    ) -> Any:
        url = f"{self.backend_url}{path}"
        if query_params:
            normalized_params = {}
            for key, value in (query_params or {}).items():
                if value is None:
                    continue
                text_value = str(value).strip()
                if not text_value:
                    continue
                normalized_params[key] = text_value
            if normalized_params:
                url = f"{url}?{urlencode(normalized_params)}"
        headers = self._build_headers(requires_auth=requires_auth)
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=self.timeout_seconds)
        elif method == "POST":
            response = requests.post(url, json=data or {}, headers=headers, timeout=self.timeout_seconds)
        elif method == "PATCH":
            response = requests.patch(url, json=data or {}, headers=headers, timeout=self.timeout_seconds)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=self.timeout_seconds)
        else:
            raise ValueError(f"Unsupported method: {method}")

        try:
            payload = response.json()
        except ValueError:
            payload = {"error": response.text or f"HTTP {response.status_code}"}
        if response.status_code >= 400:
            message = payload.get("error") if isinstance(payload, dict) else str(payload)
            normalized_message = str(message or "").strip().lower()
            is_auth_context_error = "user context" in normalized_message and "required" in normalized_message
            if response.status_code in (401, 403) or is_auth_context_error:
                raise UnauthorizedError(message or "Unauthorized", response.status_code)
            raise ApiRequestError(message or f"Request failed: {response.status_code}", response.status_code)
        return payload

    def _expect_payload_type(self, payload: Any, expected_type: type, endpoint: str) -> Any:
        if isinstance(payload, expected_type):
            return payload
        raise RuntimeError(
            f"Unexpected response shape from {endpoint}: expected {expected_type.__name__}, got {type(payload).__name__}"
        )

    def get_status(self) -> CoreStatusDto:
        payload = self._request("/status")
        payload = self._expect_payload_type(payload, dict, "/status")
        return CoreStatusDto.from_dict(payload)

    def login(self, username: str, password: str) -> str:
        payload = self._request(
            "/auth/login",
            method="POST",
            data={"username": str(username or "").strip(), "password": str(password or "")},
            requires_auth=False,
        )
        payload = self._expect_payload_type(payload, dict, "/auth/login")
        token = str(payload.get("token", "")).strip()
        if not token:
            raise RuntimeError("Login succeeded but token is missing from response.")
        return token

    def register(self, username: str, password: str, email: str = "") -> Dict[str, Any]:
        request_payload: Dict[str, Any] = {
            "username": str(username or "").strip(),
            "password": str(password or ""),
        }
        normalized_email = str(email or "").strip()
        if normalized_email:
            request_payload["email"] = normalized_email
        payload = self._request("/auth/register", method="POST", data=request_payload, requires_auth=False)
        return payload if isinstance(payload, dict) else {"result": payload}

    def get_current_user(self) -> Dict[str, Any]:
        payload = self._request("/users", method="GET", requires_auth=True)
        if isinstance(payload, dict):
            data = payload.get("data", [])
            if isinstance(data, list) and data:
                first = data[0]
                if isinstance(first, dict):
                    return first
        raise RuntimeError("Unable to resolve current user from /users response.")

    def get_getter_schema(self) -> Dict[str, str]:
        payload = self._request("/schema/getters")
        payload = self._expect_payload_type(payload, dict, "/schema/getters")
        return parse_getter_schema(payload)

    def get_executor_schema(self) -> Dict[str, str]:
        payload = self._request("/schema/executors")
        payload = self._expect_payload_type(payload, dict, "/schema/executors")
        return parse_executor_schema(payload)

    def get_getters(self) -> List[GetterSnapshotDto]:
        payload = self._request("/getters")
        payload = self._expect_payload_type(payload, dict, "/getters")
        return parse_getter_snapshots(payload)

    def get_getter(self, key: str) -> GetterSnapshotDto:
        safe_key = quote(str(key or "").strip(), safe="")
        payload = self._request(f"/getters/{safe_key}")
        if not isinstance(payload, dict):
            payload = {}
        key_value = str(payload.get("key", key))
        return GetterSnapshotDto.from_dict(key_value, payload)

    def get_executors(self) -> List[ExecutorSnapshotDto]:
        payload = self._request("/executors")
        payload = self._expect_payload_type(payload, list, "/executors")
        return parse_executor_snapshots(payload)

    def set_executor_mode(self, name: str, value: str) -> Dict[str, Any]:
        dto = SetExecutorModeRequestDto(value=value)
        safe_name = quote(str(name or "").strip(), safe="")
        payload = self._request(
            f"/api/executors/{safe_name}/mode",
            method="POST",
            data=dto.to_dict(),
        )
        return payload if isinstance(payload, dict) else {"result": payload}

    def executor_on(self, name: str) -> Dict[str, Any]:
        safe_name = quote(str(name or "").strip(), safe="")
        payload = self._request(f"/api/executors/{safe_name}/on", method="POST")
        return payload if isinstance(payload, dict) else {"result": payload}

    def executor_off(self, name: str) -> Dict[str, Any]:
        safe_name = quote(str(name or "").strip(), safe="")
        payload = self._request(f"/api/executors/{safe_name}/off", method="POST")
        return payload if isinstance(payload, dict) else {"result": payload}

    def executor_set(self, name: str, value: str) -> Dict[str, Any]:
        dto = SetExecutorValueRequestDto(value=value)
        safe_name = quote(str(name or "").strip(), safe="")
        payload = self._request(
            f"/api/executors/{safe_name}/set",
            method="POST",
            data=dto.to_dict(),
        )
        return payload if isinstance(payload, dict) else {"result": payload}

    def get_logic_full(self) -> Dict[str, Any]:
        payload = self._request("/api/json/logic/full")
        return payload if isinstance(payload, dict) else {"root": {}}

    def upload_logic(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self._request("/api/json/logic/upload", method="POST", data=payload or {})
        return response if isinstance(response, dict) else {"result": response}

    def reload_logic(self) -> Dict[str, Any]:
        response = self._request("/api/json/logic/reload", method="POST", data={})
        return response if isinstance(response, dict) else {"result": response}

    def list_devices(self) -> List[Dict[str, Any]]:
        payload = self._request("/devices")
        if isinstance(payload, dict):
            data = payload.get("data", [])
            return data if isinstance(data, list) else []
        return []

    def create_device(
        self,
        name: str,
        device_type: str = "controller",
        status: str = "online",
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        body = {
            "name": str(name or "").strip() or "Scheduled Device",
            "type": str(device_type or "controller"),
            "status": str(status or "online"),
            "metadata": metadata or {},
        }
        response = self._request("/devices", method="POST", data=body)
        return response if isinstance(response, dict) else {"result": response}

    def list_schedules(self) -> List[Dict[str, Any]]:
        payload = self._request("/schedules")
        if isinstance(payload, dict):
            data = payload.get("data", [])
            return data if isinstance(data, list) else []
        return []

    def list_sensors(self, device_id: str = "") -> List[Dict[str, Any]]:
        query_params = {}
        normalized_device_id = str(device_id or "").strip()
        if normalized_device_id:
            query_params["deviceId"] = normalized_device_id

        payload = self._request("/sensors", query_params=query_params)
        if isinstance(payload, dict):
            data = payload.get("data", [])
            if isinstance(data, list):
                return data
        return []

    def list_sensor_readings(
        self,
        *,
        device_id: str = "",
        device_name: str = "",
        sensor_id: str = "",
        from_iso: str = "",
        to_iso: str = "",
        limit: Optional[int] = None,
        order: str = "ASC",
    ) -> List[Dict[str, Any]]:
        query_params = {
            "deviceId": str(device_id or "").strip(),
            "deviceName": str(device_name or "").strip(),
            "sensorId": str(sensor_id or "").strip(),
            "from": str(from_iso or "").strip(),
            "to": str(to_iso or "").strip(),
            "order": str(order or "ASC").strip().upper(),
        }
        if isinstance(limit, int) and limit > 0:
            query_params["limit"] = str(limit)

        payload = self._request("/sensor-readings", query_params=query_params)
        if isinstance(payload, dict):
            data = payload.get("data", [])
            if isinstance(data, list):
                return data
        return []

    def create_sensor(
        self,
        *,
        device_id: str,
        name: str,
        sensor_type: str,
        unit: str = "",
        is_active: bool = True,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "deviceId": str(device_id or "").strip(),
            "name": str(name or "").strip() or "Sensor",
            "type": str(sensor_type or "").strip() or "generic",
            "isActive": bool(is_active),
            "metadata": metadata or {},
        }
        normalized_unit = str(unit or "").strip()
        if normalized_unit:
            body["unit"] = normalized_unit
        response = self._request("/sensors", method="POST", data=body)
        return response if isinstance(response, dict) else {"result": response}

    def create_sensor_reading(
        self,
        *,
        sensor_id: str,
        value: Any,
        timestamp_iso: str = "",
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "sensorId": str(sensor_id or "").strip(),
            "value": value,
            "metadata": metadata or {},
        }
        normalized_timestamp = str(timestamp_iso or "").strip()
        if normalized_timestamp:
            body["timestamp"] = normalized_timestamp
        response = self._request("/sensor-readings", method="POST", data=body)
        return response if isinstance(response, dict) else {"result": response}

    def create_schedule(
        self,
        *,
        device_id: str,
        name: str,
        cron_expression: str,
        action: str,
        payload: Dict[str, Any],
        enabled: bool = True,
        metadata: Dict[str, Any] = None,
        schedule_mode: str = "",
    ) -> Dict[str, Any]:
        body = {
            "deviceId": device_id,
            "name": name,
            "cronExpression": cron_expression,
            "action": action,
            "payload": payload or {},
            "enabled": bool(enabled),
            "metadata": metadata or {},
        }
        normalized_mode = str(schedule_mode or "").strip()
        if normalized_mode:
            body["scheduleMode"] = normalized_mode
        response = self._request("/schedules", method="POST", data=body)
        return response if isinstance(response, dict) else {"result": response}

    def update_schedule(self, schedule_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        safe_schedule_id = quote(str(schedule_id or "").strip(), safe="")
        response = self._request(f"/schedules/{safe_schedule_id}", method="PATCH", data=updates or {})
        return response if isinstance(response, dict) else {"result": response}

    def delete_schedule(self, schedule_id: str) -> Dict[str, Any]:
        safe_schedule_id = quote(str(schedule_id or "").strip(), safe="")
        response = self._request(f"/schedules/{safe_schedule_id}", method="DELETE")
        return response if isinstance(response, dict) else {"result": response}

    def list_user_logs(self) -> List[Dict[str, Any]]:
        payload = self._request("/user-logs")
        if isinstance(payload, dict):
            data = payload.get("data", [])
            return data if isinstance(data, list) else []
        return []

    def create_user_log(
        self,
        *,
        category: str,
        title: str,
        payload: Dict[str, Any],
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        body = {
            "category": str(category or "control"),
            "title": str(title or "").strip() or "Event",
            "payload": payload or {},
            "metadata": metadata or {},
        }
        response = self._request("/user-logs", method="POST", data=body)
        return response if isinstance(response, dict) else {"result": response}
