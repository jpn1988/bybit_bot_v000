#!/usr/bin/env python3
"""
Constructeur de watchlist pour le bot Bybit.

Cette classe orchestre la construction de la watchlist en utilisant :
- ConfigManager pour la configuration
- UnifiedDataManager pour les données de marché
- SymbolFilter pour le filtrage
- VolatilityTracker pour la volatilité

Responsabilités principales :
- Orchestration de la construction de la watchlist
- Application des filtres de sélection
- Coordination entre les différents composants
- Gestion de la logique métier de sélection des symboles
"""

from typing import List, Tuple, Dict, Optional
from logging_setup import setup_logging
from config_manager import ConfigManager
from unified_data_manager import UnifiedDataManager
from filters.symbol_filter import SymbolFilter
from volatility_tracker import VolatilityTracker
from instruments import category_of_symbol
from metrics import record_filter_result


class WatchlistBuilder:
    """
    Constructeur de watchlist pour le bot Bybit.

    Responsabilités principales :
    - Orchestration de la construction de la watchlist
    - Application des filtres de sélection (funding, volume, spread, 
      volatilité)
    - Coordination entre ConfigManager, UnifiedDataManager, SymbolFilter 
      et VolatilityTracker
    - Gestion de la logique métier de sélection des symboles
    - Surveillance des candidats (symboles proches des critères)

    Cette classe utilise UnifiedDataManager pour récupérer les données 
    de marché
    et applique la logique de filtrage pour construire la watchlist finale.
    """

    def __init__(self, testnet: bool = True, logger=None):
        """
        Initialise le constructeur de watchlist.

        Args:
            testnet (bool): Utiliser le testnet (True) ou le marché réel 
            (False)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()

        # Composants
        self.config_manager = ConfigManager()
        self.market_data_fetcher = UnifiedDataManager(
            testnet=testnet, logger=self.logger
        )
        self.symbol_filter = SymbolFilter(logger=self.logger)

        # Configuration et données
        self.config = {}
        self.symbol_categories = {}

        # Données de la watchlist
        self.selected_symbols = []
        self.funding_data = {}
        self.original_funding_data = {}

    def load_and_validate_config(self) -> Dict:
        """
        Charge et valide la configuration.

        Returns:
            Dict: Configuration validée
        """
        self.config = self.config_manager.load_and_validate_config()
        return self.config

    def set_symbol_categories(self, symbol_categories: Dict[str, str]):
        """
        Définit le mapping des catégories de symboles.

        Args:
            symbol_categories: Dictionnaire {symbol: category}
        """
        self.symbol_categories = symbol_categories

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
        config_params, funding_map, n0 = self._prepare_watchlist_data(
            base_url, perp_data
        )

        # Appliquer tous les filtres
        final_symbols, filter_metrics = self._apply_all_filters(
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
        return self._build_final_watchlist(final_symbols)

    def _prepare_watchlist_data(
        self, base_url: str, perp_data: Dict
    ) -> Tuple[Dict, Dict, int]:
        """Prépare les données nécessaires pour la construction de la 
        watchlist."""
        # Extraire et valider la configuration
        config_params = self._extract_config_parameters()

        # Récupérer et valider les données de funding
        funding_map = self._get_and_validate_funding_data(
            base_url, config_params["categorie"]
        )

        # Compter les symboles avant filtrage
        n0 = self._count_initial_symbols(perp_data, funding_map)

        return config_params, funding_map, n0

    def _apply_all_filters(
        self,
        perp_data: Dict,
        funding_map: Dict,
        config_params: Dict,
        volatility_tracker: VolatilityTracker,
        base_url: str,
        n0: int,
    ) -> Tuple[List, Dict]:
        """Applique tous les filtres de manière séquentielle."""
        # Appliquer le filtrage par funding, volume et temps
        filtered_symbols, n1 = self._apply_funding_volume_time_filters(
            perp_data, funding_map, config_params
        )

        # Appliquer le filtre de spread
        final_symbols, n2 = self._apply_spread_filter_with_metrics(
            filtered_symbols, config_params["spread_max"], base_url
        )

        # Appliquer le filtre de volatilité
        (
            final_symbols,
            n_after_volatility,
            n_before_volatility,
        ) = self._apply_volatility_filter(
            final_symbols, volatility_tracker, config_params
        )

        # Appliquer la limite finale
        final_symbols, n3 = self._apply_final_limit(
            final_symbols, config_params["limite"]
        )

        # Retourner les symboles finaux et les métriques
        filter_metrics = {
            "n0": n0,
            "n1": n1,
            "n2": n2,
            "n_before_volatility": n_before_volatility,
            "n_after_volatility": n_after_volatility,
            "n3": n3,
        }

        return final_symbols, filter_metrics

    def _record_filtering_metrics(
        self, filter_metrics: Dict, spread_max: float
    ):
        """Enregistre toutes les métriques de filtrage."""
        self._record_all_filter_metrics(
            filter_metrics["n0"],
            filter_metrics["n1"],
            filter_metrics["n2"],
            filter_metrics["n_before_volatility"],
            filter_metrics["n_after_volatility"],
            filter_metrics["n3"],
            spread_max,
        )

    def _build_final_watchlist(
        self, final_symbols: List
    ) -> Tuple[List[str], List[str], Dict]:
        """Construit et retourne la watchlist finale."""
        # Vérifier s'il y a des résultats
        if not final_symbols:
            self.logger.warning(
                "⚠️ Aucun symbole ne correspond aux critères de filtrage"
            )
            return [], [], {}

        # Construire les résultats finaux
        return self._build_final_results(final_symbols)

    def _extract_config_parameters(self) -> Dict:
        """Extrait les paramètres de configuration."""
        config = self.config
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

    def _get_and_validate_funding_data(
        self, base_url: str, categorie: str
    ) -> Dict:
        """Récupère et valide les données de funding."""
        funding_map = self._fetch_funding_data(base_url, categorie)

        if not funding_map:
            self.logger.warning(
                "⚠️ Aucun funding disponible pour la catégorie sélectionnée"
            )
            raise RuntimeError(
                "Aucun funding disponible pour la catégorie sélectionnée"
            )

        # Stocker les next_funding_time originaux pour fallback (REST)
        self._store_original_funding_data(funding_map)

        return funding_map

    def _count_initial_symbols(
        self, perp_data: Dict, funding_map: Dict
    ) -> int:
        """Compte les symboles avant filtrage."""
        all_symbols = list(set(perp_data["linear"] + perp_data["inverse"]))
        return len([s for s in all_symbols if s in funding_map])

    def _apply_funding_volume_time_filters(
        self, perp_data: Dict, funding_map: Dict, config_params: Dict
    ) -> Tuple[List, int]:
        """Applique les filtres de funding, volume et temps."""
        filtered_symbols = self.symbol_filter.filter_by_funding(
            perp_data,
            funding_map,
            config_params["funding_min"],
            config_params["funding_max"],
            config_params["volume_min_millions"],
            config_params["limite"],
            funding_time_min_minutes=config_params[
                "funding_time_min_minutes"
            ],
            funding_time_max_minutes=config_params[
                "funding_time_max_minutes"
            ],
        )
        return filtered_symbols, len(filtered_symbols)

    def _apply_spread_filter_with_metrics(
        self,
        filtered_symbols: List,
        spread_max: Optional[float],
        base_url: str,
    ) -> Tuple[List, int]:
        """Applique le filtre de spread et retourne les métriques."""
        final_symbols = self._apply_spread_filter(
            filtered_symbols, spread_max, base_url
        )
        return final_symbols, len(final_symbols)

    def _apply_volatility_filter(
        self,
        final_symbols: List,
        volatility_tracker: VolatilityTracker,
        config_params: Dict,
    ) -> Tuple[List, int, int]:
        """Applique le filtre de volatilité."""
        n_before_volatility = len(final_symbols) if final_symbols else 0

        if final_symbols:
            try:
                final_symbols = volatility_tracker.filter_by_volatility(
                    final_symbols,
                    config_params["volatility_min"],
                    config_params["volatility_max"],
                )
                n_after_volatility = len(final_symbols)
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Erreur lors du calcul de la volatilité : {e}"
                )
                n_after_volatility = n_before_volatility
        else:
            n_after_volatility = 0

        return final_symbols, n_after_volatility, n_before_volatility

    def _apply_final_limit(
        self, final_symbols: List, limite: Optional[int]
    ) -> Tuple[List, int]:
        """Applique la limite finale."""
        if limite is not None and len(final_symbols) > limite:
            final_symbols = final_symbols[:limite]
        return final_symbols, len(final_symbols)

    def _record_all_filter_metrics(
        self,
        n0: int,
        n1: int,
        n2: int,
        n_before_volatility: int,
        n_after_volatility: int,
        n3: int,
        spread_max: Optional[float],
    ):
        """Enregistre toutes les métriques des filtres."""
        record_filter_result("funding_volume_time", n1, n0 - n1)
        if spread_max is not None:
            record_filter_result("spread", n2, n1 - n2)
        record_filter_result(
            "volatility",
            n_after_volatility,
            n_before_volatility - n_after_volatility,
        )
        record_filter_result("final_limit", n3, n_after_volatility - n3)

    def _build_final_results(
        self, final_symbols: List
    ) -> Tuple[List[str], List[str], Dict]:
        """Construit les résultats finaux."""
        # Séparer les symboles par catégorie
        (
            linear_symbols,
            inverse_symbols,
        ) = self.symbol_filter.separate_symbols_by_category(
            final_symbols, self.symbol_categories
        )

        # Construire funding_data avec les bonnes données
        funding_data = self.symbol_filter.build_funding_data_dict(
            final_symbols
        )

        # Stocker les résultats
        self.selected_symbols = list(funding_data.keys())
        self.funding_data = funding_data

        return linear_symbols, inverse_symbols, funding_data

    def _fetch_funding_data(
        self, base_url: str, categorie: str
    ) -> Dict[str, Dict]:
        """
        Récupère les données de funding via UnifiedDataManager selon la catégorie.

        Cette méthode délègue la récupération des données à UnifiedDataManager
        qui est responsable de la gestion des appels API et du stockage des données.

        Args:
            base_url: URL de base de l'API Bybit
            categorie: Catégorie (linear, inverse, both)

        Returns:
            Dict: Données de funding récupérées par UnifiedDataManager
        """
        if categorie == "linear":
            return self.market_data_fetcher.fetch_funding_map(
                base_url, "linear", 10
            )
        elif categorie == "inverse":
            return self.market_data_fetcher.fetch_funding_map(
                base_url, "inverse", 10
            )
        else:  # "both"
            return self.market_data_fetcher.fetch_funding_data_parallel(
                base_url, ["linear", "inverse"], 10
            )

    def _store_original_funding_data(self, funding_map: Dict[str, Dict]):
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

    def _apply_spread_filter(
        self,
        filtered_symbols: List[Tuple],
        spread_max: Optional[float],
        base_url: str,
    ) -> List[Tuple]:
        """
        Applique le filtre de spread si nécessaire.

        Args:
            filtered_symbols: Symboles déjà filtrés
            spread_max: Spread maximum autorisé
            base_url: URL de base de l'API Bybit

        Returns:
            List: Symboles avec données de spread
        """
        if spread_max is None or not filtered_symbols:
            # Pas de filtre de spread, ajouter 0.0 comme spread par défaut
            return [
                (symbol, funding, volume, funding_time_remaining, 0.0)
                for symbol, funding, volume, funding_time_remaining in filtered_symbols
            ]

        try:
            # Récupérer les données de spread pour les symboles restants
            symbols_to_check = [symbol for symbol, _, _, _ in filtered_symbols]

            # Séparer les symboles par catégorie pour les requêtes spread
            linear_symbols_for_spread = [
                s
                for s in symbols_to_check
                if category_of_symbol(s, self.symbol_categories) == "linear"
            ]
            inverse_symbols_for_spread = [
                s
                for s in symbols_to_check
                if category_of_symbol(s, self.symbol_categories) == "inverse"
            ]

            # Récupérer les spreads en parallèle
            spread_data = {}
            if linear_symbols_for_spread:
                linear_spread_data = (
                    self.market_data_fetcher.fetch_spread_data(
                        base_url, linear_symbols_for_spread, 10, "linear"
                    )
                )
                spread_data.update(linear_spread_data)

            if inverse_symbols_for_spread:
                inverse_spread_data = (
                    self.market_data_fetcher.fetch_spread_data(
                        base_url, inverse_symbols_for_spread, 10, "inverse"
                    )
                )
                spread_data.update(inverse_spread_data)

            return self.symbol_filter.filter_by_spread(
                filtered_symbols, spread_data, spread_max
            )

        except Exception as e:
            self.logger.warning(
                f"⚠️ Erreur lors de la récupération des spreads : {e}"
            )
            # Continuer sans le filtre de spread
            return [
                (symbol, funding, volume, funding_time_remaining, 0.0)
                for symbol, funding, volume, funding_time_remaining in filtered_symbols
            ]

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
            funding_map = self._fetch_funding_data(base_url, categorie)

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
        return self.original_funding_data.copy()

    def get_config(self) -> Dict:
        """
        Retourne la configuration actuelle.

        Returns:
            Dictionnaire de configuration
        """
        return self.config.copy()
