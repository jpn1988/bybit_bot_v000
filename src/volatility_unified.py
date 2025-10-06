#!/usr/bin/env python3
"""
Module de volatilité unifié pour le bot Bybit.

Ce module consolide :
- Les fonctions de calcul de volatilité (de volatility.py)
- La classe VolatilityCalculator (de volatility_calculator.py)
- La gestion des clients et du filtrage

Calcule la volatilité basée sur la plage de prix (high-low) des 5 dernières bougies 1 minute.
"""

import time
import asyncio
import aiohttp
import concurrent.futures
from typing import Optional, Dict, List, Tuple
from collections import deque
from logging_setup import setup_logging
from bybit_client import BybitPublicClient
from instruments import category_of_symbol
from http_utils import get_rate_limiter


def get_async_rate_limiter():
    """Construit un rate limiter asynchrone à partir des variables d'environnement."""
    try:
        import os
        max_calls = int(os.getenv("PUBLIC_HTTP_MAX_CALLS_PER_SEC", "5"))
        window = float(os.getenv("PUBLIC_HTTP_WINDOW_SECONDS", "1"))
    except (ValueError, TypeError) as e:
        # Log de l'erreur de conversion pour debugging
        import logging
        logging.getLogger(__name__).warning(f"Erreur conversion variables d'environnement rate limiter: {e}")
        max_calls = 5
        window = 1.0
    
    # Rate limiter asynchrone simple inline
    class AsyncRateLimiter:
        def __init__(self, max_calls: int = 5, window_seconds: float = 1.0):
            self.max_calls = max_calls
            self.window_seconds = window_seconds
            self._timestamps = deque()
            self._lock = asyncio.Lock()
        
        async def acquire(self):
            """Attend de manière asynchrone si nécessaire pour respecter la limite."""
            while True:
                now = time.time()
                async with self._lock:
                    # Retirer les timestamps hors fenêtre
                    while self._timestamps and now - self._timestamps[0] > self.window_seconds:
                        self._timestamps.popleft()
                    if len(self._timestamps) < self.max_calls:
                        self._timestamps.append(now)
                        return
                    # Temps à attendre jusqu'à expiration du plus ancien
                    wait_time = self.window_seconds - (now - self._timestamps[0])
                if wait_time > 0:
                    await asyncio.sleep(min(wait_time, 0.05))
    
    return AsyncRateLimiter(max_calls=max_calls, window_seconds=window)


def get_volatility_cache_key(symbol: str) -> str:
    """
    Génère une clé de cache pour la volatilité d'un symbole.
    
    Args:
        symbol (str): Symbole
        
    Returns:
        str: Clé de cache
    """
    return f"volatility_5m_{symbol}"


def is_cache_valid(timestamp: float, ttl_seconds: int = 60) -> bool:
    """
    Vérifie si un cache est encore valide.
    
    Args:
        timestamp (float): Timestamp du cache
        ttl_seconds (int): Durée de vie en secondes
        
    Returns:
        bool: True si le cache est valide
    """
    return (time.time() - timestamp) < ttl_seconds


