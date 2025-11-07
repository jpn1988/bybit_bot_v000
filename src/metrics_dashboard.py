#!/usr/bin/env python3
"""
Dashboard de métriques pour le bot Bybit.

Ce module fournit un dashboard en ligne de commande pour visualiser
les métriques du bot en temps réel.
"""

import time
import os
from typing import Dict, Any, List
from datetime import datetime, timedelta

from enhanced_metrics import get_metrics_collector, AlertRule


class MetricsDashboard:
    """
    Dashboard de métriques en ligne de commande.

    Fonctionnalités :
    - Affichage en temps réel des métriques
    - Graphiques ASCII simples
    - Alertes visuelles
    - Export des données
    """

    def __init__(self, refresh_interval: int = 5):
        """
        Initialise le dashboard.

        Args:
            refresh_interval: Intervalle de rafraîchissement en secondes
        """
        self.refresh_interval = refresh_interval
        self.collector = get_metrics_collector()
        self.running = False

        # Configuration des couleurs (si supportées)
        self.colors = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'bold': '\033[1m',
            'reset': '\033[0m'
        }

    def clear_screen(self):
        """Efface l'écran."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(self):
        """Affiche l'en-tête du dashboard."""
        print(f"{self.colors['bold']}{self.colors['cyan']}")
        print("=" * 80)
        print("📊 DASHBOARD MÉTRIQUES BOT BYBIT")
        print("=" * 80)
        print(f"{self.colors['reset']}")

    def print_uptime(self, uptime_seconds: float):
        """Affiche l'uptime du bot."""
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        seconds = int(uptime_seconds % 60)

        print(f"{self.colors['green']}⏱️  Uptime: {hours:02d}h {minutes:02d}m {seconds:02d}s{self.colors['reset']}")
        print()

    def print_api_metrics(self, metrics: Dict[str, Any]):
        """Affiche les métriques API."""
        api_calls = metrics.get('api_calls_total', {})
        api_errors = metrics.get('api_errors_total', {})
        api_latency = metrics.get('api_latency_ms', {})

        calls_count = api_calls.get('count', 0)
        errors_count = api_errors.get('count', 0)
        avg_latency = api_latency.get('avg', 0)
        max_latency = api_latency.get('max', 0)

        error_rate = (errors_count / calls_count * 100) if calls_count > 0 else 0

        print(f"{self.colors['blue']}📡 API MÉTRIQUES{self.colors['reset']}")
        print(f"  Appels: {calls_count:,}")
        print(f"  Erreurs: {errors_count:,}")
        print(f"  Taux d'erreur: {error_rate:.1f}%")
        print(f"  Latence moy: {avg_latency:.1f}ms")
        print(f"  Latence max: {max_latency:.1f}ms")
        print()

    def print_websocket_metrics(self, metrics: Dict[str, Any]):
        """Affiche les métriques WebSocket."""
        ws_connections = metrics.get('ws_connections', {})
        ws_reconnects = metrics.get('ws_reconnects', {})
        ws_errors = metrics.get('ws_errors', {})

        connections = ws_connections.get('count', 0)
        reconnects = ws_reconnects.get('count', 0)
        errors = ws_errors.get('count', 0)

        print(f"{self.colors['magenta']}🌐 WEBSOCKET MÉTRIQUES{self.colors['reset']}")
        print(f"  Connexions: {connections}")
        print(f"  Reconnexions: {reconnects}")
        print(f"  Erreurs: {errors}")
        print()

    def print_filter_metrics(self, metrics: Dict[str, Any]):
        """Affiche les métriques de filtrage."""
        pairs_kept = metrics.get('pairs_kept', {})
        pairs_rejected = metrics.get('pairs_rejected', {})

        kept_count = pairs_kept.get('count', 0)
        rejected_count = pairs_rejected.get('count', 0)
        total = kept_count + rejected_count

        success_rate = (kept_count / total * 100) if total > 0 else 0

        print(f"{self.colors['yellow']}🔍 FILTRAGE MÉTRIQUES{self.colors['reset']}")
        print(f"  Gardées: {kept_count:,}")
        print(f"  Rejetées: {rejected_count:,}")
        print(f"  Total: {total:,}")
        print(f"  Taux de succès: {success_rate:.1f}%")
        print()

    def print_system_metrics(self, metrics: Dict[str, Any]):
        """Affiche les métriques système."""
        memory = metrics.get('memory_usage_mb', {})
        cpu = metrics.get('cpu_usage_percent', {})

        memory_usage = memory.get('latest', 0)
        cpu_usage = cpu.get('latest', 0)

        print(f"{self.colors['cyan']}💻 SYSTÈME MÉTRIQUES{self.colors['reset']}")
        print(f"  Mémoire: {memory_usage:.1f} MB")
        print(f"  CPU: {cpu_usage:.1f}%")
        print()

    def print_task_metrics(self, metrics: Dict[str, Any]):
        """Affiche les métriques des tâches."""
        task_execution = metrics.get('task_execution_time_ms', {})

        if task_execution:
            avg_time = task_execution.get('avg', 0)
            max_time = task_execution.get('max', 0)
            count = task_execution.get('count', 0)

            print(f"{self.colors['green']}⚡ TÂCHES MÉTRIQUES{self.colors['reset']}")
            print(f"  Exécutions: {count}")
            print(f"  Temps moy: {avg_time:.1f}ms")
            print(f"  Temps max: {max_time:.1f}ms")
            print()

    def print_alerts(self, metrics: Dict[str, Any]):
        """Affiche les alertes actives."""
        # Vérifier les conditions d'alerte
        alerts = []

        # Alerte taux d'erreur API élevé
        api_calls = metrics.get('api_calls_total', {})
        api_errors = metrics.get('api_errors_total', {})
        if api_calls.get('count', 0) > 0:
            error_rate = (api_errors.get('count', 0) / api_calls.get('count', 0)) * 100
            if error_rate > 10:  # Plus de 10% d'erreurs
                alerts.append(f"🚨 Taux d'erreur API élevé: {error_rate:.1f}%")

        # Alerte latence élevée
        api_latency = metrics.get('api_latency_ms', {})
        if api_latency.get('avg', 0) > 1000:  # Plus de 1 seconde
            alerts.append(f"🚨 Latence API élevée: {api_latency.get('avg', 0):.1f}ms")

        # Alerte utilisation mémoire élevée
        memory = metrics.get('memory_usage_mb', {})
        if memory.get('latest', 0) > 1000:  # Plus de 1 GB
            alerts.append(f"🚨 Utilisation mémoire élevée: {memory.get('latest', 0):.1f} MB")

        if alerts:
            print(f"{self.colors['red']}{self.colors['bold']}🚨 ALERTES ACTIVES{self.colors['reset']}")
            for alert in alerts:
                print(f"  {alert}")
            print()

    def print_footer(self):
        """Affiche le pied de page."""
        print(f"{self.colors['cyan']}")
        print("=" * 80)
        print(f"🔄 Rafraîchissement toutes les {self.refresh_interval}s | Ctrl+C pour quitter")
        print("=" * 80)
        print(f"{self.colors['reset']}")

    def run(self):
        """Lance le dashboard."""
        self.running = True
        print("🚀 Démarrage du dashboard de métriques...")
        print("Appuyez sur Ctrl+C pour arrêter")
        time.sleep(2)

        try:
            while self.running:
                self.clear_screen()
                self.print_header()

                # Obtenir les métriques
                summary = self.collector.get_all_metrics_summary(hours=1)
                metrics = summary.get('metrics', {})

                # Afficher les sections
                self.print_uptime(summary.get('uptime_seconds', 0))
                self.print_api_metrics(metrics)
                self.print_websocket_metrics(metrics)
                self.print_filter_metrics(metrics)
                self.print_system_metrics(metrics)
                self.print_task_metrics(metrics)
                self.print_alerts(metrics)
                self.print_footer()

                # Attendre le prochain rafraîchissement
                time.sleep(self.refresh_interval)

        except KeyboardInterrupt:
            print("\n🛑 Arrêt du dashboard...")
            self.running = False

    def stop(self):
        """Arrête le dashboard."""
        self.running = False


def main():
    """Fonction principale pour lancer le dashboard."""
    dashboard = MetricsDashboard(refresh_interval=5)
    dashboard.run()


if __name__ == "__main__":
    main()
