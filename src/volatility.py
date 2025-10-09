#!/usr/bin/env python3
"""
Module de volatilité refactorisé pour le bot Bybit.

Ce module coordonne les composants de calcul de volatilité :
- AsyncRateLimiter : Gestion du rate limiting
- VolatilityComputer : Calculs de volatilité
- VolatilityFilter : Filtrage par volatilité

Cette version refactorisée suit le principe de responsabilité unique.
"""

import time
import asyncio
import concurrent.futures
from typing import Optional, Dict, List, Tuple
from logging_setup import setup_logging
from bybit_client import BybitPublicClient
from async_rate_limiter import get_async_rate_limiter
from volatility_computer import VolatilityComputer, get_volatility_cache_key
from volatility_filter import VolatilityFilter


def is_cache_valid(timestamp: float, ttl_seconds: int = 60) -> bool:
    """
    Vérifie si un cache est encore valide.

    Args:
        timestamp: Timestamp du cache
        ttl_seconds: Durée de vie en secondes

    Returns:
        True si le cache est valide
    """
    return (time.time() - timestamp) < ttl_seconds


class VolatilityCalculator:
    """
    Coordinateur de calcul de volatilité pour le bot Bybit.

    Cette classe coordonne les différents composants de volatilité
    sans implémenter directement la logique métier.
    
    Responsabilité unique : Orchestration des composants de volatilité.
    """

    def __init__(self, testnet: bool = True, timeout: int = 10, logger=None):
        """
        Initialise le calculateur de volatilité.

        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            timeout: Timeout pour les requêtes
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.timeout = timeout
        self.logger = logger or setup_logging()

        # Client pour récupérer l'URL de base
        self._client: Optional[BybitPublicClient] = None

        # Composants spécialisés
        self.computer = VolatilityComputer(timeout=timeout, logger=logger)
        self.filter = VolatilityFilter(logger=logger)

        # Catégories des symboles
        self._symbol_categories: Dict[str, str] = {}

    def set_symbol_categories(self, symbol_categories: Dict[str, str]):
        """
        Définit le mapping des catégories de symboles.

        Args:
            symbol_categories: Dictionnaire {symbol: category}
        """
        self._symbol_categories = symbol_categories
        # Propager aux composants
        self.computer.set_symbol_categories(symbol_categories)

    async def compute_volatility_batch(
        self, symbols: List[str]
    ) -> Dict[str, Optional[float]]:
        """
        Calcule la volatilité pour une liste de symboles en batch.

        Args:
            symbols: Liste des symboles

        Returns:
            Dictionnaire {symbol: volatility_pct} ou None si erreur
        """
        if not symbols:
            return {}

        # Initialiser le client si nécessaire
        if not self._client:
            try:
                self._client = BybitPublicClient(
                    testnet=self.testnet, timeout=self.timeout
                )
            except Exception as e:
                self.logger.error(
                    f"⚠️ Impossible d'initialiser le client pour la "
                    f"volatilité: {e}"
                )
                return {symbol: None for symbol in symbols}

        # Obtenir l'URL de base
        base_url = self._client.public_base_url()

        # Déléguer le calcul au computer
        try:
            return await self.computer.compute_batch(base_url, symbols)
        except Exception as e:
            self.logger.error(f"⚠️ Erreur calcul volatilité batch: {e}")
            return {symbol: None for symbol in symbols}

    async def filter_by_volatility_async(
        self,
        symbols_data: List[Tuple[str, float, float, str, float]],
        volatility_min: Optional[float],
        volatility_max: Optional[float],
    ) -> List[Tuple[str, float, float, str, float, Optional[float]]]:
        """
        Filtre les symboles par volatilité avec calcul automatique.

        Args:
            symbols_data: Liste des (symbol, funding, volume,
                funding_time_remaining, spread_pct)
            volatility_min: Volatilité minimum ou None
            volatility_max: Volatilité maximum ou None

        Returns:
            Liste des (symbol, funding, volume, funding_time_remaining,
                spread_pct, volatility_pct)
        """
        # Extraire les symboles
        symbols = [symbol for symbol, _, _, _, _ in symbols_data]

        # Calculer les volatilités
        volatilities = await self.compute_volatility_batch(symbols)

        # Appliquer les filtres
        return self.filter.filter_symbols(
            symbols_data, volatilities, volatility_min, volatility_max
        )

    def filter_by_volatility(
        self,
        symbols_data: List[Tuple[str, float, float, str, float]],
        volatility_min: Optional[float],
        volatility_max: Optional[float],
    ) -> List[Tuple[str, float, float, str, float, Optional[float]]]:
        """
        Version synchrone du filtrage par volatilité.

        Args:
            symbols_data: Liste des données de symboles
            volatility_min: Volatilité minimum ou None
            volatility_max: Volatilité maximum ou None

        Returns:
            Liste filtrée avec volatilité
        """
        try:
            # Créer un nouveau event loop dans un thread séparé
            def run_in_new_loop():
                return asyncio.run(
                    self.filter_by_volatility_async(
                        symbols_data, volatility_min, volatility_max
                    )
                )

            # Utiliser un ThreadPoolExecutor avec timeout
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=1
            ) as executor:
                future = executor.submit(run_in_new_loop)
                return future.result(timeout=30)  # Timeout de 30 secondes

        except concurrent.futures.TimeoutError:
            self.logger.warning(
                f"⚠️ Timeout filtrage volatilité pour "
                f"{len(symbols_data)} symboles"
            )
            return []
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur filtrage volatilité: {e}")
            return []

    def get_statistics(
        self, volatilities: Dict[str, Optional[float]]
    ) -> Dict[str, float]:
        """
        Calcule des statistiques sur les volatilités.

        Args:
            volatilities: Dictionnaire {symbol: volatility_pct}

        Returns:
            Statistiques (min, max, moyenne)
        """
        return self.filter.get_statistics(volatilities)


# Fonctions d'export pour compatibilité avec l'ancien code
async def compute_volatility_batch_async(
    bybit_client,
    symbols: List[str],
    timeout: int = 10,
    symbol_categories: Dict[str, str] | None = None,
) -> Dict[str, Optional[float]]:
    """
    Fonction legacy pour compatibilité.
    
    Calcule la volatilité pour une liste de symboles en parallèle.
    """
    computer = VolatilityComputer(timeout=timeout)
    if symbol_categories:
        computer.set_symbol_categories(symbol_categories)
    
    base_url = bybit_client.public_base_url()
    return await computer.compute_batch(base_url, symbols)
