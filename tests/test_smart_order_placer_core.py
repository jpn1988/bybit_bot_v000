"""Tests d'intégration légers pour SmartOrderPlacer."""

from dataclasses import dataclass
from typing import Any, Dict, List

import pytest

from src.smart_order_placer import SmartOrderPlacer


@dataclass
class ImmediateFuture:
    value: Dict[str, Any]

    def result(self) -> Dict[str, Any]:
        return self.value


class SynchronousExecutor:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def submit(self, func, *args, **kwargs):
        self.calls.append({"func": func, "args": args, "kwargs": kwargs})
        return ImmediateFuture(func(*args, **kwargs))


class DummyClient:
    def __init__(self):
        self._placed: List[Dict[str, Any]] = []
        self._cancelled: List[str] = []

    def get_instruments_info(self, category, symbol):
        return {
            "list": [
                {
                    "symbol": symbol,
                    "priceFilter": {"tickSize": "0.001"},
                    "lotSizeFilter": {
                        "qtyStep": "0.1",
                        "minOrderQty": "0.1",
                        "minOrderValue": "5"
                    },
                }
            ]
        }

    def get_orderbook(self, category, symbol, limit=10):
        return {
            "b": [["1.600", "100"], ["1.599", "100"]],
            "a": [["1.700", "100"], ["1.701", "100"]],
        }

    def place_order(self, **kwargs):
        self._placed.append(kwargs)
        return {"retCode": 0, "retMsg": "OK", "orderId": "test-order-id"}

    def get_open_orders(self, **kwargs):
        return {"list": []}

    def cancel_order(self, **kwargs):
        self._cancelled.append(kwargs.get("order_id", "?"))
        return {"retCode": 0}


def make_logger():
    class Logger:
        def info(self, *args, **kwargs):
            pass

        def debug(self, *args, **kwargs):
            pass

        def warning(self, *args, **kwargs):
            pass

        def error(self, *args, **kwargs):
            pass

    return Logger()


@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch):
    monkeypatch.setattr("src.smart_order_placer.smart_order_placer.time.sleep", lambda *_, **__: None)


@pytest.fixture
def executor(monkeypatch):
    sync_executor = SynchronousExecutor()
    monkeypatch.setattr("src.smart_order_placer.smart_order_placer.GLOBAL_EXECUTOR", sync_executor)
    return sync_executor


@pytest.fixture
def dummy_client():
    return DummyClient()


@pytest.fixture
def smart_placer(dummy_client, executor):
    return SmartOrderPlacer(dummy_client, make_logger())


def test_price_formatter_respects_tick_size(smart_placer):
    formatted = smart_placer.price_formatter.format_price("ENSOUSDT", 1.701234, "spot")
    assert formatted.endswith("701")


def test_place_order_enforces_min_notional(smart_placer, dummy_client):
    result = smart_placer.place_order_with_refresh("ENSOUSDT", "Buy", "0.01", category="spot")

    assert result.success is True
    assert dummy_client._placed
    placed_order = dummy_client._placed[-1]
    order_value = float(placed_order["price"]) * float(placed_order["qty"])
    assert order_value >= 5.0 - 1e-6


def test_place_order_cycle_returns_order_info(smart_placer):
    result = smart_placer.place_order_with_refresh("ENSOUSDT", "Buy", "0.5", category="spot")

    assert result.success is True
    assert result.order_id == "test-order-id"
    assert result.price is not None
    assert result.liquidity_level is not None


