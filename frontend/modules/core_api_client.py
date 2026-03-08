import requests
from typing import Any, Dict, List
from urllib.parse import quote

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


class CoreApiClient:
    def __init__(self, backend_url: str, timeout_seconds: int = 5):
        self.backend_url = backend_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _request(self, path: str, method: str = "GET", data: Dict[str, Any] = None) -> Any:
        url = f"{self.backend_url}{path}"
        if method == "GET":
            response = requests.get(url, timeout=self.timeout_seconds)
        elif method == "POST":
            response = requests.post(url, json=data or {}, timeout=self.timeout_seconds)
        elif method == "PATCH":
            response = requests.patch(url, json=data or {}, timeout=self.timeout_seconds)
        elif method == "DELETE":
            response = requests.delete(url, timeout=self.timeout_seconds)
        else:
            raise ValueError(f"Unsupported method: {method}")

        try:
            payload = response.json()
        except ValueError:
            payload = {"error": response.text or f"HTTP {response.status_code}"}
        if response.status_code >= 400:
            message = payload.get("error") if isinstance(payload, dict) else str(payload)
            raise RuntimeError(message or f"Request failed: {response.status_code}")
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

    def list_devices(self) -> List[Dict[str, Any]]:
        payload = self._request("/devices")
        if isinstance(payload, dict):
            data = payload.get("data", [])
            return data if isinstance(data, list) else []
        return []

    def list_schedules(self) -> List[Dict[str, Any]]:
        payload = self._request("/schedules")
        if isinstance(payload, dict):
            data = payload.get("data", [])
            return data if isinstance(data, list) else []
        return []

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
