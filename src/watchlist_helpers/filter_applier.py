#!/usr/bin/env python3
"""
Helper pour l'application des filtres de watchlist.

Cette classe extrait la logique d'application des filtres
du WatchlistManager pour améliorer la lisibilité.
"""

from typing import List, Tuple, Dict, Optional
from logging_setup import setup_logging
from instruments import category_of_symbol
from .weight_calculator import WeightCalculator


class WatchlistFilterApplier:
    """
    Helper pour appliquer les filtres de sélection de symboles.

    Responsabilités :
    - Application du filtre funding/volume/temps
    - Application du filtre spread
    - Application du filtre volatilité
    - Application de la limite finale
    """

    def __init__(
        self, symbol_filter, market_data_fetcher, symbol_categories, logger=None
    ):
        """
        Initialise l'appliqueur de filtres.

        Args:
            symbol_filter: Instance de SymbolFilter
            market_data_fetcher: Instance de DataManager
            symbol_categories: Mapping des catégories de symboles
            logger: Logger pour les messages (optionnel)
        """
        self.symbol_filter = symbol_filter
        self.market_data_fetcher = market_data_fetcher
        self.symbol_categories = symbol_categories
        self.logger = logger or setup_logging()
        self.weight_calculator = WeightCalculator(logger=self.logger)

    def apply_funding_volume_time_filters(
        self, perp_data: Dict, funding_map: Dict, config_params: Dict
    ) -> Tuple[List, int]:
        """
        Applique les filtres de funding, volume et temps.

        Args:
            perp_data: Données des perpétuels
            funding_map: Données de funding
            config_params: Paramètres de configuration

        Returns:
            Tuple (symboles filtrés, nombre de symboles)
        """
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

    def apply_spread_filter(
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
            Symboles avec données de spread
        """
        if spread_max is None or not filtered_symbols:
            # Pas de filtre de spread, ajouter 0.0 par défaut
            return [
                (symbol, funding, volume, funding_time_remaining, 0.0)
                for symbol, funding, volume, funding_time_remaining in (
                    filtered_symbols
                )
            ]

        try:
            # Récupérer les données de spread
            symbols_to_check = [
                symbol for symbol, _, _, _ in filtered_symbols
            ]

            # Séparer par catégorie
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
                    self.market_data_fetcher.fetcher.fetch_spread_data(
                        base_url, linear_symbols_for_spread, 10, "linear"
                    )
                )
                spread_data.update(linear_spread_data)

            if inverse_symbols_for_spread:
                inverse_spread_data = (
                    self.market_data_fetcher.fetcher.fetch_spread_data(
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
                for symbol, funding, volume, funding_time_remaining in (
                    filtered_symbols
                )
            ]

    def apply_spread_filter_with_metrics(
        self,
        filtered_symbols: List,
        spread_max: Optional[float],
        base_url: str,
    ) -> Tuple[List, int]:
        """
        Applique le filtre de spread et retourne les métriques.

        Args:
            filtered_symbols: Symboles filtrés
            spread_max: Spread maximum
            base_url: URL de base

        Returns:
            Tuple (symboles filtrés, nombre)
        """
        final_symbols = self.apply_spread_filter(
            filtered_symbols, spread_max, base_url
        )
        return final_symbols, len(final_symbols)

    def apply_volatility_filter(
        self,
        final_symbols: List,
        volatility_tracker,
        config_params: Dict,
    ) -> Tuple[List, int, int]:
        """
        Applique le filtre de volatilité.

        Args:
            final_symbols: Symboles à filtrer
            volatility_tracker: Tracker de volatilité
            config_params: Paramètres de configuration

        Returns:
            Tuple (symboles filtrés, n_after, n_before)
        """
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

    def apply_final_limit(
        self, final_symbols: List, limite: Optional[int]
    ) -> Tuple[List, int]:
        """
        Applique la limite finale sur le nombre de symboles.

        Args:
            final_symbols: Symboles filtrés
            limite: Limite maximale

        Returns:
            Tuple (symboles limités, nombre)
        """
        if limite is not None and len(final_symbols) > limite:
            final_symbols = final_symbols[:limite]
        return final_symbols, len(final_symbols)

    def apply_weighting_system(
        self, final_symbols: List, weights_config: Dict
    ) -> Tuple[List, int]:
        """
        Applique le système de poids et tri intelligent.

        Args:
            final_symbols: Symboles après tous les filtres
            weights_config: Configuration des poids depuis parameters.yaml

        Returns:
            Tuple (symboles triés par poids, nombre)
        """
        if not final_symbols or not weights_config:
            return final_symbols, len(final_symbols) if final_symbols else 0

        try:
            # Appliquer le système de poids complet
            weighted_opportunities = self.weight_calculator.process_weighted_ranking(
                final_symbols, weights_config, self.symbol_categories
            )

            # Convertir les dictionnaires en tuples pour maintenir la compatibilité
            # Format: (symbol, funding, volume, funding_time, spread, volatility, weight)
            weighted_tuples = []
            for opp in weighted_opportunities:
                weighted_tuple = (
                    opp['symbol'],
                    opp['funding'],
                    opp['volume'],
                    opp['funding_time'],
                    opp['spread'],
                    opp['volatility'],
                    opp['weight']
                )
                weighted_tuples.append(weighted_tuple)

            return weighted_tuples, len(weighted_tuples)

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur lors de l'application du système de poids: {e}")
            # Retourner les symboles originaux en cas d'erreur
            return final_symbols, len(final_symbols)

    def apply_spot_filter(
        self, symbols: List[str], spot_checker
    ) -> Tuple[List[str], int]:
        """
        Filter symbols to keep only those available in spot.

        Args:
            symbols: List of symbols to filter
            spot_checker: SpotAvailabilityChecker instance

        Returns:
            Tuple (filtered symbols, count after filter)
        """
        if not spot_checker:
            return symbols, len(symbols)

        # Debug: Show which symbols are being tested
        self.logger.info(f"🔍 Testing {len(symbols)} symbols for spot availability: {symbols[:10]}{'...' if len(symbols) > 10 else ''}")

        # Extract symbol names from tuples if needed
        symbol_names = []
        for item in symbols:
            if isinstance(item, tuple) and len(item) > 0:
                symbol_names.append(item[0])  # First element is the symbol name
            elif isinstance(item, str):
                symbol_names.append(item)
            else:
                self.logger.warning(f"🔍 Unexpected symbol format: {item}")
                continue

        # Filter symbols and keep original format (tuples)
        filtered = []
        for item in symbols:
            if isinstance(item, tuple) and len(item) > 0:
                symbol_name = item[0]
                if spot_checker.is_spot_available(symbol_name):
                    filtered.append(item)  # Keep original tuple format
            elif isinstance(item, str):
                if spot_checker.is_spot_available(item):
                    filtered.append(item)  # Keep original string format

        # Debug: Show which symbols passed the spot filter
        if filtered:
            symbol_names = [item[0] if isinstance(item, tuple) else item for item in filtered]
            self.logger.info(f"🔍 Symbols that passed spot filter: {symbol_names}")
        else:
            self.logger.info(f"🔍 No symbols passed spot filter. Available spot symbols: {list(spot_checker._spot_available_cache)[:10]}{'...' if len(spot_checker._spot_available_cache) > 10 else ''}")

        self.logger.info(
            f"🔍 Filtre spot: {len(filtered)} symboles disponibles en spot "
            f"sur {len(symbols)} symboles perp"
        )

        return filtered, len(filtered)

    def apply_all_filters(
        self,
        perp_data: Dict,
        funding_map: Dict,
        config_params: Dict,
        volatility_tracker,
        base_url: str,
        n0: int,
        spot_checker=None,  # NEW parameter
    ) -> Tuple[List, Dict]:
        """
        Applique tous les filtres de manière séquentielle.

        Args:
            perp_data: Données des perpétuels
            funding_map: Données de funding
            config_params: Paramètres de configuration
            volatility_tracker: Tracker de volatilité
            base_url: URL de base
            n0: Nombre initial de symboles

        Returns:
            Tuple (symboles finaux, métriques de filtrage)
        """
        # Appliquer le filtrage par funding, volume et temps
        filtered_symbols, n1 = self.apply_funding_volume_time_filters(
            perp_data, funding_map, config_params
        )

        # NEW: Appliquer le filtre de disponibilité spot
        filtered_symbols, n_spot = self.apply_spot_filter(
            filtered_symbols, spot_checker
        )

        # Appliquer le filtre de spread
        final_symbols, n2 = self.apply_spread_filter_with_metrics(
            filtered_symbols, config_params["spread_max"], base_url
        )

        # Appliquer le filtre de volatilité
        (
            final_symbols,
            n_after_volatility,
            n_before_volatility,
        ) = self.apply_volatility_filter(
            final_symbols, volatility_tracker, config_params
        )

        # Appliquer la limite finale (AVANT le système de poids)
        final_symbols, n3 = self.apply_final_limit(
            final_symbols, config_params["limite"]
        )

        # Appliquer le système de poids et tri intelligent (NOUVEAU)
        final_symbols, n4 = self.apply_weighting_system(
            final_symbols, config_params.get("weights", {})
        )

        # Retourner les symboles finaux et les métriques
        filter_metrics = {
            "n0": n0,
            "n1": n1,
            "n_spot": n_spot,  # NEW metric
            "n2": n2,
            "n_before_volatility": n_before_volatility,
            "n_after_volatility": n_after_volatility,
            "n3": n3,
            "n4": n4,  # Nombre après application du système de poids
        }

        return final_symbols, filter_metrics
