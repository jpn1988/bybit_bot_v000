#!/usr/bin/env python3
"""
Calculateur de volatilité pour le bot Bybit.

Cette classe est responsable des calculs purs de volatilité basés sur
les données de klines (bougies) de l'API Bybit.
"""

import asyncio
import aiohttp
from typing import Optional, Dict, List
from logging_setup import setup_logging
from instruments import category_of_symbol
from async_rate_limiter import get_async_rate_limiter


class VolatilityComputer:
    """
    Calculateur de volatilité basé sur les klines.
    
    Responsabilité unique : Calculer la volatilité à partir des données de prix.
    
    La volatilité est calculée sur les 5 dernières bougies de 1 minute
    comme : (prix_max - prix_min) / prix_median
    """

    def __init__(self, timeout: int = 10, logger=None):
        """
        Initialise le calculateur de volatilité.

        Args:
            timeout: Timeout pour les requêtes HTTP en secondes
            logger: Logger pour les messages (optionnel)
        """
        self.timeout = timeout
        self.logger = logger or setup_logging()
        self._symbol_categories: Dict[str, str] = {}

    def set_symbol_categories(self, symbol_categories: Dict[str, str]):
        """
        Définit le mapping des catégories de symboles.

        Args:
            symbol_categories: Dictionnaire {symbol: category}
        """
        self._symbol_categories = symbol_categories

    async def compute_batch(
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
        sem = asyncio.Semaphore(5)
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


def get_volatility_cache_key(symbol: str) -> str:
    """
    Génère une clé de cache pour la volatilité d'un symbole.

    Args:
        symbol: Symbole

    Returns:
        Clé de cache
    """
    return f"volatility_5m_{symbol}"

