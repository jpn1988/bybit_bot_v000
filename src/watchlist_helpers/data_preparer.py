#!/usr/bin/env python3
"""
Helper pour la préparation des données de watchlist.

Cette classe extrait la logique de préparation des données
du WatchlistManager pour améliorer la lisibilité.
"""

from typing import Dict, Tuple
from logging_setup import setup_logging


class WatchlistDataPreparer:
    """
    Helper pour préparer les données nécessaires à la construction de la
    watchlist.

    Responsabilités :
    - Extraction des paramètres de configuration
    - Récupération des données de funding
    - Validation des données
    - Comptage initial des symboles
    """

    def __init__(self, market_data_fetcher, logger=None):
        """
        Initialise le préparateur de données.

        Args:
            market_data_fetcher: Instance de DataManager
            logger: Logger pour les messages (optionnel)
        """
        self.market_data_fetcher = market_data_fetcher
        self.logger = logger or setup_logging()
        self.original_funding_data = {}

    def extract_config_parameters(self, config: Dict) -> Dict:
        """
        Extrait les paramètres de configuration nécessaires.

        Args:
            config: Configuration complète

        Returns:
            Dictionnaire des paramètres extraits
        """
        return {
            "categorie": config.get("categorie", "both"),
            "funding_min": config.get("funding_min"),
            "funding_max": config.get("funding_max"),
            "volume_min_millions": config.get("volume_min_millions"),
            "spread_max": config.get("spread_max"),
            "volatility_min": config.get("volatility_min"),
            "volatility_max": config.get("volatility_max"),
            "limite": config.get("limite"),
            "funding_time_min_minutes": config.get(
                "funding_time_min_minutes"
            ),
            "funding_time_max_minutes": config.get(
                "funding_time_max_minutes"
            ),
        }

    def fetch_funding_data(
        self, base_url: str, categorie: str
    ) -> Dict[str, Dict]:
        """
        Récupère les données de funding selon la catégorie.

        Args:
            base_url: URL de base de l'API Bybit
            categorie: Catégorie (linear, inverse, both)

        Returns:
            Données de funding récupérées
        """
        if categorie == "linear":
            return self.market_data_fetcher.fetcher.fetch_funding_map(
                base_url, "linear", 10
            )
        elif categorie == "inverse":
            return self.market_data_fetcher.fetcher.fetch_funding_map(
                base_url, "inverse", 10
            )
        else:  # "both"
            return self.market_data_fetcher.fetcher.fetch_funding_data_parallel(
                base_url, ["linear", "inverse"], 10
            )

    def get_and_validate_funding_data(
        self, base_url: str, categorie: str
    ) -> Dict:
        """
        Récupère et valide les données de funding.

        Args:
            base_url: URL de base de l'API Bybit
            categorie: Catégorie sélectionnée

        Returns:
            Données de funding validées

        Raises:
            RuntimeError: Si aucun funding disponible
        """
        funding_map = self.fetch_funding_data(base_url, categorie)

        if not funding_map:
            self.logger.warning(
                "⚠️ Aucun funding disponible pour la catégorie "
                "sélectionnée"
            )
            raise RuntimeError(
                "Aucun funding disponible pour la catégorie sélectionnée"
            )

        # Stocker les next_funding_time originaux pour fallback
        self.store_original_funding_data(funding_map)

        return funding_map

    def store_original_funding_data(self, funding_map: Dict[str, Dict]):
        """
        Stocke les données de funding originales pour fallback.

        Args:
            funding_map: Données de funding
        """
        self.original_funding_data = {}
        for symbol, data in funding_map.items():
            try:
                next_funding_time = data.get("next_funding_time")
                if next_funding_time:
                    self.original_funding_data[symbol] = next_funding_time
            except Exception:
                continue

    def count_initial_symbols(
        self, perp_data: Dict, funding_map: Dict
    ) -> int:
        """
        Compte les symboles avant filtrage.

        Args:
            perp_data: Données des perpétuels
            funding_map: Données de funding

        Returns:
            Nombre de symboles initiaux
        """
        all_symbols = list(set(perp_data["linear"] + perp_data["inverse"]))
        return len([s for s in all_symbols if s in funding_map])

    def prepare_watchlist_data(
        self, base_url: str, perp_data: Dict, config: Dict
    ) -> Tuple[Dict, Dict, int]:
        """
        Prépare toutes les données nécessaires pour la watchlist.

        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels
            config: Configuration complète

        Returns:
            Tuple (config_params, funding_map, n0)
        """
        # Extraire les paramètres de configuration
        config_params = self.extract_config_parameters(config)

        # Récupérer et valider les données de funding
        funding_map = self.get_and_validate_funding_data(
            base_url, config_params["categorie"]
        )

        # Compter les symboles avant filtrage
        n0 = self.count_initial_symbols(perp_data, funding_map)

        return config_params, funding_map, n0

    def get_original_funding_data(self) -> Dict:
        """
        Retourne les données de funding originales stockées.

        Returns:
            Dictionnaire des next_funding_time originaux
        """
        return self.original_funding_data.copy()
