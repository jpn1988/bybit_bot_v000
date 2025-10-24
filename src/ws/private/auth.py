#!/usr/bin/env python3
import hmac
import hashlib
import time


class AuthManager:
    """Génération de signature HMAC et message d'auth WS v5."""

    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret

    def generate_signature(self, expires_ms: int) -> str:
        payload = f"GET/realtime{expires_ms}"
        return hmac.new(
            self.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def build_auth_message(self) -> tuple[dict, int]:
        """Construit le message d'auth et retourne (message, expires_ms)."""
        expires_ms = int((time.time() + 60) * 1000)
        signature = self.generate_signature(expires_ms)
        return {
            "op": "auth",
            "args": [self.api_key, expires_ms, signature],
        }, expires_ms


