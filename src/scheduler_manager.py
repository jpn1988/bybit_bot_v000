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
import inspect
import math
import re
import time
from typing import Dict, Any
from order_monitor import OrderMonitor
from smart_order_placer import SmartOrderPlacer
from utils.executors import GLOBAL_EXECUTOR
from utils.async_wrappers import run_in_thread


class SchedulerManager:
    """
    Gestionnaire de planification pour le bot Bybit.

    Cette classe gère la planification temporelle des opérations,
    notamment pour le funding sniping et autres tâches programmées.
    """

    def __init__(self, logger, funding_threshold_minutes=60, bybit_client=None, auto_trading_config=None, on_position_opened_callback=None):
        """
        Initialise le gestionnaire de planification.

        Args:
            logger: Logger pour les messages de debug et d'information
            funding_threshold_minutes: Seuil de détection du funding imminent (en minutes)
            bybit_client: Client Bybit pour passer des ordres (optionnel)
            auto_trading_config: Configuration du trading automatique (optionnel)
            on_position_opened_callback: Callback appelé lors de l'ouverture d'une position (optionnel)
        """
        self.logger = logger
        self.scan_interval = 5  # secondes
        self.funding_threshold_minutes = funding_threshold_minutes
        self.bybit_client = bybit_client
        self.auto_trading_config = auto_trading_config or {}
        self.on_position_opened_callback = on_position_opened_callback

        # Tracking des ordres passés pour éviter les doublons
        self.orders_placed = set()

        # Limite du nombre de positions simultanées
        self.max_positions = auto_trading_config.get('max_positions', 1)
        self.current_positions = set()

        # Limite de retry pour éviter les boucles infinies PostOnly
        self.max_postonly_retries = 3  # Maximum 3 tentatives PostOnly
        self.symbol_retry_count = {}  # Compteur de retry par symbole

        # Initialiser le surveillant d'ordres
        self.order_monitor = OrderMonitor(bybit_client, logger) if bybit_client else None

        # Initialiser le Smart Order Placer pour les ordres maker intelligents
        maker_cfg = (auto_trading_config or {}).get('maker', {}) if auto_trading_config else {}
        self.smart_placer = SmartOrderPlacer(bybit_client, logger, maker_cfg) if bybit_client else None

        # Optimisation: éviter les scans trop fréquents
        self.last_scan_time = 0

        self._summary_interval = 60
        self._last_summary_ts = 0.0

        self.logger.debug("🕒 Scheduler initialisé")

    def _log_periodic_summary(self):
        """Émet un résumé synthétique toutes les 60 secondes."""
        now = time.time()
        if now - self._last_summary_ts < self._summary_interval:
            return

        self._last_summary_ts = now
        self.logger.info(
            f"[SCHEDULER] Summary positions_actives={len(self.current_positions)} ordres_tentes={len(self.orders_placed)} limite={self.max_positions}"
        )

    async def check_pending_orders(self):
        """
        Vérifie les ordres en attente et annule ceux qui ont expiré.

        Cette méthode doit être appelée périodiquement pour surveiller les ordres.
        """
        if self.order_monitor:
            await self.order_monitor.check_orders_status()

    def remove_position(self, symbol: str):
        """
        Retire une position de la liste des positions actives.

        Args:
            symbol: Symbole de la position fermée
        """
        if symbol in self.current_positions:
            self.current_positions.remove(symbol)
            self.logger.info(
                f"[SCHEDULER] Position retirée: {symbol} - Positions restantes: {len(self.current_positions)}/{self.max_positions}"
            )

    def reset_orders(self):
        """
        Réinitialise la liste des ordres tentés.
        Utile pour permettre de retenter des ordres après un redémarrage.
        """
        self.orders_placed.clear()
        self.logger.debug("🔄 Liste des ordres tentés réinitialisée")

    def set_threshold(self, minutes: float):
        """
        Permet de modifier dynamiquement le seuil de détection du funding imminent.

        Args:
            minutes: Seuil en minutes pour détecter le funding imminent
        """
        self.funding_threshold_minutes = minutes
        self.logger.debug(f"🛠️ [SCHEDULER] Seuil Funding T défini à {minutes} min")

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

        # Vérifier la limite de positions simultanées
        if len(self.current_positions) >= self.max_positions:
            self.logger.debug(f"🚫 Limite de positions atteinte ({self.max_positions}) - Ignorer {symbol}")
            return False

        # Vérifier si on a déjà passé un ordre pour cette paire
        if symbol in self.orders_placed:
            self.logger.debug(f"🚫 Ordre déjà tenté pour {symbol} - Ignorer")
            return False

        # Trade immédiatement quand une opportunité est détectée
        # Plus de vérification de délai - trade dès que le scheduler détecte une paire
        return True

    def _confirm_position_opened(self, symbol: str, expected_side: str) -> bool:
        """Confirme via l'API Bybit qu'une position perp est bien ouverte."""
        try:
            import time

            normalized_side = expected_side.lower() if expected_side else ""
            for attempt in range(6):  # ~6 secondes maximum
                positions = self.bybit_client.get_positions(category="linear", settleCoin="USDT")
                if positions and positions.get("list"):
                    for position in positions["list"]:
                        if position.get("symbol") != symbol:
                            continue

                        size_raw = position.get("size", "0")
                        try:
                            size_val = float(size_raw)
                        except (TypeError, ValueError):
                            size_val = 0.0

                        side_val = (position.get("side") or "").lower()

                        if size_val > 0:
                            if normalized_side and side_val and normalized_side != side_val:
                                    self.logger.warning(
                                        f"[TRADING] ⚠️ Position détectée sur {symbol} mais côté {side_val} ≠ {normalized_side}"
                                    )
                            return True

                time.sleep(1)

        except Exception as e:
            self.logger.warning(f"[TRADING] ⚠️ Erreur lors de la confirmation position {symbol}: {e}")

        return False

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
                self.logger.debug(f"🧪 [DRY-RUN] Ordre simulé pour {symbol}: {funding_rate:.4f} @ {current_price}")
                self.orders_placed.add(symbol)
                return True

            # Déterminer le côté de l'ordre basé sur le funding rate
            # S'assurer que funding_rate est un float
            funding_rate_float = float(funding_rate) if funding_rate is not None else 0.0
            side = "Buy" if funding_rate_float > 0 else "Sell"

            # Calculer la quantité en USDT
            order_size_usdt = self.auto_trading_config.get('order_size_usdt', 10)

            # S'assurer que l'ordre respecte le minimum de 5 USDT requis par Bybit
            min_order_value_usdt = 5.0
            if order_size_usdt < min_order_value_usdt:
                self.logger.warning(f"[TRADING] ⚠️ order_size_usdt ({order_size_usdt}) < minimum requis ({min_order_value_usdt}), ajustement automatique")
                order_size_usdt = min_order_value_usdt

            # Calculer la quantité de base
            base_qty = order_size_usdt / current_price

            # Récupérer les informations du symbole pour connaître les règles
            try:
                # Utiliser un thread dédié pour éviter PERF-002

                def _get_instruments_info_sync():
                    return self.bybit_client.get_instruments_info(category="linear", symbol=symbol)

                self.logger.debug("[ASYNC] Bybit REST call exécuté dans un thread : get_instruments_info()")
                instruments_info = _get_instruments_info_sync()

                if instruments_info and 'list' in instruments_info and instruments_info['list']:
                    symbol_info = instruments_info['list'][0]
                    lot_size_filter = symbol_info.get('lotSizeFilter', {})
                    min_qty = float(lot_size_filter.get('minOrderQty', '0.001'))
                    qty_step = float(lot_size_filter.get('qtyStep', '0.001'))

                    precision_candidates = [lot_size_filter.get('quantityPrecision'), lot_size_filter.get('basePrecision')]
                    quantity_precision = None
                    for candidate in precision_candidates:
                        if candidate is None:
                            continue
                        try:
                            quantity_precision = int(float(candidate))
                            break
                        except (TypeError, ValueError):
                            continue

                    step_decimals = 0
                    if qty_step > 0:
                        step_str = f"{qty_step:.10f}".rstrip('0').rstrip('.')
                        if '.' in step_str:
                            step_decimals = len(step_str.split('.')[1])

                    decimals = quantity_precision if quantity_precision is not None else step_decimals
                    decimals = max(decimals, step_decimals)

                    target_notional = max(order_size_usdt, min_order_value_usdt)
                    required_qty = target_notional / current_price

                    qty_steps = max(1, math.ceil(required_qty / qty_step)) if qty_step > 0 else 1
                    adjusted_qty = qty_steps * qty_step if qty_step > 0 else required_qty

                    if adjusted_qty < min_qty:
                        min_steps = math.ceil(min_qty / qty_step) if qty_step > 0 else 1
                        adjusted_qty = max(min_qty, min_steps * qty_step if qty_step > 0 else min_qty)

                    qty_float = adjusted_qty if adjusted_qty > 0 else min_qty

                    if decimals > 0:
                        qty = f"{qty_float:.{decimals}f}".rstrip('0').rstrip('.')
                    else:
                        qty = f"{qty_float:.0f}"

                    if not qty or qty == '0':
                        # Utiliser decimals calculé au lieu de 6 décimales en dur
                        safe_decimals = decimals if decimals > 0 else 2
                        qty = f"{max(min_qty, qty_float):.{safe_decimals}f}".rstrip('0').rstrip('.') or str(min_qty)

                    final_order_value = float(qty) * current_price
                    if final_order_value < target_notional:
                        # Sécurité : recalculer via arrondi supérieur explicite
                        adjusted_steps = max(1, math.ceil(target_notional / (current_price * qty_step))) if qty_step > 0 else 1
                        qty_float = adjusted_steps * qty_step if qty_step > 0 else target_notional / current_price
                        if qty_step > 0 and qty_float < min_qty:
                            min_steps = math.ceil(min_qty / qty_step)
                            qty_float = max(min_qty, min_steps * qty_step)
                        if decimals > 0:
                            qty = f"{qty_float:.{decimals}f}".rstrip('0').rstrip('.')
                        else:
                            qty = f"{qty_float:.0f}"
                        if not qty or qty == '0':
                            # Utiliser decimals calculé au lieu de 6 décimales en dur
                            safe_decimals = decimals if decimals > 0 else 2
                            qty = f"{max(min_qty, qty_float):.{safe_decimals}f}".rstrip('0').rstrip('.') or str(min_qty)
                        final_order_value = float(qty) * current_price

                    self.logger.debug(
                        f"📊 [TRADING] Quantité finale pour {symbol}: {qty} (valeur ≈ {final_order_value:.2f} USDT)"
                    )
                else:
                    # Fallback si pas d'infos du symbole
                    target_notional = max(order_size_usdt, min_order_value_usdt)
                    qty_float = max(target_notional / current_price, 0.001)
                    # Utiliser 2 décimales au lieu de 6 (plus sûr, évite "too many decimals")
                    qty = f"{qty_float:.2f}".rstrip('0').rstrip('.') or "0.001"
            except Exception as e:
                self.logger.warning(f"[TRADING] ⚠️ Impossible de récupérer les infos du symbole {symbol}: {e}")
                # Fallback simple
                target_notional = max(order_size_usdt, min_order_value_usdt)
                qty_float = max(target_notional / current_price, 0.001)
                # Utiliser 2 décimales au lieu de 6 (plus sûr, évite "too many decimals")
                qty = f"{qty_float:.2f}".rstrip('0').rstrip('.') or "0.001"

            # Stratégie PostOnly conservatrice : offset fixe pour garder les ordres en attente
            offset_percent = self.auto_trading_config.get('order_offset_percent', 0.01) / 100

            if side == "Buy":
                limit_price = current_price * (1 - offset_percent)  # Prix légèrement en dessous pour Buy
            else:
                limit_price = current_price * (1 + offset_percent)  # Prix légèrement au-dessus pour Sell

            # Log détaillé pour vérification
            self.logger.debug(
                f"💰 [POSTONLY_STRATEGY] {symbol}: Prix actuel={current_price:.6f}, "
                f"Prix ordre={limit_price:.6f}, Offset={offset_percent*100:.4f}%, "
                f"PostOnly va décider si maker possible"
            )

            # Passer l'ordre
            if not self.bybit_client:
                self.logger.error("❌ [TRADING] Client Bybit non disponible")
                return False

            # Vérifier l'environnement avant de placer l'ordre
            env_info = "TESTNET" if self.bybit_client.is_testnet() else "MAINNET"
            self.logger.debug(f"🌐 [ENVIRONMENT] Placement d'ordre sur {env_info} pour {symbol}")

            # Vérifier que le client est bien authentifié
            if not self.bybit_client.is_authenticated():
                self.logger.error(f"❌ [AUTH_ERROR] Client Bybit non authentifié pour {symbol}")
                return False

            # Utiliser le Smart Order Placer pour un placement intelligent maker
            if self.smart_placer:
                # Utiliser le système maker intelligent
                result = self.smart_placer.place_order_with_refresh(
                    symbol=symbol,
                    side=side,
                    qty=qty,
                    category="linear"
                )

                if not result.success:
                    self.logger.error(f"❌ [SMART_ORDER] Échec placement intelligent {symbol}: {result.error_message}")
                    return False

                order_id = result.order_id
                self.logger.debug(f"✅ [SMART_ORDER] Ordre intelligent placé {symbol}: ID={order_id}, "
                               f"price={result.price:.6f}, offset={result.offset_percent*100:.3f}%, "
                               f"liquidity={result.liquidity_level}, retry={result.retry_count}")
            else:
                # Fallback vers l'ancienne méthode si SmartOrderPlacer non disponible
                self.logger.warning(f"[FALLBACK] ⚠️ SmartOrderPlacer non disponible, utilisation méthode classique")

                def _place_order_sync():
                    return self.bybit_client.place_order(
                        symbol=symbol,
                        side=side,
                        order_type="Limit",
                        qty=qty,
                        price=str(limit_price),
                        category="linear",
                        time_in_force="PostOnly"
                    )

                self.logger.debug("[ASYNC] Bybit REST call exécuté dans un thread : place_order()")
                response = _place_order_sync()

                # Vérifier si l'ordre a été accepté
                order_id = response.get('orderId')
                ret_code = response.get('retCode', 0)  # Par défaut 0 si pas présent
                ret_msg = response.get('retMsg', '')

                # Log de debug pour comprendre la réponse
                self.logger.debug(f"🔍 [ORDER_RESPONSE] {symbol}: orderId={order_id}, retCode={ret_code}, retMsg={ret_msg}")
                self.logger.debug(f"🔍 [ORDER_RESPONSE_FULL] {symbol}: {response}")

            # Vérifier si l'ordre a été accepté (pour la méthode fallback uniquement)
            if not self.smart_placer and not order_id:
                # Ordre rejeté - essayer avec un offset plus important si dans la limite
                if "PostOnly" in ret_msg or "maker" in ret_msg.lower():
                    # Vérifier le nombre de retry pour ce symbole
                    retry_count = self.symbol_retry_count.get(symbol, 0)

                    if retry_count < self.max_postonly_retries:
                        self.symbol_retry_count[symbol] = retry_count + 1
                        self.logger.warning(f"[POSTONLY_REJECTED] ⚠️ Ordre rejeté par PostOnly pour {symbol}, retry {retry_count + 1}/{self.max_postonly_retries}...")

                        # Augmenter l'offset progressivement
                        base_offset = self.auto_trading_config.get('order_offset_percent', 0.01) / 100
                        larger_offset = base_offset * (2 ** retry_count)  # Double l'offset à chaque retry
                        larger_offset = min(larger_offset, 0.1)  # Plafonner à 0.1%

                        if side == "Buy":
                            limit_price = current_price * (1 - larger_offset)
                        else:
                            limit_price = current_price * (1 + larger_offset)

                        self.logger.debug(f"🔄 [RETRY] Nouveau prix pour {symbol}: {limit_price:.6f} (offset: {larger_offset*100:.2f}%)")

                        # Réessayer avec le nouveau prix
                        def _retry_order():
                            return self.bybit_client.place_order(
                                symbol=symbol,
                                side=side,
                                order_type="Limit",
                                qty=qty,
                                price=str(limit_price),
                                category="linear",
                                time_in_force="PostOnly"
                            )

                        self.logger.debug("[ASYNC] Bybit REST call exécuté dans un thread : place_order() [retry]")
                        response = _retry_order()

                        order_id = response.get('orderId')
                        ret_code = response.get('retCode', 0)

                        if not order_id:
                            self.logger.error(f"❌ [TRADING] Ordre définitivement rejeté pour {symbol} après {retry_count + 1} tentatives: {response}")
                            self.orders_placed.add(symbol)
                            return False
                    else:
                        self.logger.error(f"❌ [TRADING] Limite de retry atteinte pour {symbol} ({self.max_postonly_retries} tentatives) - abandon")
                        self.orders_placed.add(symbol)
                        return False
                else:
                    self.logger.error(f"❌ [TRADING] Erreur API pour {symbol}: {response}")
                    self.orders_placed.add(symbol)
                    return False

            # Log de confirmation maker avec info environnement
            env_info = "TESTNET" if self.bybit_client.is_testnet() else "MAINNET"
            self.logger.debug(f"✅ [MAKER_CONFIRMED] Ordre accepté comme MAKER pour {symbol} (ID: {order_id}) - Environnement: {env_info}")

            # Vérification immédiate de l'existence de l'ordre
            try:
                import time
                time.sleep(1)  # Attendre 1 seconde

                # Vérifier immédiatement si l'ordre existe
                immediate_check = self.bybit_client.get_open_orders(category="linear", settleCoin="USDT")
                if immediate_check and immediate_check.get("list"):
                    matching_immediate = [o for o in immediate_check.get("list", []) if o.get("orderId") == order_id]
                    if matching_immediate:
                        self.logger.debug(f"✅ [IMMEDIATE_CHECK] Ordre {symbol} confirmé immédiatement sur Bybit")
                    else:
                        self.logger.warning(
                            f"[ORDER] ⚠️ Ordre {symbol} non trouvé immédiatement - possible problème"
                        )
                else:
                    self.logger.warning(f"[ORDER] ⚠️ Aucun ordre trouvé pour {symbol} - possible problème")
            except Exception as e:
                self.logger.warning(f"[ORDER] ⚠️ Erreur vérification immédiate {symbol}: {e}")

            # Vérifier le statut de l'ordre après un délai
            try:
                import time
                time.sleep(5)  # Attendre 5 secondes pour laisser l'ordre s'afficher

                # Vérifier le statut de l'ordre
                order_status = self.bybit_client.get_open_orders(category="linear", settleCoin="USDT")
                if order_status and order_status.get("list"):
                    matching_orders = [o for o in order_status.get("list", []) if o.get("orderId") == order_id]
                    if matching_orders:
                        order_info = matching_orders[0]
                        self.logger.debug(
                            f"🔍 [ORDER_STATUS] Ordre {symbol} trouvé: Status={order_info.get('orderStatus')}, Qty={order_info.get('qty')}, Price={order_info.get('price')}"
                        )
                        self.logger.debug(f"✅ [ORDER_VISIBLE] Ordre perp {symbol} visible sur Bybit - ID: {order_id}")
                    else:
                        self.logger.debug(
                            f"🔍 [ORDER_STATUS] Ordre {symbol} non trouvé dans les ordres ouverts - probablement exécuté"
                        )
                        self.logger.warning(
                            f"[ORDER] ⚠️ Ordre perp {symbol} non visible sur Bybit - vérifiez manuellement l'ID: {order_id}"
                        )
                else:
                    self.logger.debug(f"🔍 [ORDER_STATUS] Aucun ordre ouvert trouvé")
            except Exception as e:
                self.logger.warning(f"[ORDER] ⚠️ Erreur vérification statut ordre {symbol}: {e}")

            # Confirmer que la position est bien ouverte côté Bybit avant de continuer
            if not self._confirm_position_opened(symbol, side):
                self.logger.error(
                    f"[TRADING] ❌ Position {symbol} introuvable après placement de l'ordre {order_id}. "
                    "Annulation et nouveau scan requis."
                )
                try:
                    self.bybit_client.cancel_order(
                        symbol=symbol,
                        category="linear",
                        order_id=order_id,
                    )
                    self.logger.debug(f"🔄 [TRADING] Ordre {order_id} annulé après échec de confirmation")
                except Exception as cancel_error:
                    self.logger.warning(
                        f"[TRADING] ⚠️ Impossible d'annuler l'ordre {order_id}: {cancel_error}"
                    )
                return False

            # Marquer l'ordre comme passé et ajouter à la liste des positions
            self.orders_placed.add(symbol)
            self.current_positions.add(symbol)

            # Ajouter l'ordre au surveillant pour surveillance automatique
            if self.order_monitor:
                timeout_minutes = self.auto_trading_config.get('order_timeout_minutes', 30)
                self.order_monitor.add_order(
                    order_id=order_id,
                    symbol=symbol,
                    side=side,
                    qty=qty,
                    price=limit_price,
                    timeout_minutes=timeout_minutes
                )

                # Vérifier que l'ordre a bien été ajouté au surveillant
                self.logger.debug(f"🔍 [ORDER] Ordre ajouté au surveillant: {symbol} (ID: {order_id})")

            # Réinitialiser le compteur de retry pour ce symbole en cas de succès
            if symbol in self.symbol_retry_count:
                del self.symbol_retry_count[symbol]

            self.logger.info(
                f"[TRADING] ✅ Ordre MAKER placé pour {symbol}: {side} {qty} @ {limit_price:.4f} "
                f"(funding: {funding_rate_float:.4f}) - OrderID: {order_id} - Positions actives: {len(self.current_positions)}/{self.max_positions} - Mode: PostOnly"
            )

            self.logger.debug("Position ouverte")

            # Appeler le callback d'ouverture de position si défini
            if self.on_position_opened_callback:
                try:
                    position_data = {
                        "symbol": symbol,
                        "side": side,
                        "size": qty,
                        "price": limit_price,
                        "funding_rate": funding_rate_float
                    }
                    callback_result = self.on_position_opened_callback(symbol, position_data)
                    if inspect.isawaitable(callback_result):
                        try:
                            loop = asyncio.get_running_loop()
                        except RuntimeError:
                            asyncio.run(callback_result)
                        else:
                            loop.create_task(callback_result)
                except Exception as e:
                    self.logger.warning(f"[TRADING] ⚠️ Erreur callback position ouverte: {e}")

            return True

        except Exception as e:
            self.logger.error(f"[TRADING] ❌ Erreur lors du placement d'ordre pour {symbol}: {e}")
            # Ne pas marquer l'ordre comme passé en cas d'erreur
            return False

    async def _handle_automatic_trading(self, symbol: str, remaining_seconds: int, first_data: dict):
        """
        Gère le trading automatique pour une paire donnée.

        Args:
            symbol: Symbole de la paire
            remaining_seconds: Secondes restantes avant le funding
            first_data: Données de la première paire
        """
        # Vérifier si un ordre automatique doit être placé
        if not self._should_place_order(symbol, remaining_seconds):
            return

        try:
            if not self.bybit_client:
                self.logger.warning(f"[TRADING] ⚠️ Client Bybit non disponible pour {symbol}")
                return

            self.logger.debug("[ASYNC] Bybit REST call exécuté dans un thread : get_orderbook()")
            orderbook = await run_in_thread(
                self.bybit_client.get_orderbook,
                symbol=symbol,
                limit=1,
            )

            if orderbook and 'b' in orderbook and 'a' in orderbook:
                bid_price = float(orderbook['b'][0][0]) if orderbook['b'] else 0
                ask_price = float(orderbook['a'][0][0]) if orderbook['a'] else 0
                current_price = (bid_price + ask_price) / 2

                funding_rate = first_data.get('funding_rate', 0)

                self.logger.debug("[ASYNC] Bybit REST call exécuté dans un thread : _place_automatic_order()")
                await run_in_thread(
                    self._place_automatic_order,
                    symbol,
                    funding_rate,
                    current_price,
                )
            else:
                self.logger.warning(f"[TRADING] ⚠️ Impossible de récupérer le prix pour {symbol}")

        except Exception as e:
            self.logger.error(f"❌ [TRADING] Erreur lors de la récupération des données pour {symbol}: {e}")

    async def run_with_callback(self, data_callback):
        """
        Méthode principale du scheduler avec callback pour récupérer les données à jour.

        Args:
            data_callback: Fonction qui retourne les données de funding formatées
        """
        self.logger.info(
            f"[SCHEDULER] Scheduler démarré (seuil Funding T = {self.funding_threshold_minutes} min)"
        )

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

                        self.logger.debug(
                            f"⚡ [SCHEDULER] {symbol} funding imminent → "
                            f"{remaining_seconds:.0f}s (seuil={self.funding_threshold_minutes}min)"
                        )

                        # Récupérer les données spécifiques à cette paire
                        pair_data = watchlist_data.get(symbol, {})

                        # Gérer le trading automatique
                        await self._handle_automatic_trading(symbol, remaining_seconds, pair_data)
                else:
                    self.logger.debug(
                        f"🕒 [SCHEDULER] Aucune paire proche du funding "
                        f"(prochain scan dans {self.scan_interval}s)"
                    )

                # Vérifier les ordres en attente et annuler ceux qui ont expiré
                await self.check_pending_orders()

                # Attendre avant le prochain scan
                self._log_periodic_summary()
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
        self.logger.info(
            f"[SCHEDULER] Scheduler démarré (seuil Funding T = {self.funding_threshold_minutes} min)"
        )

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
                        self.logger.debug(
                            f"⚡ [SCHEDULER] {pair['symbol']} funding imminent → "
                            f"{pair['remaining_seconds']:.0f}s (seuil={self.funding_threshold_minutes}min)"
                        )
                else:
                    self.logger.debug(
                        f"🕒 [SCHEDULER] Aucune paire proche du funding "
                        f"(prochain scan dans {self.scan_interval}s)"
                    )

                # Vérifier les ordres en attente et annuler ceux qui ont expiré
                await self.check_pending_orders()

                # Attendre avant le prochain scan
                self._log_periodic_summary()
                await asyncio.sleep(self.scan_interval)

            except Exception as e:
                self.logger.error(f"❌ [SCHEDULER] Erreur dans la boucle de scan: {e}")
                await asyncio.sleep(self.scan_interval)
