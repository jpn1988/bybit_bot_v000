#!/usr/bin/env python3
"""
Interface pour le gestionnaire de hedging spot.

Cette interface définit le contrat pour les gestionnaires de hedging spot,
permettant de découpler les dépendances circulaires.
"""

from abc import ABC, abstractmethod


class SpotHedgeManagerInterface(ABC):
    """
    Interface pour les gestionnaires de hedging spot.

    Cette interface permet de découpler les dépendances circulaires
    entre les différents managers du bot.
    """

    @abstractmethod
    def stop(self) -> None:
        """
        Arrête le gestionnaire de hedging spot.

        Cette méthode est appelée lors de l'arrêt du bot pour nettoyer
        les ressources du gestionnaire.
        """
        pass

