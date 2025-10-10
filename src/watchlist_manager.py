#!/usr/bin/env python3
"""
Gestionnaire de watchlist pour le bot Bybit - Version refactorisée.

Cette classe orchestre la construction de la watchlist en déléguant aux
helpers spécialisés :
- WatchlistDataPreparer : Préparation des données
- WatchlistFilterApplier : Application des filtres
- WatchlistResultBuilder : Construction des résultats

Responsabilités principales :
- Orchestration de haut niveau de la construction de la watchlist
- Coordination entre les différents helpers
- Gestion de la logique métier de sélection des symboles
- Surveillance des candidats (symboles proches des critères)
"""

from typing import List, Tuple, Dict, Optional
from logging_setup import setup_logging
from config import ConfigManager
from data_manager import DataManager
from filters.symbol_filter import SymbolFilter
from volatility_tracker import VolatilityTracker
from metrics import record_filter_result
from watchlist_helpers import (
    WatchlistDataPreparer,
    WatchlistFilterApplier,
    WatchlistResultBuilder,
)


class WatchlistManager:
    """
    Gestionnaire de watchlist pour le bot Bybit - Version unifiée.

    Responsabilités principales :
    - Orchestration de la construction de la watchlist
    - Application des filtres de sélection (funding, volume, spread,
      volatilité)
    - Coordination entre ConfigManager, DataManager, SymbolFilter
      et VolatilityTracker
    - Gestion de la logique métier de sélection des symboles
    - Surveillance des candidats (symboles proches des critères)

    Cette classe utilise DataManager pour récupérer les données
    de marché
    et applique la logique de filtrage pour construire la watchlist finale.
    """

    def __init__(
        self,
        testnet: bool = True,
        config_manager: Optional[ConfigManager] = None,
        market_data_fetcher: Optional[DataManager] = None,
        symbol_filter: Optional[SymbolFilter] = None,
        logger=None,
    ):
        """
        Initialise le gestionnaire de watchlist.

        Args:
            testnet (bool): Utiliser le testnet (True) ou le marché réel
            (False)
            config_manager: Gestionnaire de configuration (optionnel, créé
            automatiquement si non fourni)
            market_data_fetcher: Gestionnaire de données (optionnel, créé
            automatiquement si non fourni)
            symbol_filter: Filtre de symboles (optionnel, créé
            automatiquement si non fourni)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()

        # Composants principaux (injection de dépendances avec fallback)
        self.config_manager = config_manager or ConfigManager(logger=self.logger)
        self.market_data_fetcher = market_data_fetcher or DataManager(
            testnet=testnet, logger=self.logger
        )
        self.symbol_filter = symbol_filter or SymbolFilter(logger=self.logger)

        # Configuration et données
        self.config = self.config_manager.load_and_validate_config()
        self.symbol_categories = {}

        # Initialiser les helpers spécialisés
        self._data_preparer = WatchlistDataPreparer(
            self.market_data_fetcher, logger=self.logger
        )
        self._filter_applier = WatchlistFilterApplier(
            self.symbol_filter,
            self.market_data_fetcher,
            self.symbol_categories,
            logger=self.logger,
        )
        self._result_builder = WatchlistResultBuilder(
            self.symbol_filter, self.symbol_categories, logger=self.logger
        )

        # Données de la watchlist
        self.selected_symbols = []
        self.funding_data = {}

    def get_config(self) -> Dict:
        """
        Retourne la configuration actuelle.

        Returns:
            Dict: Configuration actuelle
        """
        return self.config

    def set_symbol_categories(self, symbol_categories: Dict[str, str]):
        """
        Définit le mapping des catégories de symboles.

        Args:
            symbol_categories: Dictionnaire {symbol: category}
        """
        self.symbol_categories = symbol_categories
        # Propager aux helpers qui en ont besoin
        self._filter_applier.symbol_categories = symbol_categories
        self._result_builder.symbol_categories = symbol_categories

    def build_watchlist(
        self,
        base_url: str,
        perp_data: Dict,
        volatility_tracker: VolatilityTracker,
    ) -> Tuple[List[str], List[str], Dict]:
        """
        Construit la watchlist complète en appliquant tous les filtres.

        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels
            volatility_tracker: Tracker de volatilité pour le filtrage

        Returns:
            Tuple[linear_symbols, inverse_symbols, funding_data]
        """
        # Préparer la configuration et les données
        config_params, funding_map, n0 = (
            self._data_preparer.prepare_watchlist_data(
                base_url, perp_data, self.config
            )
        )

        # Appliquer tous les filtres
        final_symbols, filter_metrics = self._filter_applier.apply_all_filters(
            perp_data,
            funding_map,
            config_params,
            volatility_tracker,
            base_url,
            n0,
        )

        # Enregistrer les métriques de filtrage
        self._record_filtering_metrics(
            filter_metrics, config_params["spread_max"]
        )

        # Construire et retourner les résultats finaux
        linear_symbols, inverse_symbols, funding_data = (
            self._result_builder.build_final_watchlist(final_symbols)
        )

        # Stocker les résultats localement
        self.selected_symbols = list(funding_data.keys())
        self.funding_data = funding_data

        return linear_symbols, inverse_symbols, funding_data


    def _record_filtering_metrics(
        self, filter_metrics: Dict, spread_max: float
    ):
        """Enregistre toutes les métriques de filtrage."""
        record_filter_result(
            "funding_volume_time",
            filter_metrics["n1"],
            filter_metrics["n0"] - filter_metrics["n1"],
        )
        if spread_max is not None:
            record_filter_result(
                "spread",
                filter_metrics["n2"],
                filter_metrics["n1"] - filter_metrics["n2"],
            )
        record_filter_result(
            "volatility",
            filter_metrics["n_after_volatility"],
            filter_metrics["n_before_volatility"]
            - filter_metrics["n_after_volatility"],
        )
        record_filter_result(
            "final_limit",
            filter_metrics["n3"],
            filter_metrics["n_after_volatility"] - filter_metrics["n3"],
        )

    def find_candidate_symbols(
        self, base_url: str, perp_data: Dict
    ) -> List[str]:
        """
        Trouve les symboles qui sont proches de passer les filtres (candidats).

        Args:
            base_url: URL de base de l'API Bybit
            perp_data: Données des perpétuels

        Returns:
            Liste des symboles candidats
        """
        candidates = []
        config = self.config

        # Extraire les paramètres de configuration
        categorie = config.get("categorie", "both")
        funding_min = config.get("funding_min")
        funding_max = config.get("funding_max")
        volume_min_millions = config.get("volume_min_millions")
        funding_time_max_minutes = config.get("funding_time_max_minutes")

        # Si aucun filtre n'est configuré, pas de candidats à surveiller
        if not any([funding_min, funding_max, volume_min_millions]):
            return candidates

        # Pour éviter l'incohérence, on ne détecte des candidats que si on a
        # des filtres de funding
        if not funding_min and not funding_max:
            return candidates

        # Si le filtre de temps de funding est trop restrictif (< 10 minutes),
        # on ne détecte pas de candidats pour éviter l'incohérence
        if (
            funding_time_max_minutes is not None
            and funding_time_max_minutes < 10
        ):
            self.logger.info(
                f"ℹ️ Filtre de temps de funding trop restrictif "
                f"({funding_time_max_minutes}min) - pas de candidats détectés"
            )
            return candidates

        try:
            # Récupérer les données de funding
            funding_map = self._data_preparer.fetch_funding_data(
                base_url, categorie
            )

            # Analyser chaque symbole pour détecter les candidats
            for symbol, data in funding_map.items():
                if self.symbol_filter.check_candidate_filters(
                    symbol,
                    funding_map,
                    funding_min,
                    funding_max,
                    volume_min_millions,
                    funding_time_max_minutes,
                ):
                    candidates.append(symbol)

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur récupération candidats: {e}")

        return candidates

    def check_if_symbol_now_passes_filters(
        self, symbol: str, ticker_data: dict
    ) -> bool:
        """
        Vérifie si un symbole candidat passe maintenant les filtres.

        Args:
            symbol: Symbole à vérifier
            ticker_data: Données du ticker reçues via WebSocket

        Returns:
            True si le symbole passe maintenant les filtres
        """
        config = self.config
        funding_min = config.get("funding_min")
        funding_max = config.get("funding_max")
        volume_min_millions = config.get("volume_min_millions")

        return self.symbol_filter.check_realtime_filters(
            symbol, ticker_data, funding_min, funding_max, volume_min_millions
        )

    def get_selected_symbols(self) -> List[str]:
        """
        Retourne la liste des symboles sélectionnés.

        Returns:
            Liste des symboles de la watchlist
        """
        return self.selected_symbols.copy()

    def get_funding_data(self) -> Dict:
        """
        Retourne les données de funding de la watchlist.

        Returns:
            Dictionnaire des données de funding
        """
        return self.funding_data.copy()

    def get_original_funding_data(self) -> Dict:
        """
        Retourne les données de funding originales (next_funding_time).

        Returns:
            Dictionnaire des next_funding_time originaux
        """
        return self._data_preparer.get_original_funding_data()

    def calculate_funding_time_remaining(self, next_funding_time) -> str:
        """
        Retourne "Xh Ym Zs" à partir d'un timestamp Bybit (ms) ou ISO.

        Args:
            next_funding_time: Timestamp du prochain funding

        Returns:
            str: Temps restant formaté ou "-" si invalide
        """
        return self.symbol_filter.calculate_funding_time_remaining(
            next_funding_time
        )
