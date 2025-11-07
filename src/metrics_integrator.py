#!/usr/bin/env python3
"""
Intégrateur de métriques pour le bot Bybit.

Ce module intègre tous les systèmes de métriques :
- Collecte de métriques améliorée
- Dashboard en temps réel
- Système d'alertes
- Export des données

⚠️ NOTE: Ce module contient du code actuellement non utilisé dans le code principal.
La classe MetricsIntegrator et les fonctions publiques sont commentées car elles ne sont
pas référencées dans le code principal du bot. Elles sont conservées pour une utilisation
future potentielle.
"""

import time
import threading
from typing import Dict, Any, Optional
from pathlib import Path

from enhanced_metrics import get_metrics_collector, AlertRule
from metrics_alerts import get_alert_manager, AlertNotification
from metrics_dashboard import MetricsDashboard


# ⚠️ CODE COMMENTÉ - NON UTILISÉ DANS LE CODE PRINCIPAL
# Cette classe et les fonctions publiques ci-dessous ne sont pas référencées
# dans le code principal du bot. Conservées pour utilisation future.
#
# class MetricsIntegrator:
#     """
#     Intégrateur principal des métriques.
#
#     Ce module coordonne tous les systèmes de métriques :
#     - Collecte des métriques
#     - Surveillance des alertes
#     - Dashboard en temps réel
#     - Export des données
#     """
#
#     def __init__(self, enable_dashboard: bool = True, enable_alerts: bool = True):
#         """
#         Initialise l'intégrateur de métriques.
#
#         Args:
#             enable_dashboard: Activer le dashboard en temps réel
#             enable_alerts: Activer le système d'alertes
#         """
#         self.collector = get_metrics_collector()
#         self.alert_manager = get_alert_manager()
#         self.dashboard = MetricsDashboard() if enable_dashboard else None
#
#         self.enable_dashboard = enable_dashboard
#         self.enable_alerts = enable_alerts
#
#         self.running = False
#         self._monitor_thread: Optional[threading.Thread] = None
#
#         # Configuration des alertes par défaut
#         if enable_alerts:
#             self._setup_default_alerts()
#             self._setup_default_notifications()
#
#     def _setup_default_alerts(self):
#         """Configure les alertes par défaut."""
#         # Alerte taux d'erreur API élevé
#         self.alert_manager.add_alert(AlertRule(
#             name="API Error Rate High",
#             metric_name="error_rate_percent",
#             condition=">",
#             threshold=15.0,
#             duration_seconds=60
#         ))
#
#         # Alerte latence API élevée
#         self.alert_manager.add_alert(AlertRule(
#             name="API Latency High",
#             metric_name="api_latency_ms",
#             condition=">",
#             threshold=3000.0,
#             duration_seconds=30
#         ))
#
#         # Alerte utilisation mémoire élevée
#         self.alert_manager.add_alert(AlertRule(
#             name="Memory Usage High",
#             metric_name="memory_usage_mb",
#             condition=">",
#             threshold=1500.0,
#             duration_seconds=120
#         ))
#
#         # Alerte WebSocket déconnecté
#         self.alert_manager.add_alert(AlertRule(
#             name="WebSocket Disconnected",
#             metric_name="ws_connections",
#             condition="==",
#             threshold=0.0,
#             duration_seconds=30
#         ))
#
#         # Alerte tâches lentes
#         self.alert_manager.add_alert(AlertRule(
#             name="Slow Tasks",
#             metric_name="task_execution_time_ms",
#             condition=">",
#             threshold=5000.0,
#             duration_seconds=60
#         ))
#
#     def _setup_default_notifications(self):
#         """Configure les notifications par défaut."""
#         # Notification console
#         self.alert_manager.add_notification(AlertNotification(
#             type="console",
#             config={},
#             enabled=True
#         ))
#
#         # Notification fichier
#         self.alert_manager.add_notification(AlertNotification(
#             type="file",
#             config={"filename": "alerts.log"},
#             enabled=True
#         ))
#
#     def start(self):
#         """Démarre l'intégrateur de métriques."""
#         if self.running:
#             print("⚠️ L'intégrateur de métriques est déjà actif")
#             return
#
#         self.running = True
#
#         # Démarrer la surveillance des alertes
#         if self.enable_alerts:
#             self.alert_manager.start_monitoring(interval_seconds=30)
#             print("🔍 Surveillance des alertes démarrée")
#
#         # Démarrer le monitoring des métriques système
#         self._start_system_monitoring()
#
#         print("✅ Intégrateur de métriques démarré")
#
#     def stop(self):
#         """Arrête l'intégrateur de métriques."""
#         self.running = False
#
#         if self.dashboard:
#             self.dashboard.stop()
#
#         print("🛑 Intégrateur de métriques arrêté")
#
#     def _start_system_monitoring(self):
#         """Démarre le monitoring des métriques système."""
#         def system_monitor_loop():
#             while self.running:
#                 try:
#                     # Enregistrer les métriques système
#                     self.collector.record_system_metrics()
#
#                     # Calculer le taux d'erreur
#                     self._calculate_error_rate()
#
#                     time.sleep(60)  # Mise à jour toutes les minutes
#                 except Exception as e:
#                     print(f"❌ Erreur monitoring système: {e}")
#                     time.sleep(60)
#
#         self._monitor_thread = threading.Thread(target=system_monitor_loop, daemon=True)
#         self._monitor_thread.start()
#
#     def _calculate_error_rate(self):
#         """Calcule et enregistre le taux d'erreur."""
#         try:
#             # Obtenir les métriques API
#             api_calls = self.collector.get_metric_summary("api_calls_total", hours=1)
#             api_errors = self.collector.get_metric_summary("api_errors_total", hours=1)
#
#             if api_calls and api_errors:
#                 calls_count = api_calls.get('count', 0)
#                 errors_count = api_errors.get('count', 0)
#
#                 if calls_count > 0:
#                     error_rate = (errors_count / calls_count) * 100
#                     self.collector.record_metric("error_rate_percent", error_rate)
#         except Exception as e:
#             print(f"❌ Erreur calcul taux d'erreur: {e}")
#
#     def run_dashboard(self):
#         """Lance le dashboard en temps réel."""
#         if not self.dashboard:
#             print("❌ Dashboard non disponible")
#             return
#
#         self.dashboard.run()
#
#     def export_metrics(self, format: str = "json", hours: int = 24):
#         """Exporte les métriques."""
#         timestamp = int(time.time())
#
#         if format == "json":
#             filename = f"metrics_export_{timestamp}.json"
#             self.collector.export_to_json(filename, hours)
#             print(f"📊 Métriques exportées vers {filename}")
#
#         elif format == "csv":
#             filename = f"metrics_export_{timestamp}.csv"
#             self.collector.export_to_csv(filename, hours)
#             print(f"📊 Métriques exportées vers {filename}")
#
#         else:
#             print(f"❌ Format non supporté: {format}")
#
#     def get_status(self) -> Dict[str, Any]:
#         """Retourne le statut de l'intégrateur."""
#         status = {
#             "running": self.running,
#             "dashboard_enabled": self.enable_dashboard,
#             "alerts_enabled": self.enable_alerts,
#             "metrics_summary": self.collector.get_all_metrics_summary(hours=1)
#         }
#
#         if self.enable_alerts:
#             status["alert_status"] = self.alert_manager.get_alert_status()
#
#         return status
#
#     def add_custom_alert(self, name: str, metric_name: str, condition: str, threshold: float, duration_seconds: int = 0):
#         """Ajoute une alerte personnalisée."""
#         alert = AlertRule(
#             name=name,
#             metric_name=metric_name,
#             condition=condition,
#             threshold=threshold,
#             duration_seconds=duration_seconds
#         )
#
#         self.alert_manager.add_alert(alert)
#         print(f"✅ Alerte ajoutée: {name}")
#
#     def add_email_notification(self, smtp_config: Dict[str, str]):
#         """Ajoute une notification par email."""
#         notification = AlertNotification(
#             type="email",
#             config=smtp_config,
#             enabled=True
#         )
#
#         self.alert_manager.add_notification(notification)
#         print("✅ Notification email ajoutée")
#
#     def add_webhook_notification(self, webhook_url: str):
#         """Ajoute une notification par webhook."""
#         notification = AlertNotification(
#             type="webhook",
#             config={"webhook_url": webhook_url},
#             enabled=True
#         )
#
#         self.alert_manager.add_notification(notification)
#         print("✅ Notification webhook ajoutée")
#
#
# # ⚠️ CODE COMMENTÉ - NON UTILISÉ DANS LE CODE PRINCIPAL
# # Instance globale
# # _global_integrator: Optional[MetricsIntegrator] = None
#
#
# # ⚠️ CODE COMMENTÉ - NON UTILISÉ DANS LE CODE PRINCIPAL
# # def get_metrics_integrator() -> MetricsIntegrator:
# #     """Retourne l'instance globale de l'intégrateur de métriques."""
# #     global _global_integrator
# #     if _global_integrator is None:
# #         _global_integrator = MetricsIntegrator()
# #     return _global_integrator
#
#
# # ⚠️ CODE COMMENTÉ - NON UTILISÉ DANS LE CODE PRINCIPAL
# # Fonctions de convenance
# # def start_metrics_system(enable_dashboard: bool = True, enable_alerts: bool = True):
# #     """Démarre le système de métriques complet."""
# #     integrator = MetricsIntegrator(enable_dashboard, enable_alerts)
# #     integrator.start()
# #     return integrator
#
#
# # ⚠️ CODE COMMENTÉ - NON UTILISÉ DANS LE CODE PRINCIPAL
# # def run_dashboard():
# #     """Lance le dashboard de métriques."""
# #     integrator = get_metrics_integrator()
# #     integrator.run_dashboard()
#
#
# # ⚠️ CODE COMMENTÉ - NON UTILISÉ DANS LE CODE PRINCIPAL
# # def export_metrics(format: str = "json", hours: int = 24):
# #     """Exporte les métriques."""
# #     integrator = get_metrics_integrator()
# #     integrator.export_metrics(format, hours)
#
#
# # ⚠️ CODE COMMENTÉ - NON UTILISÉ DANS LE CODE PRINCIPAL
# # def get_metrics_status() -> Dict[str, Any]:
# #     """Retourne le statut du système de métriques."""
# #     integrator = get_metrics_integrator()
# #     return integrator.get_status()
#
#
# # ⚠️ CODE COMMENTÉ - NON UTILISÉ DANS LE CODE PRINCIPAL
# # def add_custom_alert(name: str, metric_name: str, condition: str, threshold: float, duration_seconds: int = 0):
# #     """Ajoute une alerte personnalisée."""
# #     integrator = get_metrics_integrator()
# #     integrator.add_custom_alert(name, metric_name, condition, threshold, duration_seconds)
#
#
# # ⚠️ CODE COMMENTÉ - NON UTILISÉ DANS LE CODE PRINCIPAL
# # def add_email_notification(smtp_config: Dict[str, str]):
# #     """Ajoute une notification par email."""
# #     integrator = get_metrics_integrator()
# #     integrator.add_email_notification(smtp_config)
#
#
# # ⚠️ CODE COMMENTÉ - NON UTILISÉ DANS LE CODE PRINCIPAL
# # def add_webhook_notification(webhook_url: str):
# #     """Ajoute une notification par webhook."""
# #     integrator = get_metrics_integrator()
# #     integrator.add_webhook_notification(webhook_url)
