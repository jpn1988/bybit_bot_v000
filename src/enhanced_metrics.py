#!/usr/bin/env python3
"""
Système de métriques amélioré pour le bot Bybit.

Ce module fournit un système de métriques avancé avec :
- Métriques en temps réel
- Historique des performances
- Alertes automatiques
- Export des données
- Dashboard intégré
"""

import time
import threading
import json
import csv
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
import statistics

from config.timeouts import TimeoutConfig


@dataclass
class MetricPoint:
    """Point de métrique avec timestamp et valeur."""
    timestamp: float
    value: float
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class AlertRule:
    """Règle d'alerte pour les métriques."""
    name: str
    metric_name: str
    condition: str  # ">", "<", ">=", "<=", "==", "!="
    threshold: float
    duration_seconds: int = 0  # Durée avant déclenchement
    enabled: bool = True
    callback: Optional[Callable] = None


@dataclass
class MetricConfig:
    """Configuration d'une métrique."""
    name: str
    description: str
    unit: str
    retention_days: int = 7
    max_points: int = 1000
    alert_rules: List[AlertRule] = field(default_factory=list)


class EnhancedMetricsCollector:
    """
    Collecteur de métriques amélioré avec historique et alertes.

    Fonctionnalités :
    - Collecte de métriques en temps réel
    - Historique des performances
    - Système d'alertes
    - Export des données
    - Dashboard intégré
    """

    def __init__(self, data_dir: str = "metrics_data"):
        """
        Initialise le collecteur de métriques amélioré.

        Args:
            data_dir: Répertoire pour stocker les données de métriques
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # Données des métriques
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._configs: Dict[str, MetricConfig] = {}
        self._alerts: List[AlertRule] = []

        # Thread safety
        self._lock = threading.Lock()
        self._start_time = time.time()

        # Configuration par défaut
        self._setup_default_metrics()

        # Thread de nettoyage
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def _setup_default_metrics(self):
        """Configure les métriques par défaut."""
        default_metrics = [
            MetricConfig("api_calls_total", "Total des appels API", "count"),
            MetricConfig("api_errors_total", "Total des erreurs API", "count"),
            MetricConfig("api_latency_ms", "Latence des appels API", "ms"),
            MetricConfig("ws_connections", "Connexions WebSocket", "count"),
            MetricConfig("ws_reconnects", "Reconnexions WebSocket", "count"),
            MetricConfig("ws_errors", "Erreurs WebSocket", "count"),
            MetricConfig("pairs_kept", "Paires gardées par les filtres", "count"),
            MetricConfig("pairs_rejected", "Paires rejetées par les filtres", "count"),
            MetricConfig("memory_usage_mb", "Utilisation mémoire", "MB"),
            MetricConfig("cpu_usage_percent", "Utilisation CPU", "%"),
            MetricConfig("task_execution_time_ms", "Temps d'exécution des tâches", "ms"),
            MetricConfig("error_rate_percent", "Taux d'erreur", "%"),
        ]

        for metric in default_metrics:
            self._configs[metric.name] = metric

    def record_metric(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """
        Enregistre une métrique.

        Args:
            name: Nom de la métrique
            value: Valeur de la métrique
            tags: Tags optionnels pour la métrique
        """
        if tags is None:
            tags = {}

        with self._lock:
            metric_point = MetricPoint(
                timestamp=time.time(),
                value=value,
                tags=tags
            )
            self._metrics[name].append(metric_point)

            # Vérifier les alertes
            self._check_alerts(name, value)

    def record_api_call(self, latency_ms: float, success: bool = True, endpoint: str = ""):
        """Enregistre un appel API."""
        self.record_metric("api_calls_total", 1, {"endpoint": endpoint})
        self.record_metric("api_latency_ms", latency_ms, {"endpoint": endpoint})

        if not success:
            self.record_metric("api_errors_total", 1, {"endpoint": endpoint})

    def record_websocket_event(self, event_type: str, count: int = 1):
        """Enregistre un événement WebSocket."""
        self.record_metric(f"ws_{event_type}", count)

    def record_ws_connection(self, connected: bool):
        """
        Enregistre une connexion WebSocket.
        
        Compatible avec l'API de metrics.py.
        
        Args:
            connected: True si connexion, False si déconnexion/reconnexion
        """
        if connected:
            self.record_metric("ws_connections", 1)
        else:
            self.record_metric("ws_reconnects", 1)

    def record_ws_error(self):
        """
        Enregistre une erreur WebSocket.
        
        Compatible avec l'API de metrics.py.
        """
        self.record_metric("ws_errors", 1)

    def record_filter_result(self, filter_name: str, kept: int, rejected: int):
        """Enregistre les résultats d'un filtre."""
        self.record_metric("pairs_kept", kept, {"filter": filter_name})
        self.record_metric("pairs_rejected", rejected, {"filter": filter_name})

    def record_task_execution(self, task_name: str, execution_time_ms: float, threshold_ms: float = 1000.0):
        """
        Enregistre l'exécution d'une tâche avec détection des tâches lentes.
        
        Compatible avec l'API de metrics.py qui inclut un threshold.
        
        Args:
            task_name: Nom de la tâche
            execution_time_ms: Temps d'exécution en millisecondes
            threshold_ms: Seuil pour considérer une tâche comme lente (défaut: 1000ms = 1s)
        """
        self.record_metric("task_execution_time_ms", execution_time_ms, {"task": task_name})
        if execution_time_ms > threshold_ms:
            self.record_metric("slow_tasks_count", 1)

    def record_system_metrics(self):
        """Enregistre les métriques système."""
        try:
            import psutil

            # Mémoire
            memory = psutil.virtual_memory()
            self.record_metric("memory_usage_mb", memory.used / 1024 / 1024)

            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            self.record_metric("cpu_usage_percent", cpu_percent)

        except ImportError:
            pass  # psutil non disponible

    def add_alert(self, alert: AlertRule):
        """Ajoute une règle d'alerte."""
        with self._lock:
            self._alerts.append(alert)

    def _check_alerts(self, metric_name: str, value: float):
        """Vérifie les alertes pour une métrique."""
        for alert in self._alerts:
            if not alert.enabled or alert.metric_name != metric_name:
                continue

            if self._evaluate_condition(value, alert.condition, alert.threshold):
                if alert.callback:
                    alert.callback(alert, value)
                else:
                    self._default_alert_handler(alert, value)

    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Évalue une condition d'alerte."""
        if condition == ">":
            return value > threshold
        elif condition == "<":
            return value < threshold
        elif condition == ">=":
            return value >= threshold
        elif condition == "<=":
            return value <= threshold
        elif condition == "==":
            return value == threshold
        elif condition == "!=":
            return value != threshold
        return False

    def _default_alert_handler(self, alert: AlertRule, value: float):
        """Gestionnaire d'alerte par défaut."""
        print(f"🚨 ALERTE: {alert.name} - {alert.metric_name} {alert.condition} {alert.threshold} (valeur actuelle: {value})")

    def get_metric_summary(self, name: str, hours: int = 24) -> Dict[str, Any]:
        """Retourne un résumé d'une métrique."""
        with self._lock:
            if name not in self._metrics:
                return {}

            cutoff_time = time.time() - (hours * 3600)
            recent_points = [
                point for point in self._metrics[name]
                if point.timestamp >= cutoff_time
            ]

            if not recent_points:
                return {}

            values = [point.value for point in recent_points]

            return {
                "name": name,
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "avg": statistics.mean(values),
                "median": statistics.median(values),
                "std": statistics.stdev(values) if len(values) > 1 else 0,
                "latest": values[-1],
                "latest_timestamp": recent_points[-1].timestamp
            }

    def get_all_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Retourne un résumé de toutes les métriques."""
        with self._lock:
            summary = {
                "uptime_seconds": time.time() - self._start_time,
                "metrics": {},
                "timestamp": time.time()
            }

            for name in self._metrics:
                summary["metrics"][name] = self.get_metric_summary(name, hours)

            return summary

    def build_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Retourne un résumé agrégé des métriques pour reporting.
        
        Args:
            hours: Fenêtre temporelle d'agrégation en heures
        """
        with self._lock:
            uptime = time.time() - self._start_time
            
            # Récupérer les métriques récentes (24h)
            cutoff_time = time.time() - (hours * 3600)
            
            # Agrégation des métriques
            api_calls_total = 0
            api_errors_total = 0
            api_latencies = []
            pairs_kept_total = 0
            pairs_rejected_total = 0
            ws_connections = 0
            ws_reconnects = 0
            ws_errors = 0
            slow_tasks_count = 0
            task_execution_times = defaultdict(list)
            filter_stats = defaultdict(lambda: {"kept": 0, "rejected": 0})
            last_update = time.time()
            
            # Parcourir toutes les métriques et les agréger
            for metric_name, points in self._metrics.items():
                recent_points = [
                    point for point in points
                    if point.timestamp >= cutoff_time
                ]
                
                if not recent_points:
                    continue
                
                values = [point.value for point in recent_points]
                
                # Agrégation selon le type de métrique
                if metric_name == "api_calls_total":
                    api_calls_total = sum(values)
                elif metric_name == "api_errors_total":
                    api_errors_total = sum(values)
                elif metric_name == "api_latency_ms":
                    # Collecter toutes les latences (pas juste la somme)
                    # Convertir ms en secondes pour compatibilité
                    api_latencies.extend([v / 1000.0 for v in values])
                elif metric_name == "pairs_kept":
                    pairs_kept_total = sum(values)
                    # Extraire les tags pour filter_stats
                    for point in recent_points:
                        filter_name = point.tags.get("filter", "unknown")
                        filter_stats[filter_name]["kept"] += int(point.value)
                elif metric_name == "pairs_rejected":
                    pairs_rejected_total = sum(values)
                    # Extraire les tags pour filter_stats
                    for point in recent_points:
                        filter_name = point.tags.get("filter", "unknown")
                        filter_stats[filter_name]["rejected"] += int(point.value)
                elif metric_name == "ws_connections":
                    ws_connections = sum(values)
                elif metric_name == "ws_reconnects":
                    ws_reconnects = sum(values)
                elif metric_name == "ws_errors":
                    ws_errors = sum(values)
                elif metric_name == "slow_tasks_count":
                    slow_tasks_count = sum(values)
                elif metric_name == "task_execution_time_ms":
                    # Extraire les tâches par nom depuis les tags
                    for point in recent_points:
                        task_name = point.tags.get("task", "unknown")
                        # Convertir ms en secondes pour compatibilité
                        task_execution_times[task_name].append(point.value / 1000.0)
                
                # Mettre à jour last_update avec le point le plus récent
                if recent_points:
                    last_update = max(last_update, max(point.timestamp for point in recent_points))
            
            # Calculer la latence moyenne
            avg_latency = 0.0
            if api_latencies:
                avg_latency = statistics.mean(api_latencies)
            
            # Calculer le taux d'erreur API
            error_rate = 0.0
            if api_calls_total > 0:
                error_rate = (api_errors_total / api_calls_total) * 100
            
            # Calculer le taux de réussite des filtres
            total_pairs_processed = pairs_kept_total + pairs_rejected_total
            filter_success_rate = 0.0
            if total_pairs_processed > 0:
                filter_success_rate = (pairs_kept_total / total_pairs_processed) * 100
            
            # Calculer les moyennes des temps d'exécution des tâches
            task_performance = {}
            for task_name, execution_times in task_execution_times.items():
                if execution_times:
                    avg_time = statistics.mean(execution_times)
                    max_time = max(execution_times)
                    task_performance[task_name] = {
                        "avg_execution_time_ms": round(avg_time * 1000, 2),
                        "max_execution_time_ms": round(max_time * 1000, 2),
                        "execution_count": len(execution_times)
                    }
            
            return {
                "uptime_seconds": round(uptime, 2),
                "api_calls_total": int(api_calls_total),
                "api_errors_total": int(api_errors_total),
                "api_error_rate_percent": round(error_rate, 2),
                "api_avg_latency_ms": round(avg_latency * 1000, 2),
                "pairs_kept_total": int(pairs_kept_total),
                "pairs_rejected_total": int(pairs_rejected_total),
                "filter_success_rate_percent": round(filter_success_rate, 2),
                "ws_connections": int(ws_connections),
                "ws_reconnects": int(ws_reconnects),
                "ws_errors": int(ws_errors),
                "slow_tasks_count": int(slow_tasks_count),
                "task_performance": dict(task_performance),
                "last_update": last_update,
                "filter_stats": dict(filter_stats),
            }

    def export_to_csv(self, filename: str, hours: int = 24):
        """Exporte les métriques vers un fichier CSV."""
        with self._lock:
            cutoff_time = time.time() - (hours * 3600)

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['timestamp', 'metric_name', 'value', 'tags'])

                for name, points in self._metrics.items():
                    for point in points:
                        if point.timestamp >= cutoff_time:
                            writer.writerow([
                                datetime.fromtimestamp(point.timestamp).isoformat(),
                                name,
                                point.value,
                                json.dumps(point.tags)
                            ])

    def export_to_json(self, filename: str, hours: int = 24):
        """Exporte les métriques vers un fichier JSON."""
        with self._lock:
            cutoff_time = time.time() - (hours * 3600)

            data = {
                "export_timestamp": time.time(),
                "hours": hours,
                "metrics": {}
            }

            for name, points in self._metrics.items():
                recent_points = [
                    {
                        "timestamp": point.timestamp,
                        "value": point.value,
                        "tags": point.tags
                    }
                    for point in points
                    if point.timestamp >= cutoff_time
                ]
                data["metrics"][name] = recent_points

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

    def _cleanup_loop(self):
        """Boucle de nettoyage des anciennes métriques."""
        while True:
            try:
                time.sleep(3600)  # Nettoyer toutes les heures
                self._cleanup_old_metrics()
            except Exception:
                pass

    def _cleanup_old_metrics(self):
        """Nettoie les anciennes métriques."""
        with self._lock:
            cutoff_time = time.time() - (7 * 24 * 3600)  # 7 jours

            for name, points in self._metrics.items():
                # Garder seulement les points récents
                recent_points = [
                    point for point in points
                    if point.timestamp >= cutoff_time
                ]
                self._metrics[name] = deque(recent_points, maxlen=1000)

    def reset(self):
        """Remet à zéro toutes les métriques."""
        with self._lock:
            self._metrics.clear()
            self._start_time = time.time()


