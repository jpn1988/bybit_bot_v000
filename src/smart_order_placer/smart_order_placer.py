#!/usr/bin/env python3
"""
Smart Maker Order Placer - Système d'ouverture de positions 100% maker (Version Refactorisée).

Ce module fournit un système intelligent de placement d'ordres maker avec :
- Calcul dynamique des prix basé sur la liquidité
- Classification automatique de la liquidité (spread + profondeur)
- Refresh automatique des ordres non exécutés
- Logging détaillé pour le suivi des opérations

ARCHITECTURE REFACTORISÉE:
- LiquidityClassifier: Analyse l'order book pour déterminer la liquidité
- DynamicPriceCalculator: Calcule les prix optimaux selon la liquidité
- SymbolRulesCache: Gère le cache des règles de précision
- QuantityFormatter: Formate les quantités selon les règles Bybit
- PriceFormatter: Formate les prix selon les règles Bybit
- OrderbookManager: Gère le cache de l'orderbook
- OrderValidator: Valide les ordres avant placement
- OrderRetryHandler: Gère les retries et ajustements de prix
- SmartOrderPlacer: Orchestre le placement avec refresh automatique

FONCTIONNALITÉS:
✅ 100% Maker: Tous les ordres utilisent PostOnly
✅ Prix dynamiques: Adaptation automatique à la liquidité
✅ Refresh intelligent: Annulation et remplacement automatiques
✅ Respect des limites: Minimum 5 USDT et précision Bybit
✅ Cache optimisé: Réduction des appels API
✅ Logs détaillés: Suivi complet du cycle de vie

UTILISATION:
    smart_placer = SmartOrderPlacer(bybit_client, logger)
    result = smart_placer.place_order_with_refresh(
        symbol="BTCUSDT",
        side="Buy",
        qty="0.001",
        category="linear"
    )
"""

import time
import logging
import math
import json
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

from config import get_settings
from utils.executors import GLOBAL_EXECUTOR

from .liquidity_classifier import LiquidityClassifier
from .price_calculator import DynamicPriceCalculator
from .symbol_rules_cache import SymbolRulesCache
from .quantity_formatter import QuantityFormatter
from .price_formatter import PriceFormatter
from .orderbook_manager import OrderbookManager
from .order_validator import OrderValidator
from .order_retry_handler import OrderRetryHandler

# Paramètres de refresh
ORDER_REFRESH_INTERVAL = 2  # secondes
DEFAULT_MAX_RETRIES_PERP = 3
DEFAULT_MAX_RETRIES_SPOT = 8


@dataclass
class OrderResult:
    """Résultat d'un placement d'ordre."""
    success: bool
    order_id: Optional[str] = None
    price: Optional[float] = None
    offset_percent: Optional[float] = None
    liquidity_level: Optional[str] = None
    retry_count: int = 0
    execution_time: Optional[float] = None
    error_message: Optional[str] = None


