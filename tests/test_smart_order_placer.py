"""Tests pytest pour le SmartOrderPlacer refactorisé."""

from unittest.mock import Mock

import pytest

from src.smart_order_placer import (
    DynamicPriceCalculator,
    LiquidityClassifier,
    OrderResult,
    SmartOrderPlacer,
)


@pytest.fixture
def mock_logger():
    logger = Mock()
    logger.info = Mock()
    logger.debug = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def smart_placer(mock_logger):
    bybit_client = Mock()
    placer = SmartOrderPlacer(bybit_client, mock_logger)

    placer.orderbook_manager = Mock()
    placer.price_calculator = Mock()
    placer.order_validator = Mock()
    placer.order_validator.is_non_recoverable_error.return_value = False
    placer.order_validator.parse_min_notional_from_error.return_value = None
    placer.retry_handler = Mock()
    placer.retry_handler.compute_join_quote_price.return_value = 99.5
    placer.rules_cache = Mock()
    placer.rules_cache.get_quantity_rules.return_value = {}
    placer.rules_cache.update_min_notional_override = Mock()
    placer._ensure_min_notional_qty = Mock()
    placer._place_order_sync = Mock()
    placer._wait_for_execution = Mock()
    placer.min_order_value_usdt = 5.0
    placer._symbol_min_notional_override = {}

    return placer


@pytest.fixture
def orderbook_snapshot():
    return {
        "b": [["100.00", "2"], ["99.80", "1.5"]],
        "a": [["100.10", "1.8"], ["100.25", "1.2"]],
    }


def test_place_order_success_returns_execution_result(smart_placer, orderbook_snapshot):
    smart_placer.orderbook_manager.get_cached_orderbook.return_value = orderbook_snapshot
    smart_placer.price_calculator.compute_dynamic_price.return_value = (100.0, "high_liquidity", 0.0002)
    smart_placer._ensure_min_notional_qty.return_value = "0.01"
    smart_placer._place_order_sync.return_value = {"orderId": "order-123", "retCode": 0, "retMsg": ""}
    expected_result = OrderResult(
        success=True,
        order_id="order-123",
        price=100.0,
        offset_percent=0.0002,
        liquidity_level="high_liquidity",
    )
    smart_placer._wait_for_execution.return_value = expected_result

    result = smart_placer.place_order_with_refresh("BTCUSDT", "Buy", "0.01", category="linear")

    assert result is expected_result
    smart_placer.price_calculator.compute_dynamic_price.assert_called_once_with("BTCUSDT", "Buy", orderbook_snapshot)
    smart_placer._place_order_sync.assert_called_once()
    call_args = smart_placer._wait_for_execution.call_args[0]
    assert call_args[0] == "order-123"
    assert call_args[1] == "BTCUSDT"


def test_place_order_returns_failure_if_orderbook_missing(smart_placer):
    smart_placer.orderbook_manager.get_cached_orderbook.return_value = None

    result = smart_placer.place_order_with_refresh("ETHUSDT", "Sell", "0.5")

    assert result.success is False
    assert "Impossible de récupérer le carnet" in result.error_message
    smart_placer._place_order_sync.assert_not_called()


def test_place_order_adjusts_quantity_for_min_notional(smart_placer, orderbook_snapshot):
    smart_placer.orderbook_manager.get_cached_orderbook.return_value = orderbook_snapshot
    smart_placer.price_calculator.compute_dynamic_price.return_value = (100.0, "medium_liquidity", 0.0005)
    smart_placer._ensure_min_notional_qty.return_value = "0.05"
    smart_placer._place_order_sync.return_value = {"orderId": "order-321", "retCode": 0, "retMsg": ""}
    smart_placer._wait_for_execution.return_value = OrderResult(success=True, order_id="order-321")

    smart_placer.place_order_with_refresh("BTCUSDT", "Buy", "0.01")

    assert smart_placer._place_order_sync.call_args.kwargs["qty"] == "0.05"
    smart_placer._ensure_min_notional_qty.assert_called_once()


