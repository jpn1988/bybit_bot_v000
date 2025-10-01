#!/usr/bin/env python3
"""
Implémentation concrète du filtre de symboles pour le bot Bybit.

Cette classe implémente l'interface BaseFilter pour le filtrage par funding,
volume et temps avant funding.
"""

import time
from typing import List, Tuple, Dict, Optional, Any
from logging_setup import setup_logging
from .base_filter import BaseFilter


class SymbolFilter(BaseFilter):
    """
    Filtre de symboles pour le bot Bybit.
    
    Responsabilités :
    - Filtrage par funding, volume et fenêtre temporelle
    - Filtrage par spread
    - Calculs de temps de funding
    - Tri et sélection des symboles
    """
    
    def __init__(self, logger=None):
        """
        Initialise le filtre de symboles.
        
        Args:
            logger: Logger pour les messages (optionnel)
        """
        super().__init__(logger)
    
    def get_name(self) -> str:
        """Retourne le nom du filtre."""
        return "symbol_filter"
    
    def get_description(self) -> str:
        """Retourne la description du filtre."""
        return "Filtre par funding, volume et temps avant funding"
    
    def apply(self, symbols_data: List[Any], config: Dict[str, Any]) -> List[Any]:
        """
        Applique le filtre de funding aux données de symboles.
        
        Args:
            symbols_data: Liste contenant (perp_data, funding_map, config_params)
            config: Configuration du filtre (non utilisée ici, les paramètres sont dans symbols_data)
            
        Returns:
            Liste des symboles filtrés
        """
        if len(symbols_data) < 3:
            raise ValueError("symbols_data doit contenir (perp_data, funding_map, config_params)")
        
        perp_data, funding_map, config_params = symbols_data
        
        # Extraire les paramètres de configuration
        funding_min = config_params.get("funding_min")
        funding_max = config_params.get("funding_max")
        volume_min_millions = config_params.get("volume_min_millions")
        limite = config_params.get("limite")
        funding_time_min_minutes = config_params.get("funding_time_min_minutes")
        funding_time_max_minutes = config_params.get("funding_time_max_minutes")
        
        # Appliquer le filtre de funding
        filtered_symbols = self.filter_by_funding(
            perp_data,
            funding_map,
            funding_min,
            funding_max,
            volume_min_millions,
            limite,
            funding_time_min_minutes=funding_time_min_minutes,
            funding_time_max_minutes=funding_time_max_minutes,
        )
        
        return filtered_symbols
    
    def filter_by_funding(
        self, 
        perp_data: Dict, 
        funding_map: Dict, 
        funding_min: Optional[float], 
        funding_max: Optional[float], 
        volume_min_millions: Optional[float], 
        limite: Optional[int], 
        funding_time_min_minutes: Optional[int] = None, 
        funding_time_max_minutes: Optional[int] = None
    ) -> List[Tuple[str, float, float, str]]:
        """
        Filtre les symboles par funding, volume et fenêtre temporelle avant funding.
        
        Args:
            perp_data: Données des perpétuels (linear, inverse, total)
            funding_map: Dictionnaire des funding rates, volumes et temps de funding
            funding_min: Funding minimum en valeur absolue
            funding_max: Funding maximum en valeur absolue
            volume_min_millions: Volume minimum en millions
            limite: Limite du nombre d'éléments
            funding_time_min_minutes: Temps minimum en minutes avant prochain funding
            funding_time_max_minutes: Temps maximum en minutes avant prochain funding
            
        Returns:
            Liste des (symbol, funding, volume, funding_time_remaining) triés
        """
        # Récupérer tous les symboles perpétuels
        all_symbols = list(set(perp_data["linear"] + perp_data["inverse"]))
        
        # Déterminer le volume minimum à utiliser
        effective_volume_min = None
        if volume_min_millions is not None:
            effective_volume_min = volume_min_millions * 1_000_000  # Convertir en valeur brute
        
        # Filtrer par funding, volume et fenêtre temporelle
        filtered_symbols = []
        for symbol in all_symbols:
            if symbol in funding_map:
                data = funding_map[symbol]
                funding = data["funding"]
                volume = data["volume"]
                next_funding_time = data.get("next_funding_time")
                
                # Appliquer les bornes funding/volume (utiliser valeur absolue pour funding)
                if funding_min is not None and abs(funding) < funding_min:
                    continue
                if funding_max is not None and abs(funding) > funding_max:
                    continue
                if effective_volume_min is not None and volume < effective_volume_min:
                    continue
                
                # Appliquer le filtre temporel si demandé
                if funding_time_min_minutes is not None or funding_time_max_minutes is not None:
                    # Utiliser la fonction centralisée pour calculer les minutes restantes
                    minutes_remaining = self.calculate_funding_minutes_remaining(next_funding_time)
                    
                    # Si pas de temps valide alors qu'on filtre, rejeter
                    if minutes_remaining is None:
                        continue
                    if (funding_time_min_minutes is not None and 
                        minutes_remaining < float(funding_time_min_minutes)):
                        continue
                    if (funding_time_max_minutes is not None and 
                        minutes_remaining > float(funding_time_max_minutes)):
                        continue
                
                # Calculer le temps restant avant le prochain funding (formaté)
                funding_time_remaining = self.calculate_funding_time_remaining(next_funding_time)
                
                filtered_symbols.append((symbol, funding, volume, funding_time_remaining))
        
        # Trier par |funding| décroissant
        filtered_symbols.sort(key=lambda x: abs(x[1]), reverse=True)
        
        # Appliquer la limite
        if limite is not None:
            filtered_symbols = filtered_symbols[:limite]
        
        return filtered_symbols
    
    def filter_by_spread(
        self, 
        symbols_data: List[Tuple], 
        spread_data: Dict[str, float], 
        spread_max: Optional[float]
    ) -> List[Tuple[str, float, float, str, float]]:
        """
        Filtre les symboles par spread maximum.
        
        Args:
            symbols_data: Liste des (symbol, funding, volume, funding_time_remaining)
            spread_data: Dictionnaire des spreads {symbol: spread_pct}
            spread_max: Spread maximum autorisé
            
        Returns:
            Liste des (symbol, funding, volume, funding_time_remaining, spread_pct) filtrés
        """
        if spread_max is None:
            # Pas de filtre de spread, ajouter 0.0 comme spread par défaut
            return [(symbol, funding, volume, funding_time_remaining, 0.0) 
                    for symbol, funding, volume, funding_time_remaining in symbols_data]
        
        filtered_symbols = []
        for symbol, funding, volume, funding_time_remaining in symbols_data:
            if symbol in spread_data:
                spread_pct = spread_data[symbol]
                if spread_pct <= spread_max:
                    filtered_symbols.append((symbol, funding, volume, funding_time_remaining, spread_pct))
        
        return filtered_symbols
    
    def calculate_funding_time_remaining(self, next_funding_time) -> str:
        """
        Retourne "Xh Ym Zs" à partir d'un timestamp Bybit (ms) ou ISO.
        
        Args:
            next_funding_time: Timestamp du prochain funding (ms ou ISO string)
            
        Returns:
            str: Temps restant formaté ou "-" si invalide
        """
        if not next_funding_time:
            return "-"
        
        try:
            # Gérer les deux formats : timestamp ms ou ISO string
            if isinstance(next_funding_time, str):
                if next_funding_time.isdigit():
                    # Timestamp en ms
                    target_timestamp = int(next_funding_time) / 1000
                else:
                    # ISO string
                    from datetime import datetime
                    dt = datetime.fromisoformat(next_funding_time.replace('Z', '+00:00'))
                    target_timestamp = dt.timestamp()
            else:
                # Déjà un timestamp
                target_timestamp = float(next_funding_time) / 1000 if next_funding_time > 1e10 else float(next_funding_time)
            
            current_timestamp = time.time()
            remaining_seconds = target_timestamp - current_timestamp
            
            if remaining_seconds <= 0:
                return "0s"
            
            hours = int(remaining_seconds // 3600)
            minutes = int((remaining_seconds % 3600) // 60)
            seconds = int(remaining_seconds % 60)
            
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
                
        except (ValueError, TypeError, OverflowError) as e:
            self.logger.warning(f"⚠️ Erreur calcul temps funding: {e}")
            return "-"
    
    def calculate_funding_minutes_remaining(self, next_funding_time) -> Optional[float]:
        """
        Calcule les minutes restantes avant le prochain funding.
        
        Args:
            next_funding_time: Timestamp du prochain funding
            
        Returns:
            float: Minutes restantes ou None si erreur
        """
        if not next_funding_time:
            return None
        
        try:
            # Gérer les deux formats : timestamp ms ou ISO string
            if isinstance(next_funding_time, str):
                if next_funding_time.isdigit():
                    # Timestamp en ms
                    target_timestamp = int(next_funding_time) / 1000
                else:
                    # ISO string
                    from datetime import datetime
                    dt = datetime.fromisoformat(next_funding_time.replace('Z', '+00:00'))
                    target_timestamp = dt.timestamp()
            else:
                # Déjà un timestamp
                target_timestamp = float(next_funding_time) / 1000 if next_funding_time > 1e10 else float(next_funding_time)
            
            current_timestamp = time.time()
            remaining_seconds = target_timestamp - current_timestamp
            remaining_minutes = remaining_seconds / 60
            
            return remaining_minutes if remaining_minutes > 0 else 0
            
        except (ValueError, TypeError, OverflowError):
            return None
    
    def separate_symbols_by_category(
        self, 
        symbols_data: List[Tuple], 
        symbol_categories: Dict[str, str]
    ) -> Tuple[List[str], List[str]]:
        """
        Sépare les symboles par catégorie (linear/inverse).
        
        Args:
            symbols_data: Liste des données de symboles
            symbol_categories: Mapping des catégories de symboles
            
        Returns:
            Tuple[linear_symbols, inverse_symbols]
        """
        from instruments import category_of_symbol
        
        linear_symbols = []
        inverse_symbols = []
        
        # Déterminer la structure des données selon la longueur des tuples
        if symbols_data and len(symbols_data[0]) >= 4:
            # Format: (symbol, funding, volume, funding_time_remaining, ...)
            symbols = [item[0] for item in symbols_data]
        else:
            # Format simple: [symbol, ...]
            symbols = symbols_data if isinstance(symbols_data[0], str) else [item[0] for item in symbols_data]
        
        for symbol in symbols:
            category = category_of_symbol(symbol, symbol_categories)
            if category == "linear":
                linear_symbols.append(symbol)
            elif category == "inverse":
                inverse_symbols.append(symbol)
        
        return linear_symbols, inverse_symbols

