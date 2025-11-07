#!/usr/bin/env python3
"""
Interface pour le gestionnaire de données.

Cette interface définit le contrat pour les gestionnaires de données,
permettant de découpler l'accès aux données internes.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.funding_data import FundingData


class DataManagerInterface(ABC):
    """
    Interface pour les gestionnaires de données.

    Cette interface permet de découpler l'accès aux données internes
    comme les listes de symboles par catégorie, évitant l'accès direct
    à l'attribut `.storage`.
    """

    @abstractmethod
    def get_linear_symbols(self) -> List[str]:
        """
        Récupère la liste des symboles linear.

        Returns:
            List[str]: Liste des symboles linear (copie pour éviter les modifications)
        """
        pass

    @abstractmethod
    def get_inverse_symbols(self) -> List[str]:
        """
        Récupère la liste des symboles inverse.

        Returns:
            List[str]: Liste des symboles inverse (copie pour éviter les modifications)
        """
        pass

    @abstractmethod
    def get_all_funding_data_objects(self) -> Dict[str, "FundingData"]:
        """
        Récupère toutes les données de funding en tant que Value Objects.

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Returns:
            Dict[str, FundingData]: Dictionnaire {symbol: FundingData} (copie pour éviter les modifications)
        """
        pass

    @abstractmethod
    def get_funding_data_object(self, symbol: str) -> Optional["FundingData"]:
        """
        Récupère un FundingData Value Object pour un symbole.

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Args:
            symbol: Symbole à récupérer

        Returns:
            FundingData ou None si absent
        """
        pass

    @abstractmethod
    def set_funding_data_object(self, funding_data: "FundingData") -> None:
        """
        Stocke un FundingData Value Object pour un symbole.

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Args:
            funding_data: Objet FundingData à stocker
        """
        pass

    @abstractmethod
    def update_original_funding_data(self, symbol: str, next_funding_time: str) -> None:
        """
        Met à jour les données de funding originales pour un symbole.

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Args:
            symbol: Symbole à mettre à jour
            next_funding_time: Temps du prochain funding
        """
        pass

    @abstractmethod
    def get_symbol_categories(self) -> Dict[str, str]:
        """
        Récupère le mapping des catégories de symboles.

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Returns:
            Dict[str, str]: Dictionnaire {symbol: category}
        """
        pass

    @abstractmethod
    def add_symbol_to_category(self, symbol: str, category: str) -> None:
        """
        Ajoute un symbole à une catégorie.

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Args:
            symbol: Symbole à ajouter
            category: Catégorie ("linear" ou "inverse")
        """
        pass

    @abstractmethod
    def update_price_data(
        self,
        symbol: str,
        mark_price: float,
        last_price: float,
        timestamp: float,
    ) -> None:
        """
        Met à jour les prix pour un symbole donné (compatibilité avec price_store.py).

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Args:
            symbol: Symbole du contrat (ex: BTCUSDT)
            mark_price: Prix de marque
            last_price: Dernier prix de transaction
            timestamp: Timestamp de la mise à jour
        """
        pass

