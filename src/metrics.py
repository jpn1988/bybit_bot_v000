#!/usr/bin/env python3
"""
Module de métriques pour le monitoring et l'observabilité du bot.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

Ce module fournit un système de métriques thread-safe pour surveiller
les performances et l'état du bot en temps réel.

🔍 COMPRENDRE CE FICHIER EN 3 MINUTES :

1. MetricsData (lignes 38-50) - Structure de données des métriques
2. MetricsCollector (lignes 52-156) - Collecteur thread-safe
3. Fonctions globales (lignes 158-185) - API simplifiée

📊 MÉTRIQUES COLLECTÉES :

Performance API :
- api_calls_total : Nombre total d'appels API
- api_errors_total : Nombre d'erreurs API
- api_latencies : Latences des requêtes (deque des 100 dernières)

Filtrage :
- pairs_kept_total : Nombre de paires gardées par les filtres
- pairs_rejected_total : Nombre de paires rejetées
- filter_stats : Statistiques par filtre (funding, spread, etc.)

WebSocket :
- ws_connections : Nombre de connexions établies
- ws_reconnects : Nombre de reconnexions
- ws_errors : Nombre d'erreurs WebSocket

🔒 THREAD-SAFETY :

Le collecteur utilise un verrou (threading.Lock) pour garantir
la cohérence des données dans un environnement multi-thread.

Exemple de race condition évitée :
    Thread 1 : api_calls_total += 1  # Lit 10, écrit 11
    Thread 2 : api_calls_total += 1  # Lit 10, écrit 11  ❌ Bug!
    
Avec lock :
    Thread 1 : with lock: api_calls_total += 1  # 10 → 11
    Thread 2 : with lock: api_calls_total += 1  # 11 → 12 ✅

📚 EXEMPLE D'UTILISATION :

```python
from metrics import (
    record_api_call,
    record_filter_result,
    record_ws_connection,
    get_metrics_summary
)

# Enregistrer un appel API
start = time.time()
response = requests.get("https://api.bybit.com/...")
latency = time.time() - start
record_api_call(latency, success=True)

# Enregistrer un résultat de filtre
record_filter_result("funding_filter", kept=5, rejected=10)

# Enregistrer une connexion WebSocket
record_ws_connection(connected=True)

# Obtenir le résumé des métriques
summary = get_metrics_summary()
print(f"API calls: {summary['api_calls']}")
print(f"Avg latency: {summary['avg_api_latency']:.3f}s")
print(f"WS connections: {summary['ws_connections']}")
```

📖 RÉFÉRENCES :
- threading.Lock: https://docs.python.org/3/library/threading.html#threading.Lock
- collections.deque: https://docs.python.org/3/library/collections.html#collections.deque
"""

import time
import threading
import asyncio
from typing import Dict, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
import statistics


@dataclass
class MetricsData:
    """
    Structure de données pour stocker toutes les métriques du bot.
    
    Cette dataclass contient tous les compteurs, latences et statistiques
    collectées pendant l'exécution du bot.
    
    Attributes:
        api_calls_total (int): Nombre total d'appels API effectués
        api_errors_total (int): Nombre d'erreurs API rencontrées
        pairs_kept_total (int): Nombre de paires gardées par les filtres
        pairs_rejected_total (int): Nombre de paires rejetées
        api_latencies (deque): Latences des 100 dernières requêtes API (secondes)
        last_update (float): Timestamp de la dernière mise à jour
        filter_stats (dict): Statistiques par filtre {nom: {kept, rejected}}
        ws_connections (int): Nombre de connexions WebSocket établies
        ws_reconnects (int): Nombre de reconnexions WebSocket
        ws_errors (int): Nombre d'erreurs WebSocket
        
    Example:
        ```python
        data = MetricsData()
        data.api_calls_total = 150
        data.api_errors_total = 2
        data.api_latencies.append(0.245)  # 245ms
        ```
    """

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
    filter_stats: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: {"kept": 0, "rejected": 0})
    )

    # Métriques WebSocket
    ws_connections: int = 0
    ws_reconnects: int = 0
    ws_errors: int = 0
    
    # Métriques de performance des tâches
    task_execution_times: Dict[str, deque] = field(
        default_factory=lambda: defaultdict(lambda: deque(maxlen=50))
    )
    slow_tasks_count: int = 0  # Compteur des tâches lentes (>1s)


