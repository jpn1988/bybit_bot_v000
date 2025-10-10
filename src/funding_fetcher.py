#!/usr/bin/env python3
"""
Gestionnaire de récupération des données de funding pour le bot Bybit - Version refactorisée.

Cette classe gère uniquement :
- La récupération des données de funding
- Le traitement des données de funding
- La gestion des erreurs spécifiques au funding
"""

from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor
try:
    from .logging_setup import setup_logging
    from .pagination_handler import PaginationHandler
    from .error_handler import ErrorHandler
    from .config import MAX_WORKERS_THREADPOOL
except ImportError:
    from logging_setup import setup_logging
    from pagination_handler import PaginationHandler
    from error_handler import ErrorHandler
    from config import MAX_WORKERS_THREADPOOL


class FundingFetcher:
    """
    Gestionnaire de récupération des données de funding pour le bot Bybit.

    Responsabilités :
    - Récupération des données de funding
    - Traitement des données de funding
    - Gestion des erreurs spécifiques au funding
    """

    def __init__(self, logger=None):
        """
        Initialise le gestionnaire de funding.

        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()
        self._pagination_handler = PaginationHandler(logger)
        self._error_handler = ErrorHandler(logger)

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
        try:
            self.logger.debug(f"📊 Récupération funding pour {category}...")

            # Paramètres de base pour la pagination
            params = {
                "category": category,
                "limit": 1000,  # Limite maximum supportée par l'API Bybit
            }

            # Récupérer toutes les données via pagination
            all_tickers = self._pagination_handler.fetch_paginated_data(
                base_url, "/v5/market/tickers", params, timeout
            )

            # Traiter les données de funding
            funding_map = self._process_funding_data(all_tickers)

            self.logger.info(f"✅ Funding récupéré: {len(funding_map)} symboles pour {category}")
            return funding_map

        except Exception as e:
            self._error_handler.log_error(e, f"fetch_funding_map category={category}")
            raise

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
        if len(categories) == 1:
            return self.fetch_funding_map(base_url, categories[0], timeout)

        funding_map = {}

        try:
            # Paralléliser les requêtes
            with ThreadPoolExecutor(max_workers=MAX_WORKERS_THREADPOOL) as executor:
                # Lancer les requêtes en parallèle
                futures = {
                    executor.submit(self.fetch_funding_map, base_url, category, timeout): category
                    for category in categories
                }

                # Récupérer les résultats
                for future in futures:
                    category = futures[future]
                    try:
                        category_data = future.result()
                        funding_map.update(category_data)
                        self.logger.debug(f"✅ Funding {category}: {len(category_data)} symboles")
                    except Exception as e:
                        self._error_handler.log_error(
                            e, f"fetch_funding_data_parallel category={category}"
                        )
                        raise

            self.logger.info(f"✅ Funding parallèle terminé: {len(funding_map)} symboles total")
            return funding_map

        except Exception as e:
            self._error_handler.log_error(e, "fetch_funding_data_parallel")
            raise

    def _process_funding_data(self, tickers: List[Dict[str, Any]]) -> Dict[str, Dict]:
        """
        Traite les données de tickers pour extraire les informations de funding.

        Args:
            tickers: Liste des tickers reçus de l'API

        Returns:
            Dict[str, Dict]: Dictionnaire des données de funding
        """
        funding_map = {}

        for ticker in tickers:
            try:
                # Extraire les données du ticker
                symbol = ticker.get("symbol", "")
                funding_rate = ticker.get("fundingRate")
                volume_24h = ticker.get("volume24h")
                next_funding_time = ticker.get("nextFundingTime")

                # Valider les données essentielles
                if not symbol or funding_rate is None:
                    continue

                # Construire l'entrée de funding
                funding_entry = self._build_funding_entry(
                    symbol, funding_rate, volume_24h, next_funding_time
                )

                if funding_entry:
                    funding_map[symbol] = funding_entry

            except Exception as e:
                # Logger l'erreur mais continuer le traitement
                self.logger.warning(f"⚠️ Erreur traitement ticker: {e}")
                continue

        return funding_map

    def _build_funding_entry(
        self,
        symbol: str,
        funding_rate: Any,
        volume_24h: Any,
        next_funding_time: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Construit une entrée de funding à partir des données du ticker.

        Args:
            symbol: Symbole du ticker
            funding_rate: Taux de funding
            volume_24h: Volume 24h
            next_funding_time: Prochain temps de funding

        Returns:
            Dict des données de funding ou None si invalide
        """
        try:
            # Convertir et valider les données
            funding = self._safe_float_conversion(funding_rate, "funding_rate")
            volume = self._safe_float_conversion(volume_24h, "volume_24h")

            if funding is None:
                return None

            return {
                "funding": funding,
                "volume": volume if volume is not None else 0.0,
                "next_funding_time": next_funding_time,
            }

        except Exception as e:
            self.logger.warning(f"⚠️ Erreur construction funding pour {symbol}: {e}")
            return None

    def _safe_float_conversion(self, value: Any, field_name: str) -> Optional[float]:
        """
        Convertit une valeur en float de manière sécurisée.

        Args:
            value: Valeur à convertir
            field_name: Nom du champ (pour les logs)

        Returns:
            Float converti ou None si impossible
        """
        try:
            if value is None:
                return None
            return float(value)
        except (ValueError, TypeError):
            self.logger.debug(f"⚠️ Conversion float échouée pour {field_name}: {value}")
            return None

    def validate_funding_data(self, funding_data: Dict[str, Dict]) -> bool:
        """
        Valide les données de funding récupérées.

        Args:
            funding_data: Données de funding à valider

        Returns:
            True si les données sont valides
        """
        try:
            if not funding_data:
                self.logger.warning("⚠️ Aucune donnée de funding à valider")
                return False

            valid_count = 0
            for symbol, data in funding_data.items():
                if self._validate_single_funding_entry(symbol, data):
                    valid_count += 1

            self.logger.debug(
                f"📊 Validation funding: {valid_count}/{len(funding_data)} entrées valides"
            )
            return valid_count > 0

        except Exception as e:
            self.logger.error(f"❌ Erreur validation funding: {e}")
            return False

    def _validate_single_funding_entry(self, symbol: str, data: Dict[str, Any]) -> bool:
        """
        Valide une entrée de funding individuelle.

        Args:
            symbol: Symbole à valider
            data: Données du symbole

        Returns:
            True si l'entrée est valide
        """
        try:
            if not symbol or not isinstance(data, dict):
                return False

            # Vérifier les champs requis
            required_fields = ["funding", "volume", "next_funding_time"]
            for field in required_fields:
                if field not in data:
                    return False

            # Vérifier les types
            if not isinstance(data["funding"], (int, float)):
                return False
            if not isinstance(data["volume"], (int, float)):
                return False
            if not isinstance(data["next_funding_time"], (str, type(None))):
                return False

            return True

        except Exception:
            return False
