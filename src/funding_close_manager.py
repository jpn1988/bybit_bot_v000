#!/usr/bin/env python3
"""
Gestionnaire de fermeture automatique après funding.

Cette classe gère la fermeture automatique des positions après avoir touché le funding.
Elle surveille les événements de funding via WebSocket privé et ferme automatiquement
les positions correspondantes.

Fonctionnalités :
- Surveillance des événements de funding en temps réel
- Fermeture automatique des positions après funding
- Gestion des erreurs et retry
- Logs informatifs pour le suivi
"""

import asyncio
import threading
import time
from typing import Callable, Dict, Any, Optional, Set
from logging_setup import setup_logging
from ws_private import PrivateWSClient
from config import get_settings


class FundingCloseManager:
    """
    Gestionnaire de fermeture automatique après funding.
    
    Cette classe surveille les événements de funding via WebSocket privé
    et ferme automatiquement les positions correspondantes.
    """
    
    def __init__(
        self,
        testnet: bool,
        logger,
        bybit_client,
        on_position_closed: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        """
        Initialise le gestionnaire de fermeture après funding.
        
        Args:
            testnet: Mode testnet ou mainnet
            logger: Logger pour les messages
            bybit_client: Client Bybit pour fermer les positions
            on_position_closed: Callback appelé lors de la fermeture d'une position
        """
        self.testnet = testnet
        self.logger = logger
        self.bybit_client = bybit_client
        self.on_position_closed = on_position_closed
        
        # Positions surveillées pour fermeture après funding
        self._monitored_positions: Set[str] = set()
        
        # WebSocket client pour surveiller les événements de funding
        self._ws_client: Optional[PrivateWSClient] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._last_funding_check = {}  # Cache des derniers funding rates
        
        # Configuration
        settings = get_settings()
        self.api_key = settings["api_key"]
        self.api_secret = settings["api_secret"]
        
        self.logger.info("💰 FundingCloseManager initialisé")

    def add_position_to_monitor(self, symbol: str):
        """
        Ajoute une position à surveiller pour fermeture après funding.
        
        Args:
            symbol: Symbole de la position à surveiller
        """
        self._monitored_positions.add(symbol)
        self.logger.info(f"💰 Position ajoutée à la surveillance funding: {symbol}")

    def remove_position_from_monitor(self, symbol: str):
        """
        Retire une position de la surveillance.
        
        Args:
            symbol: Symbole de la position à ne plus surveiller
        """
        if symbol in self._monitored_positions:
            self._monitored_positions.remove(symbol)
            self.logger.info(f"💰 Position retirée de la surveillance funding: {symbol}")

    def _on_funding_event(self, topic: str, data: Dict[str, Any]):
        """
        Callback pour les événements de funding.
        
        Args:
            topic: Topic de l'événement
            data: Données de l'événement
        """
        # Log de débogage pour TOUS les événements WebSocket
        self.logger.info(f"🔍 [DEBUG] Événement WebSocket reçu: topic='{topic}', type={type(data)}, data={data}")
        
        # Le topic "funding" n'existe pas dans l'API WebSocket privée de Bybit
        # On utilise la surveillance périodique via l'API REST à la place
        if topic == "position":
            self.logger.debug(f"💰 [DEBUG] Mise à jour de position reçue")
            # Les positions sont surveillées via la méthode périodique _check_positions_periodically
        else:
            self.logger.debug(f"ℹ️ [DEBUG] Topic '{topic}' reçu (surveillance via API REST)")

    def _close_position_after_funding(self, symbol: str):
        """
        Ferme automatiquement une position après avoir touché le funding.
        
        Args:
            symbol: Symbole de la position à fermer
        """
        try:
            self.logger.info(f"🔄 Fermeture automatique de la position {symbol} après funding...")
            
            # Récupérer les informations des positions (filtrer ensuite par symbole)
            positions = self.bybit_client.get_positions(category="linear", settleCoin="USDT")

            if not positions or not positions.get("list"):
                self.logger.warning(f"⚠️ Aucune position trouvée pour {symbol}")
                return
            
            # Filtrer la liste pour ne conserver que le symbole ciblé
            all_positions = positions.get("list", [])
            matching = [p for p in all_positions if p.get("symbol") == symbol]
            if not matching:
                self.logger.warning(f"⚠️ Aucune position ouverte pour {symbol}")
                return

            position_data = matching[0]
            side = position_data.get("side")
            size = position_data.get("size")
            
            if not side or not size or float(size) == 0:
                self.logger.warning(f"⚠️ Position {symbol} déjà fermée ou invalide")
                return
            
            # Déterminer le côté opposé pour fermer
            close_side = "Sell" if side == "Buy" else "Buy"
            
            # Fermer la position (ordre market pour fermeture immédiate)
            close_response = self.bybit_client.place_order(
                symbol=symbol,
                side=close_side,
                order_type="Market",
                qty=size,
                category="linear"
            )
            
            if close_response and close_response.get("orderId"):
                self.logger.info(f"✅ Position {symbol} fermée automatiquement après funding - OrderID: {close_response['orderId']}")
                
                # Appeler le callback de fermeture de position
                if self.on_position_closed:
                    try:
                        position_info = {
                            "symbol": symbol,
                            "side": close_side,
                            "size": size,
                            "reason": "funding_close"
                        }
                        self.on_position_closed(symbol, position_info)
                    except Exception as e:
                        self.logger.warning(f"⚠️ Erreur callback fermeture position: {e}")
                
                # Retirer de la surveillance
                self.remove_position_from_monitor(symbol)
                
            else:
                self.logger.error(f"❌ Échec fermeture position {symbol}: {close_response}")
                
        except Exception as e:
            self.logger.error(f"❌ Erreur fermeture automatique {symbol}: {e}")

    def _run_ws_client(self):
        """Lance le client WebSocket privé pour surveiller les événements de funding."""
        try:
            self._ws_client = PrivateWSClient(
                testnet=self.testnet,
                api_key=self.api_key,
                api_secret=self.api_secret,
                channels=["position"],  # Surveiller les positions (pas de topic "funding" disponible)
                logger=self.logger,
            )
            self._ws_client.on_topic = self._on_funding_event
            self._ws_client.run()
        except Exception as e:
            self.logger.error(f"❌ Erreur FundingCloseManager WebSocket: {e}")
        finally:
            self.logger.info("🛑 FundingCloseManager WebSocket arrêté.")
    
    def _check_positions_periodically(self):
        """Vérifie périodiquement les positions et les ferme si nécessaire (fallback)."""
        import threading
        
        def check_loop():
            while self._running:
                try:
                    if self._monitored_positions:
                        self.logger.info(f"🔍 Vérification périodique des positions: {list(self._monitored_positions)}")
                        
                        for symbol in list(self._monitored_positions):
                            position_found = self._verify_position_exists(symbol)
                            
                            if position_found:
                                self._check_funding_and_monitor(symbol)
                            else:
                                self.logger.info(f"ℹ️ Position {symbol} n'existe plus - retirer de la surveillance")
                                self.remove_position_from_monitor(symbol)
                    
                    # Attendre 30 secondes avant la prochaine vérification
                    import time
                    time.sleep(30)
                    
                except Exception as e:
                    self.logger.error(f"❌ Erreur vérification périodique: {e}")
                    import time
                    time.sleep(30)
        
        # Démarrer le thread de vérification périodique
        check_thread = threading.Thread(target=check_loop, daemon=True)
        check_thread.start()

    def _verify_position_exists(self, symbol: str) -> bool:
        """
        Vérifie si une position existe encore avec retry logic.
        
        Args:
            symbol: Symbole à vérifier
            
        Returns:
            bool: True si la position existe et est active, False sinon
        """
        import time
        
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                positions = self.bybit_client.get_positions(category="linear", settleCoin="USDT")
                
                # Debug: Afficher la réponse de l'API
                self.logger.info(f"🔍 Tentative {attempt + 1}/{max_attempts} - API Response pour {symbol}: {positions}")

                if positions and positions.get("list"):
                    all_positions = positions.get("list", [])
                    self.logger.info(f"🔍 Toutes les positions: {[p.get('symbol') for p in all_positions]}")
                    
                    matching = [p for p in all_positions if p.get("symbol") == symbol]
                    if matching:
                        position_data = matching[0]
                        size = position_data.get("size", "0")
                        
                        self.logger.info(f"🔍 Position {symbol}: size={size}")
                        
                        if size and float(size) > 0:
                            self.logger.info(f"✅ Position {symbol} confirmée (size={size}) - surveillance continue")
                            return True
                        else:
                            self.logger.info(f"ℹ️ Position {symbol} fermée (size=0) - retirer de la surveillance")
                            return False
                
                # Si pas trouvée, attendre un peu avant la prochaine tentative
                if attempt < max_attempts - 1:
                    self.logger.debug(f"⏳ Position {symbol} non trouvée, tentative {attempt + 2} dans 5s...")
                    time.sleep(5)
                    
            except Exception as e:
                self.logger.error(f"❌ Erreur tentative {attempt + 1} pour {symbol}: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(5)
        
        # Si la position n'a pas été trouvée après toutes les tentatives
        self.logger.warning(f"⚠️ Position {symbol} non trouvée après {max_attempts} tentatives")
        return False

    def _check_funding_and_monitor(self, symbol: str):
        """
        Vérifie le funding et continue la surveillance.
        
        Args:
            symbol: Symbole à surveiller
        """
        # Vérifier si le funding a été touché via API REST
        self._check_funding_event(symbol)
        self.logger.info(f"ℹ️ Position {symbol} toujours active - surveillance continue")

    def _check_funding_event(self, symbol: str):
        """
        Vérifie si un événement de funding a eu lieu pour le symbole donné.
        Utilise l'API REST pour récupérer les données de funding.
        
        Args:
            symbol: Symbole à vérifier
        """
        try:
            # Récupérer les données de funding via API REST
            funding_data = self.bybit_client.get_funding_rate(symbol=symbol)
            
            if funding_data and funding_data.get("list"):
                latest_funding = funding_data["list"][0]  # Le plus récent
                funding_rate = float(latest_funding.get("fundingRate", 0))
                funding_time = latest_funding.get("fundingRateTimestamp", "")
                
                self.logger.info(f"🔍 [DEBUG] Funding {symbol}: rate={funding_rate:.4f}, time={funding_time}")
                
                # Vérifier si c'est un nouveau funding (pas déjà traité)
                cache_key = f"{symbol}_{funding_time}"
                if cache_key not in self._last_funding_check:
                    # Vérifier si le funding est récent (dans les 5 dernières minutes)
                    import time
                    current_time = int(time.time() * 1000)  # Timestamp en millisecondes
                    funding_timestamp = int(funding_time) if funding_time else 0
                    time_diff_minutes = (current_time - funding_timestamp) / (1000 * 60)
                    
                    self.logger.info(f"🔍 [DEBUG] Différence de temps: {time_diff_minutes:.1f} minutes")
                    
                    # Ne fermer que si le funding est très récent (moins de 5 minutes)
                    if time_diff_minutes < 5:
                        self._last_funding_check[cache_key] = True
                        
                        self.logger.info(f"💰 [DEBUG] Nouveau funding récent détecté pour {symbol}: {funding_rate:.4f}")
                        self.logger.info(f"🎯 [DEBUG] Position {symbol} est surveillée ! Fermeture automatique...")
                        
                        # Fermer automatiquement la position
                        self._close_position_after_funding(symbol)
                    else:
                        self.logger.info(f"ℹ️ [DEBUG] Funding {symbol} trop ancien ({time_diff_minutes:.1f}min) - pas de fermeture")
                else:
                    self.logger.debug(f"ℹ️ [DEBUG] Funding {symbol} déjà traité: {funding_rate:.4f}")
            else:
                self.logger.warning(f"⚠️ [DEBUG] Aucune donnée de funding pour {symbol}")
                
        except Exception as e:
            self.logger.error(f"❌ [DEBUG] Erreur vérification funding {symbol}: {e}")

    def start(self):
        """Démarre le gestionnaire de fermeture après funding."""
        if not self._running:
            self._running = True
            self._monitor_thread = threading.Thread(target=self._run_ws_client, daemon=True)
            self._monitor_thread.start()
            
            # Démarrer aussi la vérification périodique comme fallback
            self._check_positions_periodically()
            
            self.logger.info("💰 FundingCloseManager démarré")

    def stop(self):
        """Arrête le gestionnaire de fermeture après funding."""
        if self._running:
            self._running = False
            if self._ws_client:
                self._ws_client.close()
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5)
            self.logger.info("🛑 FundingCloseManager arrêté")

    def get_monitored_positions(self) -> Set[str]:
        """Retourne les positions actuellement surveillées."""
        return self._monitored_positions.copy()
    
    def force_close_position(self, symbol: str):
        """
        Force la fermeture d'une position spécifique.
        
        Args:
            symbol: Symbole de la position à fermer
        """
        try:
            self.logger.info(f"🔄 Fermeture forcée de la position {symbol}...")
            self._close_position_after_funding(symbol)
        except Exception as e:
            self.logger.error(f"❌ Erreur fermeture forcée {symbol}: {e}")
    
    def force_close_all_positions(self):
        """Force la fermeture de toutes les positions surveillées."""
        try:
            monitored = list(self._monitored_positions)
            self.logger.info(f"🔄 Fermeture forcée de toutes les positions: {monitored}")
            
            for symbol in monitored:
                self.force_close_position(symbol)
                
        except Exception as e:
            self.logger.error(f"❌ Erreur fermeture forcée toutes positions: {e}")
