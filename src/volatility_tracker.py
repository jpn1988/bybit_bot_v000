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
    
    def __init__(self, testnet: bool = True, ttl_seconds: int = 120, logger=None):
        """
        Initialise le gestionnaire de volatilité.
        
        Args:
            testnet (bool): Utiliser le testnet (True) ou le marché réel (False)
            ttl_seconds (int): Durée de vie du cache en secondes
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.ttl_seconds = ttl_seconds
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
        
        # Thread volatilité démarré (silencieux)
    
    def stop_refresh_task(self):
        """Arrête la tâche de rafraîchissement."""
        self._running = False
        if self._refresh_thread and self._refresh_thread.is_alive():
            try:
                self._refresh_thread.join(timeout=5)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur arrêt thread volatilité: {e}")
        
        # Thread volatilité arrêté (silencieux)
    
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
        filtered_symbols = []
        rejected_count = 0
        
        # Séparer les symboles en cache et ceux à calculer
        symbols_to_calculate = []
        cached_volatilities = {}
        
        for symbol, funding, volume, funding_time_remaining, spread_pct in symbols_data:
            cached_vol = self.get_cached_volatility(symbol)
            if cached_vol is not None:
                cached_volatilities[symbol] = cached_vol
            else:
                symbols_to_calculate.append(symbol)
        
        # Calculer la volatilité pour les symboles manquants
        if symbols_to_calculate:
            # Calcul volatilité async (silencieux)
            batch_volatilities = await self.compute_volatility_batch(symbols_to_calculate)
            
            # Mettre à jour le cache avec les nouveaux résultats
            for symbol, vol_pct in batch_volatilities.items():
                if vol_pct is not None:
                    self.set_cached_volatility(symbol, vol_pct)
                cached_volatilities[symbol] = vol_pct
        
        # Appliquer les filtres avec toutes les volatilités (cache + calculées)
        for symbol, funding, volume, funding_time_remaining, spread_pct in symbols_data:
            vol_pct = cached_volatilities.get(symbol)
            
            # Appliquer le filtre de volatilité seulement si des seuils sont définis
            if volatility_min is not None or volatility_max is not None:
                if vol_pct is not None:
                    # Vérifier les seuils de volatilité
                    rejected_reason = None
                    if volatility_min is not None and vol_pct < volatility_min:
                        rejected_reason = f"< seuil min {volatility_min:.2%}"
                    elif volatility_max is not None and vol_pct > volatility_max:
                        rejected_reason = f"> seuil max {volatility_max:.2%}"
                    
                    if rejected_reason:
                        rejected_count += 1
                        continue
                else:
                    # Symbole sans volatilité calculée - le rejeter si des filtres sont actifs
                    rejected_count += 1
                    continue
            
            # Ajouter le symbole avec sa volatilité
            filtered_symbols.append((symbol, funding, volume, funding_time_remaining, spread_pct, vol_pct))
        
        # Log des résultats
        kept_count = len(filtered_symbols)
        threshold_info = []
        if volatility_min is not None:
            threshold_info.append(f"min={volatility_min:.2%}")
        if volatility_max is not None:
            threshold_info.append(f"max={volatility_max:.2%}")
        threshold_str = " | ".join(threshold_info) if threshold_info else "aucun seuil"
        # Filtre volatilité (silencieux)
        
        return filtered_symbols
    
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
        return asyncio.run(self.filter_by_volatility_async(
            symbols_data, volatility_min, volatility_max
        ))
    
    def _refresh_loop(self):
        """Boucle de rafraîchissement périodique du cache de volatilité."""
        # Calculer l'intervalle de rafraîchissement
        refresh_interval = max(30, min(60, self.ttl_seconds - 10))
        
        # Volatilité: thread actif (silencieux)
        
        while self._running:
            try:
                # Obtenir la liste des symboles à rafraîchir
                symbols_to_refresh = []
                if self._get_active_symbols_callback:
                    try:
                        symbols_to_refresh = self._get_active_symbols_callback()
                    except Exception as e:
                        self.logger.warning(f"⚠️ Erreur callback symboles actifs: {e}")
                
                if not symbols_to_refresh:
                    # Rien à faire, patienter un court instant
                    time.sleep(5)
                    continue
                
                # Log de cycle
                # Refresh volatilité (silencieux)
                
                # Calculer la volatilité en batch
                results = asyncio.run(self.compute_volatility_batch(symbols_to_refresh))
                
                # Mettre à jour le cache
                now_ts = time.time()
                ok_count = 0
                fail_count = 0
                
                for sym, vol_pct in results.items():
                    if vol_pct is not None:
                        cache_key = get_volatility_cache_key(sym)
                        self.volatility_cache[cache_key] = (now_ts, vol_pct)
                        ok_count += 1
                    else:
                        fail_count += 1
                
                self.logger.info(f"✅ Refresh volatilité terminé: ok={ok_count} | fail={fail_count}")
                
                # Retry pour les symboles en échec
                failed = [s for s, v in results.items() if v is None]
                if failed:
                    self.logger.info(f"🔁 Retry volatilité pour {len(failed)} symboles…")
                    time.sleep(5)
                    
                    retry_results = asyncio.run(self.compute_volatility_batch(failed))
                    retry_ok = 0
                    
                    for sym, vol_pct in retry_results.items():
                        if vol_pct is not None:
                            cache_key = get_volatility_cache_key(sym)
                            self.volatility_cache[cache_key] = (now_ts, vol_pct)
                            retry_ok += 1
                    
                    self.logger.info(f"🔁 Retry volatilité terminé: récupérés={retry_ok}/{len(failed)}")
                
                # Nettoyer le cache des symboles non suivis
                self.clear_stale_cache(symbols_to_refresh)
                
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur refresh volatilité: {e}")
                # Backoff simple en cas d'erreur globale du cycle
                time.sleep(5)
            
            # Attendre l'intervalle de rafraîchissement
            for _ in range(refresh_interval):
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
