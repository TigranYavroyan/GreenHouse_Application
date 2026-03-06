from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
import uuid

from PyQt5.QtCore import QTimer


TaskCallback = Callable[[str, Dict[str, Any]], bool]
TaskChangeCallback = Callable[["ScheduledTask"], None]


@dataclass
class ScheduledTask:
    task_id: str
    target_label: str
    command: str
    parameters: Dict[str, Any]
    delay_seconds: int
    scheduled_at: datetime
    run_at: datetime
    status: str = "pending"
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: str = ""


class SchedulerService:
    """
    In-memory one-time scheduler built on QTimer.

    The scheduling engine is intentionally decoupled from UI and transport logic:
    - command execution is provided by `execute_callback`
    - task state notifications are provided by `on_task_change`
    - persistence can be added behind this service later (per-user DB storage)
    """

    def __init__(
        self,
        execute_callback: TaskCallback,
        timer_parent=None,
        on_task_change: Optional[TaskChangeCallback] = None,
    ):
        self._execute_callback = execute_callback
        self._timer_parent = timer_parent
        self._on_task_change = on_task_change
        self._tasks: Dict[str, ScheduledTask] = {}
        self._timers: Dict[str, QTimer] = {}

    def schedule_once(
        self,
        target_label: str,
        command: str,
        parameters: Optional[Dict[str, Any]] = None,
        delay_seconds: int = 0,
    ) -> ScheduledTask:
        if delay_seconds < 0:
            raise ValueError("delay_seconds must be >= 0")

        now = datetime.now()
        run_at = now + timedelta(seconds=delay_seconds)
        task_id = str(uuid.uuid4())
        task = ScheduledTask(
            task_id=task_id,
            target_label=target_label,
            command=command,
            parameters=dict(parameters or {}),
            delay_seconds=delay_seconds,
            scheduled_at=now,
            run_at=run_at,
        )
        self._tasks[task_id] = task
        self._emit_change(task)

        timer = QTimer(self._timer_parent)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda tid=task_id: self._run_task(tid))

        interval_ms = max(1, int(delay_seconds * 1000))
        timer.start(interval_ms)
        self._timers[task_id] = timer
        return task

    def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        if task.status not in {"pending", "running"}:
            return False

        timer = self._timers.pop(task_id, None)
        if timer and timer.isActive():
            timer.stop()

        task.status = "cancelled"
        task.finished_at = datetime.now()
        self._emit_change(task)
        return True

    def clear_all_tasks(self) -> None:
        for task_id, timer in list(self._timers.items()):
            if timer and timer.isActive():
                timer.stop()
            self._timers.pop(task_id, None)

        for task in self._tasks.values():
            if task.status in {"pending", "running"}:
                task.status = "cancelled"
                task.finished_at = datetime.now()
                self._emit_change(task)

        self._tasks.clear()

    def shutdown(self) -> None:
        for timer in self._timers.values():
            if timer and timer.isActive():
                timer.stop()
        self._timers.clear()

    def list_tasks(self) -> List[ScheduledTask]:
        return sorted(
            self._tasks.values(),
            key=lambda task: (task.run_at, task.scheduled_at, task.task_id),
        )

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self._tasks.get(task_id)

    def _run_task(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            self._timers.pop(task_id, None)
            return
        if task.status != "pending":
            self._timers.pop(task_id, None)
            return

        task.status = "running"
        task.started_at = datetime.now()
        self._emit_change(task)

        success = False
        error_message = ""
        try:
            success = bool(self._execute_callback(task.command, dict(task.parameters)))
        except Exception as exc:
            success = False
            error_message = str(exc)

        task.finished_at = datetime.now()
        task.error_message = error_message
        task.status = "completed" if success else "failed"
        self._timers.pop(task_id, None)
        self._emit_change(task)

    def _emit_change(self, task: ScheduledTask) -> None:
        if self._on_task_change:
            self._on_task_change(task)
