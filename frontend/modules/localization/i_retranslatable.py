"""
IRetranslatable mixin/interface.

Any QWidget/QDialog/QMainWindow that owns user-visible text should:

    class MyDialog(QDialog, IRetranslatable):
        def __init__(self, ...):
            super().__init__(...)
            self.init_localization()  # registers + applies once
            self._build_ui()

        def retranslate_ui(self) -> None:
            self.setWindowTitle(tr_key(Dialogs.X_TITLE))
            self.ok_btn.setText(tr_key(Common.OK))
            ...

The mixin handles registration with the singleton LocalizationManager
and unregistration on widget destruction.
"""
from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QObject

from modules.localization.localization_manager import LocalizationManager


class IRetranslatable:
    """Mixin: implement `retranslate_ui` and call `init_localization`.

    NOTE: classes using this mixin must also inherit from QObject (or any
    QObject subclass like QWidget/QDialog/QMainWindow). The mixin itself
    deliberately does NOT inherit QObject so it remains MRO-safe.
    """

    _localization_initialized: bool = False

    def init_localization(self) -> None:
        """Register with LocalizationManager and run an initial pass."""
        if getattr(self, "_localization_initialized", False):
            return
        manager = LocalizationManager.instance()
        manager.register(self)

        if isinstance(self, QObject):
            self.destroyed.connect(lambda *_: manager.unregister(self))

        self._localization_initialized = True
        try:
            self.retranslate_ui()
        except Exception:
            pass

    def retranslate_ui(self) -> None:  # pragma: no cover - to be overridden
        """Override in subclasses to (re)apply translated text."""
        raise NotImplementedError("retranslate_ui must be implemented by subclasses")


def get_localized(key: str, **params) -> str:
    """Module-level convenience function (use `tr_key` from helpers)."""
    return LocalizationManager.instance().get(key, **params)


def get_optional(widget) -> Optional[LocalizationManager]:
    """Helper used by some widgets that want to defensively check init."""
    if widget is None:
        return None
    return LocalizationManager.instance()
