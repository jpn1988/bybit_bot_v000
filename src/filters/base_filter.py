#!/usr/bin/env python3
"""
Interface abstraite pour les filtres du bot Bybit.

Cette classe définit le contrat que tous les filtres doivent respecter :
- Méthode apply() pour appliquer le filtre
- Méthode get_name() pour identifier le filtre
- Support de la configuration et du logging
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging


class BaseFilter(ABC):
    """
    Interface abstraite pour tous les filtres du bot Bybit.

    Tous les filtres doivent hériter de cette classe et implémenter
    les méthodes abstraites définies ci-dessous.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialise le filtre de base.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or logging.getLogger(__name__)

    @abstractmethod
    def apply(
        self, symbols_data: List[Any], config: Dict[str, Any]
    ) -> List[Any]:
        """
        Applique le filtre aux données de symboles.

        Args:
            symbols_data: Liste des données de symboles à filtrer
            config: Configuration du filtre

        Returns:
            Liste des symboles filtrés

        Raises:
            NotImplementedError: Si la méthode n'est pas implémentée
        """
        raise NotImplementedError(
            "La méthode apply() doit être implémentée par les classes dérivées"
        )

    @abstractmethod
    def get_name(self) -> str:
        """
        Retourne le nom du filtre.

        Returns:
            Nom du filtre (ex: "funding_filter", "volatility_filter")

        Raises:
            NotImplementedError: Si la méthode n'est pas implémentée
        """
        raise NotImplementedError(
            "La méthode get_name() doit être implémentée par les classes dérivées"
        )

    def get_description(self) -> str:
        """
        Retourne une description du filtre.

        Returns:
            Description du filtre (optionnel, peut être surchargée)
        """
        return f"Filtre {self.get_name()}"

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Valide la configuration du filtre.

        Args:
            config: Configuration à valider

        Returns:
            True si la configuration est valide, False sinon

        Note:
            Cette méthode peut être surchargée par les classes dérivées
            pour ajouter une validation spécifique.
        """
        if not isinstance(config, dict):
            self.logger.warning(
                f"Configuration invalide pour {self.get_name()}: "
                f"doit être un dictionnaire"
            )
            return False
        return True

    def log_filter_result(
        self, input_count: int, output_count: int, config: Dict[str, Any]
    ):
        """
        Log le résultat de l'application du filtre.

        Args:
            input_count: Nombre de symboles en entrée
            output_count: Nombre de symboles en sortie
            config: Configuration utilisée
        """
        rejected_count = input_count - output_count
        self.logger.info(
            f"✅ {self.get_description()}: "
            f"entrée={input_count} | sortie={output_count} | rejetés={rejected_count}"
        )

    def __str__(self) -> str:
        """Représentation textuelle du filtre."""
        return f"{self.__class__.__name__}({self.get_name()})"

    def __repr__(self) -> str:
        """Représentation détaillée du filtre."""
        return (f"{self.__class__.__name__}(name='{self.get_name()}', "
                f"logger={self.logger})")
