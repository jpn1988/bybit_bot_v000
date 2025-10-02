#!/usr/bin/env python3
"""
Gestionnaire d'affichage pour le bot Bybit.

Cette classe gère uniquement :
- L'affichage des données de prix en temps réel
- Le formatage des données pour l'affichage
- La gestion de la boucle d'affichage
- Le calcul des largeurs de colonnes
"""

import time
import threading
from typing import Dict, List, Optional, Any
from logging_setup import setup_logging
from data_manager import DataManager


class DisplayManager:
    """
    Gestionnaire d'affichage pour le bot Bybit.
    
    Responsabilités :
    - Affichage des données de prix en temps réel
    - Formatage des données pour l'affichage
    - Gestion de la boucle d'affichage périodique
    - Calcul des largeurs de colonnes dynamiques
    """
    
    def __init__(self, data_manager: DataManager, logger=None):
        """
        Initialise le gestionnaire d'affichage.
        
        Args:
            data_manager: Gestionnaire de données
            logger: Logger pour les messages (optionnel)
        """
        self.data_manager = data_manager
        self.logger = logger or setup_logging()
        
        # Configuration d'affichage
        self.display_interval_seconds = 10
        self.price_ttl_sec = 120
        
        # État d'affichage
        self._first_display = True
        self._display_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Callback pour la volatilité
        self._volatility_callback: Optional[callable] = None
    
    def set_volatility_callback(self, callback: callable):
        """
        Définit le callback pour récupérer la volatilité.
        
        Args:
            callback: Fonction qui retourne la volatilité pour un symbole
        """
        self._volatility_callback = callback
    
    def set_display_interval(self, interval_seconds: int):
        """
        Définit l'intervalle d'affichage.
        
        Args:
            interval_seconds: Intervalle en secondes
        """
        self.display_interval_seconds = interval_seconds
    
    def set_price_ttl(self, ttl_seconds: int):
        """
        Définit le TTL des prix.
        
        Args:
            ttl_seconds: TTL en secondes
        """
        self.price_ttl_sec = ttl_seconds
    
    def start_display_loop(self):
        """
        Démarre la boucle d'affichage.
        """
        if self._display_thread and self._display_thread.is_alive():
            self.logger.warning("⚠️ DisplayManager déjà en cours d'exécution")
            return
        
        self._running = True
        self._display_thread = threading.Thread(target=self._display_loop)
        self._display_thread.daemon = True
        self._display_thread.start()
        
        self.logger.info("📊 Boucle d'affichage démarrée")
    
    def stop_display_loop(self):
        """
        Arrête la boucle d'affichage.
        """
        self._running = False
        if self._display_thread and self._display_thread.is_alive():
            try:
                self._display_thread.join(timeout=2)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur arrêt thread affichage: {e}")
        
        self.logger.info("📊 Boucle d'affichage arrêtée")
    
    def _display_loop(self):
        """
        Boucle d'affichage avec intervalle configurable.
        """
        while self._running:
            # Vérifier immédiatement si on doit s'arrêter
            if not self._running:
                break
                
            self._print_price_table()
            
            # Attendre selon l'intervalle configuré
            steps = int(self.display_interval_seconds * 10)  # 10 * 0.1s = interval_seconds
            for _ in range(steps):
                if not self._running:
                    break
                time.sleep(0.1)
        
        # Boucle d'affichage arrêtée
    
    def _print_price_table(self):
        """
        Affiche le tableau des prix aligné avec funding, volume en millions, 
        spread et volatilité.
        """
        # Si aucune opportunité n'est trouvée, retourner
        funding_data = self.data_manager.get_all_funding_data()
        if not funding_data:
            if self._first_display:
                self._first_display = False
            return
        
        # Calculer les largeurs de colonnes
        col_widths = self._calculate_column_widths(funding_data)
        
        # Afficher l'en-tête
        self._print_table_header(col_widths)
        
        # Afficher les données
        for symbol in funding_data.keys():
            row_data = self._prepare_row_data(symbol)
            line = self._format_table_row(symbol, row_data, col_widths)
            print(line)
        
        print()  # Ligne vide après le tableau
    
    def _calculate_column_widths(self, funding_data: Dict) -> Dict[str, int]:
        """
        Calcule les largeurs des colonnes du tableau.
        
        Args:
            funding_data: Données de funding
            
        Returns:
            Dictionnaire des largeurs de colonnes
        """
        all_symbols = list(funding_data.keys())
        max_symbol_len = max(len("Symbole"), max(len(s) for s in all_symbols)) if all_symbols else len("Symbole")
        
        return {
            "symbol": max(8, max_symbol_len),
            "funding": 12,
            "volume": 10,
            "spread": 10,
            "volatility": 12,
            "funding_time": 15
        }
    
    def _print_table_header(self, col_widths: Dict[str, int]):
        """
        Affiche l'en-tête du tableau.
        
        Args:
            col_widths: Largeurs des colonnes
        """
        w = col_widths
        header = (
            f"{'Symbole':<{w['symbol']}} | {'Funding %':>{w['funding']}} | "
            f"{'Volume (M)':>{w['volume']}} | {'Spread %':>{w['spread']}} | "
            f"{'Volatilité %':>{w['volatility']}} | "
            f"{'Funding T':>{w['funding_time']}}"
        )
        sep = (
            f"{'-'*w['symbol']}-+-{'-'*w['funding']}-+-{'-'*w['volume']}-+-"
            f"{'-'*w['spread']}-+-{'-'*w['volatility']}-+-"
            f"{'-'*w['funding_time']}"
        )
        print("\n" + header)
        print(sep)
    
    def _prepare_row_data(self, symbol: str) -> Dict[str, Any]:
        """
        Prépare les données d'une ligne avec fallback entre temps réel et REST.
        
        Args:
            symbol: Symbole à préparer
            
        Returns:
            Dict avec les clés: funding, volume, spread_pct, volatility_pct, funding_time
        """
        funding_data = self.data_manager.get_funding_data(symbol)
        realtime_info = self.data_manager.get_realtime_data(symbol)
        
        # Valeurs initiales (REST) comme fallbacks
        try:
            if funding_data and len(funding_data) >= 4:
                original_funding = funding_data[0]
                original_volume = funding_data[1]
                original_funding_time = funding_data[2]
                original_spread = funding_data[3]
            else:
                original_funding = None
                original_volume = None
                original_funding_time = "-"
                original_spread = None
        except Exception:
            original_funding = None
            original_volume = None
            original_funding_time = "-"
            original_spread = None
        
        # Récupérer les données avec priorité temps réel
        funding = self._get_funding_value(realtime_info, original_funding)
        volume = self._get_volume_value(realtime_info, original_volume)
        spread_pct = self._get_spread_value(realtime_info, original_spread)
        volatility_pct = self._get_volatility_value(symbol)
        funding_time = self._get_funding_time_value(symbol, realtime_info)
        
        return {
            "funding": funding,
            "volume": volume,
            "spread_pct": spread_pct,
            "volatility_pct": volatility_pct,
            "funding_time": funding_time
        }
    
    def _get_funding_value(self, realtime_info: Optional[Dict], original: Optional[float]) -> Optional[float]:
        """
        Récupère la valeur de funding avec fallback.
        
        Args:
            realtime_info: Données temps réel
            original: Valeur originale (REST)
            
        Returns:
            Valeur de funding ou None
        """
        if not realtime_info:
            return original
        
        funding_rate = realtime_info.get('funding_rate')
        if funding_rate is not None:
            return float(funding_rate)
        return original
    
    def _get_volume_value(self, realtime_info: Optional[Dict], original: Optional[float]) -> Optional[float]:
        """
        Récupère la valeur de volume avec fallback.
        
        Args:
            realtime_info: Données temps réel
            original: Valeur originale (REST)
            
        Returns:
            Valeur de volume ou None
        """
        if not realtime_info:
            return original
        
        volume24h = realtime_info.get('volume24h')
        if volume24h is not None:
            return float(volume24h)
        return original
    
    def _get_spread_value(self, realtime_info: Optional[Dict], original: Optional[float]) -> Optional[float]:
        """
        Récupère la valeur de spread avec fallback.
        
        Args:
            realtime_info: Données temps réel
            original: Valeur originale (REST)
            
        Returns:
            Valeur de spread ou None
        """
        if not realtime_info:
            return original
        
        # Calculer le spread en temps réel si on a bid/ask
        bid1_price = realtime_info.get('bid1_price')
        ask1_price = realtime_info.get('ask1_price')
        
        if bid1_price and ask1_price:
            try:
                bid = float(bid1_price)
                ask = float(ask1_price)
                if bid > 0 and ask > 0:
                    mid = (ask + bid) / 2
                    if mid > 0:
                        return (ask - bid) / mid
            except (ValueError, TypeError):
                pass
        
        return original
    
    def _get_volatility_value(self, symbol: str) -> Optional[float]:
        """
        Récupère la valeur de volatilité.
        
        Args:
            symbol: Symbole à récupérer
            
        Returns:
            Valeur de volatilité ou None
        """
        if self._volatility_callback:
            try:
                return self._volatility_callback(symbol)
            except Exception:
                pass
        return None
    
    def _get_funding_time_value(self, symbol: str, realtime_info: Optional[Dict]) -> str:
        """
        Récupère la valeur de temps de funding.
        
        Args:
            symbol: Symbole à récupérer
            realtime_info: Données temps réel
            
        Returns:
            Temps de funding formaté ou "-"
        """
        # Priorité aux données temps réel
        if realtime_info and realtime_info.get('next_funding_time'):
            return self._calculate_funding_time_remaining(realtime_info['next_funding_time'])
        
        # Fallback aux données originales
        original_data = self.data_manager.get_original_funding_data(symbol)
        if original_data:
            return self._calculate_funding_time_remaining(original_data)
        
        return "-"
    
    def _calculate_funding_time_remaining(self, next_funding_time) -> str:
        """
        Calcule le temps restant avant le funding.
        
        Args:
            next_funding_time: Timestamp du prochain funding
            
        Returns:
            Temps restant formaté ou "-"
        """
        try:
            # Convertir le timestamp en secondes si nécessaire
            if isinstance(next_funding_time, str):
                # Format ISO ou timestamp
                if 'T' in next_funding_time:
                    # Format ISO
                    from datetime import datetime
                    dt = datetime.fromisoformat(next_funding_time.replace('Z', '+00:00'))
                    funding_ts = dt.timestamp()
                else:
                    # Timestamp en millisecondes
                    funding_ts = float(next_funding_time) / 1000
            else:
                # Déjà un timestamp
                funding_ts = float(next_funding_time)
            
            # Calculer le temps restant
            now_ts = time.time()
            remaining_seconds = funding_ts - now_ts
            
            if remaining_seconds <= 0:
                return "0s"
            
            # Formater en heures, minutes, secondes
            hours = int(remaining_seconds // 3600)
            minutes = int((remaining_seconds % 3600) // 60)
            seconds = int(remaining_seconds % 60)
            
            if hours > 0:
                return f"{hours}h {minutes}m"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
                
        except Exception:
            return "-"
    
    def _format_table_row(self, symbol: str, row_data: Dict[str, Any], col_widths: Dict[str, int]) -> str:
        """
        Formate une ligne du tableau.
        
        Args:
            symbol: Symbole
            row_data: Données de la ligne
            col_widths: Largeurs des colonnes
            
        Returns:
            Ligne formatée
        """
        w = col_widths
        
        # Formater chaque colonne
        funding_str = self._format_funding(row_data["funding"], w["funding"])
        volume_str = self._format_volume(row_data["volume"])
        spread_str = self._format_spread(row_data["spread_pct"])
        volatility_str = self._format_volatility(row_data["volatility_pct"])
        funding_time_str = row_data["funding_time"]
        
        return (
            f"{symbol:<{w['symbol']}} | {funding_str:>{w['funding']}} | "
            f"{volume_str:>{w['volume']}} | {spread_str:>{w['spread']}} | "
            f"{volatility_str:>{w['volatility']}} | "
            f"{funding_time_str:>{w['funding_time']}}"
        )
    
    def _format_funding(self, funding: Optional[float], width: int) -> str:
        """
        Formate la valeur de funding.
        
        Args:
            funding: Valeur de funding
            width: Largeur de la colonne
            
        Returns:
            Valeur formatée
        """
        if funding is not None:
            funding_pct = funding * 100.0
            return f"{funding_pct:+{width-1}.4f}%"
        return "null"
    
    def _format_volume(self, volume: Optional[float]) -> str:
        """
        Formate la valeur de volume en millions.
        
        Args:
            volume: Valeur de volume
            
        Returns:
            Valeur formatée
        """
        if volume is not None and volume > 0:
            volume_millions = volume / 1_000_000
            return f"{volume_millions:,.1f}"
        return "null"
    
    def _format_spread(self, spread_pct: Optional[float]) -> str:
        """
        Formate la valeur de spread.
        
        Args:
            spread_pct: Valeur de spread en pourcentage
            
        Returns:
            Valeur formatée
        """
        if spread_pct is not None:
            spread_pct_display = spread_pct * 100.0
            return f"{spread_pct_display:+.3f}%"
        return "null"
    
    def _format_volatility(self, volatility_pct: Optional[float]) -> str:
        """
        Formate la valeur de volatilité.
        
        Args:
            volatility_pct: Valeur de volatilité en pourcentage
            
        Returns:
            Valeur formatée
        """
        if volatility_pct is not None:
            volatility_pct_display = volatility_pct * 100.0
            return f"{volatility_pct_display:+.3f}%"
        return "-"
    
    def is_running(self) -> bool:
        """
        Vérifie si le gestionnaire d'affichage est en cours d'exécution.
        
        Returns:
            True si en cours d'exécution
        """
        return self._running and self._display_thread and self._display_thread.is_alive()
