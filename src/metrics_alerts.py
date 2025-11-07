#!/usr/bin/env python3
"""
Système d'alertes avancé pour les métriques du bot.

Ce module fournit un système d'alertes configurable avec :
- Règles d'alerte flexibles
- Notifications multiples (email, webhook, fichier)
- Gestion des états d'alerte
- Historique des alertes
"""

import time
import json
import smtplib
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

from enhanced_metrics import get_metrics_collector, AlertRule


@dataclass
class AlertState:
    """État d'une alerte."""
    name: str
    triggered: bool = False
    first_triggered: Optional[float] = None
    last_triggered: Optional[float] = None
    trigger_count: int = 0
    last_value: Optional[float] = None


@dataclass
class AlertNotification:
    """Configuration de notification d'alerte."""
    type: str  # "email", "webhook", "file", "console"
    config: Dict[str, Any]
    enabled: bool = True


class MetricsAlertManager:
    """
    Gestionnaire d'alertes pour les métriques.

    Fonctionnalités :
    - Règles d'alerte configurables
    - Notifications multiples
    - Gestion des états d'alerte
    - Historique des alertes
    """

    def __init__(self):
        """Initialise le gestionnaire d'alertes."""
        self.collector = get_metrics_collector()
        self.alert_states: Dict[str, AlertState] = {}
        self.notifications: List[AlertNotification] = []
        self.alert_history: List[Dict[str, Any]] = []

        # Thread safety
        self._lock = threading.Lock()

        # Configuration par défaut
        self._setup_default_alerts()

    def _setup_default_alerts(self):
        """Configure les alertes par défaut."""
        # Alerte taux d'erreur API élevé
        self.add_alert(AlertRule(
            name="API Error Rate High",
            metric_name="error_rate_percent",
            condition=">",
            threshold=10.0,
            duration_seconds=60
        ))

        # Alerte latence API élevée
        self.add_alert(AlertRule(
            name="API Latency High",
            metric_name="api_latency_ms",
            condition=">",
            threshold=2000.0,
            duration_seconds=30
        ))

        # Alerte utilisation mémoire élevée
        self.add_alert(AlertRule(
            name="Memory Usage High",
            metric_name="memory_usage_mb",
            condition=">",
            threshold=1000.0,
            duration_seconds=120
        ))

        # Alerte WebSocket déconnecté
        self.add_alert(AlertRule(
            name="WebSocket Disconnected",
            metric_name="ws_connections",
            condition="==",
            threshold=0.0,
            duration_seconds=10
        ))

    def add_alert(self, alert: AlertRule):
        """Ajoute une règle d'alerte."""
        self.collector.add_alert(alert)

        # Créer l'état de l'alerte
        with self._lock:
            self.alert_states[alert.name] = AlertState(name=alert.name)

    def add_notification(self, notification: AlertNotification):
        """Ajoute une configuration de notification."""
        with self._lock:
            self.notifications.append(notification)

    def check_alerts(self):
        """Vérifie toutes les alertes."""
        with self._lock:
            for alert_name, state in self.alert_states.items():
                # Trouver la règle d'alerte correspondante
                alert_rule = None
                for alert in self.collector._alerts:
                    if alert.name == alert_name:
                        alert_rule = alert
                        break

                if not alert_rule or not alert_rule.enabled:
                    continue

                # Obtenir la valeur actuelle de la métrique
                metric_summary = self.collector.get_metric_summary(alert_rule.metric_name, hours=1)
                if not metric_summary:
                    continue

                current_value = metric_summary.get('latest', 0)
                state.last_value = current_value

                # Vérifier la condition
                condition_met = self._evaluate_condition(
                    current_value, alert_rule.condition, alert_rule.threshold
                )

                if condition_met:
                    if not state.triggered:
                        # Nouvelle alerte
                        state.triggered = True
                        state.first_triggered = time.time()
                        state.last_triggered = time.time()
                        state.trigger_count = 1

                        # Vérifier la durée
                        if alert_rule.duration_seconds == 0:
                            self._trigger_alert(alert_rule, current_value)
                    else:
                        # Alerte déjà active
                        state.last_triggered = time.time()
                        state.trigger_count += 1

                        # Vérifier si on doit déclencher l'alerte
                        if (time.time() - state.first_triggered) >= alert_rule.duration_seconds:
                            if state.trigger_count == 1:  # Première fois qu'on atteint la durée
                                self._trigger_alert(alert_rule, current_value)
                else:
                    if state.triggered:
                        # Alerte résolue
                        self._resolve_alert(alert_rule, current_value)
                        state.triggered = False
                        state.first_triggered = None
                        state.last_triggered = None
                        state.trigger_count = 0

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

    def _trigger_alert(self, alert: AlertRule, value: float):
        """Déclenche une alerte."""
        alert_data = {
            "timestamp": time.time(),
            "alert_name": alert.name,
            "metric_name": alert.metric_name,
            "condition": alert.condition,
            "threshold": alert.threshold,
            "current_value": value,
            "status": "triggered"
        }

        # Ajouter à l'historique
        with self._lock:
            self.alert_history.append(alert_data)
            # Garder seulement les 1000 dernières alertes
            if len(self.alert_history) > 1000:
                self.alert_history = self.alert_history[-1000:]

        # Envoyer les notifications
        self._send_notifications(alert_data)

    def _resolve_alert(self, alert: AlertRule, value: float):
        """Résout une alerte."""
        alert_data = {
            "timestamp": time.time(),
            "alert_name": alert.name,
            "metric_name": alert.metric_name,
            "condition": alert.condition,
            "threshold": alert.threshold,
            "current_value": value,
            "status": "resolved"
        }

        # Ajouter à l'historique
        with self._lock:
            self.alert_history.append(alert_data)

        # Envoyer les notifications de résolution
        self._send_notifications(alert_data)

    def _send_notifications(self, alert_data: Dict[str, Any]):
        """Envoie les notifications d'alerte."""
        for notification in self.notifications:
            if not notification.enabled:
                continue

            try:
                if notification.type == "email":
                    self._send_email_notification(notification, alert_data)
                elif notification.type == "webhook":
                    self._send_webhook_notification(notification, alert_data)
                elif notification.type == "file":
                    self._send_file_notification(notification, alert_data)
                elif notification.type == "console":
                    self._send_console_notification(notification, alert_data)
            except Exception as e:
                print(f"❌ Erreur envoi notification {notification.type}: {e}")

    def _send_email_notification(self, notification: AlertNotification, alert_data: Dict[str, Any]):
        """Envoie une notification par email."""
        config = notification.config

        msg = MIMEMultipart()
        msg['From'] = config.get('from_email')
        msg['To'] = config.get('to_email')
        msg['Subject'] = f"🚨 Alerte Bot Bybit: {alert_data['alert_name']}"

        body = f"""
        Alerte: {alert_data['alert_name']}
        Métrique: {alert_data['metric_name']}
        Condition: {alert_data['current_value']} {alert_data['condition']} {alert_data['threshold']}
        Statut: {alert_data['status']}
        Timestamp: {datetime.fromtimestamp(alert_data['timestamp']).isoformat()}
        """

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(config.get('smtp_host'), config.get('smtp_port'))
        server.starttls()
        server.login(config.get('username'), config.get('password'))
        server.send_message(msg)
        server.quit()

    def _send_webhook_notification(self, notification: AlertNotification, alert_data: Dict[str, Any]):
        """Envoie une notification via webhook."""
        config = notification.config

        payload = {
            "text": f"🚨 Alerte Bot Bybit: {alert_data['alert_name']}",
            "attachments": [{
                "color": "danger" if alert_data['status'] == 'triggered' else "good",
                "fields": [
                    {"title": "Métrique", "value": alert_data['metric_name'], "short": True},
                    {"title": "Condition", "value": f"{alert_data['current_value']} {alert_data['condition']} {alert_data['threshold']}", "short": True},
                    {"title": "Statut", "value": alert_data['status'], "short": True},
                    {"title": "Timestamp", "value": datetime.fromtimestamp(alert_data['timestamp']).isoformat(), "short": False}
                ]
            }]
        }

        requests.post(config.get('webhook_url'), json=payload, timeout=10)

    def _send_file_notification(self, notification: AlertNotification, alert_data: Dict[str, Any]):
        """Envoie une notification vers un fichier."""
        config = notification.config
        filename = config.get('filename', 'alerts.log')

        with open(filename, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.fromtimestamp(alert_data['timestamp']).isoformat()} - {alert_data['alert_name']} - {alert_data['status']}\n")

    def _send_console_notification(self, notification: AlertNotification, alert_data: Dict[str, Any]):
        """Envoie une notification vers la console."""
        status_icon = "🚨" if alert_data['status'] == 'triggered' else "✅"
        print(f"{status_icon} {alert_data['alert_name']}: {alert_data['current_value']} {alert_data['condition']} {alert_data['threshold']}")

    def get_alert_status(self) -> Dict[str, Any]:
        """Retourne le statut des alertes."""
        with self._lock:
            active_alerts = [
                {
                    "name": name,
                    "triggered": state.triggered,
                    "trigger_count": state.trigger_count,
                    "last_value": state.last_value,
                    "first_triggered": state.first_triggered,
                    "last_triggered": state.last_triggered
                }
                for name, state in self.alert_states.items()
            ]

            return {
                "active_alerts": active_alerts,
                "total_alerts": len(self.alert_states),
                "triggered_count": sum(1 for state in self.alert_states.values() if state.triggered),
                "recent_alerts": self.alert_history[-10:] if self.alert_history else []
            }

    def start_monitoring(self, interval_seconds: int = 30):
        """Démarre la surveillance des alertes."""
        def monitor_loop():
            while True:
                try:
                    self.check_alerts()
                    time.sleep(interval_seconds)
                except Exception as e:
                    print(f"❌ Erreur surveillance alertes: {e}")
                    time.sleep(interval_seconds)

        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        print(f"🔍 Surveillance des alertes démarrée (intervalle: {interval_seconds}s)")


# Instance globale
_global_alert_manager: Optional[MetricsAlertManager] = None


def get_alert_manager() -> MetricsAlertManager:
    """Retourne l'instance globale du gestionnaire d'alertes."""
    global _global_alert_manager
    if _global_alert_manager is None:
        _global_alert_manager = MetricsAlertManager()
    return _global_alert_manager


# Fonctions de convenance
def add_alert(alert: AlertRule):
    """Ajoute une règle d'alerte."""
    get_alert_manager().add_alert(alert)


def add_notification(notification: AlertNotification):
    """Ajoute une configuration de notification."""
    get_alert_manager().add_notification(notification)


def start_alert_monitoring(interval_seconds: int = 30):
    """Démarre la surveillance des alertes."""
    get_alert_manager().start_monitoring(interval_seconds)


def get_alert_status() -> Dict[str, Any]:
    """Retourne le statut des alertes."""
    return get_alert_manager().get_alert_status()