async def compute_volatility_batch_async(
    bybit_client, 
    symbols: List[str], 
    timeout: int = 10,
    symbol_categories: Dict[str, str] | None = None
) -> Dict[str, Optional[float]]:
    """
    Calcule la volatilité 5 minutes pour une liste de symboles en parallèle.
    OPTIMISATION: Utilise aiohttp et asyncio.gather() pour paralléliser les appels API.
    
    Args:
        bybit_client: Instance du client Bybit (pour récupérer l'URL de base)
        symbols (List[str]): Liste des symboles à analyser
        timeout (int): Timeout pour les requêtes HTTP en secondes
        
    Returns:
        Dict[str, Optional[float]]: Dictionnaire {symbol: volatility_pct} ou None si erreur
    """
    if not symbols:
        return {}
    
    # Récupérer l'URL de base du client
    base_url = bybit_client.public_base_url()
    
    # Limiter la concurrence globale pour éviter le rate limit (plus conservateur)
    sem = asyncio.Semaphore(5)
    async_rate_limiter = get_async_rate_limiter()

    async def limited_task(sym: str):
        # Respecter le rate limiter asynchrone avant chaque requête
        await async_rate_limiter.acquire()
        async with sem:
            return await _compute_single_volatility_async(session, base_url, sym, symbol_categories)

    # Créer une session aiohttp
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        # Créer les tâches async pour chaque symbole
        tasks = []
        for symbol in symbols:
            task = limited_task(symbol)
            tasks.append(task)
        
        # Exécuter toutes les tâches en parallèle
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Construire le dictionnaire de résultats
        volatility_results = {}
        for i, result in enumerate(results):
            symbol = symbols[i]
            if isinstance(result, Exception):
                # En cas d'erreur, mettre None et enrichir le contexte en log
                try:
                    # Ne pas importer le logger globalement pour éviter dépendances circulaires
                    import logging
                    logging.getLogger(__name__).warning(
                        (
                            f"Erreur async kline | endpoint=/v5/market/kline symbol={symbol} "
                            f"timeout={timeout}s error={result}"
                        )
                    )
                except (ImportError, AttributeError) as e:
                    # Erreur de logging - ne pas bloquer le flux
                    pass
                volatility_results[symbol] = None
            else:
                volatility_results[symbol] = result
        
        return volatility_results