class MetricsCollector:
    """
    Collecteur de métriques thread-safe pour le bot.
    
    Ce collecteur maintient un ensemble de métriques thread-safe qui peuvent
    être mises à jour depuis n'importe quel thread en toute sécurité.
    
    Architecture :
    - 1 verrou (threading.Lock) pour la synchronisation
    - 1 instance MetricsData pour stocker les données
    - Méthodes thread-safe pour enregistrer les métriques
    
    Attributes:
        _data (MetricsData): Données des métriques
        _lock (threading.Lock): Verrou pour thread-safety
        _start_time (float): Timestamp de démarrage du collecteur
        
    Example:
        ```python
        # Créer le collecteur (généralement singleton)
        collector = MetricsCollector()
        
        # Enregistrer des métriques depuis différents threads
        collector.record_api_call(latency=0.245, success=True)
        collector.record_filter_result("funding", kept=5, rejected=3)
        collector.record_ws_connection(connected=True)
        
        # Obtenir le résumé
        summary = collector.get_metrics_summary()
        print(f"Total API calls: {summary['api_calls']}")
        ```
        
    Note:
        - Toutes les méthodes sont thread-safe (utilisent self._lock)
        - Les latences sont limitées aux 100 dernières (deque maxlen=100)
        - Le start_time permet de calculer l'uptime
    """

    def __init__(self):
        """
        Initialise le collecteur de métriques.
        
        Crée la structure de données, le verrou et enregistre le temps de démarrage.
        """
        self._data = MetricsData()
        self._lock = threading.Lock()
        self._start_time = time.time()

    def record_api_call(self, latency: float, success: bool = True):
        """
        Enregistre un appel API avec sa latence et son statut.
        
        Cette méthode est thread-safe et peut être appelée depuis n'importe quel thread.
        
        Args:
            latency (float): Latence de la requête en secondes
                          Exemple: 0.245 = 245ms
            success (bool): True si la requête a réussi, False sinon
                          Si False, incrémente aussi api_errors_total
                          
        Example:
            ```python
            # Mesurer une requête API
            start = time.time()
            try:
                response = client.get("https://api.bybit.com/...")
                latency = time.time() - start
                record_api_call(latency, success=True)
            except Exception:
                latency = time.time() - start
                record_api_call(latency, success=False)
            ```
            
        Note:
            - Les latences sont stockées dans une deque (max 100)
            - Anciennes latences sont automatiquement supprimées
        """
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

    def record_task_execution(self, task_name: str, execution_time: float, threshold: float = 1.0):
        """
        Enregistre le temps d'exécution d'une tâche.
        
        Cette méthode ajoute une nouvelle méthode pour tracker les performances
        des tâches critiques et détecter les tâches lentes.
        
        Args:
            task_name (str): Nom de la tâche (ex: "volatility_calculation", "pagination")
            execution_time (float): Temps d'exécution en secondes
            threshold (float): Seuil en secondes pour considérer une tâche comme lente (défaut: 1.0)
        """
        with self._lock:
            self._data.task_execution_times[task_name].append(execution_time)
            if execution_time > threshold:
                self._data.slow_tasks_count += 1
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
                error_rate = (
                    self._data.api_errors_total / self._data.api_calls_total
                ) * 100

            # Calculer le taux de réussite des filtres
            total_pairs_processed = (
                self._data.pairs_kept_total + self._data.pairs_rejected_total
            )
            filter_success_rate = 0.0
            if total_pairs_processed > 0:
                filter_success_rate = (
                    self._data.pairs_kept_total / total_pairs_processed
                ) * 100

            # Calculer les moyennes des temps d'exécution des tâches
            task_performance = {}
            for task_name, execution_times in self._data.task_execution_times.items():
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
                "slow_tasks_count": self._data.slow_tasks_count,
                "task_performance": task_performance,
                "last_update": self._data.last_update,
                "filter_stats": dict(self._data.filter_stats),
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


def record_task_execution(task_name: str, execution_time: float, threshold: float = 1.0):
    """Enregistre le temps d'exécution d'une tâche."""
    metrics_collector.record_task_execution(task_name, execution_time, threshold)


def get_metrics_summary() -> Dict[str, Any]:
    """Retourne un résumé des métriques."""
    return metrics_collector.get_metrics_summary()


def monitor_task_performance(task_name: str, threshold: float = 1.0):
    """
    Décorateur pour monitorer automatiquement les performances des tâches.
    
    Utilisation :
        @monitor_task_performance("volatility_calculation", threshold=2.0)
        async def compute_volatility(symbols):
            # ... code de la tâche
    
    Args:
        task_name (str): Nom de la tâche pour l'identification
        threshold (float): Seuil en secondes pour considérer une tâche comme lente
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
                    record_task_execution(task_name, execution_time, threshold)
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
                    record_task_execution(task_name, execution_time, threshold)
                    if execution_time > threshold:
                        import logging
                        logging.warning(f"⚠️ Tâche lente détectée: {task_name} a pris {execution_time:.2f}s")
            return sync_wrapper
    return decorator
