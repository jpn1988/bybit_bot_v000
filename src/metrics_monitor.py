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
        # Monitoring des métriques démarré
    
    def stop(self):
        """Arrête le monitoring des métriques."""
        if not self.running:
            return
        
        self.running = False
        self._stop_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            # Attendre l'arrêt propre avec timeout plus court
            self.monitor_thread.join(timeout=3)  # Timeout réduit à 3s
            
            # Si le thread ne s'est pas arrêté, forcer l'arrêt
            if self.monitor_thread.is_alive():
                self.logger.warning("⚠️ Thread métriques n'a pas pu s'arrêter proprement, arrêt forcé")
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
            
            # Métriques bot
            
            # Détails par filtre
            
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


