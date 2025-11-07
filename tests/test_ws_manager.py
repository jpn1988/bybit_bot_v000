import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ws.manager import WebSocketManager


@pytest.mark.asyncio
async def test_start_connections_configures_strategy():
    manager = WebSocketManager(testnet=True, data_manager=Mock(), logger=Mock())
    manager._ensure_executor_ready = AsyncMock()
    manager._start_connections_by_strategy = AsyncMock()

    await manager.start_connections(["BTCUSDT"], ["BTCUSD"], on_ticker_callback=Mock())

    manager._ensure_executor_ready.assert_awaited()
    manager._start_connections_by_strategy.assert_awaited()
    assert manager.linear_symbols == ["BTCUSDT"]
    assert manager.inverse_symbols == ["BTCUSD"]
    assert manager.is_running() is True

    manager._ws_conns = []
    manager._ws_tasks = []
    await manager.stop()


def test_set_ticker_callback_and_handle():
    data_manager = Mock()
    manager = WebSocketManager(testnet=True, data_manager=data_manager, logger=Mock())
    callback = Mock()
    manager.set_ticker_callback(callback)

    manager._handle_ticker({
        "symbol": "BTCUSDT",
        "markPrice": "50000.0",
        "lastPrice": "50010.0",
    })

    data_manager.update_price_data.assert_called_once()
    callback.assert_called_once()


def test_handle_ticker_invalid_data_is_ignored():
    data_manager = Mock()
    manager = WebSocketManager(testnet=True, data_manager=data_manager, logger=Mock())

    manager._handle_ticker({"symbol": "BTCUSDT", "markPrice": "50000"})
    data_manager.update_price_data.assert_not_called()


@pytest.mark.asyncio
async def test_stop_resets_state():
    manager = WebSocketManager(testnet=True, logger=Mock())
    manager.running = True
    manager._ws_conns = [Mock()]
    future = asyncio.get_event_loop().create_future()
    manager._ws_tasks = [future]
    manager.linear_symbols = ["BTCUSDT"]
    manager.inverse_symbols = ["BTCUSD"]

    await manager.stop()

    assert manager.running is False
    assert manager._ws_conns == []
    assert manager._ws_tasks == []
    assert manager.get_connected_symbols() == {"linear": [], "inverse": []}


@pytest.mark.asyncio
async def test_double_start_logs_warning():
    logger = Mock()
    manager = WebSocketManager(testnet=True, logger=logger)
    manager.running = True

    await manager.start_connections(["BTCUSDT"], [])
    logger.warning.assert_called_with("⚠️ WebSocketManager déjà en cours d'exécution")
