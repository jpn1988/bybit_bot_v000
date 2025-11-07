import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from data_fetcher import DataFetcher
from funding_fetcher import FundingFetcher
from pagination_handler import PaginationHandler
from display_manager import DisplayManager
from metrics_monitor import MetricsMonitor
from callback_manager import CallbackManager
from volatility_tracker import VolatilityTracker
from models.funding_data import FundingData


class DummyDataManager:
    def __init__(self, funding_map=None):
        self._funding_map = funding_map or {}
        self.storage = Mock()

    def get_all_funding_data_objects(self):
        return self._funding_map


def test_data_fetcher_fetch_complete_market_data_success():
    logger = Mock()
    fetcher = DataFetcher(logger=logger)

    with patch.object(fetcher, "fetch_funding_data_parallel", return_value={"BTCUSDT": {"funding": 0.0001}}), \
         patch.object(fetcher, "fetch_spread_data", side_effect=[{"BTCUSDT": 0.001}]), \
         patch.object(fetcher, "validate_funding_data", return_value=True), \
         patch.object(fetcher, "validate_spread_data", return_value=True):
        result = fetcher.fetch_complete_market_data(
            base_url="https://api.bybit.com",
            categories=["linear"],
            symbols=["BTCUSDT"],
            timeout=5,
        )

    assert result["funding_valid"] is True
    assert result["spread_valid"] is True
    assert result["spread_data"] == {"BTCUSDT": 0.001}


def test_data_fetcher_logs_warning_when_funding_invalid():
    logger = Mock()
    fetcher = DataFetcher(logger=logger)

    with patch.object(fetcher, "fetch_funding_data_parallel", return_value={}), \
         patch.object(fetcher, "fetch_spread_data", return_value={}), \
         patch.object(fetcher, "validate_funding_data", return_value=False), \
         patch.object(fetcher, "validate_spread_data", return_value=True):
        fetcher.fetch_complete_market_data("base", ["linear"], ["BTCUSDT"], timeout=1)

    logger.warning.assert_called_with("⚠️ Données de funding invalides")


def test_funding_fetcher_fetch_funding_map_success():
    logger = Mock()
    with patch("funding_fetcher.PaginationHandler") as MockPagination, \
         patch("funding_fetcher.ErrorHandler"):
        pagination = MockPagination.return_value
        pagination.fetch_paginated_data.return_value = [
            {
                "symbol": "BTCUSDT",
                "fundingRate": "0.0002",
                "volume24h": "1200000",
                "nextFundingTime": "1h",
            },
            {"symbol": "", "fundingRate": None},
        ]
        fetcher = FundingFetcher(logger=logger)
        result = fetcher.fetch_funding_map("https://api", "linear", timeout=2)

    assert "BTCUSDT" in result
    assert result["BTCUSDT"]["funding"] == 0.0002
    pagination.fetch_paginated_data.assert_called_once()


def test_funding_fetcher_fetch_funding_map_logs_error():
    logger = Mock()
    with patch("funding_fetcher.PaginationHandler") as MockPagination, \
         patch("funding_fetcher.ErrorHandler") as MockErrorHandler:
        pagination = MockPagination.return_value
        pagination.fetch_paginated_data.side_effect = RuntimeError("boom")
        error_handler = MockErrorHandler.return_value
        fetcher = FundingFetcher(logger=logger)

        with pytest.raises(RuntimeError):
            fetcher.fetch_funding_map("https://api", "linear")

    error_handler.log_error.assert_called_once()


def test_pagination_handler_fetch_paginated_data_multiple_pages():
    handler = PaginationHandler(logger=Mock())
    page_one = {"list": [{"a": 1}], "nextPageCursor": "cursor"}
    page_two = {"list": [{"a": 2}], "nextPageCursor": None}

    with patch.object(handler, "_make_paginated_request", side_effect=[page_one, page_two]):
        data = handler.fetch_paginated_data("https://api", "/endpoint", {"limit": 1}, timeout=1)

    assert data == [{"a": 1}, {"a": 2}]


