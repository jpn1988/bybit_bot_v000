#!/usr/bin/env python3
"""
Planificateur de volatilité pour le bot Bybit.

Cette classe gère uniquement :
- Le rafraîchissement périodique des données de volatilité
- La gestion des threads de rafraîchissement
- La coordination des cycles de rafraîchissement
"""

import time
import threading
from typing import List, Optional, Callable, Dict
from logging_setup import setup_logging
from volatility_calculator import VolatilityCalculator
from volatility_cache import VolatilityCache


class VolatilityScheduler:
    """
    Planificateur de volatilité pour le bot Bybit.
    
    Responsabilités :
    - Rafraîchissement périodique des données de volatilité
    - Gestion des threads de rafraîchissement
    - Coordination des cycles de rafraîchissement
    """
    
    def __init__(self, calculator: VolatilityCalculator, cache: VolatilityCache, logger=None):
        """
        Initialise le planificateur de volatilité.
        
        Args:
            calculator: Calculateur de volatilité
            cache: Cache de volatilité
            logger: Logger pour les messages (optionnel)
        """
        self.calculator = calculator
        self.cache = cache
        self.logger = logger or setup_logging()
        
        # Thread de rafraîchissement
        self._refresh_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Callback pour obtenir la liste des symboles actifs
        self._get_active_symbols_callback: Optional[Callable[[], List[str]]] = None
    
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
        return max(20, min(40, self.cache.ttl_seconds - 10))  # Intervalle plus court : 20-40s
    
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
        ok_count, fail_count = self.cache.update_cache_with_results(results, now_ts)
        
        self.logger.info(f"✅ Refresh volatilité terminé: ok={ok_count} | fail={fail_count}")
        
        # Retry pour les symboles en échec
        failed_symbols = [s for s, v in results.items() if v is None]
        if failed_symbols:
            self._retry_failed_symbols(failed_symbols, now_ts)
        
        # Nettoyer le cache des symboles non suivis
        self.cache.clear_stale_cache(symbols)
    
    def _run_async_volatility_batch(self, symbols: List[str]) -> Dict[str, Optional[float]]:
        """
        Exécute le calcul de volatilité en batch de manière synchrone.
        
        Args:
            symbols: Liste des symboles
            
        Returns:
            Dictionnaire {symbol: volatility_pct}
        """
        try:
            import asyncio
            import concurrent.futures
            
            # Créer un nouveau event loop dans un thread séparé pour éviter les conflits
            def run_in_new_loop():
                return asyncio.run(self.calculator.compute_volatility_batch(symbols))
            
            # Utiliser un ThreadPoolExecutor avec timeout pour éviter les blocages
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_new_loop)
                return future.result(timeout=30)  # Timeout de 30 secondes
                
        except concurrent.futures.TimeoutError:
            self.logger.warning(f"⚠️ Timeout calcul volatilité pour {len(symbols)} symboles")
            return {symbol: None for symbol in symbols}
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur calcul volatilité: {e}")
            return {symbol: None for symbol in symbols}
    
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
                self.cache.set_cached_volatility(symbol, vol_pct)
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
    
    def is_running(self) -> bool:
        """
        Vérifie si le planificateur est en cours d'exécution.
        
        Returns:
            True si le rafraîchissement est actif
        """
        return self._running and self._refresh_thread and self._refresh_thread.is_alive()
