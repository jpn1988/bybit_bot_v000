#!/usr/bin/env python3
import json
from typing import Callable, Optional


class PrivateMessageRouter:
    """Routage des messages privés (order/position/wallet/execution)."""

    def __init__(self, on_topic: Optional[Callable[[str, dict], None]] = None, on_pong: Optional[Callable[[], None]] = None, logger=None):
        self.on_topic = on_topic
        self.on_pong = on_pong
        self.logger = logger

    def route(self, raw_message: str) -> None:
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            try:
                self.logger and self.logger.debug(f"Message brut reçu: {raw_message[:100]}...")
            except Exception:
                pass
            return

        # Ping/Pong
        if data.get("op") == "pong" or "pong" in str(data).lower():
            try:
                self.logger and self.logger.debug("pong")
            except Exception:
                pass
            if callable(self.on_pong):
                try:
                    self.on_pong()
                except Exception:
                    pass
            return

        # Topics
        topic = data.get("topic", "")

        # Log de débogage pour TOUS les messages reçus
        try:
            self.logger and self.logger.info(f"🔍 [DEBUG] Message WebSocket reçu: topic='{topic}', data={data}")
        except Exception:
            pass

        if topic and callable(self.on_topic):
            try:
                self.logger and self.logger.info(f"🔍 [DEBUG] Appel callback on_topic avec topic='{topic}'")
                self.on_topic(topic, data)
            except Exception as e:
                try:
                    self.logger and self.logger.error(f"❌ [DEBUG] Erreur callback on_topic: {e}")
                except Exception:
                    pass
        else:
            # Debug court
            message_preview = (
                str(data)[:100] + "..." if len(str(data)) > 100 else str(data)
            )
            try:
                self.logger and self.logger.info(f"ℹ️ [DEBUG] Message sans topic ou callback: {message_preview}")
            except Exception:
                pass