def test_place_order_retries_on_missing_order_id(smart_placer, orderbook_snapshot):
    smart_placer.orderbook_manager.get_cached_orderbook.return_value = orderbook_snapshot
    smart_placer.price_calculator.compute_dynamic_price.return_value = (100.0, "medium_liquidity", 0.0005)
    smart_placer._ensure_min_notional_qty.side_effect = ["0.01", "0.02", "0.02"]
    smart_placer._place_order_sync.side_effect = [
        {"orderId": None, "retCode": 0, "retMsg": "temp"},
        {"orderId": "order-456", "retCode": 0, "retMsg": ""},
    ]
    smart_placer.retry_handler.compute_join_quote_price.return_value = 99.8
    smart_placer._wait_for_execution.return_value = OrderResult(success=True, order_id="order-456")
    smart_placer.perp_max_retries = 2

    result = smart_placer.place_order_with_refresh("BTCUSDT", "Sell", "0.01")

    assert result.success is True
    assert smart_placer._place_order_sync.call_count == 2
    smart_placer.retry_handler.compute_join_quote_price.assert_called_once()


def test_place_order_stops_on_non_recoverable_error(smart_placer, orderbook_snapshot):
    smart_placer.orderbook_manager.get_cached_orderbook.return_value = orderbook_snapshot
    smart_placer.price_calculator.compute_dynamic_price.return_value = (100.0, "low_liquidity", 0.001)
    smart_placer._ensure_min_notional_qty.return_value = "0.02"
    smart_placer._place_order_sync.return_value = {"orderId": None, "retCode": 30228, "retMsg": "delisting"}
    smart_placer.order_validator.is_non_recoverable_error.return_value = True

    result = smart_placer.place_order_with_refresh("BTCUSDT", "Buy", "0.02")

    assert result.success is False
    assert "Arrêt immédiat" in result.error_message
    smart_placer._wait_for_execution.assert_not_called()


def test_place_order_handles_min_notional_error_and_retries(smart_placer, orderbook_snapshot):
    smart_placer.orderbook_manager.get_cached_orderbook.return_value = orderbook_snapshot
    smart_placer.price_calculator.compute_dynamic_price.return_value = (100.0, "medium_liquidity", 0.0005)
    smart_placer.rules_cache.get_quantity_rules.return_value = {
        "min_notional": "5",
        "qty_step": "0.01",
        "min_qty": "0.01",
    }
    smart_placer._ensure_min_notional_qty.side_effect = ["0.01", "0.02", "0.02"]
    smart_placer._place_order_sync.side_effect = [
        {"orderId": None, "retCode": 110094, "retMsg": "Minimum order value 10"},
        {"orderId": "order-789", "retCode": 0, "retMsg": ""},
    ]
    smart_placer.order_validator.parse_min_notional_from_error.return_value = "10"
    smart_placer._wait_for_execution.return_value = OrderResult(success=True, order_id="order-789")

    result = smart_placer.place_order_with_refresh("BTCUSDT", "Buy", "0.01")

    assert result.success is True
    assert smart_placer._place_order_sync.call_count == 2
    second_call_qty = smart_placer._place_order_sync.call_args_list[1].kwargs["qty"]
    assert second_call_qty == "0.02"
    smart_placer.rules_cache.update_min_notional_override.assert_called_once()


def test_liquidity_classifier_handles_structured_orderbook():
    classifier = LiquidityClassifier()
    orderbook = {
        "b": [["50000.00", "5"], ["49999.50", "4"]],
        "a": [["50000.10", "5"], ["50000.60", "4"]],
    }

    result = classifier.classify_liquidity(orderbook)

    assert result in {"high_liquidity", "medium_liquidity"}


def test_liquidity_classifier_fallbacks_to_low_liquidity():
    classifier = LiquidityClassifier()
    orderbook = {
        "b": [["100.0", "0.01"]],
        "a": [["101.5", "0.01"]],
    }

    result = classifier.classify_liquidity(orderbook)

    assert result == "low_liquidity"


def test_dynamic_price_calculator_buy_uses_bid_offset():
    calculator = DynamicPriceCalculator()
    orderbook = {
        "b": [["100.0", "1"], ["99.9", "1"]],
        "a": [["100.5", "1"], ["100.6", "1"]],
    }

    price, level, offset = calculator.compute_dynamic_price("BTCUSDT", "Buy", orderbook)

    assert price < float(orderbook["b"][0][0])
    assert offset > 0
    assert level in {"high_liquidity", "medium_liquidity", "low_liquidity"}


def test_dynamic_price_calculator_sell_uses_ask_offset():
    calculator = DynamicPriceCalculator()
    orderbook = {
        "b": [["100.0", "1"], ["99.9", "1"]],
        "a": [["100.5", "1"], ["100.6", "1"]],
    }

    price, level, offset = calculator.compute_dynamic_price("BTCUSDT", "Sell", orderbook)

    assert price > float(orderbook["a"][0][0])
    assert offset > 0
    assert level in {"high_liquidity", "medium_liquidity", "low_liquidity"}
