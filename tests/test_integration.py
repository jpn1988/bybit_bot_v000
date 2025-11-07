import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from data_manager import DataManager
from models.funding_data import FundingData
from ws.manager import WebSocketManager
from bot_initializer import BotInitializer


@pytest.fixture
def mock_logger():
    return Mock()


def test_data_manager_funding_roundtrip(mock_logger):
    manager = DataManager(testnet=True, logger=mock_logger)

    funding = FundingData(
        symbol="BTCUSDT",
        funding_rate=0.0001,
        volume_24h=1_000_000,
        next_funding_time="1h",
        spread_pct=0.001,
        volatility_pct=0.05,
    )
    manager.set_funding_data_object(funding)

    retrieved = manager.get_funding_data_object("BTCUSDT")
    assert retrieved == funding

    stats = manager.get_data_stats()
    assert stats["funding_data_objects"] == 1


def test_data_manager_symbol_lists_updates(mock_logger):
    manager = DataManager(testnet=True, logger=mock_logger)

    manager.update_symbol_lists_from_opportunities(["BTCUSDT"], ["BTCUSD"])
    manager.add_symbol_to_category("ETHUSDT", "linear")

    assert sorted(manager.get_linear_symbols()) == ["BTCUSDT", "ETHUSDT"]
    assert manager.get_inverse_symbols() == ["BTCUSD"]

    manager.remove_symbol_from_category("BTCUSDT", "linear")
    assert manager.get_linear_symbols() == ["ETHUSDT"]


def test_data_flow_updates_storage(mock_logger):
    manager = DataManager(testnet=True, logger=mock_logger)

    funding = FundingData(
        symbol="BTCUSDT",
        funding_rate=0.0001,
        volume_24h=500_000,
        next_funding_time="2h",
        spread_pct=0.002,
    )
    manager.set_funding_data_object(funding)
    manager.update_realtime_data("BTCUSDT", {"markPrice": "50000", "lastPrice": "50010"})

    stored = manager.get_realtime_data("BTCUSDT")
    assert stored["mark_price"] == "50000"
    assert stored["last_price"] == "50010"


@pytest.mark.asyncio
async def test_websocket_manager_start_connections_sets_symbols(mock_logger):
    manager = WebSocketManager(testnet=True, data_manager=Mock(), logger=mock_logger)
    manager._ensure_executor_ready = AsyncMock()
    manager._start_connections_by_strategy = AsyncMock()

    await manager.start_connections(["BTCUSDT"], [])

    assert manager.running is True
    assert manager.linear_symbols == ["BTCUSDT"]
    manager._ensure_executor_ready.assert_awaited()
    manager._start_connections_by_strategy.assert_awaited()

    manager._ws_conns = []
    manager._ws_tasks = []
    await manager.stop()


def test_websocket_manager_handle_ticker_updates_data_manager(mock_logger):
    data_manager = Mock()
    manager = WebSocketManager(testnet=True, data_manager=data_manager, logger=mock_logger)

    manager.set_ticker_callback(Mock())
    manager._handle_ticker({
        "symbol": "BTCUSDT",
        "markPrice": "50000.0",
        "lastPrice": "50005.0",
    })

    data_manager.update_price_data.assert_called_once()


@patch("candidate_monitor.CandidateMonitor")
def test_bot_initializer_get_managers(mock_candidate_monitor, mock_logger):
    initializer = BotInitializer(testnet=True, logger=mock_logger)

    initializer.initialize_managers()
    initializer.initialize_specialized_managers()
    initializer.setup_manager_callbacks()

    managers = initializer.get_managers()
    expected = {
        "data_manager",
        "display_manager",
        "monitoring_manager",
        "ws_manager",
        "volatility_tracker",
        "watchlist_manager",
        "callback_manager",
        "opportunity_manager",
    }
    assert expected.issubset(managers.keys())
    for key in expected:
        assert managers[key] is not None
