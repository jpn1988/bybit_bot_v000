"""Module de monitoring périodique des métriques."""

import threading
from typing import Optional
from enhanced_metrics import get_metrics_summary
from logging_setup import setup_logging
from config.timeouts import TimeoutConfig


class MetricsMonitor:
    """Moniteur périodique des métriques."""

    def __init__(self, interval_minutes: int = None):
        """
        Initialise le moniteur de métriques.

        Args:
            interval_minutes (int): Intervalle de monitoring en minutes
        """
        if interval_minutes is None:
            from config.constants import DEFAULT_METRICS_INTERVAL
            interval_minutes = DEFAULT_METRICS_INTERVAL
        self.interval_seconds = interval_minutes * 60
        self.logger = setup_logging()
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self):
        """Démarre le monitoring des métriques."""
        if self.running:
            self.logger.warning(
                "⚠️ Le monitoring des métriques est déjà actif"
            )
            return

        self.running = True
        self._stop_event.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True
        )
        self.monitor_thread.start()
        # Monitoring des métriques démarré

    def stop(self):
        """Arrête le monitoring des métriques."""
        if not self.running:
            return

        self.running = False
        self._stop_event.set()

        if self.monitor_thread and self.monitor_thread.is_alive():
            # Attendre l'arrêt propre avec timeout
            self.monitor_thread.join(timeout=TimeoutConfig.ASYNC_TASK_SHUTDOWN)

            # Si le thread ne s'est pas arrêté, forcer l'arrêt
            if self.monitor_thread.is_alive():
                self.logger.warning(
                    "⚠️ Thread métriques n'a pas pu s'arrêter proprement, arrêt forcé"
                )
                # Marquer le thread comme daemon pour qu'il s'arrête avec le programme
                self.monitor_thread.daemon = True

        # Nettoyer la référence du thread
        self.monitor_thread = None
        # Monitoring des métriques arrêté

    def _monitor_loop(self):
        """Boucle principale de monitoring."""
        while self.running and not self._stop_event.is_set():
            try:
                self._log_metrics()
            except Exception as e:
                self.logger.error(
                    f"❌ Erreur lors du monitoring des métriques: {e}"
                )

            # Attendre l'intervalle ou jusqu'à l'arrêt
            if self._stop_event.wait(self.interval_seconds):
                break

    def _log_metrics(self):
        """Log les métriques actuelles."""
        try:
            metrics = get_metrics_summary()

            # Calculer l'uptime en heures/minutes
            uptime_hours = metrics["uptime_seconds"] / 3600
            uptime_minutes = (metrics["uptime_seconds"] % 3600) / 60

            # Afficher le résumé des métriques du bot
            self.logger.info("=" * 70)
            self.logger.info("📊 RÉSUMÉ DES MÉTRIQUES DU BOT")
            self.logger.info("=" * 70)

            # Uptime
            self.logger.info(
                f"⏱️  Uptime: {int(uptime_hours)}h {int(uptime_minutes)}m "
                f"({metrics['uptime_seconds']:.0f}s)"
            )

            # Métriques API
            self.logger.info(
                f"📡 API: {metrics['api_calls_total']} appels | "
                f"{metrics['api_errors_total']} erreurs | "
                f"Taux erreur: {metrics['api_error_rate_percent']:.1f}% | "
                f"Latence moy: {metrics['api_avg_latency_ms']:.1f}ms"
            )

            # Métriques de filtrage
            total_pairs = metrics['pairs_kept_total'] + metrics['pairs_rejected_total']
            self.logger.info(
                f"🔍 Filtrage: {metrics['pairs_kept_total']} gardées | "
                f"{metrics['pairs_rejected_total']} rejetées | "
                f"Total: {total_pairs} | "
                f"Taux succès: {metrics['filter_success_rate_percent']:.1f}%"
            )

            # Métriques WebSocket
            self.logger.info(
                f"🌐 WebSocket: {metrics['ws_connections']} connexions | "
                f"{metrics['ws_reconnects']} reconnexions | "
                f"{metrics['ws_errors']} erreurs"
            )

            # Détails par filtre (si disponibles)
            filter_stats = metrics.get('filter_stats', {})
            if filter_stats:
                self.logger.info("-" * 70)
                self.logger.info("📋 Détails par filtre:")
                for filter_name, stats in filter_stats.items():
                    kept = stats.get('kept', 0)
                    rejected = stats.get('rejected', 0)
                    total = kept + rejected
                    success_rate = (kept / total * 100) if total > 0 else 0
                    self.logger.info(
                        f"   • {filter_name}: {kept} gardées | "
                        f"{rejected} rejetées | "
                        f"Taux: {success_rate:.1f}%"
                    )

            self.logger.info("=" * 70)

        except Exception as e:
            self.logger.error(f"❌ Erreur lors du formatage des métriques: {e}")

    def log_metrics_now(self):
        """Force l'affichage des métriques maintenant."""
        try:
            self._log_metrics()
        except Exception as e:
            self.logger.error(
                f"❌ Erreur lors de l'affichage des métriques: {e}"
            )


# Instance globale du moniteur
metrics_monitor = MetricsMonitor()


def start_metrics_monitoring(interval_minutes: int = 5):
    """Démarre le monitoring des métriques."""
    global metrics_monitor
    metrics_monitor = MetricsMonitor(interval_minutes)
    metrics_monitor.start()
    return metrics_monitor
