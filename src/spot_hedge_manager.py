#!/usr/bin/env python3
"""
Gestionnaire de hedging spot automatique pour le bot Bybit.

Ce module gère le hedging automatique des positions perpetual en ouvrant
immédiatement une position spot inverse pour neutraliser le risque directionnel.

Fonctionnalités :
- Hedge automatique immédiat après ouverture position perp
- Fermeture automatique du spot en même temps que le perp
- Ordres limit PostOnly pour frais maker
- Gestion des erreurs et retry logic
- Tracking des hedges actifs
"""

import asyncio
import time
import threading
from typing import Dict, Any, Optional, NamedTuple
from collections import namedtuple
from logging_setup import setup_logging
from order_monitor import OrderMonitor
from smart_order_placer import SmartOrderPlacer
from utils.async_wrappers import run_in_thread
from interfaces.spot_hedge_manager_interface import SpotHedgeManagerInterface

# Structure pour tracker les informations de hedge
HedgeInfo = namedtuple('HedgeInfo', [
    'perp_side',      # Side de la position perp ("Buy" ou "Sell")
    'spot_order_id',  # ID de l'ordre spot placé
    'spot_side',      # Side de l'ordre spot ("Buy" ou "Sell")
    'spot_size',      # Taille de l'ordre spot
    'spot_price',     # Prix de l'ordre spot
    'perp_size',      # Taille de la position perp (pour référence)
    'perp_price'      # Prix de la position perp (pour référence)
])


