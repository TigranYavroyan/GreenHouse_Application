import requests
from typing import Any, Dict, List

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
        else:
            raise ValueError(f"Unsupported method: {method}")

        payload = response.json()
        if response.status_code >= 400:
            message = payload.get("error") if isinstance(payload, dict) else str(payload)
            raise RuntimeError(message or f"Request failed: {response.status_code}")
        return payload

    def get_status(self) -> CoreStatusDto:
        payload = self._request("/status")
        return CoreStatusDto.from_dict(payload if isinstance(payload, dict) else {})

    def get_getter_schema(self) -> Dict[str, str]:
        payload = self._request("/schema/getters")
        return parse_getter_schema(payload if isinstance(payload, dict) else {})

    def get_executor_schema(self) -> Dict[str, str]:
        payload = self._request("/schema/executors")
        return parse_executor_schema(payload if isinstance(payload, dict) else {})

    def get_getters(self) -> List[GetterSnapshotDto]:
        payload = self._request("/getters")
        return parse_getter_snapshots(payload if isinstance(payload, dict) else {})

    def get_getter(self, key: str) -> GetterSnapshotDto:
        payload = self._request(f"/getters/{key}")
        if not isinstance(payload, dict):
            payload = {}
        key_value = str(payload.get("key", key))
        return GetterSnapshotDto.from_dict(key_value, payload)

    def get_executors(self) -> List[ExecutorSnapshotDto]:
        payload = self._request("/executors")
        return parse_executor_snapshots(payload if isinstance(payload, list) else [])

    def set_executor_mode(self, name: str, value: str) -> Dict[str, Any]:
        dto = SetExecutorModeRequestDto(value=value)
        payload = self._request(
            f"/api/executors/{name}/mode",
            method="POST",
            data=dto.to_dict(),
        )
        return payload if isinstance(payload, dict) else {"result": payload}

    def executor_on(self, name: str) -> Dict[str, Any]:
        payload = self._request(f"/api/executors/{name}/on", method="POST")
        return payload if isinstance(payload, dict) else {"result": payload}

    def executor_off(self, name: str) -> Dict[str, Any]:
        payload = self._request(f"/api/executors/{name}/off", method="POST")
        return payload if isinstance(payload, dict) else {"result": payload}

    def executor_set(self, name: str, value: str) -> Dict[str, Any]:
        dto = SetExecutorValueRequestDto(value=value)
        payload = self._request(
            f"/api/executors/{name}/set",
            method="POST",
            data=dto.to_dict(),
        )
        return payload if isinstance(payload, dict) else {"result": payload}