def test_display_manager_print_price_table_outputs_rows(capsys):
    funding = FundingData(
        symbol="BTCUSDT",
        funding_rate=0.0001,
        volume_24h=1_500_000,
        next_funding_time="1h",
        spread_pct=0.001,
        volatility_pct=0.02,
    )
    data_manager = DummyDataManager({"BTCUSDT": funding})

    with patch("display_manager.TableFormatter") as MockFormatter:
        formatter = MockFormatter.return_value
        formatter.are_all_data_available.return_value = True
        formatter.calculate_column_widths.return_value = {
            "symbol": 8,
            "funding": 12,
            "volume": 10,
            "spread": 10,
            "volatility": 12,
            "funding_time": 15,
        }
        formatter.format_table_header.return_value = "HEADER"
        formatter.format_table_separator.return_value = "SEPARATOR"
        formatter.prepare_row_data.return_value = {
            "funding": funding.funding_rate,
            "volume": funding.volume_24h,
            "spread_pct": funding.spread_pct,
            "volatility_pct": funding.volatility_pct,
            "funding_time": funding.next_funding_time,
        }
        formatter.format_table_row.return_value = "ROW:BTCUSDT"

        display = DisplayManager(data_manager, logger=Mock())
        display._print_price_table()

    captured = capsys.readouterr().out
    assert "ROW:BTCUSDT" in captured


def test_metrics_monitor_start_stop(monkeypatch):
    monitor = MetricsMonitor(interval_minutes=1)
    monitor.logger = Mock()

    thread_mock = Mock()
    thread_mock.is_alive.return_value = False
    monkeypatch.setattr("metrics_monitor.threading.Thread", Mock(return_value=thread_mock))

    monitor.start()
    assert monitor.running is True

    monitor.stop()
    assert monitor.running is False
    assert monitor.monitor_thread is None


def test_callback_manager_ticker_callback_updates_storage():
    manager = CallbackManager(logger=Mock())
    data_manager = DummyDataManager()

    callback = manager._create_ticker_callback(data_manager)
    callback({"symbol": "BTCUSDT", "price": 50000})

    data_manager.storage.update_realtime_data.assert_called_once_with(
        "BTCUSDT", {"symbol": "BTCUSDT", "price": 50000}
    )


def test_callback_manager_active_symbols_callback_uses_storage():
    manager = CallbackManager(logger=Mock())
    data_manager = DummyDataManager()
    data_manager.storage.get_all_symbols.return_value = ["BTCUSDT"]

    callback = manager._create_active_symbols_callback(data_manager)
    assert callback() == ["BTCUSDT"]
    data_manager.storage.get_all_symbols.assert_called_once_with()


def test_volatility_tracker_delegates_to_components():
    calculator = Mock()
    cache = Mock()
    scheduler = Mock()
    tracker = VolatilityTracker(
        logger=Mock(), calculator=calculator, cache=cache, scheduler=scheduler
    )

    tracker.set_symbol_categories({"BTCUSDT": "linear"})
    calculator.set_symbol_categories.assert_called_once_with({"BTCUSDT": "linear"})

    tracker.set_active_symbols_callback(lambda: ["BTCUSDT"])
    scheduler.set_active_symbols_callback.assert_called_once()

    tracker.start_refresh_task()
    scheduler.start_refresh_task.assert_called_once()

    tracker.stop_refresh_task()
    scheduler.stop_refresh_task.assert_called_once()

    tracker.set_cached_volatility("BTCUSDT", 0.05)
    cache.set_cached_volatility.assert_called_once_with("BTCUSDT", 0.05)

    tracker.clear_stale_cache(["BTCUSDT"])
    cache.clear_stale_cache.assert_called_once_with(["BTCUSDT"])


@patch("opportunity_manager.OpportunityIntegrator")
@patch("opportunity_manager.OpportunityScanner")
@pytest.mark.asyncio
async def test_opportunity_manager_on_new_opportunity_async(mock_scanner, mock_integrator):
    from opportunity_manager import OpportunityManager

    data_manager = Mock()
    watchlist = Mock()
    volatility = Mock()

    manager = OpportunityManager(
        data_manager=data_manager,
        watchlist_manager=watchlist,
        volatility_tracker=volatility,
        logger=Mock(),
    )

    manager.start_websocket_connections_async = AsyncMock()

    ws_manager = Mock()
    ws_manager.running = False

    await manager.on_new_opportunity_async([
        "BTCUSDT"
    ], [], ws_manager, watchlist)

    manager.start_websocket_connections_async.assert_awaited_once_with(
        ws_manager, ["BTCUSDT"], []
    )