class SmartOrderPlacer:
    """Orchestre le placement et le refresh des ordres maker intelligents."""

    def __init__(self, bybit_client, logger: Optional[logging.Logger] = None, maker_config: Optional[Dict[str, Any]] = None):
        self.bybit_client = bybit_client
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialiser les helpers
        self.rules_cache = SymbolRulesCache(bybit_client, logger)
        self.quantity_formatter = QuantityFormatter(self.rules_cache, logger)
        self.price_formatter = PriceFormatter(self.rules_cache, logger)
        self.orderbook_manager = OrderbookManager(bybit_client, logger)
        self.order_validator = OrderValidator(logger)
        self.retry_handler = OrderRetryHandler(self.rules_cache, self.orderbook_manager, logger)
        self.price_calculator = DynamicPriceCalculator(logger)
        
        # Overrides dynamiques pour le minimum notionnel détecté par symbole
        self._symbol_min_notional_override: Dict[Tuple[str, str], float] = {}
        
        # Paramètres dynamiques via configuration
        self.shadow_mode = False
        self.perp_max_retries = DEFAULT_MAX_RETRIES_PERP
        self.spot_max_retries = DEFAULT_MAX_RETRIES_SPOT
        self.refresh_interval_perp = ORDER_REFRESH_INTERVAL
        self.refresh_interval_spot = max(0.5, ORDER_REFRESH_INTERVAL / 2)
        
        try:
            settings = get_settings()
            auto_cfg = settings.get('auto_trading', {}) or {}
            self.shadow_mode = bool(auto_cfg.get('shadow_mode', False))
            maker_cfg_settings = auto_cfg.get('maker', {}) or {}
        except Exception:
            maker_cfg_settings = {}

        try:
            maker_cfg_user = maker_config or {}
            maker_cfg = {**maker_cfg_settings, **maker_cfg_user}

            perp_retries = maker_cfg.get('max_retries_perp', DEFAULT_MAX_RETRIES_PERP)
            spot_retries = maker_cfg.get('max_retries_spot', DEFAULT_MAX_RETRIES_SPOT)
            refresh_perp = maker_cfg.get('refresh_interval_perp_seconds', self.refresh_interval_perp)
            refresh_spot = maker_cfg.get('refresh_interval_spot_seconds', self.refresh_interval_spot)
            min_notional_override = maker_cfg.get('min_order_value_usdt', auto_cfg.get('order_size_usdt', 10))

            try:
                perp_retries = int(perp_retries)
            except (TypeError, ValueError):
                perp_retries = DEFAULT_MAX_RETRIES_PERP
            try:
                spot_retries = int(spot_retries)
            except (TypeError, ValueError):
                spot_retries = DEFAULT_MAX_RETRIES_SPOT

            if perp_retries >= 1:
                self.perp_max_retries = perp_retries
            if spot_retries >= 1:
                self.spot_max_retries = spot_retries

            try:
                refresh_perp = float(refresh_perp)
            except (TypeError, ValueError):
                refresh_perp = self.refresh_interval_perp
            try:
                refresh_spot = float(refresh_spot)
            except (TypeError, ValueError):
                refresh_spot = self.refresh_interval_spot

            if refresh_perp > 0:
                self.refresh_interval_perp = refresh_perp
            if refresh_spot > 0:
                self.refresh_interval_spot = refresh_spot

            try:
                self.min_order_value_usdt = float(min_notional_override)
            except (TypeError, ValueError):
                self.min_order_value_usdt = 10.0
            if self.min_order_value_usdt <= 0:
                self.min_order_value_usdt = 10.0
        except Exception:
            # Conserver les valeurs par défaut en cas d'erreur de config
            pass

        if not hasattr(self, "min_order_value_usdt"):
            self.min_order_value_usdt = 10.0

    def place_order_with_refresh(
        self,
        symbol: str,
        side: str,
        qty: str,
        category: str = "linear",
        force_exact_quantity: bool = False
    ) -> OrderResult:
        """
        Place un ordre maker avec refresh automatique si non exécuté.

        CYCLE DE VIE COMPLET:
        1. Récupération order book (avec cache 30s)
        2. Calcul prix dynamique basé sur liquidité du marché
        3. Vérification minimum 5 USDT (ajustement auto si nécessaire)
        4. Placement ordre PostOnly (garantit 100% maker)
        5. Surveillance exécution pendant 5 secondes
        6. Si non exécuté → Retry avec prix plus agressif (max 3 tentatives)

        Args:
            symbol: Symbole de la paire (ex: "BTCUSDT")
            side: "Buy" ou "Sell"
            qty: Quantité à trader (sera ajustée si < 5 USDT)
            category: "linear", "inverse", ou "spot"
            force_exact_quantity: Si True, ne réduit jamais la quantité

        Returns:
            OrderResult: Résultat complet avec succès, order_id, prix, etc.
        """
        start_time = time.time()

        try:
            # Shadow mode: ne pas placer, simuler succès immédiat
            if self.shadow_mode:
                self.logger.info(
                    f"[ORDER] [SHADOW_MODE] {symbol} {side} qty={qty} category={category} (aucun ordre envoyé)"
                )
                return OrderResult(
                    success=True,
                    order_id="shadow_order",
                    price=None,
                    offset_percent=None,
                    liquidity_level=None,
                    retry_count=0,
                    execution_time=0.0,
                )
            
            # Récupérer le carnet d'ordres (avec cache)
            orderbook = self.orderbook_manager.get_cached_orderbook(symbol, category)
            if not orderbook:
                return OrderResult(
                    success=False,
                    error_message=f"Impossible de récupérer le carnet d'ordres pour {symbol}"
                )

            # Calculer le prix dynamique
            limit_price, liquidity_level, offset_percent = self.price_calculator.compute_dynamic_price(
                symbol, side, orderbook
            )

            max_retries = self.spot_max_retries if category == "spot" else self.perp_max_retries

            # Boucle de placement avec retry
            for retry in range(max_retries + 1):
                try:
                    qty = self._ensure_min_notional_qty(
                        symbol,
                        category,
                        qty,
                        limit_price,
                        safety_factor=1.002,
                        force_exact_quantity=force_exact_quantity,
                    )

                    # Log de la tentative
                    attempt_msg = (
                        f"[ORDER] [MAKER-OPEN] {symbol} {side} | price={limit_price:.6f} | "
                        f"offset={offset_percent*100:.3f}% | liquidity={liquidity_level} | retry={retry}"
                    )
                    if retry == 0:
                        self.logger.info(attempt_msg)
                    else:
                        self.logger.debug(attempt_msg)

                    # Placer l'ordre
                    response = self._place_order_sync(
                        symbol=symbol,
                        side=side,
                        qty=qty,
                        price=limit_price,
                        category=category
                    )

                    order_id = response.get('orderId')
                    ret_code = response.get('retCode', 0)
                    ret_msg = response.get('retMsg', '')

                    # Vérifier les erreurs non-récupérables
                    if self.order_validator.is_non_recoverable_error(ret_code, ret_msg):
                        error_type = "délisting" if (ret_code == 30228 or "delisting" in ret_msg.lower()) else "non-récupérable"
                        self.logger.warning(
                            f"🚫 [ORDER] {symbol}: Erreur {error_type} détectée (retCode={ret_code}): {ret_msg}. "
                            f"Arrêt immédiat des tentatives - symbole ignoré."
                        )
                        return OrderResult(
                            success=False,
                            error_message=f"Erreur {error_type} (retCode={ret_code}): {ret_msg}. Arrêt immédiat des tentatives."
                        )

                    # Gérer les erreurs de min notional
                    if ret_code == 110094 or "minimum order value" in ret_msg.lower():
                        hinted_min_notional = self.order_validator.parse_min_notional_from_error(ret_msg)
                        rules = self.rules_cache.get_quantity_rules(symbol, category)
                        try:
                            rule_min_notional = float(rules.get("min_notional", 0.0))
                        except (TypeError, ValueError):
                            rule_min_notional = 0.0

                        override_key = (symbol, category)
                        override_min = self._symbol_min_notional_override.get(override_key, 0.0)

                        try:
                            limit_price_float = float(limit_price)
                        except (TypeError, ValueError):
                            limit_price_float = 0.0

                        try:
                            current_notional = float(qty) * limit_price_float
                        except (TypeError, ValueError):
                            current_notional = 0.0

                        effective_min_notional_candidates = [5.0, rule_min_notional, override_min, self.min_order_value_usdt]
                        if hinted_min_notional:
                            try:
                                effective_min_notional_candidates.append(float(hinted_min_notional))
                            except (TypeError, ValueError):
                                pass

                        effective_min_notional = max(effective_min_notional_candidates)

                        if current_notional > 0.0:
                            effective_min_notional = max(effective_min_notional, current_notional * 1.05)
                        else:
                            effective_min_notional *= 1.05

                        self._symbol_min_notional_override[override_key] = effective_min_notional
                        self.rules_cache.update_min_notional_override(symbol, category, effective_min_notional)

                        bumped_qty = self._ensure_min_notional_qty(
                            symbol,
                            category,
                            qty,
                            limit_price,
                            safety_factor=1.05,
                            hinted_min_notional=effective_min_notional,
                            force_exact_quantity=force_exact_quantity,
                        )
                        if bumped_qty != qty:
                            self.logger.info(
                                f"[ORDER] [MAKER-OPEN] Ajustement min notional {symbol}: qty {qty} -> {bumped_qty} (valeur≈{current_notional:.4f} USDT, min_requis≈{effective_min_notional:.4f} USDT)"
                            )
                            qty = bumped_qty
                            continue

                    if not order_id:
                        if retry < max_retries:
                            self.logger.warning(
                                f"[ORDER] ⚠️ [MAKER-OPEN] Ordre rejeté pour {symbol} (retry {retry+1}/{max_retries}): {ret_msg}"
                            )
                            # Ajuster le prix pour le prochain essai (join-quote plus agressif)
                            limit_price = self.retry_handler.compute_join_quote_price(symbol, side, category, limit_price)
                            continue
                        else:
                            return OrderResult(
                                success=False,
                                error_message=f"Ordre rejeté après {max_retries} tentatives: {ret_msg}"
                            )

                    # Ordre accepté - vérifier l'exécution
                    execution_result = self._wait_for_execution(
                        order_id, symbol, category, limit_price, offset_percent, liquidity_level, retry, side, max_retries
                    )

                    # Si demande de remplacement, ajuster le prix et retenter
                    if (not execution_result.success) and execution_result.error_message and execution_result.error_message.startswith("REPLACE:"):
                        try:
                            new_price = float(execution_result.error_message.split(":", 1)[1])
                            limit_price = new_price
                            continue
                        except Exception:
                            pass

                    execution_time = time.time() - start_time
                    execution_result.execution_time = execution_time

                    return execution_result

                except Exception as e:
                    self.logger.error(f"[ORDER] ❌ [MAKER-OPEN] Erreur placement {symbol} (retry {retry}): {e}")
                    if retry == max_retries:
                        return OrderResult(
                            success=False,
                            error_message=f"Erreur après {max_retries} tentatives: {str(e)}"
                        )
                    time.sleep(1)  # Pause avant retry

            return OrderResult(
                success=False,
                error_message="Nombre maximum de tentatives atteint"
            )

        except Exception as e:
            self.logger.error(f"[ORDER] ❌ [MAKER-OPEN] Erreur fatale {symbol}: {e}")
            return OrderResult(
                success=False,
                error_message=f"Erreur fatale: {str(e)}"
            )

    def _ensure_min_notional_qty(
        self,
        symbol: str,
        category: str,
        qty: str,
        price: float,
        safety_factor: float = 1.0,
        hinted_min_notional: Optional[float] = None,
        force_exact_quantity: bool = False,
    ) -> str:
        """Ajuste la quantité pour garantir une valeur nominale minimale.
        
        Args:
            force_exact_quantity: Si True, ne réduit jamais la quantité en dessous de qty
                (utile pour les hedges qui doivent être exacts)
        """
        try:
            qty_float = max(float(qty), 0.0)
            price_float = float(price)
        except (TypeError, ValueError):
            return qty

        if price_float <= 0:
            return qty

        # S'assurer que les règles sont chargées
        rules = self.rules_cache.get_quantity_rules(symbol, category)
        override_key = (symbol, category)
        override_min_notional = self._symbol_min_notional_override.get(override_key)

        if override_min_notional is not None:
            try:
                override_min_notional = float(override_min_notional)
            except (TypeError, ValueError):
                override_min_notional = None

        qty_step = float(rules.get('qty_step', 0.001))
        min_qty = float(rules.get('min_qty', qty_step))
        min_notional = float(rules.get('min_notional', 5.0))

        if override_min_notional and override_min_notional > min_notional:
            min_notional = override_min_notional

        if hinted_min_notional is not None and hinted_min_notional > min_notional:
            min_notional = hinted_min_notional

        # Calculer le notional de la quantité originale
        original_notional = qty_float * price_float
        
        target_notional = max(
            self.min_order_value_usdt * safety_factor,
            min_notional * safety_factor,
            original_notional,
        )

        # Calcul direct du nombre de steps nécessaires pour atteindre target_notional
        required_steps = None
        if qty_step > 0:
            # Calculer le nombre de steps nécessaire (arrondi vers le haut)
            required_steps = math.ceil(target_notional / (price_float * qty_step))
            adjusted_qty = required_steps * qty_step
            # S'assurer qu'on respecte min_qty
            if adjusted_qty < min_qty:
                min_steps = math.ceil(min_qty / qty_step)
                adjusted_qty = min_steps * qty_step
        else:
            adjusted_qty = max(target_notional / price_float, min_qty)
        
        # IMPORTANT: Si force_exact_quantity=True, ne jamais réduire la quantité en dessous de l'originale
        if force_exact_quantity:
            # Arrondir qty_float selon qty_step pour garantir la cohérence
            if qty_step > 0:
                original_steps = round(qty_float / qty_step)
                rounded_original_qty = original_steps * qty_step
            else:
                rounded_original_qty = qty_float
            
            # Si la quantité originale respecte déjà le min_notional minimum, l'utiliser telle quelle
            if original_notional >= min_notional * safety_factor:
                adjusted_qty = rounded_original_qty
                self.logger.info(
                    f"🔒 [QTY_CALC] {symbol}: Force exact quantity activé - utilisation quantité originale: {rounded_original_qty:.10f} "
                    f"(notional={original_notional:.6f} USDT >= min={min_notional * safety_factor:.6f} USDT)"
                )
            else:
                # Si la quantité originale est trop petite, prendre le max entre adjusted_qty et rounded_original_qty
                adjusted_qty = max(adjusted_qty, rounded_original_qty)
                if adjusted_qty > rounded_original_qty:
                    self.logger.warning(
                        f"⚠️ [QTY_CALC] {symbol}: Force exact quantity - ajustement à la hausse pour min_notional: "
                        f"{rounded_original_qty:.10f} -> {adjusted_qty:.10f} (min_notional requis: {min_notional * safety_factor:.6f} USDT)"
                    )
                else:
                    self.logger.info(
                        f"🔒 [QTY_CALC] {symbol}: Force exact quantity - quantité préservée: {rounded_original_qty:.10f} "
                        f"(min_notional sera ajusté si nécessaire)"
                    )

        # Logs d'information
        self.logger.info(
            f"🔍 [QTY_CALC] {symbol}: qty_initiale={qty_float:.10f}, target_notional={target_notional:.6f}, "
            f"qty_step={qty_step}, required_steps={required_steps if required_steps is not None else 'N/A'}, "
            f"adjusted_qty={adjusted_qty:.10f}"
        )

        # Boucle de sécurité pour garantir qu'on atteint target_notional
        max_iterations = 1000
        iteration = 0
        while adjusted_qty * price_float + 1e-9 < target_notional and iteration < max_iterations:
            if qty_step > 0:
                adjusted_qty += qty_step
            else:
                adjusted_qty = target_notional / price_float
                break
            iteration += 1

        # Vérification finale
        final_value = adjusted_qty * price_float
        if final_value < target_notional - 1e-6:
            self.logger.warning(
                f"⚠️ [QTY_CALC] {symbol}: Impossible d'atteindre target_notional={target_notional:.6f} "
                f"avec qty={adjusted_qty:.10f} (value={final_value:.6f})"
            )

        # Formater la quantité en utilisant QuantityFormatter
        qty_str = self.quantity_formatter.format_quantity(symbol, adjusted_qty, category, round_up=False)

        # 🔍 DEBUG : Log du formatage
        self.logger.debug(
            f"[DEBUG_QTY] {symbol} ({category}) - _ensure_min_notional_qty: "
            f"qty_entrée={qty} (type={type(qty).__name__}, repr={repr(qty)}), "
            f"qty_step={qty_step}, adjusted_qty={adjusted_qty:.10f}, "
            f"qty_str_après_formatage={qty_str} (type={type(qty_str).__name__}, repr={repr(qty_str)})"
        )

        # Vérification critique : s'assurer que le formatage n'a pas réduit la valeur
        try:
            qty_parsed = float(qty_str)
            value_after_format = qty_parsed * price_float

            # Si le formatage a réduit la valeur en dessous du target, ajuster
            if value_after_format < target_notional - 1e-6:
                self.logger.warning(
                    f"⚠️ [QTY_FORMAT] {symbol}: Formatage a réduit la valeur! "
                    f"adjusted_qty={adjusted_qty:.10f} -> qty_str={qty_str} -> qty_parsed={qty_parsed:.10f}, "
                    f"value={value_after_format:.6f} < target={target_notional:.6f}"
                )
                # Recalculer avec plus de précision
                if qty_step > 0:
                    additional_steps = math.ceil((target_notional - value_after_format) / (price_float * qty_step))
                    qty_parsed = (required_steps + additional_steps) * qty_step if required_steps is not None else adjusted_qty + (additional_steps * qty_step)
                    qty_str = self.quantity_formatter.format_quantity(symbol, qty_parsed, category, round_up=False)
                else:
                    qty_parsed = target_notional / price_float
                    qty_str = f"{qty_parsed:.8f}".rstrip('0').rstrip('.')

                value_after_format = qty_parsed * price_float
                self.logger.info(
                    f"✅ [QTY_FORMAT] {symbol}: Quantité corrigée qty={qty_str}, valeur={value_after_format:.6f} USDT"
                )
        except Exception as e:
            self.logger.warning(f"⚠️ [QTY_FORMAT] {symbol}: Erreur vérification formatage: {e}")

        if qty_str != qty:
            try:
                old_value = qty_float * price_float
                new_value = float(qty_str) * price_float
                self.logger.info(
                    f"🔧 [MAKER-OPEN] Ajustement min notional {symbol}: qty {qty} -> {qty_str} "
                    f"(valeur {old_value:.6f} → {new_value:.6f} USDT, target={target_notional:.6f})"
                )
            except Exception:
                pass

        return qty_str

    def _place_order_sync(self, symbol: str, side: str, qty: str, price: float, category: str) -> Dict[str, Any]:
        """Place un ordre de manière synchrone."""
        # Formater le prix selon les règles de Bybit
        formatted_price = self.price_formatter.format_price(symbol, price, category)

        # Vérifier que la quantité respecte le minimum notionnel
        try:
            qty_float = float(qty)
            price_float = float(formatted_price)

            if price_float <= 0:
                raise ValueError(f"Prix invalide pour {symbol}: {formatted_price}")

            rules = self.rules_cache.get_quantity_rules(symbol, category)
            min_notional_rule = float(rules.get('min_notional', 5.0))

            base_min_notional = max(self.min_order_value_usdt, min_notional_rule)
            required_min_notional = base_min_notional * 1.02  # marge de sécurité 2%

            # Calculer la valeur actuelle
            current_value = qty_float * price_float

            self.logger.info(
                f"🔍 [PLACE_ORDER] {symbol}: qty_reçue={qty_float:.10f}, price={price_float:.6f}, "
                f"current_value={current_value:.6f}, required={required_min_notional:.6f}"
            )

            # Si la valeur est insuffisante, recalculer la quantité
            if current_value < required_min_notional - 1e-6:
                qty_step = float(rules.get('qty_step', 1.0))
                min_qty_rule = float(rules.get('min_qty', 0.0))

                self.logger.warning(
                    f"⚠️ [PLACE_ORDER] {symbol}: valeur insuffisante! {current_value:.6f} < {required_min_notional:.6f}, "
                    f"recalcul forcé avec qty_step={qty_step}"
                )

                # Calcul direct de la quantité nécessaire
                if qty_step > 0:
                    steps = math.ceil(required_min_notional / (price_float * qty_step))
                    qty_float = steps * qty_step
                    if qty_float < min_qty_rule:
                        min_steps = math.ceil(min_qty_rule / qty_step)
                        qty_float = min_steps * qty_step

                    # Vérification que la valeur est suffisante après calcul
                    verification_value = qty_float * price_float
                    if verification_value < required_min_notional - 1e-6:
                        qty_float += qty_step
                        verification_value = qty_float * price_float
                        self.logger.info(
                            f"✅ [PLACE_ORDER] {symbol}: Ajout step supplémentaire, "
                            f"qty={qty_float:.10f}, valeur={verification_value:.6f}"
                        )
                else:
                    qty_float = max(min_qty_rule, required_min_notional / price_float)

                # Formater la quantité avec précision maximale
                qty = self.quantity_formatter.format_quantity(symbol, qty_float, category, round_up=False)

                # Vérification finale après formatage
                qty_final_float = float(qty)
                final_value_check = qty_final_float * price_float
                if final_value_check < required_min_notional - 1e-6:
                    self.logger.error(
                        f"❌ [PLACE_ORDER] {symbol}: Formatage a réduit la valeur! "
                        f"qty={qty_float:.10f} -> qty_str={qty} -> qty_parsed={qty_final_float:.10f}, "
                        f"value={final_value_check:.6f} < required={required_min_notional:.6f}"
                    )
                    # Recalculer directement
                    if qty_step > 0:
                        steps = math.ceil(required_min_notional / (price_float * qty_step))
                        qty_float = steps * qty_step
                        qty_float += qty_step  # Ajouter un step de sécurité
                        qty = self.quantity_formatter.format_quantity(symbol, qty_float, category, round_up=False)
                    else:
                        qty_float = required_min_notional / price_float
                        qty = f"{qty_float:.8f}".rstrip('0').rstrip('.')

                    final_value_check = float(qty) * price_float
                    self.logger.info(
                        f"✅ [PLACE_ORDER] {symbol}: Quantité corrigée après formatage, "
                        f"qty={qty}, valeur={final_value_check:.6f}"
                    )

            final_value = float(qty) * price_float

            self.logger.info(
                f"[ORDER] [MAKER-OPEN] Placement {symbol}: side={side} qty={qty} price={formatted_price} "
                f"valeur≈{final_value:.6f} USDT (min requis≈{required_min_notional:.6f})"
            )
        except Exception as e:
            self.logger.warning(f"[ORDER] ⚠️ [MAKER-OPEN] Erreur ajustement quantité: {e}")

        time_in_force = "PostOnly" if category != "spot" else "GTC"

        # Vérification finale (doublon de sécurité)
        try:
            final_order_value = float(qty) * float(formatted_price)
            rules = self.rules_cache.get_quantity_rules(symbol, category)
            min_notional_rule = float(rules.get('min_notional', 5.0))
            override_min = self._symbol_min_notional_override.get((symbol, category), 0.0)
            try:
                override_min = float(override_min)
            except (TypeError, ValueError):
                override_min = 0.0

            base_min_notional = max(self.min_order_value_usdt, min_notional_rule, override_min)
            required_min_notional = base_min_notional * 1.02

            if final_order_value + 1e-9 < required_min_notional:
                self.logger.error(
                    f"[ORDER] ❌ Valeur notionnelle insuffisante pour {symbol}: qty={qty} price={formatted_price} "
                    f"value={final_order_value:.6f} min_requis≈{required_min_notional:.6f}"
                )
                raise ValueError(
                    f"Valeur notionnelle insuffisante pour {symbol} (value={final_order_value:.6f} < min={required_min_notional:.6f})"
                )
        except ValueError:
            raise
        except Exception as e:
            self.logger.warning(f"[ORDER] ⚠️ [MAKER-OPEN] Erreur vérification finale: {e}")

        executor = GLOBAL_EXECUTOR
        
        # 🔍 DEBUG : Log AVANT formatage final
        cache_key = f"{symbol}_{category}"
        rules_before = self.rules_cache.get_quantity_rules(symbol, category)
        self.logger.debug(
            f"[DEBUG_QTY] {symbol} ({category}) - _place_order_sync AVANT formatage final: "
            f"qty_reçue={qty} (type={type(qty).__name__}, repr={repr(qty)}), "
            f"cache_key={cache_key}, "
            f"qty_step_dans_cache={rules_before.get('qty_step', 'N/A')}, "
            f"quantity_precision_dans_cache={rules_before.get('quantity_precision', 'N/A')}"
        )
        
        # ✅ CORRECTION : Reformater la quantité juste avant l'envoi pour garantir le bon format
        try:
            rules = self.rules_cache.get_quantity_rules(symbol, category)
            qty_float = float(qty)
            qty = self.quantity_formatter.format_quantity(symbol, qty_float, category, round_up=False)
            
            # 🔍 DEBUG : Log APRÈS formatage final
            test_order_data = {"qty": qty}
            json_test = json.dumps(test_order_data, separators=(',', ':'))
            self.logger.debug(
                f"[DEBUG_QTY] {symbol} ({category}) - _place_order_sync APRÈS formatage final: "
                f"qty_float={qty_float:.10f}, qty_finale={qty} (type={type(qty).__name__}, repr={repr(qty)}), "
                f"qty_dans_json_test={json_test}"
            )
        except Exception as e:
            self.logger.warning(f"[ORDER] ⚠️ Erreur reformatage quantité finale {symbol}: {e}")
        
        future = executor.submit(
            self.bybit_client.place_order,
            symbol=symbol,
            side=side,
            order_type="Limit",
            qty=qty,
            price=formatted_price,
            category=category,
            time_in_force=time_in_force
        )
        return future.result()

    def _wait_for_execution(
        self,
        order_id: str,
        symbol: str,
        category: str,
        price: float,
        offset_percent: float,
        liquidity_level: str,
        retry: int,
        side: str,
        max_retries: int
    ) -> OrderResult:
        """Attend l'exécution de l'ordre avec refresh si nécessaire."""
        start_wait = time.time()

        # Attendre l'intervalle de refresh (plus rapide pour le spot)
        refresh_interval = self.refresh_interval_perp if category != "spot" else self.refresh_interval_spot
        time.sleep(refresh_interval)

        # Vérifier si l'ordre est toujours en attente
        was_cancelled = False

        if self._is_order_still_pending(order_id, symbol, category):
            wait_time = time.time() - start_wait
            self.logger.debug(f"[ORDER] [MAKER-OPEN] Refresh pending après {wait_time:.1f}s")

            # Annuler l'ordre
            try:
                self.bybit_client.cancel_order(
                    symbol=symbol,
                    order_id=order_id,
                    category=category
                )
                self.logger.debug(f"[ORDER] 🔄 [MAKER-OPEN] Ordre {order_id} annulé pour refresh")
                was_cancelled = True
            except Exception as e:
                self.logger.warning(f"[ORDER] ⚠️ [MAKER-OPEN] Erreur annulation {order_id}: {e}")

            # Si on peut encore retry, proposer un remplacement au prix join-quote
            if retry < max_retries:
                # Récupérer un nouveau carnet d'ordres
                orderbook = self.orderbook_manager.get_cached_orderbook(symbol, category)
                if orderbook:
                    # Utiliser un prix join-quote agressif pour la prochaine tentative
                    new_price = self.retry_handler.compute_join_quote_price(symbol, side, category, price)
                    self.logger.debug(f"[ORDER] [MAKER-OPEN] Replacement proposé price={new_price:.6f}")
                    # Retourner une intention de remplacement au caller
                    return OrderResult(success=False, error_message=f"REPLACE:{new_price}")

        # Ordre exécuté ou timeout
        execution_time = time.time() - start_wait

        if was_cancelled:
            self.logger.debug(f"[ORDER] [MAKER-OPEN] Ordre {order_id} annulé après {execution_time:.1f}s")
            return OrderResult(
                success=False,
                order_id=order_id,
                price=price,
                offset_percent=offset_percent,
                liquidity_level=liquidity_level,
                retry_count=retry,
                error_message="CANCELLED"
            )

        if self._is_order_still_pending(order_id, symbol, category):
            self.logger.warning(f"[ORDER] ⚠️ [MAKER-OPEN] Ordre {order_id} toujours en attente après {execution_time:.1f}s")
            return OrderResult(
                success=False,
                order_id=order_id,
                price=price,
                offset_percent=offset_percent,
                liquidity_level=liquidity_level,
                retry_count=retry,
                error_message="PENDING"
            )

        self.logger.info(f"[ORDER] [MAKER-OPEN] Exécuté complètement après {execution_time:.1f}s ✅")

        return OrderResult(
            success=True,
            order_id=order_id,
            price=price,
            offset_percent=offset_percent,
            liquidity_level=liquidity_level,
            retry_count=retry
        )

    def _is_order_still_pending(self, order_id: str, symbol: str, category: str) -> bool:
        """Vérifie si un ordre est toujours en attente."""
        try:
            # Ajouter le paramètre settleCoin pour les catégories linear
            params = {"category": category}
            if category == "linear":
                params["settleCoin"] = "USDT"

            open_orders = self.bybit_client.get_open_orders(**params)
            if open_orders and open_orders.get("list"):
                for order in open_orders["list"]:
                    if (order.get("orderId") == order_id and
                        order.get("symbol") == symbol):
                        return order.get("orderStatus") in ["New", "PartiallyFilled"]
            return False
        except Exception as e:
            self.logger.warning(f"[ORDER] ⚠️ [PENDING_CHECK] Erreur vérification {order_id}: {e}")
            return False