class SpotHedgeManager(SpotHedgeManagerInterface):
    """
    Gestionnaire de hedging spot automatique.

    Cette classe surveille les positions perpetual et place automatiquement
    des ordres spot inverses pour neutraliser le risque directionnel.
    """

    def __init__(
        self,
        testnet: bool,
        logger,
        bybit_client,
        auto_trading_config: Dict[str, Any],
        spot_checker=None
    ):
        """
        Initialise le gestionnaire de hedging spot.

        Args:
            testnet: Mode testnet ou mainnet
            logger: Logger pour les messages
            bybit_client: Client Bybit pour passer les ordres
            auto_trading_config: Configuration du trading automatique
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()
        self.bybit_client = bybit_client
        self.auto_trading_config = auto_trading_config
        self.spot_checker = spot_checker

        # Configuration du hedging spot
        self.spot_hedge_config = auto_trading_config.get('spot_hedge', {})
        self.enabled = self.spot_hedge_config.get('enabled', False)

        # Tracking des hedges actifs
        self._active_hedges: Dict[str, HedgeInfo] = {}

        # Thread safety
        self._lock = threading.Lock()

        # OrderMonitor pour surveiller les ordres spot
        self.order_monitor = OrderMonitor(
            bybit_client=bybit_client,
            logger=logger,
            on_order_timeout=self._handle_spot_order_timeout
        )

        # Smart Order Placer pour les ordres spot intelligents
        maker_cfg = auto_trading_config.get('maker', {}) if auto_trading_config else {}
        if bybit_client:
            self.smart_placer = SmartOrderPlacer(bybit_client, logger, maker_cfg)
        else:
            self.smart_placer = None
            if self.enabled:
                self.logger.warning("⚠️ [SPOT_HEDGE] bybit_client est None mais hedging activé - hedge désactivé")
                self.enabled = False

        # Configuration des paramètres
        self.offset_percent = self.spot_hedge_config.get('offset_percent', 0.02) / 100
        self.timeout_minutes = self.spot_hedge_config.get('timeout_minutes', 30)
        self.retry_on_reject = self.spot_hedge_config.get('retry_on_reject', True)
        self.max_retry_offset_percent = self.spot_hedge_config.get('max_retry_offset_percent', 0.1) / 100

        # Limite de retry pour éviter les boucles infinies PostOnly
        self.max_postonly_retries = 3  # Maximum 3 tentatives PostOnly
        self.symbol_retry_count = {}  # Compteur de retry par symbole

        if self.enabled:
            self.logger.info("🔄 SpotHedgeManager initialisé (hedging activé)")
        else:
            self.logger.info("ℹ️ SpotHedgeManager initialisé (hedging désactivé)")

    async def on_perp_position_opened(self, symbol: str, position_data: Dict[str, Any]) -> None:
        """
        Appelé quand une position perp est ouverte - place le hedge spot.

        Args:
            symbol: Symbole de la position perp (ex: "BTCUSDT")
            position_data: Données de la position perp
        """
        if not self.enabled:
            return

        # Vérifier que smart_placer est disponible
        if not self.smart_placer:
            self.logger.error(f"❌ [SPOT_HEDGE] smart_placer non disponible - hedge impossible pour {symbol}")
            return

        try:
            self.logger.info(f"🔄 [SPOT_HEDGE] Position perp ouverte détectée: {symbol}")

            # Vérifier disponibilité spot
            if not await self._check_spot_availability(symbol):
                return

            # Extraire et valider les données de position perp
            perp_data = await self._extract_perp_position_data(symbol, position_data)
            if not perp_data:
                return

            perp_side, perp_size, perp_size_float, perp_price = perp_data
            spot_side = "Sell" if perp_side == "Buy" else "Buy"
            spot_symbol = symbol  # Même symbole, category différente

            # Récupérer le prix actuel du marché spot
            current_price = await self._get_current_spot_price_async(spot_symbol)
            if not current_price:
                return

            # Calculer la quantité spot nécessaire
            spot_size = await self._calculate_spot_hedge_quantity(
                symbol, perp_size, perp_size_float, perp_price, position_data, current_price
            )
            if not spot_size:
                return

            # S'assurer d'avoir le solde nécessaire (achat préalable si vente)
            spot_size = await self._ensure_spot_balance_for_sell(
                symbol, spot_symbol, spot_side, spot_size, current_price
            )
            if not spot_size:
                return

            # Calculer le prix limite avec offset
            limit_price = self._calculate_hedge_price(symbol, spot_side, current_price)

            # Valider la logique du hedge
            if not self._validate_hedge_logic(symbol, perp_side, spot_side):
                return

            # Placer l'ordre spot
            success = await run_in_thread(
                self._place_spot_hedge_order,
                symbol=spot_symbol,
                side=spot_side,
                size=spot_size,
                price=limit_price,
                perp_side=perp_side,
                perp_size=perp_size,
                perp_price=perp_price
            )

            if success:
                self.logger.info(f"✅ [SPOT_HEDGE] Hedge placé avec succès pour {symbol}")
                self.logger.info("Hedge exécuté")
            else:
                self.logger.error(f"❌ [SPOT_HEDGE] Échec placement hedge pour {symbol}")

        except Exception as e:
            self.logger.error(f"❌ [SPOT_HEDGE] Erreur hedge {symbol}: {e}")

    async def _check_spot_availability(self, symbol: str) -> bool:
        """
        Vérifie si un symbole est disponible en spot.

        Args:
            symbol: Symbole à vérifier

        Returns:
            True si disponible, False sinon
        """
        if hasattr(self, 'spot_checker') and self.spot_checker:
            if not self.spot_checker.is_spot_available(symbol):
                self.logger.warning(
                    f"⚠️ [SPOT_HEDGE] Symbole {symbol} non disponible en spot - hedge ignoré"
                )
                return False
            return True
        else:
            # Fallback to old method if spot_checker not available
            self.logger.debug("[ASYNC] Bybit REST call exécuté dans un thread : _is_spot_symbol_available()")
            is_available = await run_in_thread(self._is_spot_symbol_available, symbol)
            if not is_available:
                self.logger.warning(f"⚠️ [SPOT_HEDGE] Symbole {symbol} non disponible en spot - hedge ignoré")
                return False
            return True

    async def _extract_perp_position_data(
        self, symbol: str, position_data: Dict[str, Any]
    ) -> Optional[tuple]:
        """
        Extrait et valide les données de position perp.

        Args:
            symbol: Symbole de la position
            position_data: Données brutes de la position

        Returns:
            Tuple (perp_side, perp_size, perp_size_float, perp_price) ou None si invalide
        """
        perp_side = position_data.get('side', '')
        perp_size = position_data.get('size', '0')
        perp_price = position_data.get('price', 0)

        try:
            perp_size_float = abs(float(perp_size))
        except (ValueError, TypeError):
            perp_size_float = 0.0

        if not perp_side or perp_size_float == 0:
            self.logger.warning(f"⚠️ [SPOT_HEDGE] Données position perp invalides pour {symbol}")
            return None

        return (perp_side, perp_size, perp_size_float, perp_price)

    async def _get_current_spot_price_async(self, symbol: str) -> Optional[float]:
        """
        Récupère le prix actuel du marché spot de manière asynchrone.

        Args:
            symbol: Symbole spot

        Returns:
            Prix actuel ou None si erreur
        """
        self.logger.debug("[ASYNC] Bybit REST call exécuté dans un thread : _get_current_spot_price()")
        current_price = await run_in_thread(self._get_current_spot_price, symbol)
        if not current_price:
            self.logger.error(f"❌ [SPOT_HEDGE] Impossible de récupérer le prix spot pour {symbol}")
            return None
        return current_price

    async def _calculate_spot_hedge_quantity(
        self,
        symbol: str,
        perp_size: str,
        perp_size_float: float,
        perp_price: Any,
        position_data: Dict[str, Any],
        current_price: float
    ) -> Optional[str]:
        """
        Calcule la quantité spot nécessaire pour le hedge.

        Args:
            symbol: Symbole
            perp_size: Taille perp (string)
            perp_size_float: Taille perp (float)
            perp_price: Prix perp
            position_data: Données complètes de la position
            current_price: Prix actuel spot

        Returns:
            Quantité spot formatée ou None si erreur
        """
        try:
            perp_value_usdt = None
            for field in ("positionValue", "position_value", "positionValueAbs", "positionValueUsd"):
                raw_value = position_data.get(field)
                if raw_value not in (None, ""):
                    try:
                        perp_value_usdt = abs(float(raw_value))
                        break
                    except (ValueError, TypeError):
                        continue

            if perp_value_usdt is None:
                try:
                    perp_price_float = float(perp_price) if perp_price else current_price
                except (ValueError, TypeError):
                    perp_price_float = current_price
                perp_value_usdt = perp_size_float * perp_price_float

            perp_value_usdt = abs(perp_value_usdt)

            min_order_value_usdt = 5.0
            target_value_usdt = max(perp_value_usdt, min_order_value_usdt)
            spot_size_float = target_value_usdt / current_price

            spot_size = self.smart_placer.quantity_formatter.format_quantity(
                symbol, spot_size_float, "spot", round_up=True
            )

            try:
                final_spot_value = float(spot_size) * current_price
            except (ValueError, TypeError):
                final_spot_value = target_value_usdt

            self.logger.info(
                f"📊 [SPOT_HEDGE] Calcul spot: perp={perp_size} → valeur={perp_value_usdt:.2f} USDT → "
                f"spot={spot_size} @ {current_price:.6f} = {final_spot_value:.2f} USDT"
            )

            return spot_size

        except (ValueError, TypeError) as e:
            self.logger.warning(f"⚠️ [SPOT_HEDGE] Erreur calcul quantité spot: {e}")
            return str(perp_size_float)

    async def _ensure_spot_balance_for_sell(
        self,
        symbol: str,
        spot_symbol: str,
        spot_side: str,
        spot_size: str,
        current_price: float
    ) -> Optional[str]:
        """
        S'assure d'avoir le solde nécessaire pour une vente spot (achat préalable si nécessaire).

        Args:
            symbol: Symbole
            spot_symbol: Symbole spot
            spot_side: Côté de l'ordre spot
            spot_size: Quantité spot formatée
            current_price: Prix actuel

        Returns:
            Quantité spot ajustée ou None si erreur
        """
        if spot_side == "Sell":
            # Vérifier si on a déjà les tokens en spot
            available_spot_balance = await run_in_thread(self._get_spot_balance, symbol)
            spot_size_float = float(spot_size)
            
            if available_spot_balance < spot_size_float:
                # Besoin d'acheter les tokens spot d'abord
                needed_qty = spot_size_float - available_spot_balance
                self.logger.info(
                    f"💰 [SPOT_HEDGE] Achat préalable nécessaire pour {symbol}: "
                    f"besoin={spot_size_float:.6f}, disponible={available_spot_balance:.6f}, "
                    f"à acheter={needed_qty:.6f}"
                )
                
                # Formater la quantité à acheter
                qty_to_buy = self.smart_placer.quantity_formatter.format_quantity(
                    symbol, needed_qty, "spot", round_up=True
                )
                
                # Acheter les tokens spot
                buy_success = await run_in_thread(
                    self._buy_spot_tokens_for_hedge,
                    symbol=spot_symbol,
                    qty=qty_to_buy,
                    current_price=current_price
                )
                
                if not buy_success:
                    self.logger.error(
                        f"❌ [SPOT_HEDGE] Échec achat préalable {symbol} - hedge annulé"
                    )
                    return None
                
                self.logger.info(f"✅ [SPOT_HEDGE] Tokens spot achetés pour hedge {symbol}")
                
                # Attendre un court délai pour que les tokens soient disponibles
                await asyncio.sleep(1.0)
                
                # Vérifier à nouveau le solde après l'achat
                new_spot_balance = await run_in_thread(self._get_spot_balance, symbol)
                self.logger.info(
                    f"🔍 [SPOT_HEDGE] Solde spot après achat {symbol}: {new_spot_balance:.6f}"
                )
                
                # Ajuster la quantité de vente au solde réel disponible
                if new_spot_balance < spot_size_float:
                    spot_size_float = new_spot_balance
                    spot_size = self.smart_placer.quantity_formatter.format_quantity(
                        symbol, spot_size_float, "spot", round_up=False
                    )
                    self.logger.warning(
                        f"⚠️ [SPOT_HEDGE] Ajustement quantité vente {symbol}: {spot_size} (solde disponible)"
                    )
                else:
                    # IMPORTANT : Recalculer spot_size avec spot_size_float pour garantir la quantité exacte
                    spot_size = self.smart_placer.quantity_formatter.format_quantity(
                        symbol, spot_size_float, "spot", round_up=True
                    )
                    self.logger.info(
                        f"✅ [SPOT_HEDGE] Solde suffisant pour vente {symbol}: "
                        f"{new_spot_balance:.6f} >= {spot_size_float:.6f}, "
                        f"quantité à vendre: {spot_size} (valeur: {float(spot_size) * current_price:.2f} USDT)"
                    )
            else:
                self.logger.info(
                    f"✅ [SPOT_HEDGE] Solde spot suffisant pour {symbol}: "
                    f"disponible={available_spot_balance:.6f}, besoin={spot_size_float:.6f}"
                )
        else:
            # Pour acheter en spot (hedge d'une position perp Sell), vérifier USDT
            available_usdt = await run_in_thread(self._get_usdt_spot_balance)
            required_usdt = float(spot_size) * current_price
            
            if available_usdt < required_usdt:
                self.logger.warning(
                    f"⚠️ [SPOT_HEDGE] Solde USDT spot insuffisant pour {symbol}: "
                    f"demandé={required_usdt:.2f} USDT, disponible={available_usdt:.2f} USDT. "
                    f"Hedge peut échouer."
                )
            else:
                self.logger.info(
                    f"✅ [SPOT_HEDGE] Solde USDT suffisant pour {symbol}: "
                    f"disponible={available_usdt:.2f} USDT, besoin={required_usdt:.2f} USDT"
                )

        return spot_size

    def _calculate_hedge_price(self, symbol: str, spot_side: str, current_price: float) -> float:
        """
        Calcule le prix limite avec offset pour le hedge.

        Args:
            symbol: Symbole
            spot_side: Côté de l'ordre spot
            current_price: Prix actuel du marché

        Returns:
            Prix limite formaté
        """
        if spot_side == "Buy":
            limit_price_float = current_price * (1 - self.offset_percent)  # Prix légèrement en dessous
        else:
            limit_price_float = current_price * (1 + self.offset_percent)  # Prix légèrement au-dessus

        limit_price_formatted = self.smart_placer.price_formatter.format_price(
            symbol, limit_price_float, "spot"
        )
        try:
            limit_price = float(limit_price_formatted)
        except (ValueError, TypeError):
            limit_price = limit_price_float

        return limit_price

    def _validate_hedge_logic(self, symbol: str, perp_side: str, spot_side: str) -> bool:
        """
        Valide que la logique du hedge est correcte.

        Args:
            symbol: Symbole
            perp_side: Côté de la position perp
            spot_side: Côté de l'ordre spot

        Returns:
            True si valide, False sinon
        """
        # Vérification critique : s'assurer que spot_side est bien "Sell" pour hedger un perp Buy
        if perp_side == "Buy" and spot_side != "Sell":
            self.logger.error(
                f"❌ [SPOT_HEDGE] ERREUR LOGIQUE: perp_side=Buy mais spot_side={spot_side} (devrait être Sell)! "
                f"Hedge annulé pour éviter double exposition."
            )
            return False
        
        if perp_side == "Sell" and spot_side != "Buy":
            self.logger.error(
                f"❌ [SPOT_HEDGE] ERREUR LOGIQUE: perp_side=Sell mais spot_side={spot_side} (devrait être Buy)! "
                f"Hedge annulé pour éviter double exposition."
            )
            return False

        self.logger.info(
            f"🔄 [SPOT_HEDGE] Calcul hedge {symbol}: perp={perp_side}, spot={spot_side} "
            f"(offset: {self.offset_percent*100:.2f}%)"
        )

        self.logger.info(
            f"📤 [SPOT_HEDGE] Placement ordre hedge {symbol}: side={spot_side} (hedge de perp {perp_side})"
        )

        return True

    def _track_hedge_order(
        self,
        symbol: str,
        order_id: str,
        spot_side: str,
        spot_size: str,
        spot_price: float,
        perp_side: str,
        perp_size: str,
        perp_price: float
    ) -> None:
        """
        Track un ordre hedge dans le système de suivi.

        Args:
            symbol: Symbole du hedge
            order_id: ID de l'ordre spot
            spot_side: Côté de l'ordre spot
            spot_size: Taille de l'ordre spot
            spot_price: Prix de l'ordre spot
            perp_side: Côté de la position perp
            perp_size: Taille de la position perp
            perp_price: Prix de la position perp
        """
        with self._lock:
            self._active_hedges[symbol] = HedgeInfo(
                perp_side=perp_side,
                spot_order_id=order_id,
                spot_side=spot_side,
                spot_size=spot_size,
                spot_price=spot_price,
                perp_size=perp_size,
                perp_price=perp_price
            )

        # Ajouter à l'OrderMonitor pour surveillance timeout
        if self.order_monitor and order_id != "dry_run_order":
            self.order_monitor.add_order(
                order_id=order_id,
                symbol=symbol,
                side=spot_side,
                qty=spot_size,
                price=spot_price,
                timeout_minutes=self.timeout_minutes
            )

    def on_perp_position_closed(self, symbol: str, position_data: Dict[str, Any]) -> None:
        """
        Appelé quand une position perp est fermée - ferme le hedge spot.

        Args:
            symbol: Symbole de la position perp fermée
            position_data: Données de la position perp
        """
        if not self.enabled:
            return

        try:
            with self._lock:
                if symbol not in self._active_hedges:
                    self.logger.debug(f"ℹ️ [SPOT_HEDGE] Aucun hedge actif pour {symbol}")
                    return

                hedge_info = self._active_hedges[symbol]
                self.logger.info(f"🔄 [SPOT_HEDGE] Fermeture hedge pour {symbol}")

                # Fermer le spot avec un ordre inverse
                success = self._close_spot_hedge(symbol, hedge_info)

                if success:
                    # Retirer du tracking
                    del self._active_hedges[symbol]
                    self.logger.info(f"✅ [SPOT_HEDGE] Hedge fermé pour {symbol}")
                else:
                    self.logger.error(f"❌ [SPOT_HEDGE] Échec fermeture hedge pour {symbol}")

        except Exception as e:
            self.logger.error(f"❌ [SPOT_HEDGE] Erreur fermeture hedge {symbol}: {e}")

    def _place_spot_hedge_order(
        self,
        symbol: str,
        side: str,
        size: str,
        price: float,
        perp_side: str,
        perp_size: str,
        perp_price: float
    ) -> bool:
        """
        Place un ordre spot pour le hedge.

        Args:
            symbol: Symbole spot
            side: Côté de l'ordre ("Buy" ou "Sell")
            size: Taille de l'ordre
            price: Prix limite
            perp_side: Côté de la position perp (pour référence)
            perp_size: Taille de la position perp (pour référence)
            perp_price: Prix de la position perp (pour référence)

        Returns:
            True si l'ordre a été placé avec succès
        """
        try:
            executed_price = price
            
            # Log détaillé du side exact de l'ordre
            hedge_type = "VENTE (hedge perp Buy)" if side == "Sell" and perp_side == "Buy" else \
                        "ACHAT (hedge perp Sell)" if side == "Buy" and perp_side == "Sell" else \
                        f"ORDRE {side} (perp {perp_side})"
            self.logger.info(
                f"🔍 [SPOT_HEDGE] Placement ordre {symbol}: {hedge_type}, side={side}, qty={size}, price={price:.6f}"
            )
            
            # Vérifier le mode dry-run / shadow mode global
            if self.auto_trading_config.get('dry_run', False) or self.auto_trading_config.get('shadow_mode', False):
                self.logger.info(f"🧪 [SPOT_HEDGE] [DRY-RUN] Ordre spot simulé pour {symbol}: {side} {size} @ {price:.6f} ({hedge_type})")

                # Simuler un hedge actif en mode dry-run
                self._track_hedge_order(
                    symbol=symbol,
                    order_id="dry_run_order",
                    spot_side=side,
                    spot_size=size,
                    spot_price=price,
                    perp_side=perp_side,
                    perp_size=perp_size,
                    perp_price=perp_price
                )
                return True

            # Utiliser le Smart Order Placer pour un placement intelligent maker
            # IMPORTANT: force_exact_quantity=True pour garantir que la quantité de hedge ne soit jamais réduite
            result = self.smart_placer.place_order_with_refresh(
                symbol=symbol,
                side=side,
                qty=size,
                category="spot",
                force_exact_quantity=True  # Garantir un hedge exact sans réduction de quantité
            )

            if not result.success:
                self.logger.error(
                    f"❌ [SPOT_HEDGE] Échec placement intelligent {symbol}: {result.error_message} "
                    f"(side={side}, hedge de perp {perp_side})"
                )
                return False

            order_id = result.order_id
            executed_price = result.price if result.price is not None else price
            self.logger.info(
                f"✅ [SPOT_HEDGE] Ordre spot intelligent placé {symbol}: {hedge_type}, ID={order_id}, "
                f"side={side}, price={executed_price:.6f}, offset={result.offset_percent*100:.3f}%, "
                f"liquidity={result.liquidity_level}, retry={result.retry_count}"
            )

            # Réinitialiser le compteur de retry pour ce symbole en cas de succès
            if symbol in self.symbol_retry_count:
                del self.symbol_retry_count[symbol]

            # Ordre accepté - tracker le hedge
            self._track_hedge_order(
                symbol=symbol,
                order_id=order_id,
                spot_side=side,
                spot_size=size,
                spot_price=executed_price,
                perp_side=perp_side,
                perp_size=perp_size,
                perp_price=perp_price
            )

            self.logger.info(
                f"✅ [SPOT_HEDGE] Ordre spot placé pour {symbol} ({hedge_type}): "
                f"OrderID={order_id}, side={side}, qty={size}, price={executed_price:.6f}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"❌ [SPOT_HEDGE] Erreur placement ordre spot {symbol} ({hedge_type}, side={side}): {e}"
            )
            return False

    def _retry_spot_order_with_larger_offset(
        self,
        symbol: str,
        side: str,
        size: str,
        original_price: float,
        perp_side: str,
        perp_size: str,
        perp_price: float
    ) -> bool:
        """
        Réessaie l'ordre spot avec un offset plus large.

        Args:
            symbol: Symbole spot
            side: Côté de l'ordre
            size: Taille de l'ordre
            original_price: Prix original
            perp_side: Côté de la position perp
            perp_size: Taille de la position perp
            perp_price: Prix de la position perp

        Returns:
            True si l'ordre a été placé avec succès
        """
        try:
            # Incrémenter le compteur de retry pour ce symbole
            retry_count = self.symbol_retry_count.get(symbol, 0) + 1
            self.symbol_retry_count[symbol] = retry_count

            # Calculer le nouveau prix avec offset progressif
            base_offset = self.offset_percent
            larger_offset = base_offset * (2 ** retry_count)  # Double l'offset à chaque retry
            larger_offset = min(larger_offset, self.max_retry_offset_percent)  # Plafonner

            if side == "Buy":
                retry_price = original_price * (1 - larger_offset)
            else:
                retry_price = original_price * (1 + larger_offset)

            # Formater le prix selon les contraintes de précision
            retry_price_formatted = self.smart_placer.price_formatter.format_price(symbol, retry_price, "spot")
            try:
                retry_price = float(retry_price_formatted)
            except (ValueError, TypeError):
                pass  # Garder retry_price tel quel si conversion échoue

            self.logger.info(f"🔄 [SPOT_HEDGE] Retry {symbol} avec prix {retry_price} (offset: {larger_offset*100:.2f}%)")

            # Réessayer avec le nouveau prix (via smart_placer pour cohérence)
            response = self.smart_placer.bybit_client.place_order(
                symbol=symbol,
                side=side,
                order_type="Limit",
                qty=size,
                price=str(retry_price),
                category="spot",
                time_in_force="GTC"
            )

            order_id = response.get('orderId')

            if not order_id:
                self.logger.error(f"❌ [SPOT_HEDGE] Retry échoué pour {symbol}: {response}")
                return False

            # Succès - tracker le hedge
            self._track_hedge_order(
                symbol=symbol,
                order_id=order_id,
                spot_side=side,
                spot_size=size,
                spot_price=retry_price,
                perp_side=perp_side,
                perp_size=perp_size,
                perp_price=perp_price
            )

            # Réinitialiser le compteur de retry pour ce symbole en cas de succès
            if symbol in self.symbol_retry_count:
                del self.symbol_retry_count[symbol]

            self.logger.info(f"✅ [SPOT_HEDGE] Retry réussi pour {symbol} - OrderID: {order_id}")
            return True

        except Exception as e:
            self.logger.error(f"❌ [SPOT_HEDGE] Erreur retry {symbol}: {e}")
            return False

    def _close_spot_hedge(self, symbol: str, hedge_info: HedgeInfo) -> bool:
        """
        Ferme un hedge spot actif.

        Args:
            symbol: Symbole du hedge
            hedge_info: Informations du hedge à fermer

        Returns:
            True si la fermeture a réussi
        """
        try:
            # Annuler l'ordre spot en attente s'il existe
            if hedge_info.spot_order_id and hedge_info.spot_order_id != "dry_run_order":
                try:
                    self.bybit_client.cancel_order(
                        symbol=symbol,
                        order_id=hedge_info.spot_order_id,
                        category="spot"
                    )
                    self.logger.info(f"🔄 [SPOT_HEDGE] Ordre spot annulé pour {symbol} - OrderID: {hedge_info.spot_order_id}")
                except Exception as e:
                    self.logger.warning(f"⚠️ [SPOT_HEDGE] Erreur annulation ordre {symbol}: {e}")

            # En mode dry-run, pas besoin de fermer réellement
            if self.auto_trading_config.get('dry_run', False):
                self.logger.info(f"🧪 [SPOT_HEDGE] [DRY-RUN] Fermeture hedge simulée pour {symbol}")
                return True

            # Fermer avec un ordre Market pour garantir l'exécution
            close_side = "Sell" if hedge_info.spot_side == "Buy" else "Buy"

            close_response = self.smart_placer.bybit_client.place_order(
                symbol=symbol,
                side=close_side,
                order_type="Market",
                qty=hedge_info.spot_size,
                category="spot"
            )

            if close_response and close_response.get("orderId"):
                self.logger.info(f"✅ [SPOT_HEDGE] Hedge fermé avec Market pour {symbol} - OrderID: {close_response['orderId']}")
                return True
            else:
                self.logger.error(f"❌ [SPOT_HEDGE] Échec fermeture Market {symbol}: {close_response}")
                return False

        except Exception as e:
            self.logger.error(f"❌ [SPOT_HEDGE] Erreur fermeture hedge {symbol}: {e}")
            return False

    def _is_spot_symbol_available(self, symbol: str) -> bool:
        """
        Vérifie si un symbole est disponible en spot sur Bybit.

        Args:
            symbol: Symbole à vérifier

        Returns:
            True si le symbole existe en spot, False sinon
        """
        try:
            # Essayer de récupérer les tickers spot pour ce symbole
            ticker_data = self.bybit_client.get_tickers(symbol=symbol, category="spot")

            if ticker_data and ticker_data.get("list") and len(ticker_data["list"]) > 0:
                return True

            return False

        except Exception as e:
            # Si erreur API (ex: "Not supported symbols"), le symbole n'existe pas en spot
            self.logger.debug(f"🔍 [SPOT_HEDGE] Symbole {symbol} non disponible en spot: {e}")
            return False

    def _get_current_spot_price(self, symbol: str) -> Optional[float]:
        """
        Récupère le prix actuel du marché spot.

        Args:
            symbol: Symbole spot

        Returns:
            Prix actuel ou None si erreur
        """
        try:
            ticker_data = self.bybit_client.get_tickers(symbol=symbol, category="spot")

            if ticker_data and ticker_data.get("list"):
                latest_ticker = ticker_data["list"][0]
                last_price = latest_ticker.get("lastPrice")
                if last_price:
                    return float(last_price)

            self.logger.warning(f"⚠️ [SPOT_HEDGE] Impossible de récupérer le prix spot pour {symbol}")
            return None

        except Exception as e:
            self.logger.error(f"❌ [SPOT_HEDGE] Erreur récupération prix spot {symbol}: {e}")
            return None

    def _get_spot_balance(self, symbol: str) -> float:
        """
        Récupère le solde spot disponible pour un symbole.
        
        Args:
            symbol: Symbole (ex: "MMTUSDT")
            
        Returns:
            Solde disponible en float (0.0 si erreur ou non disponible)
        """
        try:
            # Extraire le coin de base (ex: "MMT" de "MMTUSDT")
            base_coin = symbol.replace("USDT", "").replace("USDC", "").replace("BTC", "").replace("ETH", "")
            
            # Essayer d'abord avec SPOT, puis fallback sur UNIFIED si erreur
            try:
                balance_response = self.bybit_client.get_wallet_balance(account_type="SPOT")
                # Vérifier si la réponse contient une erreur
                ret_code = balance_response.get("retCode", 0) if balance_response else 0
                ret_msg = balance_response.get("retMsg", "") if balance_response else ""
                
                if ret_code != 0 and ("only support UNIFIED" in str(ret_msg) or ret_code == 10001):
                    raise RuntimeError(f"accountType only support UNIFIED")  # Forcer le fallback
                    
            except RuntimeError as e:
                # Si erreur "only support UNIFIED", utiliser UNIFIED
                error_msg = str(e)
                if "only support UNIFIED" in error_msg or "retCode=10001" in error_msg or "10001" in error_msg:
                    self.logger.debug(f"🔄 [SPOT_HEDGE] SPOT non supporté, utilisation UNIFIED pour {symbol}")
                    balance_response = self.bybit_client.get_wallet_balance(account_type="UNIFIED")
                else:
                    # Autre erreur, propager
                    raise
            
            if not balance_response or balance_response.get("retCode") != 0:
                self.logger.warning(f"⚠️ [SPOT_HEDGE] Impossible de récupérer le solde pour {symbol}")
                return 0.0
            
            # Extraire le solde de la coin de base
            result = balance_response.get("result", {})
            account_list = result.get("list", []) if result else balance_response.get("list", [])
            if not account_list:
                return 0.0
            
            account = account_list[0]
            coins = account.get("coin", [])
            
            for coin in coins:
                if coin.get("coin") == base_coin:
                    available_balance = coin.get("availableToWithdraw", "0")
                    wallet_balance = coin.get("walletBalance", "0")
                    balance_str = available_balance if available_balance and float(available_balance) > 0 else wallet_balance
                    try:
                        return float(balance_str)
                    except (ValueError, TypeError):
                        return 0.0
            
            return 0.0
            
        except Exception as e:
            self.logger.warning(f"⚠️ [SPOT_HEDGE] Erreur récupération solde spot {symbol}: {e}")
            return 0.0

    def _get_usdt_spot_balance(self) -> float:
        """
        Récupère le solde USDT disponible en spot.
        
        Returns:
            Solde USDT disponible en float (0.0 si erreur)
        """
        try:
            # Essayer d'abord avec SPOT, puis fallback sur UNIFIED si erreur
            try:
                balance_response = self.bybit_client.get_wallet_balance(account_type="SPOT")
                # Vérifier si la réponse contient une erreur
                ret_code = balance_response.get("retCode", 0) if balance_response else 0
                ret_msg = balance_response.get("retMsg", "") if balance_response else ""
                
                if ret_code != 0 and ("only support UNIFIED" in str(ret_msg) or ret_code == 10001):
                    raise RuntimeError(f"accountType only support UNIFIED")  # Forcer le fallback
                    
            except RuntimeError as e:
                # Si erreur "only support UNIFIED", utiliser UNIFIED
                error_msg = str(e)
                if "only support UNIFIED" in error_msg or "retCode=10001" in error_msg or "10001" in error_msg:
                    self.logger.debug(f"🔄 [SPOT_HEDGE] SPOT non supporté, utilisation UNIFIED pour USDT")
                    balance_response = self.bybit_client.get_wallet_balance(account_type="UNIFIED")
                else:
                    # Autre erreur, propager
                    raise
            
            if not balance_response or balance_response.get("retCode") != 0:
                self.logger.warning(f"⚠️ [SPOT_HEDGE] Impossible de récupérer le solde USDT")
                return 0.0
            
            result = balance_response.get("result", {})
            account_list = result.get("list", []) if result else balance_response.get("list", [])
            if not account_list:
                return 0.0
            
            account = account_list[0]
            coins = account.get("coin", [])
            
            for coin in coins:
                if coin.get("coin") == "USDT":
                    available_balance = coin.get("availableToWithdraw", "0")
                    wallet_balance = coin.get("walletBalance", "0")
                    balance_str = available_balance if available_balance and float(available_balance) > 0 else wallet_balance
                    try:
                        return float(balance_str)
                    except (ValueError, TypeError):
                        return 0.0
            
            return 0.0
            
        except Exception as e:
            self.logger.warning(f"⚠️ [SPOT_HEDGE] Erreur récupération solde USDT spot: {e}")
            return 0.0

    def _buy_spot_tokens_for_hedge(
        self,
        symbol: str,
        qty: str,
        current_price: float
    ) -> bool:
        """
        Achète les tokens spot nécessaires pour le hedge.
        
        Args:
            symbol: Symbole spot
            qty: Quantité à acheter (en tokens)
            current_price: Prix actuel du marché
            
        Returns:
            True si l'achat a réussi
        """
        try:
            self.logger.info(
                f"💰 [SPOT_HEDGE] Achat spot préalable {symbol}: {qty} @ ~{current_price:.6f}"
            )
            
            # Utiliser SmartOrderPlacer pour l'achat
            # IMPORTANT: force_exact_quantity=True pour garantir qu'on achète exactement la quantité nécessaire
            result = self.smart_placer.place_order_with_refresh(
                symbol=symbol,
                side="Buy",
                qty=qty,
                category="spot",
                force_exact_quantity=True  # Garantir l'achat exact de la quantité nécessaire pour le hedge
            )
            
            if result.success:
                self.logger.info(
                    f"✅ [SPOT_HEDGE] Achat spot réussi {symbol}: OrderID={result.order_id}"
                )
                return True
            else:
                self.logger.error(
                    f"❌ [SPOT_HEDGE] Échec achat spot {symbol}: {result.error_message}"
                )
                return False
                    
        except Exception as e:
            self.logger.error(f"❌ [SPOT_HEDGE] Erreur achat spot {symbol}: {e}")
            return False

    def _handle_spot_order_timeout(self, order_id: str, symbol: str, side: str, qty: str, price: float):
        """
        Callback appelé quand un ordre spot expire.

        Args:
            order_id: ID de l'ordre expiré
            symbol: Symbole de l'ordre
            side: Côté de l'ordre
            qty: Quantité
            price: Prix de l'ordre
        """
        try:
            self.logger.warning(f"⏰ [SPOT_HEDGE] Timeout ordre spot pour {symbol} - OrderID: {order_id}")

            # Retirer le hedge du tracking
            with self._lock:
                if symbol in self._active_hedges:
                    del self._active_hedges[symbol]

            # Placer un ordre Market pour garantir l'exécution
            self.logger.info(f"🔄 [SPOT_HEDGE] Fallback Market pour {symbol}")

            market_response = self.smart_placer.bybit_client.place_order(
                symbol=symbol,
                side=side,
                order_type="Market",
                qty=qty,
                category="spot"
            )

            if market_response and market_response.get("orderId"):
                self.logger.info(f"✅ [SPOT_HEDGE] Fallback Market réussi pour {symbol} - OrderID: {market_response['orderId']}")
            else:
                self.logger.error(f"❌ [SPOT_HEDGE] Échec Fallback Market {symbol}: {market_response}")

        except Exception as e:
            self.logger.error(f"❌ [SPOT_HEDGE] Erreur timeout {symbol}: {e}")

    def get_active_hedges(self) -> Dict[str, HedgeInfo]:
        """
        Retourne les hedges actifs.

        Returns:
            Dict des hedges actifs {symbol: HedgeInfo}
        """
        with self._lock:
            return self._active_hedges.copy()

    def get_hedge_status(self) -> Dict[str, Any]:
        """
        Retourne le statut du hedging.

        Returns:
            Dict avec le statut du hedging
        """
        with self._lock:
            return {
                "enabled": self.enabled,
                "active_hedges_count": len(self._active_hedges),
                "active_hedges": list(self._active_hedges.keys()),
                "config": {
                    "offset_percent": self.offset_percent * 100,
                    "timeout_minutes": self.timeout_minutes,
                    "retry_on_reject": self.retry_on_reject,
                    "max_retry_offset_percent": self.max_retry_offset_percent * 100
                }
            }

    def force_close_all_hedges(self):
        """
        Force la fermeture de tous les hedges actifs.
        """
        try:
            with self._lock:
                hedges_to_close = list(self._active_hedges.items())

            if not hedges_to_close:
                self.logger.info("ℹ️ [SPOT_HEDGE] Aucun hedge actif à fermer")
                return

            self.logger.info(f"🔄 [SPOT_HEDGE] Fermeture forcée de {len(hedges_to_close)} hedge(s)")

            for symbol, hedge_info in hedges_to_close:
                self._close_spot_hedge(symbol, hedge_info)
                with self._lock:
                    if symbol in self._active_hedges:
                        del self._active_hedges[symbol]

            self.logger.info("✅ [SPOT_HEDGE] Tous les hedges fermés")

        except Exception as e:
            self.logger.error(f"❌ [SPOT_HEDGE] Erreur fermeture forcée: {e}")

    def stop(self):
        """
        Arrête le gestionnaire de hedging.
        """
        try:
            self.logger.info("🛑 [SPOT_HEDGE] Arrêt du SpotHedgeManager...")

            # Fermer tous les hedges actifs
            self.force_close_all_hedges()

            # Arrêter l'OrderMonitor
            if hasattr(self.order_monitor, 'stop'):
                self.order_monitor.stop()

            self.logger.info("✅ [SPOT_HEDGE] SpotHedgeManager arrêté")

        except Exception as e:
            self.logger.error(f"❌ [SPOT_HEDGE] Erreur arrêt: {e}")
