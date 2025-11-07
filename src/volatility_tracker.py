#!/usr/bin/env python3
"""
Gestionnaire de volatilité dédié pour le bot Bybit - Version refactorisée.

Cette classe coordonne les différents composants :
- VolatilityCalculator : Calculs purs
- VolatilityCache : Gestion du cache
- VolatilityScheduler : Rafraîchissement périodique
"""

from typing import List, Tuple, Dict, Optional, Callable
from logging_setup import setup_logging
from interfaces.volatility_tracker_interface import VolatilityTrackerInterface
from volatility import VolatilityCalculator
from volatility_cache import VolatilityCache
from volatility_scheduler import VolatilityScheduler


class VolatilityTracker(VolatilityTrackerInterface):
    """
    Gestionnaire de volatilité pour le bot Bybit - Version refactorisée.

    Cette classe coordonne les différents composants :
    - VolatilityCalculator : Calculs purs
    - VolatilityCache : Gestion du cache
    - VolatilityScheduler : Rafraîchissement périodique
    """

    def __init__(
        self,
        testnet: bool = True,
        ttl_seconds: int = 120,
        max_cache_size: int = 1000,
        logger=None,
        calculator=None,
        cache=None,
        scheduler=None,
    ):
        """
        Initialise le gestionnaire de volatilité.

        Args:
            testnet (bool): Utiliser le testnet (True) ou le marché réel (False)
            ttl_seconds (int): Durée de vie du cache en secondes
            max_cache_size (int): Taille maximale du cache
            logger: Logger pour les messages (optionnel)
            calculator: Calculateur de volatilité (optionnel, créé automatiquement si non fourni)
            cache: Cache de volatilité (optionnel, créé automatiquement si non fourni)
            scheduler: Planificateur de volatilité (optionnel, créé automatiquement si non fourni)
        """
        self.testnet = testnet
        self.ttl_seconds = ttl_seconds
        self.max_cache_size = max_cache_size
        self.logger = logger or setup_logging()

        # Initialiser les composants spécialisés (injection avec fallback)
        self.calculator = calculator or VolatilityCalculator(
            testnet=testnet, logger=self.logger
        )
        self.cache = cache or VolatilityCache(
            ttl_seconds=ttl_seconds,
            max_cache_size=max_cache_size,
            logger=self.logger,
        )
        self.scheduler = scheduler or VolatilityScheduler(
            self.calculator, self.cache, logger=self.logger
        )

        # Callback pour obtenir la liste des symboles actifs
        self._get_active_symbols_callback: Optional[
            Callable[[], List[str]]
        ] = None

    def set_symbol_categories(self, symbol_categories: Dict[str, str]):
        """
        Définit le mapping des catégories de symboles.

        Args:
            symbol_categories: Dictionnaire {symbol: category}
        """
        self.calculator.set_symbol_categories(symbol_categories)

    def set_active_symbols_callback(self, callback: Callable[[], List[str]]):
        """
        Définit le callback pour obtenir la liste des symboles actifs.

        Args:
            callback: Fonction qui retourne la liste des symboles actifs
        """
        self._get_active_symbols_callback = callback
        self.scheduler.set_active_symbols_callback(callback)

    def start_refresh_task(self):
        """Démarre la tâche de rafraîchissement automatique."""
        self.scheduler.start_refresh_task()

    def stop_refresh_task(self):
        """Arrête la tâche de rafraîchissement."""
        self.scheduler.stop_refresh_task()

    def get_cached_volatility(self, symbol: str) -> Optional[float]:
        """
        Récupère la volatilité en cache pour un symbole.

        Args:
            symbol: Symbole à rechercher

        Returns:
            Volatilité en pourcentage ou None si absent/expiré
        """
        return self.cache.get_cached_volatility(symbol)

    def set_cached_volatility(self, symbol: str, volatility_pct: float):
        """
        Met à jour le cache de volatilité pour un symbole.

        Args:
            symbol: Symbole
            volatility_pct: Volatilité en pourcentage
        """
        self.cache.set_cached_volatility(symbol, volatility_pct)

    def clear_stale_cache(self, active_symbols: List[str]):
        """
        Nettoie le cache des symboles non actifs.

        Args:
            active_symbols: Liste des symboles actifs
        """
        self.cache.clear_stale_cache(active_symbols)

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
        return await self.calculator.compute_volatility_batch(symbols)

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
        return await self.calculator.filter_by_volatility_async(
            symbols_data, volatility_min, volatility_max
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
        return self.calculator.filter_by_volatility(
            symbols_data, volatility_min, volatility_max
        )

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Retourne les statistiques du cache.

        Returns:
            Dictionnaire avec les stats du cache
        """
        return self.cache.get_cache_stats()

    def is_running(self) -> bool:
        """
        Vérifie si le tracker est en cours d'exécution.

        Returns:
            True si le rafraîchissement est actif
        """
        return self.scheduler.is_running()