async def _compute_single_volatility_async(
    session: aiohttp.ClientSession, 
    base_url: str, 
    symbol: str, 
    symbol_categories: Dict[str, str] | None = None
) -> Optional[float]:
    """
    Calcule la volatilité pour un seul symbole de manière asynchrone.
    Fonction helper pour la parallélisation.
    
    Args:
        session (aiohttp.ClientSession): Session HTTP asynchrone
        base_url (str): URL de base de l'API Bybit
        symbol (str): Symbole à analyser
        
    Returns:
        Optional[float]: Volatilité en pourcentage ou None si erreur
    """
    try:
        # Déterminer la catégorie via mapping officiel si disponible, sinon fallback heuristique
        category = category_of_symbol(symbol, symbol_categories)
        
        # Construire l'URL pour récupérer les bougies 1 minute
        url = f"{base_url}/v5/market/kline"
        params = {
            "category": category,
            "symbol": symbol,
            "interval": "1",  # 1 minute
            "limit": 6  # 6 bougies pour avoir 5 minutes + 1 de sécurité
        }
        
        # Faire la requête HTTP asynchrone
        async with session.get(url, params=params) as response:
            # Vérifier le statut HTTP
            if response.status >= 400:
                try:
                    import logging
                    logging.getLogger(__name__).warning(
                        (
                            f"Erreur HTTP kline GET {url} | category={category} symbol={symbol} "
                            f"interval={params['interval']} timeout={session.timeout.total} status={response.status}"
                        )
                    )
                except (ImportError, AttributeError) as e:
                    # Erreur de logging - ne pas bloquer le flux
                    pass
                return None
            
            data = await response.json()
            
            # Vérifier le retCode
            if data.get("retCode") != 0:
                try:
                    import logging
                    logging.getLogger(__name__).warning(
                        (
                            f"Erreur API kline GET {url} | category={category} symbol={symbol} "
                            f"interval={params['interval']} retCode={data.get('retCode')} retMsg=\"{data.get('retMsg','')}\""
                        )
                    )
                except (ImportError, AttributeError) as e:
                    # Erreur de logging - ne pas bloquer le flux
                    pass
                return None
            
            result = data.get("result", {})
            klines = result.get("list", [])
            
            # Vérifier qu'on a assez de données
            if len(klines) < 5:
                return None
            
            # Extraire les prix (high et low de chaque bougie)
            # Les bougies sont triées par timestamp décroissant (plus récent en premier)
            prices_high = []
            prices_low = []
            
            for kline in klines[:5]:  # Prendre les 5 plus récentes
                try:
                    high = float(kline[2])  # Index 2 = high
                    low = float(kline[3])   # Index 3 = low
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
            pmin = min(prices_low)   # Prix minimum sur la période
            pmid = (pmax + pmin) / 2  # Prix médian
            
            # Éviter la division par zéro
            if pmid <= 0:
                return None
            
            # Calculer la volatilité en pourcentage
            vol_pct = (pmax - pmin) / pmid
            
            return vol_pct
            
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError, KeyError, IndexError) as e:
        # Erreurs spécifiques : réseau, timeout, conversion, accès données
        import logging
        logging.getLogger(__name__).error(f"Erreur calcul volatilité pour {symbol}: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        # Erreur inattendue - log pour debugging
        import logging
        logging.getLogger(__name__).error(f"Erreur inattendue calcul volatilité pour {symbol}: {type(e).__name__}: {e}")
        return None


class VolatilityCalculator:
    """
    Calculateur de volatilité pour le bot Bybit - Version unifiée.
    
    Responsabilités :
    - Calcul de la volatilité en batch et async
    - Gestion des clients pour les calculs
    - Opérations de calcul pures et filtrage
    """
    
    def __init__(self, testnet: bool = True, timeout: int = 10, logger=None):
        """
        Initialise le calculateur de volatilité.
        
        Args:
            testnet (bool): Utiliser le testnet (True) ou le marché réel (False)
            timeout (int): Timeout pour les requêtes
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.timeout = timeout
        self.logger = logger or setup_logging()
        
        # Client pour les calculs
        self._client: Optional[BybitPublicClient] = None
        
        # Catégories des symboles
        self._symbol_categories: Dict[str, str] = {}
    
    def set_symbol_categories(self, symbol_categories: Dict[str, str]):
        """
        Définit le mapping des catégories de symboles.
        
        Args:
            symbol_categories: Dictionnaire {symbol: category}
        """
        self._symbol_categories = symbol_categories
    
    async def compute_volatility_batch(self, symbols: List[str]) -> Dict[str, Optional[float]]:
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
                self._client = BybitPublicClient(testnet=self.testnet, timeout=self.timeout)
            except Exception as e:
                self.logger.error(f"⚠️ Impossible d'initialiser le client pour la volatilité: {e}")
                return {symbol: None for symbol in symbols}
        
        try:
            return await compute_volatility_batch_async(
                self._client,
                symbols,
                timeout=self.timeout,
                symbol_categories=self._symbol_categories
            )
        except Exception as e:
            self.logger.error(f"⚠️ Erreur calcul volatilité batch: {e}")
            return {symbol: None for symbol in symbols}
    
    def compute_volatility_batch_sync(self, symbols: List[str]) -> Dict[str, Optional[float]]:
        """
        Version synchrone du calcul de volatilité en batch.
        
        Args:
            symbols: Liste des symboles
            
        Returns:
            Dictionnaire {symbol: volatility_pct}
        """
        try:
            # Créer un nouveau event loop dans un thread séparé pour éviter les conflits
            def run_in_new_loop():
                return asyncio.run(self.compute_volatility_batch(symbols))
            
            # Utiliser un ThreadPoolExecutor avec timeout pour éviter les blocages
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_new_loop)
                return future.result(timeout=30)  # Timeout de 30 secondes
                
        except concurrent.futures.TimeoutError:
            self.logger.warning(f"⚠️ Timeout calcul volatilité synchrone pour {len(symbols)} symboles")
            return {symbol: None for symbol in symbols}
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur calcul volatilité synchrone: {e}")
            return {symbol: None for symbol in symbols}
    
    async def filter_by_volatility_async(
        self,
        symbols_data: List[Tuple[str, float, float, str, float]],
        volatility_min: Optional[float],
        volatility_max: Optional[float]
    ) -> List[Tuple[str, float, float, str, float, Optional[float]]]:
        """
        Filtre les symboles par volatilité avec calcul automatique.
        
        Args:
            symbols_data: Liste des (symbol, funding, volume, funding_time_remaining, spread_pct)
            volatility_min: Volatilité minimum ou None
            volatility_max: Volatilité maximum ou None
            
        Returns:
            Liste des (symbol, funding, volume, funding_time_remaining, spread_pct, volatility_pct)
        """
        # Préparer les volatilités (cache + calcul)
        all_volatilities = await self._prepare_volatility_data(symbols_data)
        
        # Appliquer les filtres de volatilité
        filtered_symbols = self._apply_volatility_filters(
            symbols_data, all_volatilities, volatility_min, volatility_max
        )
        
        return filtered_symbols
    
    async def _prepare_volatility_data(self, symbols_data: List[Tuple[str, float, float, str, float]]) -> Dict[str, Optional[float]]:
        """
        Prépare les données de volatilité en utilisant le cache et les calculs.
        
        Args:
            symbols_data: Liste des données de symboles
            
        Returns:
            Dictionnaire {symbol: volatility_pct}
        """
        # Pour cette version simplifiée, on calcule directement
        # Dans la version complète, on utiliserait le cache
        symbols_to_calculate = [symbol for symbol, _, _, _, _ in symbols_data]
        
        # Calculer la volatilité pour tous les symboles
        return await self.compute_volatility_batch(symbols_to_calculate)
    
    def _apply_volatility_filters(
        self, 
        symbols_data: List[Tuple[str, float, float, str, float]], 
        all_volatilities: Dict[str, Optional[float]], 
        volatility_min: Optional[float], 
        volatility_max: Optional[float]
    ) -> List[Tuple[str, float, float, str, float, Optional[float]]]:
        """
        Applique les filtres de volatilité aux symboles.
        
        Args:
            symbols_data: Liste des données de symboles
            all_volatilities: Dictionnaire des volatilités
            volatility_min: Seuil minimum
            volatility_max: Seuil maximum
            
        Returns:
            Liste filtrée des symboles avec volatilité
        """
        filtered_symbols = []
        rejected_count = 0
        
        for symbol, funding, volume, funding_time_remaining, spread_pct in symbols_data:
            vol_pct = all_volatilities.get(symbol)
            
            # Vérifier si le symbole passe les filtres
            if self._should_reject_symbol(vol_pct, volatility_min, volatility_max):
                rejected_count += 1
                continue
            
            # Ajouter le symbole avec sa volatilité
            filtered_symbols.append((symbol, funding, volume, funding_time_remaining, spread_pct, vol_pct))
        
        return filtered_symbols
    
    def _should_reject_symbol(self, vol_pct: Optional[float], volatility_min: Optional[float], volatility_max: Optional[float]) -> bool:
        """
        Détermine si un symbole doit être rejeté selon les critères de volatilité.
        
        Args:
            vol_pct: Volatilité du symbole
            volatility_min: Seuil minimum
            volatility_max: Seuil maximum
            
        Returns:
            True si le symbole doit être rejeté
        """
        # Pas de filtres actifs - accepter tous les symboles
        if volatility_min is None and volatility_max is None:
            return False
        
        # Symbole sans volatilité calculée - le rejeter si des filtres sont actifs
        if vol_pct is None:
            return True
        
        # Vérifier les seuils de volatilité
        if volatility_min is not None and vol_pct < volatility_min:
            return True
        
        if volatility_max is not None and vol_pct > volatility_max:
            return True
        
        return False
    
    def filter_by_volatility(
        self,
        symbols_data: List[Tuple[str, float, float, str, float]],
        volatility_min: Optional[float],
        volatility_max: Optional[float]
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
            # Créer un nouveau event loop dans un thread séparé pour éviter les conflits
            def run_in_new_loop():
                return asyncio.run(self.filter_by_volatility_async(
                    symbols_data, volatility_min, volatility_max
                ))
            
            # Utiliser un ThreadPoolExecutor avec timeout pour éviter les blocages
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_new_loop)
                return future.result(timeout=30)  # Timeout de 30 secondes
                
        except concurrent.futures.TimeoutError:
            self.logger.warning(f"⚠️ Timeout filtrage volatilité pour {len(symbols_data)} symboles")
            return []
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur filtrage volatilité: {e}")
            return []
