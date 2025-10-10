#!/usr/bin/env python3
"""
Moniteur de santé du bot Bybit - Version refactorisée.

Cette classe gère uniquement :
- La surveillance de la santé des composants
- Le monitoring de l'utilisation mémoire
- La gestion des redémarrages automatiques
"""

import gc
from logging_setup import setup_logging
from display_manager import DisplayManager
from monitoring_manager import MonitoringManager
from volatility_tracker import VolatilityTracker


class BotHealthMonitor:
    """
    Moniteur de santé du bot Bybit.

    Responsabilités :
    - Surveillance de la santé des composants
    - Monitoring de l'utilisation mémoire
    - Gestion des redémarrages automatiques
    """

    def __init__(self, logger=None):
        """
        Initialise le moniteur de santé.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()
        self._memory_check_counter = 0
        self._memory_check_interval = 300  # 5 minutes

    def check_components_health(
        self,
        monitoring_manager: MonitoringManager,
        display_manager: DisplayManager,
        volatility_tracker: VolatilityTracker,
    ) -> bool:
        """
        Vérifie que tous les composants critiques sont actifs.

        Args:
            monitoring_manager: Gestionnaire de surveillance
            display_manager: Gestionnaire d'affichage
            volatility_tracker: Tracker de volatilité

        Returns:
            True si tous les composants sont sains
        """
        try:
            # Vérifier que le monitoring continue fonctionne
            if not monitoring_manager.is_running():
                self.logger.warning("⚠️ Monitoring manager arrêté")
                return False

            # Vérifier que le display manager fonctionne
            if not display_manager.is_running():
                self.logger.warning("⚠️ Display manager arrêté")
                return False

            # Vérifier que le volatility tracker fonctionne
            if not volatility_tracker.is_running():
                self.logger.warning("⚠️ Volatility tracker arrêté")
                return False

            return True

        except Exception as e:
            self.logger.warning(
                f"⚠️ Erreur vérification santé composants: {e}"
            )
            return False

    def monitor_memory_usage(self) -> float:
        """
        Surveille l'utilisation mémoire et alerte si nécessaire.

        Returns:
            Utilisation mémoire en MB
        """
        try:
            import psutil

            # Obtenir l'utilisation mémoire actuelle
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024

            # Seuil d'alerte (500MB)
            if memory_mb > 500:
                self.logger.warning(
                    f"⚠️ Utilisation mémoire élevée: {memory_mb:.1f}MB"
                )

                # Forcer le garbage collection
                collected = gc.collect()
                if collected > 0:
                    self.logger.info(
                        f"🧹 Garbage collection effectué: {collected} objets libérés"
                    )

                    # Vérifier l'utilisation après nettoyage
                    new_memory_mb = process.memory_info().rss / 1024 / 1024
                    self.logger.info(
                        f"📊 Mémoire après nettoyage: {new_memory_mb:.1f}MB"
                    )
                    return new_memory_mb

            return memory_mb

        except ImportError:
            # psutil non disponible, utiliser une approche basique
            import sys

            memory_mb = sys.getsizeof(self) / 1024 / 1024
            if memory_mb > 100:  # Seuil plus bas sans psutil
                self.logger.warning(
                    f"⚠️ Utilisation mémoire estimée élevée: {memory_mb:.1f}MB"
                )
            return memory_mb
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur monitoring mémoire: {e}")
            return 0

    def should_check_memory(self) -> bool:
        """
        Détermine si une vérification mémoire doit être effectuée.

        Returns:
            True si une vérification est nécessaire
        """
        self._memory_check_counter += 1
        if self._memory_check_counter >= self._memory_check_interval:
            self._memory_check_counter = 0
            return True
        return False

    def get_health_status(
        self,
        monitoring_manager: MonitoringManager,
        display_manager: DisplayManager,
        volatility_tracker: VolatilityTracker,
    ) -> dict:
        """
        Retourne le statut de santé global du bot.

        Args:
            monitoring_manager: Gestionnaire de surveillance
            display_manager: Gestionnaire d'affichage
            volatility_tracker: Tracker de volatilité

        Returns:
            Dictionnaire contenant le statut de santé
        """
        return {
            "monitoring_running": monitoring_manager.is_running(),
            "display_running": display_manager.is_running(),
            "volatility_running": volatility_tracker.is_running(),
            "memory_usage_mb": self.monitor_memory_usage(),
            "overall_healthy": self.check_components_health(
                monitoring_manager, display_manager, volatility_tracker
            ),
        }

    def reset_memory_counter(self):
        """Remet à zéro le compteur de vérification mémoire."""
        self._memory_check_counter = 0

    def set_memory_check_interval(self, interval: int):
        """
        Définit l'intervalle de vérification mémoire.

        Args:
            interval: Intervalle en secondes
        """
        self._memory_check_interval = interval
        self.logger.info(
            f"📊 Intervalle de vérification mémoire défini à {interval} secondes"
        )
