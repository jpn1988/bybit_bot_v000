#!/usr/bin/env python3
"""
Module de volatilité refactorisé pour le bot Bybit.

Ce module gère le calcul et le filtrage de la volatilité :
- Calcul de volatilité à partir des klines (bougies)
- Filtrage des symboles par volatilité
- Gestion du rate limiting pour les requêtes API

Cette version fusionnée élimine la duplication entre VolatilityCalculator
et VolatilityComputer.
"""

import time
import asyncio
import aiohttp
import concurrent.futures
from typing import Optional, Dict, List, Tuple
from logging_setup import setup_logging
from interfaces.bybit_client_interface import BybitClientInterface
from bybit_client import BybitPublicClient
from async_rate_limiter import get_async_rate_limiter
from volatility_filter import VolatilityFilter
from instruments import category_of_symbol
from config.timeouts import TimeoutConfig, ConcurrencyConfig
from metrics import monitor_task_performance


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


def get_volatility_cache_key(symbol: str) -> str:
    """
    Génère une clé de cache pour la volatilité d'un symbole.

    Args:
        symbol: Symbole

    Returns:
        Clé de cache
    """
    return f"volatility_5m_{symbol}"


class VolatilityCalculator:
    """
    Calculateur de volatilité pour le bot Bybit.

    Cette classe gère le calcul de volatilité basé sur les klines (bougies)
    et le filtrage des symboles selon leurs critères de volatilité.
    
    La volatilité est calculée sur les 5 dernières bougies de 1 minute
    comme : (prix_max - prix_min) / prix_median
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
        self._client: Optional[BybitClientInterface] = None

        # Composant de filtrage
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

    @monitor_task_performance("volatility_batch_calculation", threshold=2.0)
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

        # Calculer la volatilité pour tous les symboles
        try:
            return await self._compute_batch(base_url, symbols)
        except Exception as e:
            self.logger.error(f"⚠️ Erreur calcul volatilité batch: {e}")
            return {symbol: None for symbol in symbols}

    async def _compute_batch(
        self, base_url: str, symbols: List[str]
    ) -> Dict[str, Optional[float]]:
        """
        Calcule la volatilité pour une liste de symboles en parallèle.

        Args:
            base_url: URL de base de l'API Bybit
            symbols: Liste des symboles à analyser

        Returns:
            Dictionnaire {symbol: volatility_pct} ou None si erreur
        """
        if not symbols:
            return {}

        # Limiter la concurrence globale pour éviter le rate limit
        # OPTIMISATION: Utilise la configuration externalisée au lieu d'une valeur codée en dur
        sem = asyncio.Semaphore(ConcurrencyConfig.VOLATILITY_MAX_CONCURRENT_REQUESTS)
        async_rate_limiter = get_async_rate_limiter()

        async def limited_task(sym: str):
            """Tâche avec rate limiting et semaphore."""
            # Respecter le rate limiter asynchrone avant chaque requête
            await async_rate_limiter.acquire()
            async with sem:
                return await self._compute_single(session, base_url, sym)

        # Créer une session aiohttp
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as session:
            # Créer les tâches async pour chaque symbole
            tasks = [limited_task(symbol) for symbol in symbols]

            # Exécuter toutes les tâches en parallèle
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Construire le dictionnaire de résultats
            volatility_results = {}
            for i, result in enumerate(results):
                symbol = symbols[i]
                if isinstance(result, Exception):
                    self.logger.warning(
                        f"Erreur async kline | symbol={symbol} "
                        f"timeout={self.timeout}s error={result}"
                    )
                    volatility_results[symbol] = None
                else:
                    volatility_results[symbol] = result

            return volatility_results

    async def _compute_single(
        self, session: aiohttp.ClientSession, base_url: str, symbol: str
    ) -> Optional[float]:
        """
        Calcule la volatilité pour un seul symbole.

        Args:
            session: Session HTTP asynchrone
            base_url: URL de base de l'API Bybit
            symbol: Symbole à analyser

        Returns:
            Volatilité en pourcentage ou None si erreur
        """
        try:
            # Récupérer les données klines
            klines = await self._fetch_klines(session, base_url, symbol)
            if not klines:
                return None

            # Calculer la volatilité à partir des klines
            return self._calculate_volatility(klines)

        except Exception as e:
            self.logger.error(
                f"Erreur inattendue calcul volatilité pour {symbol}: "
                f"{type(e).__name__}: {e}"
            )
            return None

    async def _fetch_klines(
        self, session: aiohttp.ClientSession, base_url: str, symbol: str
    ) -> Optional[List]:
        """
        Récupère les klines (bougies) pour un symbole.

        Args:
            session: Session HTTP asynchrone
            base_url: URL de base de l'API
            symbol: Symbole à récupérer

        Returns:
            Liste des klines ou None si erreur
        """
        try:
            # Déterminer la catégorie
            category = category_of_symbol(symbol, self._symbol_categories)

            # Construire l'URL et les paramètres
            url = f"{base_url}/v5/market/kline"
            params = {
                "category": category,
                "symbol": symbol,
                "interval": "1",  # 1 minute
                "limit": 6,  # 6 bougies pour avoir 5 minutes + 1 de sécurité
            }

            # Faire la requête HTTP asynchrone
            async with session.get(url, params=params) as response:
                # Vérifier le statut HTTP
                if response.status >= 400:
                    self.logger.warning(
                        f"Erreur HTTP kline GET {url} | "
                        f"category={category} symbol={symbol} "
                        f"status={response.status}"
                    )
                    return None

                data = await response.json()

                # Vérifier le retCode
                if data.get("retCode") != 0:
                    self.logger.warning(
                        f"Erreur API kline GET {url} | "
                        f"category={category} symbol={symbol} "
                        f'retCode={data.get("retCode")} '
                        f'retMsg="{data.get("retMsg", "")}"'
                    )
                    return None

                # Extraire les klines
                result = data.get("result", {})
                klines = result.get("list", [])

                # Vérifier qu'on a assez de données
                if len(klines) < 5:
                    return None

                return klines

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ValueError,
            TypeError,
            KeyError,
        ) as e:
            self.logger.error(
                f"Erreur fetch klines pour {symbol}: {type(e).__name__}: {e}"
            )
            return None

    def _calculate_volatility(self, klines: List) -> Optional[float]:
        """
        Calcule la volatilité à partir des klines.

        Args:
            klines: Liste des klines (format Bybit)

        Returns:
            Volatilité en pourcentage ou None si erreur
        """
        try:
            # Extraire les prix (high et low de chaque bougie)
            # Les bougies sont triées par timestamp décroissant
            prices_high = []
            prices_low = []

            for kline in klines[:5]:  # Prendre les 5 plus récentes
                try:
                    high = float(kline[2])  # Index 2 = high
                    low = float(kline[3])  # Index 3 = low
                    prices_high.append(high)
                    prices_low.append(low)
                except (ValueError, TypeError, IndexError):
                    # Ignorer les bougies avec des données invalides
                    continue

            # Vérifier qu'on a assez de données valides
            if len(prices_high) < 3:  # Au moins 3 bougies valides
                return None

            # Calculer la volatilité
            pmax = max(prices_high)  # Prix maximum sur la période
            pmin = min(prices_low)  # Prix minimum sur la période
            pmid = (pmax + pmin) / 2  # Prix médian

            # Éviter la division par zéro
            if pmid <= 0:
                return None

            # Calculer la volatilité en pourcentage
            vol_pct = (pmax - pmin) / pmid

            return vol_pct

        except (ValueError, TypeError) as e:
            self.logger.warning(f"Erreur calcul volatilité: {e}")
            return None

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

        CORRECTIF PERF-002: Évite la création d'event loops temporaires en vérifiant
        s'il y a déjà une event loop active et en utilisant une approche plus optimale.

        Args:
            symbols_data: Liste des données de symboles
            volatility_min: Volatilité minimum ou None
            volatility_max: Volatilité maximum ou None

        Returns:
            Liste filtrée avec volatilité
        """
        try:
            # CORRECTIF PERF-002: Vérifier d'abord s'il y a une event loop active
            try:
                # Test si on est dans une event loop existante
                loop = asyncio.get_running_loop()
                # Si on arrive ici, on est dans une event loop - utiliser run_in_executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._filter_in_new_loop, symbols_data, volatility_min, volatility_max)
                    return future.result(timeout=TimeoutConfig.FUTURE_RESULT)
            except RuntimeError:
                # Pas d'event loop active - créer une nouvelle event loop comme avant
                return self._filter_in_new_loop(symbols_data, volatility_min, volatility_max)

        except concurrent.futures.TimeoutError:
            self.logger.warning(
                f"⚠️ Timeout filtrage volatilité pour "
                f"{len(symbols_data)} symboles"
            )
            return []
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur filtrage volatilité: {e}")
            return []

    def _filter_in_new_loop(
        self,
        symbols_data: List[Tuple[str, float, float, str, float]],
        volatility_min: Optional[float],
        volatility_max: Optional[float],
    ) -> List[Tuple[str, float, float, str, float, Optional[float]]]:
        """
        Helper method pour exécuter le filtrage dans une nouvelle event loop.
        
        CORRECTIF PERF-002: Méthode séparée pour éviter la duplication de code
        et améliorer la lisibilité.
        
        Args:
            symbols_data: Liste des données de symboles
            volatility_min: Volatilité minimum ou None
            volatility_max: Volatilité maximum ou None

        Returns:
            Liste filtrée avec volatilité
        """
        try:
            return asyncio.run(
                self.filter_by_volatility_async(
                    symbols_data, volatility_min, volatility_max
                )
            )
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur dans _filter_in_new_loop: {e}")
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


# Fonction d'export pour compatibilité avec l'ancien code
