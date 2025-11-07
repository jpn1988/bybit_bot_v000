#!/usr/bin/env python3
"""
Interface pour le gestionnaire de stockage de données.

Cette interface définit le contrat pour les gestionnaires de stockage,
permettant de découpler l'accès aux données internes.
"""

from abc import ABC, abstractmethod
from typing import List


class DataStorageInterface(ABC):
    """
    Interface pour les gestionnaires de stockage de données.

    Cette interface permet de découpler l'accès aux données internes
    comme les listes de symboles par catégorie.
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

