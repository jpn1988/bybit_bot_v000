#!/usr/bin/env python3
import threading
import time
from typing import Callable


class AuthWatchdog:
    """Surveille l'état d'authentification et déclenche une reconnexion."""

    def __init__(self, should_reconnect: Callable[[], bool], trigger_reconnect: Callable[[], None], logger) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._should_reconnect = should_reconnect
        self._trigger_reconnect = trigger_reconnect
        self.logger = logger

    def start(self, name: str = "ws_private_watchdog") -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name=name)
        self._thread.start()
        try:
            self.logger.debug("🐕 Thread watchdog démarré")
        except Exception:
            pass

    def _loop(self) -> None:
        try:
            from config.timeouts import TimeoutConfig
            interval = TimeoutConfig.WATCHDOG_INTERVAL
        except Exception:
            interval = 1.0
        while not self._stop.is_set():
            try:
                if self._should_reconnect():
                    try:
                        self.logger.warning("⏳ Auth sans réponse → redémarrage WS")
                    except Exception:
                        pass
                    self._trigger_reconnect()
            except Exception:
                pass
            self._stop.wait(timeout=interval)

    def stop(self, join_timeout: float | None = None) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            try:
                from config.timeouts import TimeoutConfig
                join_timeout = join_timeout or TimeoutConfig.THREAD_WS_PRIVATE_SHUTDOWN
            except Exception:
                pass
            try:
                self._thread.join(timeout=join_timeout)
            except Exception:
                pass


