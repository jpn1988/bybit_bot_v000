#!/usr/bin/env python3
"""
Calculateur de volatilité pour le bot Bybit.

Cette classe gère uniquement :
- Le calcul de la volatilité en batch et async
- Les opérations de calcul pures
- La gestion des clients pour les calculs
"""

import asyncio
import time
from typing import List, Dict, Optional, Tuple
from logging_setup import setup_logging
from bybit_client import BybitPublicClient
from volatility import compute_volatility_batch_async


class VolatilityCalculator:
    """
    Calculateur de volatilité pour le bot Bybit.
    
    Responsabilités :
    - Calcul de la volatilité en batch et async
    - Gestion des clients pour les calculs
    - Opérations de calcul pures
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
