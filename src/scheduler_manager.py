#!/usr/bin/env python3
"""
Gestionnaire de planification pour le bot Bybit.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

Ce module gère la planification temporelle du bot, notamment pour le
funding sniping et autres opérations programmées.

🔍 COMPRENDRE CE MODULE :

1. SchedulerManager : Classe principale pour la gestion du timing
   ├─> __init__() : Initialise le logger
   └─> run() : Méthode principale (sera implémentée plus tard)

📚 FLUX DÉTAILLÉ : Ce module sera étendu pour gérer :
- Timing des opérations de funding
- Planification des tâches périodiques
- Coordination temporelle avec les autres composants

🎯 COMPOSANTS UTILISÉS :
- Logger : Pour les messages de debug et d'information
- Watchlist data : Données de surveillance pour le timing
"""

import asyncio
import re
from typing import Dict, Any


class SchedulerManager:
    """
    Gestionnaire de planification pour le bot Bybit.
    
    Cette classe gère la planification temporelle des opérations,
    notamment pour le funding sniping et autres tâches programmées.
    """

    def __init__(self, logger, funding_threshold_minutes=60, bybit_client=None, auto_trading_config=None):
        """
        Initialise le gestionnaire de planification.
        
        Args:
            logger: Logger pour les messages de debug et d'information
            funding_threshold_minutes: Seuil de détection du funding imminent (en minutes)
            bybit_client: Client Bybit pour passer des ordres (optionnel)
            auto_trading_config: Configuration du trading automatique (optionnel)
        """
        self.logger = logger
        self.scan_interval = 5  # secondes
        self.funding_threshold_minutes = funding_threshold_minutes
        self.bybit_client = bybit_client
        self.auto_trading_config = auto_trading_config or {}
        
        # Tracking des ordres passés pour éviter les doublons
        self.orders_placed = set()
        
        # Optimisation: éviter les scans trop fréquents
        self.last_scan_time = 0
        
        self.logger.info("🕒 Scheduler initialisé")

    def set_threshold(self, minutes: float):
        """
        Permet de modifier dynamiquement le seuil de détection du funding imminent.
        
        Args:
            minutes: Seuil en minutes pour détecter le funding imminent
        """
        self.funding_threshold_minutes = minutes
        self.logger.info(f"🛠️ [SCHEDULER] Seuil Funding T défini à {minutes} min")

    def parse_funding_time(self, funding_t_str: str) -> int:
        """
        Convertit un texte '2h 15m 30s' ou '22m 59s' en secondes.
        
        Args:
            funding_t_str: Chaîne de temps au format "Xh Ym Zs" ou "Ym Zs"
            
        Returns:
            int: Nombre de secondes total
        """
        if not funding_t_str or funding_t_str == "-":
            return 0
            
        h = m = s = 0
        if match := re.search(r"(\d+)h", funding_t_str):
            h = int(match.group(1))
        if match := re.search(r"(\d+)m", funding_t_str):
            m = int(match.group(1))
        if match := re.search(r"(\d+)s", funding_t_str):
            s = int(match.group(1))
        return h * 3600 + m * 60 + s

    def _should_place_order(self, symbol: str, remaining_seconds: int) -> bool:
        """
        Détermine si un ordre doit être placé pour cette paire.
        
        Args:
            symbol: Symbole de la paire
            remaining_seconds: Secondes restantes avant le funding
            
        Returns:
            bool: True si un ordre doit être placé
        """
        # Vérifier si le trading automatique est activé
        if not self.auto_trading_config.get('enabled', False):
            return False
            
        # Vérifier si on a déjà passé un ordre pour cette paire
        if symbol in self.orders_placed:
            return False
            
        # Trade immédiatement quand une opportunité est détectée
        # Plus de vérification de délai - trade dès que le scheduler détecte une paire
        return True

    def _place_automatic_order(self, symbol: str, funding_rate: float, current_price: float) -> bool:
        """
        Place un ordre automatique pour la paire donnée.
        
        Args:
            symbol: Symbole de la paire
            funding_rate: Taux de funding actuel
            current_price: Prix actuel de la paire
            
        Returns:
            bool: True si l'ordre a été placé avec succès
        """
        try:
            # Vérifier le mode dry-run
            if self.auto_trading_config.get('dry_run', False):
                self.logger.info(f"🧪 [DRY-RUN] Ordre simulé pour {symbol}: {funding_rate:.4f} @ {current_price}")
                self.orders_placed.add(symbol)
                return True
                
            # Déterminer le côté de l'ordre basé sur le funding rate
            # S'assurer que funding_rate est un float
            funding_rate_float = float(funding_rate) if funding_rate is not None else 0.0
            side = "Buy" if funding_rate_float > 0 else "Sell"
            
            # Calculer la quantité en USDT
            order_size_usdt = self.auto_trading_config.get('order_size_usdt', 10)
            
            # Calculer la quantité de base
            base_qty = order_size_usdt / current_price
            
            # Récupérer les informations du symbole pour connaître les règles
            try:
                # Utiliser un thread dédié pour éviter PERF-002
                import concurrent.futures
                
                def _get_instruments_info_sync():
                    return self.bybit_client.get_instruments_info(category="linear", symbol=symbol)
                
                # Exécuter dans un thread dédié
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(_get_instruments_info_sync)
                    instruments_info = future.result()
                
                if instruments_info and 'list' in instruments_info and instruments_info['list']:
                    symbol_info = instruments_info['list'][0]
                    lot_size_filter = symbol_info.get('lotSizeFilter', {})
                    min_qty = float(lot_size_filter.get('minOrderQty', '0.001'))
                    qty_step = float(lot_size_filter.get('qtyStep', '0.001'))
                    
                    # Ajuster la quantité selon les règles du symbole
                    # Arrondir à la valeur minimale requise
                    if base_qty < min_qty:
                        qty = str(min_qty)
                        self.logger.info(f"📊 [TRADING] Quantité ajustée au minimum pour {symbol}: {qty}")
                    else:
                        # Arrondir selon le step requis
                        adjusted_qty = round(base_qty / qty_step) * qty_step
                        qty = f"{adjusted_qty:.6f}".rstrip('0').rstrip('.')
                        if not qty or qty == '0':
                            qty = str(min_qty)
                else:
                    # Fallback si pas d'infos du symbole
                    qty = f"{max(base_qty, 0.001):.6f}".rstrip('0').rstrip('.')
                    if not qty or qty == '0':
                        qty = "0.001"
            except Exception as e:
                self.logger.warning(f"⚠️ [TRADING] Impossible de récupérer les infos du symbole {symbol}: {e}")
                # Fallback simple
                qty = f"{max(base_qty, 0.001):.6f}".rstrip('0').rstrip('.')
                if not qty or qty == '0':
                    qty = "0.001"
            
            # Calculer le prix limite avec offset
            offset_percent = self.auto_trading_config.get('order_offset_percent', 0.1) / 100
            if side == "Buy":
                limit_price = current_price * (1 + offset_percent)  # Prix plus élevé pour Buy
            else:
                limit_price = current_price * (1 - offset_percent)  # Prix plus bas pour Sell
                
            # Passer l'ordre
            if not self.bybit_client:
                self.logger.error("❌ [TRADING] Client Bybit non disponible")
                return False
            
            # Utiliser un thread dédié pour éviter PERF-002
            import concurrent.futures
            
            def _place_order_sync():
                return self.bybit_client.place_order(
                    symbol=symbol,
                    side=side,
                    order_type="Limit",
                    qty=qty,
                    price=str(limit_price),
                    category="linear"
                )
            
            # Exécuter dans un thread dédié
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_place_order_sync)
                response = future.result()
            
            # Marquer l'ordre comme passé
            self.orders_placed.add(symbol)
            
            self.logger.info(
                f"✅ [TRADING] Ordre placé pour {symbol}: {side} {qty} @ {limit_price:.4f} "
                f"(funding: {funding_rate_float:.4f})"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [TRADING] Erreur lors du placement d'ordre pour {symbol}: {e}")
            # Ne pas marquer l'ordre comme passé en cas d'erreur
            return False

    def _handle_automatic_trading(self, symbol: str, remaining_seconds: int, first_data: dict):
        """
        Gère le trading automatique pour une paire donnée.
        
        Args:
            symbol: Symbole de la paire
            remaining_seconds: Secondes restantes avant le funding
            first_data: Données de la première paire
        """
        # Vérifier si un ordre automatique doit être placé
        if self._should_place_order(symbol, remaining_seconds):
            # Récupérer le prix actuel et le funding rate
            try:
                # Obtenir le prix actuel depuis le carnet d'ordres
                if self.bybit_client:
                    # Utiliser un thread dédié pour éviter PERF-002
                    import concurrent.futures
                    import asyncio
                    
                    def _get_orderbook_sync():
                        return self.bybit_client.get_orderbook(symbol=symbol, limit=1)
                    
                    # Exécuter dans un thread dédié
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(_get_orderbook_sync)
                        orderbook = future.result()
                    
                    if orderbook and 'b' in orderbook and 'a' in orderbook:
                        bid_price = float(orderbook['b'][0][0]) if orderbook['b'] else 0
                        ask_price = float(orderbook['a'][0][0]) if orderbook['a'] else 0
                        current_price = (bid_price + ask_price) / 2
                        
                        # Récupérer le funding rate depuis les données de la watchlist
                        funding_rate = first_data.get('funding_rate', 0)
                        
                        # Placer l'ordre automatique
                        self._place_automatic_order(symbol, funding_rate, current_price)
                    else:
                        self.logger.warning(f"⚠️ [TRADING] Impossible de récupérer le prix pour {symbol}")
                else:
                    self.logger.warning(f"⚠️ [TRADING] Client Bybit non disponible pour {symbol}")
            except Exception as e:
                self.logger.error(f"❌ [TRADING] Erreur lors de la récupération des données pour {symbol}: {e}")

    async def run_with_callback(self, data_callback):
        """
        Méthode principale du scheduler avec callback pour récupérer les données à jour.
        
        Args:
            data_callback: Fonction qui retourne les données de funding formatées
        """
        self.logger.info(f"🕒 Scheduler démarré (seuil Funding T = {self.funding_threshold_minutes} min)")
        
        while True:
            try:
                # Récupérer les données à jour via le callback
                watchlist_data = data_callback()
                
                # Vérifier si les données sont disponibles
                if not watchlist_data:
                    self.logger.debug(f"🕒 [SCHEDULER] Aucune donnée disponible (prochain scan dans {self.scan_interval}s)")
                    await asyncio.sleep(self.scan_interval)
                    continue
                
                imminent_pairs = []
                
                # Sélectionner UNIQUEMENT la première paire de la watchlist
                first_symbol = None
                first_data = None
                
                # Récupérer la première paire de la watchlist
                for symbol, data in watchlist_data.items():
                    if isinstance(data, dict):
                        first_symbol = symbol
                        first_data = data
                        break
                
                if first_symbol and first_data:
                    # Récupérer le funding time formaté (ex: "22m 59s")
                    funding_t_str = first_data.get('next_funding_time', None)
                    
                    if funding_t_str and funding_t_str != "-":
                        # Convertir la chaîne en secondes
                        remaining_seconds = self.parse_funding_time(funding_t_str)
                        
                        # Log debug pour le suivi (avec plus de détails)
                        self.logger.debug(f"[SCHEDULER] {first_symbol}: funding={funding_t_str} ({remaining_seconds}s) - Seuil: {self.funding_threshold_minutes}min")
                        
                        # Vérifier si le funding est imminent selon le seuil
                        if remaining_seconds > 0 and remaining_seconds <= self.funding_threshold_minutes * 60:
                            imminent_pairs.append({
                                'symbol': first_symbol,
                                'remaining_seconds': remaining_seconds,
                                'remaining_minutes': remaining_seconds / 60
                            })
                
                # Afficher les paires avec funding imminent et gérer le trading automatique
                if imminent_pairs:
                    for pair in imminent_pairs:
                        symbol = pair['symbol']
                        remaining_seconds = pair['remaining_seconds']
                        
                        self.logger.info(
                            f"⚡ [SCHEDULER] {symbol} funding imminent → "
                            f"{remaining_seconds:.0f}s (seuil={self.funding_threshold_minutes}min)"
                        )
                        
                        # Récupérer les données spécifiques à cette paire
                        pair_data = watchlist_data.get(symbol, {})
                        
                        # Gérer le trading automatique
                        self._handle_automatic_trading(symbol, remaining_seconds, pair_data)
                else:
                    self.logger.debug(
                        f"🕒 [SCHEDULER] Aucune paire proche du funding "
                        f"(prochain scan dans {self.scan_interval}s)"
                    )
                
                # Attendre avant le prochain scan
                await asyncio.sleep(self.scan_interval)
                
            except Exception as e:
                self.logger.error(f"❌ [SCHEDULER] Erreur dans la boucle de scan: {e}")
                await asyncio.sleep(self.scan_interval)

    async def run(self, watchlist_data: Dict[str, Any]):
        """
        Méthode principale du scheduler - analyse régulièrement la watchlist
        pour détecter les paires dont le Funding T est proche du seuil.
        
        Args:
            watchlist_data: Données de la watchlist pour le timing
        """
        self.logger.info(f"🕒 Scheduler démarré (seuil Funding T = {self.funding_threshold_minutes} min)")
        
        while True:
            try:
                imminent_pairs = []
                
                # Analyser seulement la première paire de la watchlist
                first_symbol = None
                first_data = None
                
                # Récupérer la première paire
                for symbol, data in watchlist_data.items():
                    if isinstance(data, dict):
                        first_symbol = symbol
                        first_data = data
                        break
                
                if first_symbol and first_data:
                    # Récupérer le funding time formaté (ex: "22m 59s")
                    funding_t_str = first_data.get('next_funding_time', None)
                    
                    if funding_t_str and funding_t_str != "-":
                        # Convertir la chaîne en secondes
                        remaining_seconds = self.parse_funding_time(funding_t_str)
                        
                        # Log debug pour le suivi
                        self.logger.debug(f"[SCHEDULER] {first_symbol}: funding={funding_t_str} ({remaining_seconds}s)")
                        
                        # Vérifier si le funding est imminent selon le seuil
                        if remaining_seconds > 0 and remaining_seconds <= self.funding_threshold_minutes * 60:
                            imminent_pairs.append({
                                'symbol': first_symbol,
                                'remaining_seconds': remaining_seconds,
                                'remaining_minutes': remaining_seconds / 60
                            })
                
                # Afficher les paires avec funding imminent
                if imminent_pairs:
                    for pair in imminent_pairs:
                        self.logger.info(
                            f"⚡ [SCHEDULER] {pair['symbol']} funding imminent → "
                            f"{pair['remaining_seconds']:.0f}s (seuil={self.funding_threshold_minutes}min)"
                        )
                else:
                    self.logger.debug(
                        f"🕒 [SCHEDULER] Aucune paire proche du funding "
                        f"(prochain scan dans {self.scan_interval}s)"
                    )
                
                # Attendre avant le prochain scan
                await asyncio.sleep(self.scan_interval)
                
            except Exception as e:
                self.logger.error(f"❌ [SCHEDULER] Erreur dans la boucle de scan: {e}")
                await asyncio.sleep(self.scan_interval)
