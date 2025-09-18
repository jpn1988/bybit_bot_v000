"""Module de monitoring périodique des métriques."""

import time
import threading
from typing import Optional
from metrics import get_metrics_summary
from logging_setup import setup_logging


class MetricsMonitor:
    """Moniteur périodique des métriques."""
    
    def __init__(self, interval_minutes: int = 5):
        """
        Initialise le moniteur de métriques.
        
        Args:
            interval_minutes (int): Intervalle de monitoring en minutes
        """
        self.interval_seconds = interval_minutes * 60
        self.logger = setup_logging()
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def start(self):
        """Démarre le monitoring des métriques."""
        if self.running:
            self.logger.warning("⚠️ Le monitoring des métriques est déjà actif")
            return
        
        self.running = True
        self._stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info(f"📊 Monitoring des métriques démarré (intervalle: {self.interval_seconds//60} minutes)")
    
    def stop(self):
        """Arrête le monitoring des métriques."""
        if not self.running:
            return
        
        self.running = False
        self._stop_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        self.logger.info("📊 Monitoring des métriques arrêté")
    
    def _monitor_loop(self):
        """Boucle principale de monitoring."""
        while self.running and not self._stop_event.is_set():
            try:
                self._log_metrics()
            except Exception as e:
                self.logger.error(f"❌ Erreur lors du monitoring des métriques: {e}")
            
            # Attendre l'intervalle ou jusqu'à l'arrêt
            if self._stop_event.wait(self.interval_seconds):
                break
    
    def _log_metrics(self):
        """Log les métriques actuelles."""
        try:
            metrics = get_metrics_summary()
            
            # Formatage des métriques pour les logs
            uptime_hours = metrics["uptime_seconds"] / 3600
            
            self.logger.info("📊 MÉTRIQUES BOT:")
            self.logger.info(f"   ⏱️  Uptime: {uptime_hours:.1f}h")
            self.logger.info(f"   🔌 API: {metrics['api_calls_total']} appels | {metrics['api_error_rate_percent']}% erreurs | {metrics['api_avg_latency_ms']}ms latence")
            self.logger.info(f"   🎯 Filtres: {metrics['pairs_kept_total']} gardées | {metrics['pairs_rejected_total']} rejetées | {metrics['filter_success_rate_percent']}% succès")
            self.logger.info(f"   🌐 WebSocket: {metrics['ws_connections']} connexions | {metrics['ws_reconnects']} reconnexions | {metrics['ws_errors']} erreurs")
            
            # Détails par filtre si disponibles
            if metrics["filter_stats"]:
                self.logger.info("   📈 Détails par filtre:")
                for filter_name, stats in metrics["filter_stats"].items():
                    kept = stats["kept"]
                    rejected = stats["rejected"]
                    total = kept + rejected
                    success_rate = (kept / total * 100) if total > 0 else 0
                    self.logger.info(f"      {filter_name}: {kept} gardées | {rejected} rejetées | {success_rate:.1f}% succès")
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors du formatage des métriques: {e}")
    
    def log_metrics_now(self):
        """Force l'affichage des métriques maintenant."""
        try:
            self._log_metrics()
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de l'affichage des métriques: {e}")


# Instance globale du moniteur
metrics_monitor = MetricsMonitor()


def start_metrics_monitoring(interval_minutes: int = 5):
    """Démarre le monitoring des métriques."""
    global metrics_monitor
    metrics_monitor = MetricsMonitor(interval_minutes)
    metrics_monitor.start()


def stop_metrics_monitoring():
    """Arrête le monitoring des métriques."""
    global metrics_monitor
    metrics_monitor.stop()


def log_metrics_now():
    """Force l'affichage des métriques maintenant."""
    global metrics_monitor
    metrics_monitor.log_metrics_now()