# Instance globale
_global_collector: Optional[EnhancedMetricsCollector] = None


def get_metrics_collector() -> EnhancedMetricsCollector:
    """Retourne l'instance globale du collecteur de métriques."""
    global _global_collector
    if _global_collector is None:
        _global_collector = EnhancedMetricsCollector()
    return _global_collector


# Fonctions de convenance
def record_metric(name: str, value: float, tags: Optional[Dict[str, str]] = None):
    """Enregistre une métrique."""
    get_metrics_collector().record_metric(name, value, tags)


def record_api_call(latency_ms: float, success: bool = True, endpoint: str = ""):
    """Enregistre un appel API."""
    get_metrics_collector().record_api_call(latency_ms, success, endpoint)


def record_websocket_event(event_type: str, count: int = 1):
    """Enregistre un événement WebSocket."""
    get_metrics_collector().record_websocket_event(event_type, count)


def record_ws_connection(connected: bool):
    """Enregistre une connexion ou reconnexion WebSocket."""
    get_metrics_collector().record_ws_connection(connected)


def record_ws_error():
    """Enregistre une erreur WebSocket."""
    get_metrics_collector().record_ws_error()


def record_filter_result(filter_name: str, kept: int, rejected: int):
    """Enregistre les résultats d'un filtre."""
    get_metrics_collector().record_filter_result(filter_name, kept, rejected)


