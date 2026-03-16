import base64
import json
from typing import Dict, Optional

from PyQt5.QtCore import QSettings


class AuthSessionManager:
    """
    Stores and manages desktop JWT session state.
    """

    _TOKEN_KEY = "auth/token"

    def __init__(self, organization: str = "GreenhouseAutomation", application: str = "Desktop"):
        self._settings = QSettings(organization, application)

    def get_token(self) -> Optional[str]:
        raw_value = self._settings.value(self._TOKEN_KEY, "")
        token = str(raw_value or "").strip()
        return token or None

    def set_token(self, token: str) -> None:
        normalized = str(token or "").strip()
        if not normalized:
            self.clear_token()
            return
        self._settings.setValue(self._TOKEN_KEY, normalized)
        self._settings.sync()

    def clear_token(self) -> None:
        self._settings.remove(self._TOKEN_KEY)
        self._settings.sync()

    def decode_claims(self, token: Optional[str] = None) -> Dict[str, str]:
        """
        Decode JWT payload for UI convenience only.
        Signature verification is still performed by backend middleware.
        """
        jwt_token = token or self.get_token()
        if not jwt_token:
            return {}

        parts = jwt_token.split(".")
        if len(parts) < 2:
            return {}

        payload_segment = parts[1]
        padding = "=" * (-len(payload_segment) % 4)
        try:
            decoded = base64.urlsafe_b64decode(payload_segment + padding)
            parsed = json.loads(decoded.decode("utf-8"))
            if isinstance(parsed, dict):
                return parsed
            return {}
        except Exception:
            return {}

