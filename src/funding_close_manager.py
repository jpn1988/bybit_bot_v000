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
from order_monitor import OrderMonitor
from utils.async_wrappers import run_in_thread


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
        auto_trading_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialise le gestionnaire de fermeture après funding.

        Args:
            testnet: Mode testnet ou mainnet
            logger: Logger pour les messages
            bybit_client: Client Bybit pour fermer les positions
            on_position_closed: Callback appelé lors de la fermeture d'une position
            auto_trading_config: Configuration du trading automatique
        """
        self.testnet = testnet
        self.logger = logger
        self.bybit_client = bybit_client
        self.on_position_closed = on_position_closed
        self.auto_trading_config = auto_trading_config or {}
        self.enabled = self._normalize_auto_close_flag(
            self.auto_trading_config.get("auto_close_after_funding", False)
        )

        if not self.enabled:
            self.logger.info("[FUNDING] 💤 FundingCloseManager désactivé (auto_close_after_funding=False)")
            self.logger.info("[FUNDING] 💤 Aucun thread démarré pour la fermeture automatique")
            # Gardes simples : ne pas initialiser les composants coûteux
            self._monitored_positions: Set[str] = set()
            self._ws_client = None
            self._monitor_thread = None
            self._running = False
            self._last_funding_check = {}
            self._summary_interval = 60
            self._last_summary_ts = 0.0
            self.order_monitor = None
            self._pending_close_orders = {}
            self.api_key = None
            self.api_secret = None
            return

        # Positions surveillées pour fermeture après funding
        self._monitored_positions: Set[str] = set()

        # WebSocket client pour surveiller les événements de funding
        self._ws_client: Optional[PrivateWSClient] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._last_funding_check = {}  # Cache des derniers funding rates
        self._summary_interval = 60
        self._last_summary_ts = 0.0

        # OrderMonitor pour surveiller les ordres de fermeture limite
        self.order_monitor = OrderMonitor(
            bybit_client=bybit_client,
            logger=logger,
            on_order_timeout=self._handle_close_order_timeout
        )

        # Dictionnaire pour tracker les ordres de fermeture limite en cours
        self._pending_close_orders: Dict[str, str] = {}  # symbol -> order_id

        # Configuration
        settings = get_settings()
        self.api_key = settings["api_key"]
        self.api_secret = settings["api_secret"]

        self.logger.debug("💰 FundingCloseManager initialisé avec OrderMonitor")

    @staticmethod
    def _normalize_auto_close_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def is_enabled(self) -> bool:
        return getattr(self, "enabled", False)

    def check_existing_positions(self):
        """
        Vérifie et ajoute les positions existantes à la surveillance au démarrage.
        """
        try:
            if not self.is_enabled():
                self.logger.info("[FUNDING] 💤 Vérification initiale ignorée (FundingCloseManager désactivé)")
                return
            self.logger.debug("🔍 Vérification des positions existantes pour surveillance funding...")

            # Récupérer les positions existantes
            positions = self.bybit_client.get_positions(category="linear", settleCoin="USDT")

            if positions and positions.get("list"):
                existing_positions = positions["list"]
                active_positions = [pos for pos in existing_positions if float(pos.get("size", 0)) > 0]

                if active_positions:
                    self.logger.debug(f"📈 {len(active_positions)} position(s) existante(s) détectée(s) pour surveillance funding:")
                    for pos in active_positions:
                        symbol = pos.get("symbol", "N/A")
                        size = pos.get("size", "0")
                        side = pos.get("side", "N/A")
                        self.logger.debug(f"   - {symbol}: {side} {size}")

                        # Ajouter à la surveillance
                        self.add_position_to_monitor(symbol)
                else:
                    self.logger.debug("ℹ️ Aucune position active détectée pour surveillance funding")
            else:
                self.logger.debug("ℹ️ Aucune position trouvée pour surveillance funding")

        except Exception as e:
            self.logger.error(f"❌ Erreur vérification positions existantes: {e}")

    def add_position_to_monitor(self, symbol: str):
        """
        Ajoute une position à surveiller pour fermeture après funding.

        Args:
            symbol: Symbole de la position à surveiller
        """
        if not self.is_enabled():
            return

        self._monitored_positions.add(symbol)
        self.logger.debug(f"💰 Position ajoutée à la surveillance funding: {symbol}")
        self.logger.debug(f"💰 Positions surveillées: {list(self._monitored_positions)}")
        self.logger.debug(f"💰 FundingCloseManager running: {self._running}")

    def remove_position_from_monitor(self, symbol: str):
        """
        Retire une position de la surveillance.

        Args:
            symbol: Symbole de la position à ne plus surveiller
        """
        if not self.is_enabled():
            return

        if symbol in self._monitored_positions:
            self._monitored_positions.remove(symbol)
            self.logger.debug(f"💰 Position retirée de la surveillance funding: {symbol}")

            # Nettoyer l'ordre de fermeture en cours s'il existe
            if symbol in self._pending_close_orders:
                order_id = self._pending_close_orders[symbol]
                self.order_monitor.remove_order(order_id)
                del self._pending_close_orders[symbol]
                self.logger.debug(f"🧹 Ordre de fermeture nettoyé pour {symbol}")

    def _on_funding_event(self, topic: str, data: Dict[str, Any]):
        """
        Callback pour les événements de funding.

        Args:
            topic: Topic de l'événement
            data: Données de l'événement
        """
        # Log de débogage allégé pour les événements WebSocket
        if not self.is_enabled():
            return

        self.logger.debug(f"🔍 Événement WebSocket reçu: topic='{topic}'")

        # Le topic "funding" n'existe pas dans l'API WebSocket privée de Bybit
        # On utilise la surveillance périodique via l'API REST à la place
        if topic == "position":
            self.logger.debug("💰 Mise à jour de position reçue")
            # Les positions sont surveillées via la méthode périodique _check_positions_periodically
        else:
            self.logger.debug(f"ℹ️ Topic '{topic}' reçu (surveillance via API REST)")

    def _close_position_after_funding(self, symbol: str):
        """
        Fermeture automatique désactivée à la demande de l'utilisateur.
        """
        if not self.is_enabled():
            return
        self.logger.debug(f"[FUNDING_CLOSE_DISABLED] Fermeture auto désactivée - aucune action pour {symbol}")

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """
        Récupère le prix actuel du marché pour un symbole.

        Args:
            symbol: Symbole pour lequel récupérer le prix

        Returns:
            Prix actuel ou None si erreur
        """
        try:
            # Utiliser l'API pour récupérer le prix actuel
            ticker_data = self.bybit_client.get_tickers(symbol=symbol, category="linear")

            if ticker_data and ticker_data.get("list"):
                latest_ticker = ticker_data["list"][0]
                last_price = latest_ticker.get("lastPrice")
                if last_price:
                    return float(last_price)

            self.logger.warning(f"[FUNDING] ⚠️ Impossible de récupérer le prix pour {symbol}")
            return None

        except Exception as e:
            self.logger.error(f"❌ Erreur récupération prix {symbol}: {e}")
            return None

    def _handle_close_order_timeout(self, order_id: str, symbol: str, side: str, qty: str, price: float):
        """
        Callback appelé quand un ordre de fermeture limite expire.

        Args:
            order_id: ID de l'ordre expiré
            symbol: Symbole de la position
            side: Côté de l'ordre
            qty: Quantité
            price: Prix de l'ordre
        """
        try:
            if not self.is_enabled():
                return

            self.logger.warning(f"[FUNDING] ⏰ [TIMEOUT] Ordre limite de fermeture expiré pour {symbol} - OrderID: {order_id}")

            # Retirer de la liste des ordres en cours
            if symbol in self._pending_close_orders:
                del self._pending_close_orders[symbol]

            # Placer un ordre Market pour garantir la fermeture
            self.logger.info(f"[FUNDING] 🔄 [FALLBACK] Passage à un ordre Market pour fermer {symbol}")

            market_response = self.bybit_client.place_order(
                symbol=symbol,
                side=side,
                order_type="Market",
                qty=qty,
                category="linear"
            )

            if market_response and market_response.get("orderId"):
                self.logger.info(f"[FUNDING] ✅ [FALLBACK] Position {symbol} fermée avec ordre Market - OrderID: {market_response['orderId']}")

                # Appeler le callback de fermeture de position
                if self.on_position_closed:
                    try:
                        position_info = {
                            "symbol": symbol,
                            "side": side,
                            "size": qty,
                            "reason": "funding_close_fallback"
                        }
                        self.on_position_closed(symbol, position_info)
                    except Exception as e:
                        self.logger.warning(f"[FUNDING] ⚠️ Erreur callback fermeture position fallback: {e}")

                # Retirer de la surveillance
                self.remove_position_from_monitor(symbol)
                self.logger.info("[FUNDING] Fermeture funding OK")

            else:
                self.logger.error(f"[FUNDING] ❌ [FALLBACK] Échec fermeture Market {symbol}: {market_response}")

        except Exception as e:
            self.logger.error(f"[FUNDING] ❌ [FALLBACK] Erreur fermeture fallback {symbol}: {e}")

    def _run_ws_client(self):
        """Lance le client WebSocket privé pour surveiller les événements de funding."""
        if not self.is_enabled():
            return
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
            self.logger.debug("🛑 FundingCloseManager WebSocket arrêté.")

    def _check_positions_periodically(self):
        """Vérifie périodiquement les positions et les ferme si nécessaire (fallback)."""
        if not self.is_enabled():
            return
        import threading

        async def check_loop_async():
            self.logger.debug("🔄 [FUNDING_MONITOR] Thread de vérification périodique démarré")
            while self._running:
                try:
                    # Vérifier les ordres en attente pour les timeouts
                    await self.order_monitor.check_orders_status()

                    if self._monitored_positions:
                        self.logger.debug(f"🔍 [FUNDING_MONITOR] Vérification périodique des positions: {list(self._monitored_positions)}")

                        for symbol in list(self._monitored_positions):
                            self.logger.debug("[ASYNC] Bybit REST call exécuté dans un thread : _verify_position_exists()")
                            position_found = await run_in_thread(self._verify_position_exists, symbol)

                            if position_found:
                                self.logger.debug("[ASYNC] Bybit REST call exécuté dans un thread : _check_funding_and_monitor()")
                                await run_in_thread(self._check_funding_and_monitor, symbol)
                            else:
                                self.logger.debug(f"ℹ️ [FUNDING_MONITOR] Position {symbol} n'existe plus - retirer de la surveillance")
                                self.remove_position_from_monitor(symbol)
                    else:
                        self.logger.debug("🔍 [FUNDING_MONITOR] Aucune position surveillée")

                    # Attendre un délai adaptatif basé sur le nombre de positions surveillées
                    # Plus de positions = vérification plus fréquente, moins de positions = moins fréquent
                    delay = max(5, min(15, 20 - len(self._monitored_positions)))
                    self._log_periodic_summary()
                    await asyncio.sleep(delay)

                except Exception as e:
                    self.logger.error(f"❌ [FUNDING_MONITOR] Erreur vérification périodique: {e}")
                    await asyncio.sleep(30)

        def thread_target():
            asyncio.run(check_loop_async())

        # Démarrer le thread de vérification périodique
        check_thread = threading.Thread(target=thread_target, daemon=True, name="FundingCloseMonitor")
        check_thread.start()
        self.logger.debug("🔄 [FUNDING_MONITOR] Thread de vérification périodique lancé")

    def _log_periodic_summary(self):
        """Émet un résumé d'activité au plus toutes les 60 secondes."""
        if not self.is_enabled():
            return
        now = time.time()
        if now - self._last_summary_ts < self._summary_interval:
            return

        self._last_summary_ts = now
        self.logger.info(
            f"[FUNDING] Summary positions={len(self._monitored_positions)} ordres_en_attente={len(self._pending_close_orders)} auto_close={self.is_enabled()}"
        )

    def _verify_position_exists(self, symbol: str) -> bool:
        """
        Vérifie si une position existe encore avec retry logic adaptatif.

        Args:
            symbol: Symbole à vérifier

        Returns:
            bool: True si la position existe et est active, False sinon
        """
        if not self.is_enabled():
            return False
        import time

        max_attempts = 8  # Plus de tentatives pour plus de robustesse
        base_delay = 3  # Délai de base plus court
        max_delay = 30  # Délai maximum pour éviter l'attente excessive

        # Vérifier d'abord si l'ordre a été exécuté (sans délai initial)
        if not self._check_order_execution(symbol):
            self.logger.warning(f"[FUNDING] ⚠️ Ordre {symbol} non exécuté - position probablement non ouverte")
            return False

        for attempt in range(max_attempts):
            try:
                positions = self.bybit_client.get_positions(category="linear", settleCoin="USDT")

                # Debug: Afficher la réponse de l'API
                self.logger.debug(f"🔍 Tentative {attempt + 1}/{max_attempts} - API Response pour {symbol}: {positions}")

                if positions and positions.get("list"):
                    all_positions = positions.get("list", [])
                    self.logger.debug(f"🔍 Toutes les positions: {[p.get('symbol') for p in all_positions]}")

                    matching = [p for p in all_positions if p.get("symbol") == symbol]
                    if matching:
                        position_data = matching[0]
                        size = position_data.get("size", "0")

                        self.logger.debug(f"🔍 Position {symbol}: size={size}")

                        if size and float(size) > 0:
                            self.logger.debug(f"✅ Position {symbol} confirmée (size={size}) - surveillance continue")
                            return True
                        else:
                            self.logger.debug(f"ℹ️ Position {symbol} fermée (size=0) - retirer de la surveillance")
                            return False

                # Délai adaptatif : plus court au début, plus long si nécessaire
                if attempt < max_attempts - 1:  # Pas d'attente après la dernière tentative
                    delay = min(base_delay * (2 ** attempt), max_delay)  # Délai exponentiel avec plafond
                    self.logger.debug(f"⏳ Position {symbol} non trouvée, tentative {attempt + 2} dans {delay}s...")
                    time.sleep(delay)

            except Exception as e:
                self.logger.error(f"❌ Erreur tentative {attempt + 1} pour {symbol}: {e}")
                if attempt < max_attempts - 1:
                    delay = 5 + (attempt * 2)
                    time.sleep(delay)

        # Si la position n'a pas été trouvée après toutes les tentatives
        self.logger.warning(f"[FUNDING] ⚠️ Position {symbol} non trouvée après {max_attempts} tentatives")
        return False

    def _check_order_execution(self, symbol: str) -> bool:
        """
        Vérifie si un ordre récent a été exécuté en vérifiant les ordres ouverts.

        Args:
            symbol: Symbole à vérifier

        Returns:
            bool: True si un ordre a été exécuté récemment (pas d'ordre ouvert trouvé)
        """
        try:
            if not self.is_enabled():
                return True
            # Récupérer les ordres ouverts
            open_orders = self.bybit_client.get_open_orders(category="linear", settleCoin="USDT")

            current_time = time.time()

            # Vérifier les ordres ouverts récents pour ce symbole
            if open_orders and open_orders.get("list"):
                for order in open_orders["list"]:
                    if order.get("symbol") == symbol:
                        order_time = int(order.get("createdTime", 0)) / 1000
                        if current_time - order_time < 300:  # 5 minutes
                            self.logger.debug(f"🔍 Ordre ouvert récent trouvé pour {symbol}: {order.get('orderId')}")
                            return False  # Ordre encore ouvert

            # Aucun ordre ouvert trouvé pour ce symbole - probablement exécuté
            self.logger.debug(f"✅ Aucun ordre ouvert trouvé pour {symbol} - probablement exécuté")
            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur vérification exécution ordre {symbol}: {e}")
            # En cas d'erreur, assumer qu'un ordre a pu être exécuté pour ne pas bloquer
            return True

    def _check_funding_and_monitor(self, symbol: str):
        """
        Vérifie le funding et continue la surveillance.

        Args:
            symbol: Symbole à surveiller
        """
        if not self.is_enabled():
            return
        self.logger.debug(f"🔍 [FUNDING_CHECK] Vérification du funding pour {symbol}")
        # Vérifier si le funding a été touché via API REST
        self._check_funding_event(symbol)
        self.logger.debug(f"ℹ️ [FUNDING_CHECK] Position {symbol} toujours active - surveillance continue")

    def _check_funding_event(self, symbol: str):
        """
        Vérifie si un événement de funding a eu lieu pour le symbole donné.
        Utilise l'API REST pour récupérer les données de funding.

        Args:
            symbol: Symbole à vérifier
        """
        if not self.is_enabled():
            return
        try:
            # Récupérer les données de funding via API REST
            funding_data = self.bybit_client.get_funding_rate(symbol=symbol)

            if funding_data and funding_data.get("list"):
                latest_funding = funding_data["list"][0]  # Le plus récent
                funding_rate = float(latest_funding.get("fundingRate", 0))
                funding_time = latest_funding.get("fundingRateTimestamp", "")

                self.logger.debug(f"🔍 [FUNDING_CHECK] Funding {symbol}: rate={funding_rate:.4f}, time={funding_time}")

                # Vérifier si c'est un nouveau funding (pas déjà traité)
                cache_key = f"{symbol}_{funding_time}"
                if cache_key not in self._last_funding_check:
                    # Vérifier si le funding est récent (dans les 5 dernières minutes)
                    import time
                    current_time = int(time.time() * 1000)  # Timestamp en millisecondes
                    funding_timestamp = int(funding_time) if funding_time else 0
                    time_diff_minutes = (current_time - funding_timestamp) / (1000 * 60)

                    self.logger.debug(f"🔍 [FUNDING_CHECK] Différence de temps: {time_diff_minutes:.1f} minutes")

                    # Fermer si le funding est récent (moins de 5 minutes) ET que la position est surveillée
                    if time_diff_minutes < 5 and symbol in self._monitored_positions:
                        self._last_funding_check[cache_key] = True

                        self.logger.debug(f"💰 [FUNDING] NOUVEAU funding détecté pour {symbol}: {funding_rate:.4f}")
                        self.logger.debug(f"🎯 [FUNDING] Position {symbol} est surveillée ! Fermeture automatique...")

                        # Fermeture automatique désactivée
                        self.logger.debug(f"[FUNDING_CLOSE_DISABLED] Pas de fermeture auto pour {symbol}")
                    elif symbol not in self._monitored_positions:
                        self.logger.debug(f"ℹ️ [FUNDING_CHECK] Position {symbol} non surveillée - pas de fermeture")
                    else:
                        self.logger.debug(f"ℹ️ [FUNDING_CHECK] Funding {symbol} trop ancien ({time_diff_minutes:.1f}min) - pas de fermeture")
                else:
                    self.logger.debug(f"ℹ️ [FUNDING_CHECK] Funding {symbol} déjà traité: {funding_rate:.4f}")
            else:
                self.logger.warning(f"[FUNDING] ⚠️ [FUNDING_CHECK] Aucune donnée de funding pour {symbol}")

        except Exception as e:
            self.logger.error(f"[FUNDING] ❌ [FUNDING_CHECK] Erreur vérification funding {symbol}: {e}")

    def start(self):
        """Démarre le gestionnaire de fermeture après funding."""
        if not self.is_enabled():
            self.logger.info("[FUNDING] 💤 FundingCloseManager désactivé — aucun thread démarré")
            return
        if not self._running:
            self._running = True

            # Vérifier les positions existantes au démarrage
            self.check_existing_positions()

            self._monitor_thread = threading.Thread(target=self._run_ws_client, daemon=True)
            self._monitor_thread.start()

            # Démarrer aussi la vérification périodique comme fallback
            self._check_positions_periodically()

            self.logger.info("[FUNDING] 💰 FundingCloseManager démarré")

    def stop(self):
        """Arrête le gestionnaire de fermeture après funding."""
        if self._running:
            self._running = False
            if self._ws_client:
                self._ws_client.close()
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5)
            self.logger.info("[FUNDING] 🛑 FundingCloseManager arrêté")

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
            if not self.is_enabled():
                self.logger.info("[FUNDING] 💤 Fermeture forcée ignorée (manager désactivé)")
                return
            self.logger.info(f"[FUNDING] 🔄 Fermeture forcée de la position {symbol}...")
            self._close_position_after_funding(symbol)
        except Exception as e:
            self.logger.error(f"❌ Erreur fermeture forcée {symbol}: {e}")

    def force_close_all_positions(self):
        """Force la fermeture de toutes les positions surveillées."""
        try:
            if not self.is_enabled():
                self.logger.info("[FUNDING] 💤 Fermeture forcée globale ignorée (manager désactivé)")
                return
            monitored = list(self._monitored_positions)
            self.logger.info(f"[FUNDING] 🔄 Fermeture forcée de toutes les positions: {monitored}")

            for symbol in monitored:
                self.force_close_position(symbol)

        except Exception as e:
            self.logger.error(f"❌ Erreur fermeture forcée toutes positions: {e}")

    def test_funding_detection(self, symbol: str):
        """
        Teste la détection de funding pour un symbole donné.
        Utile pour diagnostiquer les problèmes.

        Args:
            symbol: Symbole à tester
        """
        try:
            self.logger.debug(f"🧪 [TEST] Test de détection de funding pour {symbol}")
            self.logger.debug(f"🧪 [TEST] Position surveillée: {symbol in self._monitored_positions}")
            self.logger.debug(f"🧪 [TEST] Manager running: {self._running}")

            # Forcer la vérification
            self._check_funding_event(symbol)

        except Exception as e:
            self.logger.error(f"❌ [TEST] Erreur test funding {symbol}: {e}")
