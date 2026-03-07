from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TypedValueDto:
    value_type: str
    value: Any

    @staticmethod
    def from_dict(payload: Optional[Dict[str, Any]]) -> "TypedValueDto":
        data = payload or {}
        return TypedValueDto(
            value_type=str(data.get("type", "unknown")),
            value=data.get("value"),
        )


@dataclass(frozen=True)
class GetterSnapshotDto:
    key: str
    valid: bool
    stamp_ms: int
    data: TypedValueDto

    @staticmethod
    def from_dict(key: str, payload: Optional[Dict[str, Any]]) -> "GetterSnapshotDto":
        data = payload or {}
        return GetterSnapshotDto(
            key=key,
            valid=bool(data.get("valid", False)),
            stamp_ms=int(data.get("stampMs", 0) or 0),
            data=TypedValueDto.from_dict(data.get("data")),
        )


@dataclass(frozen=True)
class ExecutorSnapshotDto:
    executor_id: int
    name: str
    valid: bool
    stamp_ms: int
    mode: str
    data: TypedValueDto

    @staticmethod
    def from_dict(payload: Optional[Dict[str, Any]]) -> "ExecutorSnapshotDto":
        data = payload or {}
        return ExecutorSnapshotDto(
            executor_id=int(data.get("id", 0) or 0),
            name=str(data.get("name", "")),
            valid=bool(data.get("valid", False)),
            stamp_ms=int(data.get("stampMs", 0) or 0),
            mode=str(data.get("mode", "AUTO")),
            data=TypedValueDto.from_dict(data.get("data")),
        )


@dataclass(frozen=True)
class CoreStatusDto:
    status: str

    @staticmethod
    def from_dict(payload: Optional[Dict[str, Any]]) -> "CoreStatusDto":
        data = payload or {}
        return CoreStatusDto(status=str(data.get("status", "unknown")))


@dataclass(frozen=True)
class SetExecutorModeRequestDto:
    value: str

    def to_dict(self) -> Dict[str, str]:
        return {"value": self.value}


@dataclass(frozen=True)
class SetExecutorValueRequestDto:
    value: str

    def to_dict(self) -> Dict[str, str]:
        return {"value": self.value}


def parse_getter_schema(payload: Optional[Dict[str, Any]]) -> Dict[str, str]:
    data = payload or {}
    return {str(k): str(v) for k, v in data.items()}


def parse_executor_schema(payload: Optional[Dict[str, Any]]) -> Dict[str, str]:
    data = payload or {}
    return {str(k): str(v) for k, v in data.items()}


def parse_getter_snapshots(payload: Optional[Dict[str, Any]]) -> List[GetterSnapshotDto]:
    data = payload or {}
    snapshots: List[GetterSnapshotDto] = []
    for key, item in data.items():
        snapshots.append(GetterSnapshotDto.from_dict(str(key), item if isinstance(item, dict) else {}))
    snapshots.sort(key=lambda entry: entry.key.lower())
    return snapshots


def parse_executor_snapshots(payload: Optional[List[Dict[str, Any]]]) -> List[ExecutorSnapshotDto]:
    data = payload or []
    snapshots = [ExecutorSnapshotDto.from_dict(item if isinstance(item, dict) else {}) for item in data]
    snapshots.sort(key=lambda entry: entry.name.lower())
    return snapshots