def record_task_execution(task_name: str, execution_time_ms: float, threshold_ms: float = 1000.0):
    """Enregistre l'exécution d'une tâche."""
    get_metrics_collector().record_task_execution(task_name, execution_time_ms, threshold_ms)


def get_metrics_summary(hours: int = 24) -> Dict[str, Any]:
    """Retourne un résumé des métriques."""
    return get_metrics_collector().build_metrics_summary(hours)


def add_alert(alert: AlertRule):
    """Ajoute une règle d'alerte."""
    get_metrics_collector().add_alert(alert)


def export_metrics_csv(filename: str, hours: int = 24):
    """Exporte les métriques vers un fichier CSV."""
    get_metrics_collector().export_to_csv(filename, hours)


def export_metrics_json(filename: str, hours: int = 24):
    """Exporte les métriques vers un fichier JSON."""
    get_metrics_collector().export_to_json(filename, hours)


def monitor_task_performance(task_name: str, threshold: float = 1.0):
    """
    Décorateur pour monitorer automatiquement les performances des tâches.
    
    Utilisation :
        @monitor_task_performance("volatility_calculation", threshold=2.0)
        async def compute_volatility(symbols):
            # ... code de la tâche
    
    Args:
        task_name: Nom de la tâche pour l'identification
        threshold: Seuil en secondes pour considérer une tâche comme lente
    """
    def decorator(func):
        import inspect
        if inspect.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    execution_time = time.time() - start_time
                    execution_time_ms = execution_time * 1000
                    threshold_ms = threshold * 1000
                    get_metrics_collector().record_task_execution(task_name, execution_time_ms, threshold_ms)
                    if execution_time > threshold:
                        import logging
                        logging.warning(f"⚠️ Tâche lente détectée: {task_name} a pris {execution_time:.2f}s")
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    execution_time = time.time() - start_time
                    execution_time_ms = execution_time * 1000
                    threshold_ms = threshold * 1000
                    get_metrics_collector().record_task_execution(task_name, execution_time_ms, threshold_ms)
                    if execution_time > threshold:
                        import logging
                        logging.warning(f"⚠️ Tâche lente détectée: {task_name} a pris {execution_time:.2f}s")
            return sync_wrapper
    return decorator
