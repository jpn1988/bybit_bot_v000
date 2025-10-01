#!/usr/bin/env python3
"""
Gestionnaire de volatilité dédié pour le bot Bybit.

Cette classe gère uniquement :
- Le calcul de la volatilité (batch + async)
- Le rafraîchissement périodique des données de volatilité
- Le stockage temporaire avec TTL (time-to-live)
"""

import time
import asyncio
import threading
from typing import List, Tuple, Dict, Optional, Callable
from logging_setup import setup_logging
from bybit_client import BybitPublicClient
from volatility import get_volatility_cache_key, is_cache_valid, compute_volatility_batch_async


class VolatilityTracker:
    """
    Gestionnaire de volatilité pour le bot Bybit.
    
    Responsabilités :
    - Calcul de la volatilité en batch et async
    - Cache avec TTL pour les données de volatilité
    - Rafraîchissement périodique automatique
    - Filtrage des symboles par volatilité
    """
    
    def __init__(self, testnet: bool = True, ttl_seconds: int = 120, max_cache_size: int = 1000, logger=None):
        """
        Initialise le gestionnaire de volatilité.
        
        Args:
            testnet (bool): Utiliser le testnet (True) ou le marché réel (False)
            ttl_seconds (int): Durée de vie du cache en secondes
            max_cache_size (int): Taille maximale du cache
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.ttl_seconds = ttl_seconds
        self.max_cache_size = max_cache_size
        self.logger = logger or setup_logging()
        
        # Cache de volatilité {cache_key: (timestamp, volatility_pct)}
        self.volatility_cache: Dict[str, Tuple[float, float]] = {}
        
        # Thread de rafraîchissement
        self._refresh_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Symboles à surveiller
        self._symbols_to_track: List[str] = []
        
        # Client pour les calculs
        self._client: Optional[BybitPublicClient] = None
        
        # Catégories des symboles
        self._symbol_categories: Dict[str, str] = {}
        
        # Callback pour obtenir la liste des symboles actifs
        self._get_active_symbols_callback: Optional[Callable[[], List[str]]] = None
    
    def set_symbol_categories(self, symbol_categories: Dict[str, str]):
        """
        Définit le mapping des catégories de symboles.
        
        Args:
            symbol_categories: Dictionnaire {symbol: category}
        """
        self._symbol_categories = symbol_categories
    
    def set_active_symbols_callback(self, callback: Callable[[], List[str]]):
        """
        Définit le callback pour obtenir la liste des symboles actifs.
        
        Args:
            callback: Fonction qui retourne la liste des symboles actifs
        """
        self._get_active_symbols_callback = callback
    
    def start_refresh_task(self):
        """Démarre la tâche de rafraîchissement automatique."""
        if self._refresh_thread and self._refresh_thread.is_alive():
            self.logger.info("ℹ️ Thread volatilité déjà actif")
            return
        
        self._running = True
        self._refresh_thread = threading.Thread(target=self._refresh_loop)
        self._refresh_thread.daemon = True
        self._refresh_thread.start()
        
        # Thread volatilité démarré
    
    def stop_refresh_task(self):
        """Arrête la tâche de rafraîchissement."""
        self._running = False
        if self._refresh_thread and self._refresh_thread.is_alive():
            try:
                self._refresh_thread.join(timeout=5)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur arrêt thread volatilité: {e}")
        
        # Thread volatilité arrêté
    
    def get_cached_volatility(self, symbol: str) -> Optional[float]:
        """
        Récupère la volatilité en cache pour un symbole.
        
        Args:
            symbol: Symbole à rechercher
            
        Returns:
            Volatilité en pourcentage ou None si absent/expiré
        """
        cache_key = get_volatility_cache_key(symbol)
        cached_data = self.volatility_cache.get(cache_key)
        
        if cached_data and is_cache_valid(cached_data[0], ttl_seconds=self.ttl_seconds):
            return cached_data[1]
        
        return None
    
    def set_cached_volatility(self, symbol: str, volatility_pct: float):
        """
        Met à jour le cache de volatilité pour un symbole.
        
        Args:
            symbol: Symbole
            volatility_pct: Volatilité en pourcentage
        """
        cache_key = get_volatility_cache_key(symbol)
        self.volatility_cache[cache_key] = (time.time(), volatility_pct)
        
        # Nettoyer le cache si nécessaire
        if len(self.volatility_cache) > self.max_cache_size:
            self._cleanup_cache()
    
    def clear_stale_cache(self, active_symbols: List[str]):
        """
        Nettoie le cache des symboles non actifs.
        
        Args:
            active_symbols: Liste des symboles actifs
        """
        try:
            active_set = set(active_symbols)
            stale_keys = []
            
            for cache_key in list(self.volatility_cache.keys()):
                # Extraire le symbole du cache_key (format: "volatility_5m_SYMBOL")
                symbol = cache_key.split("volatility_5m_")[-1]
                if symbol not in active_set:
                    stale_keys.append(cache_key)
            
            for key in stale_keys:
                self.volatility_cache.pop(key, None)
                
            if stale_keys:
                self.logger.debug(f"🧹 Cache volatilité nettoyé: {len(stale_keys)} entrées supprimées")
                
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur nettoyage cache volatilité: {e}")
    
    def _cleanup_cache(self):
        """Nettoie le cache en supprimant les entrées les plus anciennes."""
        try:
            if len(self.volatility_cache) <= self.max_cache_size:
                return
            
            # Trier par timestamp et garder les plus récents
            sorted_items = sorted(self.volatility_cache.items(), key=lambda x: x[1][0], reverse=True)
            items_to_keep = sorted_items[:self.max_cache_size]
            
            # Reconstruire le cache
            self.volatility_cache = dict(items_to_keep)
            
            removed_count = len(sorted_items) - len(items_to_keep)
            if removed_count > 0:
                self.logger.debug(f"🧹 Cache volatilité nettoyé: {removed_count} entrées supprimées")
                
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur nettoyage cache volatilité: {e}")
    
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
                self._client = BybitPublicClient(testnet=self.testnet, timeout=10)
            except Exception as e:
                self.logger.error(f"⚠️ Impossible d'initialiser le client pour la volatilité: {e}")
                return {symbol: None for symbol in symbols}
        
        try:
            return await compute_volatility_batch_async(
                self._client,
                symbols,
                timeout=10,
                symbol_categories=self._symbol_categories
            )
        except Exception as e:
            self.logger.error(f"⚠️ Erreur calcul volatilité batch: {e}")
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
        # Séparer les symboles en cache et ceux à calculer
        symbols_to_calculate = []
        cached_volatilities = {}
        
        for symbol, _, _, _, _ in symbols_data:
            cached_vol = self.get_cached_volatility(symbol)
            if cached_vol is not None:
                cached_volatilities[symbol] = cached_vol
            else:
                symbols_to_calculate.append(symbol)
        
        # Calculer la volatilité pour les symboles manquants
        if symbols_to_calculate:
            await self._calculate_missing_volatilities(symbols_to_calculate, cached_volatilities)
        
        return cached_volatilities
    
    async def _calculate_missing_volatilities(self, symbols_to_calculate: List[str], all_volatilities: Dict[str, Optional[float]]):
        """
        Calcule la volatilité pour les symboles manquants et met à jour le cache.
        
        Args:
            symbols_to_calculate: Liste des symboles à calculer
            all_volatilities: Dictionnaire des volatilités (modifié en place)
        """
        # Calcul volatilité async
        batch_volatilities = await self.compute_volatility_batch(symbols_to_calculate)
        
        # Mettre à jour le cache avec les nouveaux résultats
        for symbol, vol_pct in batch_volatilities.items():
            if vol_pct is not None:
                self.set_cached_volatility(symbol, vol_pct)
            all_volatilities[symbol] = vol_pct
    
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
            # Essayer d'utiliser l'event loop existant
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Si la boucle tourne, créer une tâche
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.filter_by_volatility_async(
                        symbols_data, volatility_min, volatility_max
                    ))
                    return future.result()
            else:
                # Si la boucle ne tourne pas, l'utiliser directement
                return loop.run_until_complete(self.filter_by_volatility_async(
                    symbols_data, volatility_min, volatility_max
                ))
        except RuntimeError:
            # Pas d'event loop, en créer un nouveau
            return asyncio.run(self.filter_by_volatility_async(
                symbols_data, volatility_min, volatility_max
            ))
    
    def _refresh_loop(self):
        """Boucle de rafraîchissement périodique du cache de volatilité."""
        refresh_interval = self._calculate_refresh_interval()
        
        while self._running:
            try:
                # Obtenir les symboles à rafraîchir
                symbols_to_refresh = self._get_symbols_to_refresh()
                
                if not symbols_to_refresh:
                    time.sleep(5)
                    continue
                
                # Effectuer le cycle de rafraîchissement
                self._perform_refresh_cycle(symbols_to_refresh)
                
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur refresh volatilité: {e}")
                time.sleep(5)
            
            # Attendre l'intervalle de rafraîchissement avec vérification d'interruption
            self._wait_for_next_cycle(refresh_interval)
    
    def _calculate_refresh_interval(self) -> int:
        """
        Calcule l'intervalle de rafraîchissement optimal.
        
        Returns:
            Intervalle en secondes (entre 30 et 60s)
        """
        return max(30, min(60, self.ttl_seconds - 10))
    
    def _get_symbols_to_refresh(self) -> List[str]:
        """
        Récupère la liste des symboles actifs à rafraîchir.
        
        Returns:
            Liste des symboles ou liste vide si erreur
        """
        if not self._get_active_symbols_callback:
            return []
        
        try:
            return self._get_active_symbols_callback()
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur callback symboles actifs: {e}")
            return []
    
    def _perform_refresh_cycle(self, symbols: List[str]):
        """
        Effectue un cycle complet de rafraîchissement de volatilité.
        
        Args:
            symbols: Liste des symboles à rafraîchir
        """
        # Calculer la volatilité pour tous les symboles
        results = self._run_async_volatility_batch(symbols)
        
        # Mettre à jour le cache avec les résultats
        now_ts = time.time()
        ok_count, fail_count = self._update_cache_with_results(results, now_ts)
        
        self.logger.info(f"✅ Refresh volatilité terminé: ok={ok_count} | fail={fail_count}")
        
        # Retry pour les symboles en échec
        failed_symbols = [s for s, v in results.items() if v is None]
        if failed_symbols:
            self._retry_failed_symbols(failed_symbols, now_ts)
        
        # Nettoyer le cache des symboles non suivis
        self.clear_stale_cache(symbols)
    
    def _run_async_volatility_batch(self, symbols: List[str]) -> Dict[str, Optional[float]]:
        """
        Exécute le calcul de volatilité en batch de manière synchrone.
        
        Args:
            symbols: Liste des symboles
            
        Returns:
            Dictionnaire {symbol: volatility_pct}
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Event loop en cours - utiliser un thread séparé
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, 
                        self.compute_volatility_batch(symbols)
                    )
                    return future.result()
            else:
                # Event loop disponible - l'utiliser directement
                return loop.run_until_complete(self.compute_volatility_batch(symbols))
        except RuntimeError:
            # Pas d'event loop - en créer un nouveau
            return asyncio.run(self.compute_volatility_batch(symbols))
    
    def _update_cache_with_results(self, results: Dict[str, Optional[float]], 
                                   timestamp: float) -> tuple[int, int]:
        """
        Met à jour le cache de volatilité avec les résultats.
        
        Args:
            results: Résultats du calcul de volatilité
            timestamp: Timestamp pour le cache
            
        Returns:
            Tuple (ok_count, fail_count)
        """
        ok_count = 0
        fail_count = 0
        
        for symbol, vol_pct in results.items():
            if vol_pct is not None:
                cache_key = get_volatility_cache_key(symbol)
                self.volatility_cache[cache_key] = (timestamp, vol_pct)
                ok_count += 1
            else:
                fail_count += 1
        
        return ok_count, fail_count
    
    def _retry_failed_symbols(self, failed_symbols: List[str], timestamp: float):
        """
        Effectue un retry pour les symboles en échec.
        
        Args:
            failed_symbols: Liste des symboles à retry
            timestamp: Timestamp pour le cache
        """
        self.logger.info(f"🔁 Retry volatilité pour {len(failed_symbols)} symboles…")
        time.sleep(5)
        
        # Retry du calcul
        retry_results = self._run_async_volatility_batch(failed_symbols)
        
        # Mettre à jour le cache avec les résultats du retry
        retry_ok = 0
        for symbol, vol_pct in retry_results.items():
            if vol_pct is not None:
                cache_key = get_volatility_cache_key(symbol)
                self.volatility_cache[cache_key] = (timestamp, vol_pct)
                retry_ok += 1
        
        self.logger.info(f"🔁 Retry volatilité terminé: récupérés={retry_ok}/{len(failed_symbols)}")
    
    def _wait_for_next_cycle(self, interval: int):
        """
        Attend l'intervalle spécifié avec vérification d'interruption.
        
        Args:
            interval: Intervalle en secondes
        """
        for _ in range(interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Retourne les statistiques du cache.
        
        Returns:
            Dictionnaire avec les stats du cache
        """
        now = time.time()
        total = len(self.volatility_cache)
        valid = sum(1 for timestamp, _ in self.volatility_cache.values() 
                   if is_cache_valid(timestamp, self.ttl_seconds))
        expired = total - valid
        
        return {
            "total": total,
            "valid": valid,
            "expired": expired
        }
    
    def is_running(self) -> bool:
        """
        Vérifie si le tracker est en cours d'exécution.
        
        Returns:
            True si le rafraîchissement est actif
        """
        return self._running and self._refresh_thread and self._refresh_thread.is_alive()
