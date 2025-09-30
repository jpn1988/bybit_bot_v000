#!/usr/bin/env python3
"""
Filtre de symboles pour le bot Bybit.

Cette classe gère uniquement :
- Le filtrage par funding, volume et temps avant funding
- Le filtrage par spread
- Les calculs de temps de funding
- Les utilitaires de filtrage
"""

import time
from typing import List, Tuple, Dict, Optional
from logging_setup import setup_logging


class SymbolFilter:
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
        self.logger = logger or setup_logging()
    
    def calculate_funding_time_remaining(self, next_funding_time) -> str:
        """
        Retourne "Xh Ym Zs" à partir d'un timestamp Bybit (ms) ou ISO.
        
        Args:
            next_funding_time: Timestamp du prochain funding
            
        Returns:
            str: Temps restant formaté ou "-" si invalide
        """
        if not next_funding_time:
            return "-"
        try:
            import datetime
            funding_dt = None
            if isinstance(next_funding_time, (int, float)):
                funding_dt = datetime.datetime.fromtimestamp(float(next_funding_time) / 1000, tz=datetime.timezone.utc)
            elif isinstance(next_funding_time, str):
                if next_funding_time.isdigit():
                    funding_dt = datetime.datetime.fromtimestamp(float(next_funding_time) / 1000, tz=datetime.timezone.utc)
                else:
                    funding_dt = datetime.datetime.fromisoformat(next_funding_time.replace('Z', '+00:00'))
                    if funding_dt.tzinfo is None:
                        funding_dt = funding_dt.replace(tzinfo=datetime.timezone.utc)
            if funding_dt is None:
                return "-"
            now = datetime.datetime.now(datetime.timezone.utc)
            delta = (funding_dt - now).total_seconds()
            if delta <= 0:
                return "-"
            total_seconds = int(delta)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            if minutes > 0:
                return f"{minutes}m {seconds}s"
            return f"{seconds}s"
        except Exception as e:
            self.logger.error(f"Erreur calcul temps funding formaté: {type(e).__name__}: {e}")
            return "-"
    
    def calculate_funding_minutes_remaining(self, next_funding_time) -> Optional[float]:
        """
        Retourne les minutes restantes avant le prochain funding (pour filtrage).
        
        Args:
            next_funding_time: Timestamp du prochain funding
            
        Returns:
            float: Minutes restantes ou None si invalide
        """
        if not next_funding_time:
            return None
        try:
            import datetime
            funding_dt = None
            if isinstance(next_funding_time, (int, float)):
                funding_dt = datetime.datetime.fromtimestamp(float(next_funding_time) / 1000, tz=datetime.timezone.utc)
            elif isinstance(next_funding_time, str):
                if next_funding_time.isdigit():
                    funding_dt = datetime.datetime.fromtimestamp(float(next_funding_time) / 1000, tz=datetime.timezone.utc)
                else:
                    funding_dt = datetime.datetime.fromisoformat(next_funding_time.replace('Z', '+00:00'))
                    if funding_dt.tzinfo is None:
                        funding_dt = funding_dt.replace(tzinfo=datetime.timezone.utc)
            if funding_dt is None:
                return None
            now = datetime.datetime.now(datetime.timezone.utc)
            delta_sec = (funding_dt - now).total_seconds()
            if delta_sec <= 0:
                return None
            return delta_sec / 60.0  # Convertir en minutes
        except Exception as e:
            self.logger.error(f"Erreur calcul minutes funding: {type(e).__name__}: {e}")
            return None
    
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
        symbols_data: List[Tuple[str, float, float, str]], 
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
            for symbol_data in symbols_data:
                symbol = symbol_data[0]
                category = category_of_symbol(symbol, symbol_categories)
                if category == "linear":
                    linear_symbols.append(symbol)
                elif category == "inverse":
                    inverse_symbols.append(symbol)
        
        return linear_symbols, inverse_symbols
    
    def build_funding_data_dict(
        self, 
        symbols_data: List[Tuple]
    ) -> Dict[str, Tuple]:
        """
        Construit le dictionnaire de données de funding à partir des symboles filtrés.
        
        Args:
            symbols_data: Liste des données de symboles filtrés
            
        Returns:
            Dict: Dictionnaire {symbol: (funding, volume, funding_time_remaining, spread_pct, volatility_pct)}
        """
        funding_data = {}
        
        if not symbols_data:
            return funding_data
        
        # Déterminer le format des données selon la longueur des tuples
        tuple_length = len(symbols_data[0])
        
        if tuple_length == 6:
            # Format: (symbol, funding, volume, funding_time_remaining, spread_pct, volatility_pct)
            for symbol, funding, volume, funding_time_remaining, spread_pct, volatility_pct in symbols_data:
                funding_data[symbol] = (funding, volume, funding_time_remaining, spread_pct, volatility_pct)
        elif tuple_length == 5:
            # Format: (symbol, funding, volume, funding_time_remaining, spread_pct)
            for symbol, funding, volume, funding_time_remaining, spread_pct in symbols_data:
                funding_data[symbol] = (funding, volume, funding_time_remaining, spread_pct, None)
        elif tuple_length == 4:
            # Format: (symbol, funding, volume, funding_time_remaining)
            for symbol, funding, volume, funding_time_remaining in symbols_data:
                funding_data[symbol] = (funding, volume, funding_time_remaining, 0.0, None)
        else:
            # Format: (symbol, funding, volume)
            for symbol, funding, volume in symbols_data:
                funding_data[symbol] = (funding, volume, "-", 0.0, None)
        
        return funding_data
    
    def check_candidate_filters(
        self, 
        symbol: str, 
        funding_map: Dict, 
        funding_min: Optional[float], 
        funding_max: Optional[float], 
        volume_min_millions: Optional[float],
        funding_time_max_minutes: Optional[int]
    ) -> bool:
        """
        Vérifie si un symbole est un candidat potentiel avec des seuils plus permissifs.
        
        Args:
            symbol: Symbole à vérifier
            funding_map: Données de funding
            funding_min: Funding minimum
            funding_max: Funding maximum
            volume_min_millions: Volume minimum en millions
            funding_time_max_minutes: Temps maximum avant funding
            
        Returns:
            bool: True si c'est un candidat potentiel
        """
        if symbol not in funding_map:
            return False
        
        data = funding_map[symbol]
        funding = data["funding"]
        volume = data["volume"]
        funding_abs = abs(funding)
        
        # Convertir volume en millions
        effective_volume_min = None
        if volume_min_millions is not None:
            effective_volume_min = volume_min_millions * 1_000_000
        
        # Vérifier si c'est un candidat potentiel avec des seuils plus permissifs
        is_candidate = False
        
        # Candidat pour funding_min (80% du seuil minimum)
        if funding_min is not None and funding_abs >= (funding_min * 0.8) and funding_abs < funding_min:
            if effective_volume_min is None or volume >= (effective_volume_min * 0.9):
                is_candidate = True
        
        # Candidat pour funding_max (100% du seuil maximum)
        elif funding_max is not None and funding_abs > funding_max and funding_abs <= (funding_max * 1.2):
            if effective_volume_min is None or volume >= (effective_volume_min * 0.9):
                is_candidate = True
        
        # Candidat pour volume (90% du seuil minimum)
        elif effective_volume_min is not None and volume >= (effective_volume_min * 0.9) and volume < effective_volume_min:
            if funding_min is None or funding_abs >= (funding_min * 0.8):
                is_candidate = True
        
        return is_candidate
    
    def check_realtime_filters(
        self, 
        symbol: str, 
        ticker_data: dict, 
        funding_min: Optional[float], 
        funding_max: Optional[float], 
        volume_min_millions: Optional[float]
    ) -> bool:
        """
        Vérifie si un symbole candidat passe maintenant les filtres en temps réel.
        
        Args:
            symbol: Symbole à vérifier
            ticker_data: Données du ticker reçues via WebSocket
            funding_min: Funding minimum
            funding_max: Funding maximum
            volume_min_millions: Volume minimum en millions
            
        Returns:
            bool: True si le symbole passe maintenant les filtres
        """
        # Récupérer les données du ticker
        funding_rate = ticker_data.get("fundingRate")
        volume24h = ticker_data.get("volume24h")
        
        if funding_rate is None:
            return False
        
        try:
            funding = float(funding_rate)
            funding_abs = abs(funding)
        except (ValueError, TypeError):
            return False
        
        # Convertir volume en millions
        effective_volume_min = None
        if volume_min_millions is not None:
            effective_volume_min = volume_min_millions * 1_000_000
        
        # Vérifier les filtres
        if funding_min is not None and funding_abs < funding_min:
            return False
        
        if funding_max is not None and funding_abs > funding_max:
            return False
        
        if volume24h is not None and effective_volume_min is not None:
            try:
                volume = float(volume24h)
                if volume < effective_volume_min:
                    return False
            except (ValueError, TypeError):
                return False
        
        return True
