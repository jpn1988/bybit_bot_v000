"""Module de métriques pour le monitoring du bot."""

import time
import threading
from typing import Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
import statistics


@dataclass
class MetricsData:
    """Structure pour stocker les métriques."""
    # Compteurs
    api_calls_total: int = 0
    api_errors_total: int = 0
    pairs_kept_total: int = 0
    pairs_rejected_total: int = 0

    # Latences (en secondes)
    api_latencies: deque = field(default_factory=lambda: deque(maxlen=100))

    # Dernière mise à jour
    last_update: float = field(default_factory=time.time)

    # Métriques par filtre
    filter_stats: Dict[str, Dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: {"kept": 0, "rejected": 0}))

    # Métriques WebSocket
    ws_connections: int = 0
    ws_reconnects: int = 0
    ws_errors: int = 0


class MetricsCollector:
    """Collecteur de métriques thread-safe."""

    def __init__(self):
        self._data = MetricsData()
        self._lock = threading.Lock()
        self._start_time = time.time()

    def record_api_call(self, latency: float, success: bool = True):
        """Enregistre un appel API."""
        with self._lock:
            self._data.api_calls_total += 1
            self._data.api_latencies.append(latency)
            if not success:
                self._data.api_errors_total += 1
            self._data.last_update = time.time()

    def record_filter_result(self, filter_name: str, kept: int, rejected: int):
        """Enregistre les résultats d'un filtre."""
        with self._lock:
            self._data.pairs_kept_total += kept
            self._data.pairs_rejected_total += rejected
            self._data.filter_stats[filter_name]["kept"] += kept
            self._data.filter_stats[filter_name]["rejected"] += rejected
            self._data.last_update = time.time()

    def record_ws_connection(self, connected: bool):
        """Enregistre une connexion WebSocket."""
        with self._lock:
            if connected:
                self._data.ws_connections += 1
            else:
                self._data.ws_reconnects += 1
            self._data.last_update = time.time()

    def record_ws_error(self):
        """Enregistre une erreur WebSocket."""
        with self._lock:
            self._data.ws_errors += 1
            self._data.last_update = time.time()

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Retourne un résumé des métriques."""
        with self._lock:
            uptime = time.time() - self._start_time

            # Calculer la latence moyenne
            avg_latency = 0.0
            if self._data.api_latencies:
                avg_latency = statistics.mean(self._data.api_latencies)

            # Calculer le taux d'erreur API
            error_rate = 0.0
            if self._data.api_calls_total > 0:
                error_rate = (self._data.api_errors_total / self._data.api_calls_total) * 100

            # Calculer le taux de réussite des filtres
            total_pairs_processed = self._data.pairs_kept_total + self._data.pairs_rejected_total
            filter_success_rate = 0.0
            if total_pairs_processed > 0:
                filter_success_rate = (self._data.pairs_kept_total / total_pairs_processed) * 100

            return {
                "uptime_seconds": round(uptime, 2),
                "api_calls_total": self._data.api_calls_total,
                "api_errors_total": self._data.api_errors_total,
                "api_error_rate_percent": round(error_rate, 2),
                "api_avg_latency_ms": round(avg_latency * 1000, 2),
                "pairs_kept_total": self._data.pairs_kept_total,
                "pairs_rejected_total": self._data.pairs_rejected_total,
                "filter_success_rate_percent": round(filter_success_rate, 2),
                "ws_connections": self._data.ws_connections,
                "ws_reconnects": self._data.ws_reconnects,
                "ws_errors": self._data.ws_errors,
                "last_update": self._data.last_update,
                "filter_stats": dict(self._data.filter_stats)
            }

    def reset(self):
        """Remet à zéro toutes les métriques."""
        with self._lock:
            self._data = MetricsData()
            self._start_time = time.time()


# Instance globale du collecteur de métriques
metrics_collector = MetricsCollector()


def record_api_call(latency: float, success: bool = True):
    """Enregistre un appel API."""
    metrics_collector.record_api_call(latency, success)


def record_filter_result(filter_name: str, kept: int, rejected: int):
    """Enregistre les résultats d'un filtre."""
    metrics_collector.record_filter_result(filter_name, kept, rejected)


def record_ws_connection(connected: bool):
    """Enregistre une connexion WebSocket."""
    metrics_collector.record_ws_connection(connected)


def record_ws_error():
    """Enregistre une erreur WebSocket."""
    metrics_collector.record_ws_error()


def get_metrics_summary() -> Dict[str, Any]:
    """Retourne un résumé des métriques."""
    return metrics_collector.get_metrics_summary()
