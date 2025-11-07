"""
Symbol Rules Cache - Gestion du cache des règles de précision.

Ce module gère le cache des règles de précision (qty_step, min_qty, min_notional, tick_size)
pour éviter les appels API répétés.
"""

import logging
from typing import Dict, Any, Optional, Tuple


class SymbolRulesCache:
    """Gère le cache des règles de précision pour les symboles."""

    def __init__(self, bybit_client, logger: Optional[logging.Logger] = None):
        self.bybit_client = bybit_client
        self.logger = logger or logging.getLogger(__name__)
        self._symbol_precision_cache: Dict[Tuple[str, str], float] = {}
        self._symbol_qty_cache: Dict[str, Dict[str, Any]] = {}

    def get_tick_size(self, symbol: str, category: str) -> float:
        """
        Retourne le tickSize pour un symbole (utilise le cache).

        Args:
            symbol: Symbole de la paire
            category: Catégorie (linear, spot, etc.)

        Returns:
            float: Tick size pour le symbole
        """
        try:
            cache_key = (symbol, category)

            if cache_key not in self._symbol_precision_cache:
                # Hydrater via formatage (remplit le cache)
                self._load_tick_size(symbol, category)
            tick = self._symbol_precision_cache.get(cache_key, 0.00001)
            return float(tick)
        except Exception:
            return 0.00001

    def _load_tick_size(self, symbol: str, category: str) -> None:
        """Charge le tick size depuis l'API et le met en cache."""
        try:
            cache_key = (symbol, category)
            instruments_info = self.bybit_client.get_instruments_info(category=category, symbol=symbol)
            info_list = None
            if instruments_info:
                if 'list' in instruments_info:
                    info_list = instruments_info['list']
                elif 'result' in instruments_info and instruments_info['result'] and 'list' in instruments_info['result']:
                    info_list = instruments_info['result']['list']
            if info_list:
                symbol_info = info_list[0]
                price_filter = symbol_info.get('priceFilter', {})
                tick_size = float(price_filter.get('tickSize', '0.00001'))
                self._symbol_precision_cache[cache_key] = tick_size
            else:
                # Fallback pour les symboles non trouvés
                self._symbol_precision_cache[cache_key] = 0.00001
        except Exception as e:
            self.logger.warning(f"[CACHE] ⚠️ Erreur chargement tick size {symbol}: {e}")
            self._symbol_precision_cache[(symbol, category)] = 0.00001

    def get_quantity_rules(self, symbol: str, category: str) -> Dict[str, Any]:
        """
        Récupère les règles de quantité pour un symbole (avec cache).

        Args:
            symbol: Symbole de la paire
            category: Catégorie (linear, spot, etc.)

        Returns:
            Dict contenant qty_step, min_qty, min_notional, quantity_precision
        """
        cache_key = f"{symbol}_{category}"
        if cache_key not in self._symbol_qty_cache:
            self._load_quantity_rules(symbol, category)
        return self._symbol_qty_cache.get(cache_key, {
            'qty_step': 0.001,
            'min_qty': 0.001,
            'min_notional': 5.0,
            'quantity_precision': None,
        })

    def _load_quantity_rules(self, symbol: str, category: str) -> None:
        """Charge les règles de quantité depuis l'API et les met en cache."""
        try:
            cache_key = f"{symbol}_{category}"
            instruments_info = self.bybit_client.get_instruments_info(category=category, symbol=symbol)
            qty_step = None
            min_order_qty = 0.001
            min_notional = 5.0
            quantity_precision = None
            info_list = None
            if instruments_info:
                if 'list' in instruments_info:
                    info_list = instruments_info['list']
                elif 'result' in instruments_info and instruments_info['result'] and 'list' in instruments_info['result']:
                    info_list = instruments_info['result']['list']
            if info_list:
                symbol_info = info_list[0]
                lot = symbol_info.get('lotSizeFilter', {})
                qty_step_str = lot.get('qtyStep')
                if qty_step_str not in (None, '', '0'):
                    try:
                        qty_step = float(qty_step_str)
                    except (TypeError, ValueError):
                        qty_step = None
                if lot.get('quantityPrecision') is not None:
                    try:
                        quantity_precision = int(float(lot['quantityPrecision']))
                    except (TypeError, ValueError):
                        quantity_precision = None
                elif lot.get('basePrecision') is not None:
                    try:
                        quantity_precision = int(float(lot['basePrecision']))
                    except (TypeError, ValueError):
                        quantity_precision = None

                min_order_qty = float(lot.get('minOrderQty', str(min_order_qty)))
                # min order value (USDT) si exposé
                try:
                    if 'minOrderValue' in lot:
                        min_notional = float(lot['minOrderValue'])
                    elif 'minNotional' in lot:
                        min_notional = float(lot['minNotional'])
                    else:
                        trading = symbol_info.get('linearInstrument', {}) or symbol_info
                        min_notional = float(trading.get('minOrderValue', trading.get('minNotional', min_notional)))
                except Exception:
                    min_notional = 5.0

            if qty_step is None or qty_step == 0:
                if quantity_precision is not None and quantity_precision >= 0:
                    qty_step = 10 ** (-quantity_precision) if quantity_precision > 0 else 1.0
                else:
                    qty_step = 0.00001

            self._symbol_qty_cache[cache_key] = {
                'qty_step': float(qty_step),
                'min_qty': float(min_order_qty),
                'min_notional': float(min_notional),
                'quantity_precision': quantity_precision,
            }
        except Exception as e:
            self.logger.warning(f"[CACHE] ⚠️ Erreur chargement règles quantité {symbol}: {e}")
            self._symbol_qty_cache[f"{symbol}_{category}"] = {
                'qty_step': 0.001,
                'min_qty': 0.001,
                'min_notional': 5.0,
                'quantity_precision': None,
            }

    def update_min_notional_override(self, symbol: str, category: str, min_notional: float) -> None:
        """Met à jour le min_notional dans le cache pour un symbole."""
        cache_key = f"{symbol}_{category}"
        if cache_key in self._symbol_qty_cache:
            self._symbol_qty_cache[cache_key]['min_notional'] = min_notional

