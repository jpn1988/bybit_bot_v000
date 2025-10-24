#!/usr/bin/env python3
import time
from typing import List


class BackoffTransport:
    """
    Gère l'attente de reconnexion avec backoff progressif et arrêt réactif.
    """

    def __init__(self, reconnect_delays: List[int]):
        self.reconnect_delays = reconnect_delays or [1, 2, 5, 10, 30]

    def wait(self, current_index: int, is_running_callable) -> int:
        """
        Attend le délai de reconnexion correspondant en vérifiant régulièrement
        l'état 'running' via un callback.

        Returns: le nouvel index de backoff (éventuellement incrémenté)
        """
        delay = self.reconnect_delays[min(current_index, len(self.reconnect_delays) - 1)]
        try:
            from config.timeouts import TimeoutConfig
            step = getattr(TimeoutConfig, "SHORT_SLEEP", 0.1)
        except Exception:
            step = 0.1

        for _ in range(int(delay / step)):
            if not is_running_callable():
                return current_index
            time.sleep(step)

        # Augmenter l'index jusqu'au max
        if current_index < len(self.reconnect_delays) - 1:
            return current_index + 1
        return current_index


