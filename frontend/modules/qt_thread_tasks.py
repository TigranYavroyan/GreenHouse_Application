"""Run blocking work off the Qt GUI thread; apply results via queued signals."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional, TypeVar

from PyQt5.QtCore import QObject, Qt, pyqtSignal

from modules.core_api_client import UnauthorizedError

T = TypeVar("T")

UNAUTHORIZED_FAILURE_PREFIX = "__unauthorized__:"


class _ThreadTaskBridge(QObject):
    """Emits from worker thread; slots run on the receiver's thread (GUI) when queued."""

    finished = pyqtSignal(object)
    failed = pyqtSignal(str)


def run_thread_task(
    parent: QObject,
    fn: Callable[[], T],
    on_finished: Callable[[T], None],
    on_failed: Callable[[str], None],
    thread_name: str = "qt-blocking-task",
) -> None:
    """
    Run ``fn`` on a daemon thread. ``on_finished`` / ``on_failed`` run on the GUI thread.

    ``parent`` must live on the GUI thread (typically ``self`` of ``QMainWindow``).
    """
    bridge = _ThreadTaskBridge(parent)
    log = logging.getLogger("qt_thread_tasks")

    def _finish_ok(result: object) -> None:
        bridge.deleteLater()
        try:
            on_finished(result)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            log.error("Thread task on_finished raised: %s", exc, exc_info=True)

    def _finish_err(message: str) -> None:
        bridge.deleteLater()
        try:
            on_failed(message)
        except Exception as exc:  # noqa: BLE001
            log.error("Thread task on_failed raised: %s", exc, exc_info=True)

    bridge.finished.connect(_finish_ok, Qt.QueuedConnection)
    bridge.failed.connect(_finish_err, Qt.QueuedConnection)

    def job() -> None:
        try:
            out = fn()
            bridge.finished.emit(out)
        except UnauthorizedError as error:
            bridge.failed.emit(UNAUTHORIZED_FAILURE_PREFIX + str(error))
        except Exception as error:  # noqa: BLE001 — boundary from worker thread
            text = str(error).strip() or type(error).__name__
            bridge.failed.emit(text)

    threading.Thread(target=job, name=thread_name, daemon=True).start()


def is_unauthorized_thread_failure(message: str) -> bool:
    return bool(message.startswith(UNAUTHORIZED_FAILURE_PREFIX))


def unauthorized_message_from_thread_failure(message: str) -> str:
    return message[len(UNAUTHORIZED_FAILURE_PREFIX) :]


def dispatch_thread_failure_to_ui(
    parent: QObject,
    message: str,
    *,
    logger: Optional[Any] = None,
    log_label: str = "Background task",
) -> bool:
    """
    If ``message`` is an unauthorized marker, forward to ``handle_unauthorized_error`` and return True.
    Otherwise return False (caller should log / show the error).
    """
    if not is_unauthorized_thread_failure(message):
        return False
    body = unauthorized_message_from_thread_failure(message)
    if logger is not None:
        logger.warning("%s unauthorized: %s", log_label, body)
    if hasattr(parent, "handle_unauthorized_error") and callable(getattr(parent, "handle_unauthorized_error")):
        parent.handle_unauthorized_error(body)
    return True
