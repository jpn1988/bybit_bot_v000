#!/usr/bin/env python3
"""
Gestionnaire de récupération de données pour le bot Bybit - Version refactorisée.

Cette classe coordonne les différents composants spécialisés :
- FundingFetcher : Récupération des données de funding
- SpreadFetcher : Récupération des données de spread
- PaginationHandler : Gestion de la pagination
- ErrorHandler : Gestion des erreurs

Cette version refactorisée améliore la lisibilité en séparant clairement les responsabilités.
"""

from typing import Dict, List, Optional, Any
try:
    from .logging_setup import setup_logging
    from .funding_fetcher import FundingFetcher
    from .spread_fetcher import SpreadFetcher
    from .pagination_handler import PaginationHandler
    from .error_handler import ErrorHandler
except ImportError:
    from logging_setup import setup_logging
    from funding_fetcher import FundingFetcher
    from spread_fetcher import SpreadFetcher
    from pagination_handler import PaginationHandler
    from error_handler import ErrorHandler


class DataFetcher:
    """
    Gestionnaire de récupération de données pour le bot Bybit - Version refactorisée.

    Cette classe coordonne les différents composants spécialisés :
    - FundingFetcher : Récupération des données de funding
    - SpreadFetcher : Récupération des données de spread
    - PaginationHandler : Gestion de la pagination
    - ErrorHandler : Gestion des erreurs

    Cette version améliore la lisibilité en séparant clairement les responsabilités.
    """

    def __init__(self, logger=None):
        """
        Initialise le gestionnaire de récupération de données.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()

        # Initialiser les composants spécialisés
        self._funding_fetcher = FundingFetcher(logger)
        self._spread_fetcher = SpreadFetcher(logger)
        self._pagination_handler = PaginationHandler(logger)
        self._error_handler = ErrorHandler(logger)

    # ===== MÉTHODES DE FUNDING (DÉLÉGATION VERS FUNDING_FETCHER) =====

    def fetch_funding_map(
        self, base_url: str, category: str, timeout: int = 10
    ) -> Dict[str, Dict]:
        """
        Récupère les taux de funding pour une catégorie donnée.

        Args:
            base_url: URL de base de l'API Bybit
            category: Catégorie (linear ou inverse)
            timeout: Timeout pour les requêtes HTTP

        Returns:
            Dict[str, Dict]: Dictionnaire {symbol: {funding, volume, next_funding_time}}

        Raises:
            RuntimeError: En cas d'erreur HTTP ou API
        """
        return self._funding_fetcher.fetch_funding_map(base_url, category, timeout)

    def fetch_funding_data_parallel(
        self, base_url: str, categories: List[str], timeout: int = 10
    ) -> Dict[str, Dict]:
        """
        Récupère les données de funding pour plusieurs catégories en parallèle.

        Args:
            base_url: URL de base de l'API Bybit
            categories: Liste des catégories à récupérer
            timeout: Timeout pour les requêtes HTTP

        Returns:
            Dict[str, Dict]: Dictionnaire combiné de toutes les catégories
        """
        return self._funding_fetcher.fetch_funding_data_parallel(base_url, categories, timeout)

    # ===== MÉTHODES DE SPREAD (DÉLÉGATION VERS SPREAD_FETCHER) =====

    def fetch_spread_data(
        self,
        base_url: str,
        symbols: List[str],
        timeout: int = 10,
        category: str = "linear",
    ) -> Dict[str, float]:
        """
        Récupère les spreads via /v5/market/tickers paginé, puis filtre localement.

        Args:
            base_url: URL de base de l'API Bybit
            symbols: Liste cible des symboles à retourner
            timeout: Timeout HTTP
            category: "linear" ou "inverse"

        Returns:
            Dict[str, float]: map {symbol: spread_pct}
        """
        return self._spread_fetcher.fetch_spread_data(base_url, symbols, timeout, category)

    # ===== MÉTHODES DE PAGINATION (DÉLÉGATION VERS PAGINATION_HANDLER) =====

    def fetch_paginated_data(
        self,
        base_url: str,
        endpoint: str,
        params: Dict,
        timeout: int = 10,
        max_pages: int = 100,
    ) -> List[Dict]:
        """
        Récupère toutes les données via pagination.

        Args:
            base_url: URL de base de l'API
            endpoint: Endpoint à appeler
            params: Paramètres de la requête
            timeout: Timeout HTTP
            max_pages: Nombre maximum de pages à récupérer

        Returns:
            Liste de toutes les données récupérées
        """
        return self._pagination_handler.fetch_paginated_data(
            base_url, endpoint, params, timeout, max_pages
        )

    # ===== MÉTHODES DE VALIDATION =====

    def validate_funding_data(self, funding_data: Dict[str, Dict]) -> bool:
        """
        Valide les données de funding récupérées.

        Args:
            funding_data: Données de funding à valider

        Returns:
            True si les données sont valides
        """
        return self._funding_fetcher.validate_funding_data(funding_data)

    def validate_spread_data(self, spread_data: Dict[str, float]) -> bool:
        """
        Valide les données de spread récupérées.

        Args:
            spread_data: Données de spread à valider

        Returns:
            True si les données sont valides
        """
        return self._spread_fetcher.validate_spread_data(spread_data)

    # ===== MÉTHODES DE GESTION D'ERREURS =====

    def handle_error(self, error: Exception, context: str = ""):
        """
        Gère une erreur avec le contexte approprié.

        Args:
            error: Exception à gérer
            context: Contexte de l'erreur
        """
        self._error_handler.log_error(error, context)

    def should_retry(self, error: Exception, attempt: int, max_attempts: int = 3) -> bool:
        """
        Détermine si une opération doit être retentée.

        Args:
            error: Exception rencontrée
            attempt: Numéro de la tentative actuelle
            max_attempts: Nombre maximum de tentatives

        Returns:
            True si l'opération doit être retentée
        """
        return self._error_handler.should_retry(error, attempt, max_attempts)

    # ===== MÉTHODES DE COORDINATION =====

    def fetch_complete_market_data(
        self,
        base_url: str,
        categories: List[str],
        symbols: List[str],
        timeout: int = 10,
    ) -> Dict[str, Any]:
        """
        Récupère toutes les données de marché (funding + spreads) en une seule opération.

        Args:
            base_url: URL de base de l'API Bybit
            categories: Liste des catégories à récupérer
            symbols: Liste des symboles pour les spreads
            timeout: Timeout pour les requêtes HTTP

        Returns:
            Dict contenant funding_data et spread_data
        """
        try:
            self.logger.info(f"📊 Récupération complète des données de marché...")
            
            # Récupérer les données de funding
            funding_data = self.fetch_funding_data_parallel(base_url, categories, timeout)
            
            # Récupérer les données de spread
            spread_data = {}
            for category in categories:
                category_spreads = self.fetch_spread_data(base_url, symbols, timeout, category)
                spread_data.update(category_spreads)
            
            # Valider les données
            funding_valid = self.validate_funding_data(funding_data)
            spread_valid = self.validate_spread_data(spread_data)
            
            if not funding_valid:
                self.logger.warning("⚠️ Données de funding invalides")
            if not spread_valid:
                self.logger.warning("⚠️ Données de spread invalides")
            
            result = {
                "funding_data": funding_data,
                "spread_data": spread_data,
                "funding_valid": funding_valid,
                "spread_valid": spread_valid,
            }
            
            self.logger.info(
                f"✅ Données de marché récupérées: {len(funding_data)} funding, "
                f"{len(spread_data)} spreads"
            )
            return result
            
        except Exception as e:
            self._error_handler.log_error(e, "fetch_complete_market_data")
            raise

    def get_fetching_stats(self) -> Dict[str, int]:
        """
        Retourne les statistiques de récupération.

        Returns:
            Dict avec les statistiques
        """
        return {
            "funding_fetcher_available": hasattr(self._funding_fetcher, 'logger'),
            "spread_fetcher_available": hasattr(self._spread_fetcher, 'logger'),
            "pagination_handler_available": hasattr(self._pagination_handler, 'logger'),
            "error_handler_available": hasattr(self._error_handler, 'logger'),
        }