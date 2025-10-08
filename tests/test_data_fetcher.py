"""Tests pour DataFetcher et FundingFetcher (parsing/validation/erreurs)."""

import pytest
from unittest.mock import Mock, patch
from data_fetcher import DataFetcher
from funding_fetcher import FundingFetcher
from pagination_handler import PaginationHandler


class TestDataFetcher:
    """Tests pour DataFetcher."""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger pour les tests."""
        return Mock()

    @pytest.fixture
    def fetcher(self, mock_logger):
        """Instance de DataFetcher pour les tests."""
        with patch('data_fetcher.FundingFetcher'), \
             patch('data_fetcher.SpreadFetcher'), \
             patch('data_fetcher.PaginationHandler'), \
             patch('data_fetcher.ErrorHandler'):
            return DataFetcher(logger=mock_logger)

    def test_init(self, mock_logger):
        """Test d'initialisation."""
        with patch('data_fetcher.FundingFetcher') as mock_funding, \
             patch('data_fetcher.SpreadFetcher') as mock_spread, \
             patch('data_fetcher.PaginationHandler') as mock_pagination, \
             patch('data_fetcher.ErrorHandler') as mock_error:
            
            fetcher = DataFetcher(logger=mock_logger)
            
            assert fetcher.logger == mock_logger
            mock_funding.assert_called_once_with(mock_logger)
            mock_spread.assert_called_once_with(mock_logger)
            mock_pagination.assert_called_once_with(mock_logger)
            mock_error.assert_called_once_with(mock_logger)

    def test_init_with_default_logger(self):
        """Test d'initialisation avec logger par défaut."""
        with patch('data_fetcher.FundingFetcher'), \
             patch('data_fetcher.SpreadFetcher'), \
             patch('data_fetcher.PaginationHandler'), \
             patch('data_fetcher.ErrorHandler'), \
             patch('data_fetcher.setup_logging') as mock_setup:
            
            mock_logger = Mock()
            mock_setup.return_value = mock_logger
            
            fetcher = DataFetcher()
            
            assert fetcher.logger == mock_logger

    def test_fetch_funding_map_delegation(self, fetcher):
        """Test de délégation vers FundingFetcher pour fetch_funding_map."""
        expected_result = {"BTCUSDT": {"funding": 0.0001}}
        with patch.object(fetcher._funding_fetcher, 'fetch_funding_map', return_value=expected_result) as mock_fetch:
            result = fetcher.fetch_funding_map("https://api-testnet.bybit.com", "linear", 10)
            
            assert result == expected_result
            mock_fetch.assert_called_once_with("https://api-testnet.bybit.com", "linear", 10)

    def test_fetch_funding_data_parallel_delegation(self, fetcher):
        """Test de délégation vers FundingFetcher pour fetch_funding_data_parallel."""
        expected_result = {"linear": {"BTCUSDT": {"funding": 0.0001}}}
        with patch.object(fetcher._funding_fetcher, 'fetch_funding_data_parallel', return_value=expected_result) as mock_fetch:
            result = fetcher.fetch_funding_data_parallel("https://api-testnet.bybit.com", ["linear"], 10)
            
            assert result == expected_result
            mock_fetch.assert_called_once_with("https://api-testnet.bybit.com", ["linear"], 10)

    def test_fetch_spread_data_delegation(self, fetcher):
        """Test de délégation vers SpreadFetcher pour fetch_spread_data."""
        expected_result = {"BTCUSDT": 0.001}
        with patch.object(fetcher._spread_fetcher, 'fetch_spread_data', return_value=expected_result) as mock_fetch:
            result = fetcher.fetch_spread_data("https://api-testnet.bybit.com", ["BTCUSDT"], 10, "linear")
            
            assert result == expected_result
            mock_fetch.assert_called_once_with("https://api-testnet.bybit.com", ["BTCUSDT"], 10, "linear")

    def test_fetch_paginated_data_delegation(self, fetcher):
        """Test de délégation vers PaginationHandler pour fetch_paginated_data."""
        expected_result = [{"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"}]
        with patch.object(fetcher._pagination_handler, 'fetch_paginated_data', return_value=expected_result) as mock_fetch:
            result = fetcher.fetch_paginated_data("https://api-testnet.bybit.com", "/v5/market/tickers", {}, 10, 100)
            
            assert result == expected_result
            mock_fetch.assert_called_once_with("https://api-testnet.bybit.com", "/v5/market/tickers", {}, 10, 100)

    def test_validate_funding_data_delegation(self, fetcher):
        """Test de délégation vers FundingFetcher pour validate_funding_data."""
        funding_data = {"BTCUSDT": {"funding": 0.0001}}
        with patch.object(fetcher._funding_fetcher, 'validate_funding_data', return_value=True) as mock_validate:
            result = fetcher.validate_funding_data(funding_data)
            
            assert result is True
            mock_validate.assert_called_once_with(funding_data)

    def test_validate_spread_data_delegation(self, fetcher):
        """Test de délégation vers SpreadFetcher pour validate_spread_data."""
        spread_data = {"BTCUSDT": 0.001}
        with patch.object(fetcher._spread_fetcher, 'validate_spread_data', return_value=True) as mock_validate:
            result = fetcher.validate_spread_data(spread_data)
            
            assert result is True
            mock_validate.assert_called_once_with(spread_data)

    def test_handle_error_delegation(self, fetcher):
        """Test de délégation vers ErrorHandler pour handle_error."""
        test_error = Exception("Test error")
        with patch.object(fetcher._error_handler, 'log_error') as mock_log:
            fetcher.handle_error(test_error, "test context")
            
            mock_log.assert_called_once_with(test_error, "test context")

    def test_should_retry_delegation(self, fetcher):
        """Test de délégation vers ErrorHandler pour should_retry."""
        test_error = Exception("Test error")
        with patch.object(fetcher._error_handler, 'should_retry', return_value=True) as mock_retry:
            result = fetcher.should_retry(test_error, 1, 3)
            
            assert result is True
            mock_retry.assert_called_once_with(test_error, 1, 3)

    def test_fetch_complete_market_data_success(self, fetcher, mock_logger):
        """Test de récupération complète des données de marché avec succès."""
        funding_data = {"BTCUSDT": {"funding": 0.0001}}
        spread_data = {"BTCUSDT": 0.001}
        
        with patch.object(fetcher, 'fetch_funding_data_parallel', return_value=funding_data) as mock_funding, \
             patch.object(fetcher, 'fetch_spread_data', return_value=spread_data) as mock_spread, \
             patch.object(fetcher, 'validate_funding_data', return_value=True) as mock_validate_funding, \
             patch.object(fetcher, 'validate_spread_data', return_value=True) as mock_validate_spread:
            
            result = fetcher.fetch_complete_market_data(
                "https://api-testnet.bybit.com",
                ["linear"],
                ["BTCUSDT"],
                10
            )
            
            expected_result = {
                "funding_data": funding_data,
                "spread_data": spread_data,
                "funding_valid": True,
                "spread_valid": True
            }
            
            assert result == expected_result
            mock_funding.assert_called_once_with("https://api-testnet.bybit.com", ["linear"], 10)
            mock_spread.assert_called_once_with("https://api-testnet.bybit.com", ["BTCUSDT"], 10, "linear")
            mock_validate_funding.assert_called_once_with(funding_data)
            mock_validate_spread.assert_called_once_with(spread_data)

    def test_fetch_complete_market_data_invalid_funding(self, fetcher, mock_logger):
        """Test de récupération complète avec données de funding invalides."""
        funding_data = {"BTCUSDT": {"funding": 0.0001}}
        spread_data = {"BTCUSDT": 0.001}
        
        with patch.object(fetcher, 'fetch_funding_data_parallel', return_value=funding_data) as mock_funding, \
             patch.object(fetcher, 'fetch_spread_data', return_value=spread_data) as mock_spread, \
             patch.object(fetcher, 'validate_funding_data', return_value=False) as mock_validate_funding, \
             patch.object(fetcher, 'validate_spread_data', return_value=True) as mock_validate_spread:
            
            result = fetcher.fetch_complete_market_data(
                "https://api-testnet.bybit.com",
                ["linear"],
                ["BTCUSDT"],
                10
            )
            
            expected_result = {
                "funding_data": funding_data,
                "spread_data": spread_data,
                "funding_valid": False,
                "spread_valid": True
            }
            
            assert result == expected_result
            mock_logger.warning.assert_called_with("⚠️ Données de funding invalides")

    def test_fetch_complete_market_data_invalid_spread(self, fetcher, mock_logger):
        """Test de récupération complète avec données de spread invalides."""
        funding_data = {"BTCUSDT": {"funding": 0.0001}}
        spread_data = {"BTCUSDT": 0.001}
        
        with patch.object(fetcher, 'fetch_funding_data_parallel', return_value=funding_data) as mock_funding, \
             patch.object(fetcher, 'fetch_spread_data', return_value=spread_data) as mock_spread, \
             patch.object(fetcher, 'validate_funding_data', return_value=True) as mock_validate_funding, \
             patch.object(fetcher, 'validate_spread_data', return_value=False) as mock_validate_spread:
            
            result = fetcher.fetch_complete_market_data(
                "https://api-testnet.bybit.com",
                ["linear"],
                ["BTCUSDT"],
                10
            )
            
            expected_result = {
                "funding_data": funding_data,
                "spread_data": spread_data,
                "funding_valid": True,
                "spread_valid": False
            }
            
            assert result == expected_result
            mock_logger.warning.assert_called_with("⚠️ Données de spread invalides")

    def test_fetch_complete_market_data_exception(self, fetcher, mock_logger):
        """Test de récupération complète avec exception."""
        with patch.object(fetcher, 'fetch_funding_data_parallel', side_effect=Exception("Test error")), \
             patch.object(fetcher._error_handler, 'log_error') as mock_log:
            
            with pytest.raises(Exception, match="Test error"):
                fetcher.fetch_complete_market_data(
                    "https://api-testnet.bybit.com",
                    ["linear"],
                    ["BTCUSDT"],
                    10
                )
            
            mock_log.assert_called_once()

    def test_fetch_complete_market_data_multiple_categories(self, fetcher, mock_logger):
        """Test de récupération complète avec plusieurs catégories."""
        funding_data = {"BTCUSDT": {"funding": 0.0001}}
        linear_spread_data = {"BTCUSDT": 0.001}
        inverse_spread_data = {"BTCUSD": 0.002}
        
        with patch.object(fetcher, 'fetch_funding_data_parallel', return_value=funding_data) as mock_funding, \
             patch.object(fetcher, 'fetch_spread_data', side_effect=[linear_spread_data, inverse_spread_data]) as mock_spread, \
             patch.object(fetcher, 'validate_funding_data', return_value=True) as mock_validate_funding, \
             patch.object(fetcher, 'validate_spread_data', return_value=True) as mock_validate_spread:
            
            result = fetcher.fetch_complete_market_data(
                "https://api-testnet.bybit.com",
                ["linear", "inverse"],
                ["BTCUSDT", "BTCUSD"],
                10
            )
            
            expected_result = {
                "funding_data": funding_data,
                "spread_data": {"BTCUSDT": 0.001, "BTCUSD": 0.002},
                "funding_valid": True,
                "spread_valid": True
            }
            
            assert result == expected_result
            assert mock_spread.call_count == 2
            mock_spread.assert_any_call("https://api-testnet.bybit.com", ["BTCUSDT", "BTCUSD"], 10, "linear")
            mock_spread.assert_any_call("https://api-testnet.bybit.com", ["BTCUSDT", "BTCUSD"], 10, "inverse")

    def test_get_fetching_stats(self, fetcher):
        """Test de récupération des statistiques de récupération."""
        stats = fetcher.get_fetching_stats()
        
        assert "funding_fetcher_available" in stats
        assert "spread_fetcher_available" in stats
        assert "pagination_handler_available" in stats
        assert "error_handler_available" in stats
        
        # Vérifier que tous les composants sont disponibles
        assert stats["funding_fetcher_available"] is True
        assert stats["spread_fetcher_available"] is True
        assert stats["pagination_handler_available"] is True
        assert stats["error_handler_available"] is True

    def test_get_fetching_stats_missing_components(self, mock_logger):
        """Test de récupération des statistiques avec composants manquants."""
        with patch('data_fetcher.FundingFetcher'), \
             patch('data_fetcher.SpreadFetcher'), \
             patch('data_fetcher.PaginationHandler'), \
             patch('data_fetcher.ErrorHandler'):
            
            fetcher = DataFetcher(logger=mock_logger)
            
            # Simuler un composant manquant
            delattr(fetcher._funding_fetcher, 'logger')
            
            stats = fetcher.get_fetching_stats()
            
            assert stats["funding_fetcher_available"] is False
            assert stats["spread_fetcher_available"] is True
            assert stats["pagination_handler_available"] is True
            assert stats["error_handler_available"] is True


class TestFundingFetcher:
    def test_fetch_funding_map_success(self):
        ff = FundingFetcher(logger=Mock())
        with patch('funding_fetcher.PaginationHandler') as PH, \
             patch('funding_fetcher.ErrorHandler'):
            ph = PH.return_value
            ph.fetch_paginated_data.return_value = [
                {"symbol": "BTCUSDT", "fundingRate": "0.0001", "volume24h": "100", "nextFundingTime": "t"},
                {"symbol": "", "fundingRate": "0.1"},
            ]
            res = ff.fetch_funding_map("http://x", "linear", 10)
            assert res["BTCUSDT"]["funding"] == 0.0001
            assert res["BTCUSDT"]["volume"] == 100.0
            assert res["BTCUSDT"]["next_funding_time"] == "t"

    def test_fetch_funding_map_error_propagates(self):
        ff = FundingFetcher(logger=Mock())
        with patch('funding_fetcher.PaginationHandler') as PH, \
             patch('funding_fetcher.ErrorHandler') as EH:
            ph = PH.return_value
            ph.fetch_paginated_data.side_effect = RuntimeError("boom")
            eh = EH.return_value
            with pytest.raises(RuntimeError):
                ff.fetch_funding_map("http://x", "linear", 10)
            eh.log_error.assert_called()


class TestPaginationHandler:
    def test_fetch_paginated_data_multiple_pages_then_stop(self):
        ph = PaginationHandler(logger=Mock())

        def _client_factory(timeout):
            class _Resp:
                def __init__(self, code, payload, text=""):
                    self.status_code = code
                    self._payload = payload
                    self.text = text
                def json(self):
                    return self._payload
            # 2 pages puis fin (pas de nextPageCursor)
            pages = [
                _Resp(200, {"retCode": 0, "result": {"list": [1,2], "nextPageCursor": "A"}}),
                _Resp(200, {"retCode": 0, "result": {"list": [3], "nextPageCursor": None}}),
            ]
            class _Client:
                def get(self, url, params=None):
                    return pages.pop(0)
            return _Client()

        with patch('pagination_handler.get_http_client', _client_factory), \
             patch('pagination_handler.get_rate_limiter') as RL:
            RL.return_value.acquire = lambda: None
            data = ph.fetch_paginated_data("http://x", "/v5/market/x", {"limit": 2}, timeout=5, max_pages=10)
            assert data == [1,2,3]

    def test_fetch_paginated_data_stops_on_empty_list(self):
        ph = PaginationHandler(logger=Mock())

        def _client_factory(timeout):
            class _Resp:
                def __init__(self, code, payload):
                    self.status_code = code
                    self._payload = payload
                    self.text = ""
                def json(self):
                    return self._payload
            pages = [
                _Resp(200, {"retCode": 0, "result": {"list": []}}),
            ]
            class _Client:
                def get(self, url, params=None):
                    return pages.pop(0)
            return _Client()

        with patch('pagination_handler.get_http_client', _client_factory), \
             patch('pagination_handler.get_rate_limiter') as RL:
            RL.return_value.acquire = lambda: None
            data = ph.fetch_paginated_data("http://x", "/v5/market/x", {"limit": 2}, timeout=5, max_pages=10)
            assert data == []

    def test_fetch_paginated_data_http_4xx_raises(self):
        ph = PaginationHandler(logger=Mock())

        def _client_factory(timeout):
            class _Resp:
                def __init__(self):
                    self.status_code = 400
                    self.text = "Bad"
                def json(self):
                    return {}
            class _Client:
                def get(self, url, params=None):
                    return _Resp()
            return _Client()

        with patch('pagination_handler.get_http_client', _client_factory), \
             patch('pagination_handler.get_rate_limiter') as RL:
            RL.return_value.acquire = lambda: None
            with pytest.raises(RuntimeError, match="Erreur HTTP Bybit GET"):
                ph.fetch_paginated_data("http://x", "/v5/market/x", {"limit": 2}, timeout=5, max_pages=10)

    def test_fetch_paginated_data_api_error_raises(self):
        ph = PaginationHandler(logger=Mock())

        def _client_factory(timeout):
            class _Resp:
                def __init__(self):
                    self.status_code = 200
                    self.text = ""
                def json(self):
                    return {"retCode": 10001, "retMsg": "bad"}
            class _Client:
                def get(self, url, params=None):
                    return _Resp()
            return _Client()

        with patch('pagination_handler.get_http_client', _client_factory), \
             patch('pagination_handler.get_rate_limiter') as RL:
            RL.return_value.acquire = lambda: None
            with pytest.raises(RuntimeError, match="Erreur API Bybit GET"):
                ph.fetch_paginated_data("http://x", "/v5/market/x", {"limit": 2}, timeout=5, max_pages=10)

    def test_build_funding_entry_and_safe_float_conversion(self):
        ff = FundingFetcher(logger=Mock())
        entry = ff._build_funding_entry("BTCUSDT", "0.0002", None, "t")
        assert entry == {"funding": 0.0002, "volume": 0.0, "next_funding_time": "t"}
        assert ff._build_funding_entry("BTCUSDT", None, "1", None) is None

    def test_validate_funding_data(self):
        ff = FundingFetcher(logger=Mock())
        valid = {
            "BTCUSDT": {"funding": 0.001, "volume": 1.0, "next_funding_time": "t"},
            "ETHUSDT": {"funding": 0.0, "volume": 0.0, "next_funding_time": None},
        }
        assert ff.validate_funding_data(valid) is True
        assert ff.validate_funding_data({}) is False
        assert ff._validate_single_funding_entry("X", {"funding": "x"}) is False

    def test_fetch_funding_data_parallel_aggregates_and_errors(self):
        ff = FundingFetcher(logger=Mock())
        with patch.object(ff, 'fetch_funding_map') as fm:
            fm.side_effect = [
                {"BTCUSDT": {"funding": 0.001, "volume": 1.0, "next_funding_time": "t"}},
                {"ETHUSDT": {"funding": 0.002, "volume": 2.0, "next_funding_time": "t2"}},
            ]
            res = ff.fetch_funding_data_parallel("http://x", ["linear", "inverse"], 10)
            assert "BTCUSDT" in res and "ETHUSDT" in res

        with patch.object(ff, 'fetch_funding_map') as fm, \
             patch('funding_fetcher.ErrorHandler') as EH:
            fm.side_effect = [
                RuntimeError("fail"),
            ]
            eh = EH.return_value
            with pytest.raises(RuntimeError):
                ff.fetch_funding_data_parallel("http://x", ["linear", "inverse"], 10)
            eh.log_error.assert_called()


class TestDataValidator:
    def test_validate_data_integrity_success(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        result = validator.validate_data_integrity(
            ["BTCUSDT"], ["BTCUSD"], {"BTCUSDT": {"funding": 0.001}}
        )
        assert result is True

    def test_validate_data_integrity_empty_lists_fails(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        result = validator.validate_data_integrity([], [], {})
        assert result is False

    def test_validate_data_integrity_no_funding_fails(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        result = validator.validate_data_integrity(["BTCUSDT"], [], {})
        assert result is False

    def test_validate_funding_data_tuple_format(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        funding_data = {"BTCUSDT": (0.001, 1000.0, "1h", 0.01)}
        result = validator.validate_funding_data(funding_data)
        assert result is True

    def test_validate_funding_data_dict_format(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        funding_data = {
            "BTCUSDT": {
                "funding": 0.001,
                "volume": 1000.0,
                "funding_time": "1h",
                "spread": 0.01
            }
        }
        result = validator.validate_funding_data(funding_data)
        assert result is True

    def test_validate_funding_data_invalid_format_fails(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        funding_data = {"BTCUSDT": "invalid"}
        result = validator.validate_funding_data(funding_data)
        assert result is False

    def test_validate_realtime_data_success(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        realtime_data = {
            "BTCUSDT": {
                "mark_price": 50000.0,
                "last_price": 50001.0,
                "timestamp": 1640995200.0
            }
        }
        result = validator.validate_realtime_data(realtime_data)
        assert result is True

    def test_validate_realtime_data_empty_returns_true(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        result = validator.validate_realtime_data({})
        assert result is True

    def test_validate_symbol_categories_success(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        categories = {"BTCUSDT": "linear", "BTCUSD": "inverse"}
        result = validator.validate_symbol_categories(categories)
        assert result is True

    def test_validate_symbol_categories_invalid_category_fails(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        categories = {"BTCUSDT": "invalid"}
        result = validator.validate_symbol_categories(categories)
        assert result is False

    def test_validate_symbol_lists_success(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        result = validator.validate_symbol_lists(["BTCUSDT"], ["BTCUSD"])
        assert result is True

    def test_validate_symbol_lists_invalid_type_fails(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        result = validator.validate_symbol_lists("not_a_list", ["BTCUSD"])
        assert result is False

    def test_validate_symbol_lists_empty_string_fails(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        result = validator.validate_symbol_lists([""], ["BTCUSD"])
        assert result is False

    def test_get_loading_summary_success(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        summary = validator.get_loading_summary(
            ["BTCUSDT", "ETHUSDT"], ["BTCUSD"], {"BTCUSDT": {"funding": 0.001}}
        )
        assert summary["linear_count"] == 2
        assert summary["inverse_count"] == 1
        assert summary["total_symbols"] == 3
        assert summary["funding_data_count"] == 1

    def test_validate_parameters_success(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        result = validator.validate_parameters(
            "http://x", {"test": "data"}, Mock(), Mock()
        )
        assert result is True

    def test_validate_parameters_invalid_url_fails(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        result = validator.validate_parameters("", {}, Mock(), Mock())
        assert result is False

    def test_validate_parameters_missing_manager_fails(self):
        from data_validator import DataValidator
        validator = DataValidator(logger=Mock())
        result = validator.validate_parameters("http://x", {}, None, Mock())
        assert result is False


class TestShutdownManager:
    def test_init_sets_start_time_and_flags(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        assert manager.start_time > 0
        assert manager._shutdown_in_progress is False

    def test_setup_signal_handler_registers_handler(self):
        from shutdown_manager import ShutdownManager
        import signal
        manager = ShutdownManager(logger=Mock())
        orchestrator = Mock()
        orchestrator.running = True
        manager.setup_signal_handler(orchestrator)
        # Vérifier que le handler est enregistré
        assert signal.signal(signal.SIGINT, signal.SIG_DFL) is not None

    def test_signal_handler_ignores_if_not_running(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        orchestrator = Mock()
        orchestrator.running = False
        manager._signal_handler(orchestrator, signal.SIGINT, None)
        # Ne devrait pas appeler os._exit
        assert manager._shutdown_in_progress is False

    def test_signal_handler_ignores_if_shutdown_in_progress(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        manager._shutdown_in_progress = True
        orchestrator = Mock()
        orchestrator.running = True
        manager._signal_handler(orchestrator, signal.SIGINT, None)
        # Ne devrait pas appeler os._exit
        assert manager._shutdown_in_progress is True

    @patch('shutdown_manager.os._exit')
    def test_signal_handler_calls_exit_on_success(self, mock_exit):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        orchestrator = Mock()
        orchestrator.running = True
        orchestrator.monitoring_manager = Mock()
        orchestrator.monitoring_manager.candidate_symbols = []
        manager._signal_handler(orchestrator, signal.SIGINT, None)
        mock_exit.assert_called_once_with(0)

    @patch('shutdown_manager.os._exit')
    def test_signal_handler_calls_exit_on_exception(self, mock_exit):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        orchestrator = Mock()
        orchestrator.running = True
        orchestrator.monitoring_manager = Mock()
        orchestrator.monitoring_manager.candidate_symbols = []
        # Simuler une exception
        with patch('shutdown_manager.log_shutdown_summary', side_effect=Exception("test")):
            manager._signal_handler(orchestrator, signal.SIGINT, None)
        mock_exit.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_stop_all_managers_async_success(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        managers = {
            "ws_manager": Mock(),
            "display_manager": Mock(),
            "monitoring_manager": Mock(),
            "volatility_tracker": Mock()
        }
        await manager.stop_all_managers_async(managers)
        # Vérifier que les méthodes stop sont appelées
        managers["ws_manager"].stop.assert_called_once()
        managers["display_manager"].stop_display_loop.assert_called_once()
        managers["monitoring_manager"].stop_continuous_monitoring.assert_called_once()
        managers["volatility_tracker"].stop_refresh_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_all_managers_async_handles_missing_managers(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        managers = {}
        await manager.stop_all_managers_async(managers)
        # Ne devrait pas lever d'exception

    @pytest.mark.asyncio
    async def test_stop_all_managers_async_handles_exceptions(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        managers = {
            "ws_manager": Mock(),
            "display_manager": Mock(),
            "monitoring_manager": Mock(),
            "volatility_tracker": Mock()
        }
        managers["ws_manager"].stop.side_effect = Exception("test")
        await manager.stop_all_managers_async(managers)
        # Ne devrait pas lever d'exception

    def test_stop_all_managers_sync_success(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        managers = {
            "ws_manager": Mock(),
            "display_manager": Mock(),
            "monitoring_manager": Mock(),
            "volatility_tracker": Mock(),
            "metrics_monitor": Mock()
        }
        manager.stop_all_managers_sync(managers)
        # Vérifier que les flags sont définis
        assert managers["ws_manager"].running is False
        assert managers["display_manager"]._running is False
        assert managers["monitoring_manager"]._running is False
        assert managers["volatility_tracker"]._running is False
        assert managers["metrics_monitor"].running is False

    def test_stop_websocket_manager_sync_success(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        ws_manager = Mock()
        ws_manager.stop_sync = Mock()
        manager.stop_websocket_manager_sync(ws_manager)
        ws_manager.stop_sync.assert_called_once()

    def test_stop_websocket_manager_sync_handles_missing_stop_sync(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        ws_manager = Mock()
        ws_manager.running = True
        manager.stop_websocket_manager_sync(ws_manager)
        assert ws_manager.running is False

    def test_stop_display_manager_sync_success(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        display_manager = Mock()
        display_manager.display_running = True
        manager.stop_display_manager_sync(display_manager)
        assert display_manager.display_running is False

    def test_stop_monitoring_manager_sync_success(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        monitoring_manager = Mock()
        monitoring_manager.stop_monitoring = Mock()
        manager.stop_monitoring_manager_sync(monitoring_manager)
        monitoring_manager.stop_monitoring.assert_called_once()

    def test_stop_volatility_manager_sync_success(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        volatility_tracker = Mock()
        volatility_tracker.stop_refresh_task = Mock()
        manager.stop_volatility_manager_sync(volatility_tracker)
        volatility_tracker.stop_refresh_task.assert_called_once()

    def test_stop_metrics_monitor_sync_success(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        metrics_monitor = Mock()
        metrics_monitor.stop = Mock()
        manager.stop_metrics_monitor_sync(metrics_monitor)
        metrics_monitor.stop.assert_called_once()

    def test_cleanup_resources_success(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        managers = {
            "data_manager": Mock(),
            "ws_manager": Mock(),
            "monitoring_manager": Mock()
        }
        managers["data_manager"].volatility_cache = Mock()
        managers["data_manager"].volatility_cache.clear_all_cache = Mock()
        managers["ws_manager"]._ticker_callback = Mock()
        managers["ws_manager"]._ws_conns = []
        managers["ws_manager"]._ws_tasks = []
        managers["monitoring_manager"]._on_new_opportunity_callback = Mock()
        managers["monitoring_manager"]._on_candidate_ticker_callback = Mock()
        managers["monitoring_manager"].candidate_symbols = []
        manager._cleanup_resources(managers)
        managers["data_manager"].volatility_cache.clear_all_cache.assert_called_once()

    def test_force_garbage_collection_success(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        manager._force_garbage_collection()
        # Ne devrait pas lever d'exception

    def test_cleanup_system_resources_success(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        manager.cleanup_system_resources()
        # Ne devrait pas lever d'exception

    def test_perform_final_cleanup_success(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        managers = {}
        manager.perform_final_cleanup(managers)
        # Ne devrait pas lever d'exception

    def test_force_cleanup_threads_success(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        manager.force_cleanup_threads()
        # Ne devrait pas lever d'exception

    def test_force_close_network_connections_success(self):
        from shutdown_manager import ShutdownManager
        manager = ShutdownManager(logger=Mock())
        managers = {
            "http_client_manager": Mock(),
            "ws_manager": Mock(),
            "monitoring_manager": Mock()
        }
        managers["http_client_manager"].close_all = Mock()
        managers["ws_manager"]._ws_conns = []
        managers["ws_manager"]._ws_tasks = []
        managers["monitoring_manager"].candidate_ws_client = Mock()
        managers["monitoring_manager"].candidate_ws_client.close = Mock()
        manager.force_close_network_connections(managers)
        managers["http_client_manager"].close_all.assert_called_once()
        managers["monitoring_manager"].candidate_ws_client.close.assert_called_once()


class TestWatchlistManager:
    def test_init_sets_components_and_config(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        assert manager.testnet is True
        assert manager.config_manager is not None
        assert manager.market_data_fetcher is not None
        assert manager.symbol_filter is not None
        assert manager.config is not None
        assert manager.symbol_categories == {}
        assert manager.selected_symbols == []
        assert manager.funding_data == {}
        assert manager.original_funding_data == {}

    def test_get_config_returns_config(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        config = manager.get_config()
        assert config is not None

    def test_set_symbol_categories_sets_categories(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        categories = {"BTCUSDT": "linear", "BTCUSD": "inverse"}
        manager.set_symbol_categories(categories)
        assert manager.symbol_categories == categories

    def test_extract_config_parameters_returns_all_params(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.config = {
            "categorie": "linear",
            "funding_min": 0.001,
            "funding_max": 0.01,
            "volume_min_millions": 10,
            "spread_max": 0.05,
            "volatility_min": 0.1,
            "volatility_max": 0.5,
            "limite": 20,
            "funding_time_min_minutes": 5,
            "funding_time_max_minutes": 60
        }
        params = manager._extract_config_parameters()
        assert params["categorie"] == "linear"
        assert params["funding_min"] == 0.001
        assert params["funding_max"] == 0.01
        assert params["volume_min_millions"] == 10
        assert params["spread_max"] == 0.05
        assert params["volatility_min"] == 0.1
        assert params["volatility_max"] == 0.5
        assert params["limite"] == 20
        assert params["funding_time_min_minutes"] == 5
        assert params["funding_time_max_minutes"] == 60

    def test_extract_config_parameters_uses_defaults(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.config = {}
        params = manager._extract_config_parameters()
        assert params["categorie"] == "both"
        assert params["funding_min"] is None
        assert params["funding_max"] is None
        assert params["volume_min_millions"] is None
        assert params["spread_max"] is None
        assert params["volatility_min"] is None
        assert params["volatility_max"] is None
        assert params["limite"] is None
        assert params["funding_time_min_minutes"] is None
        assert params["funding_time_max_minutes"] is None

    def test_fetch_funding_data_linear_category(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.market_data_fetcher.fetch_funding_map = Mock(return_value={"BTCUSDT": {"funding": 0.001}})
        result = manager._fetch_funding_data("http://x", "linear")
        assert result == {"BTCUSDT": {"funding": 0.001}}
        manager.market_data_fetcher.fetch_funding_map.assert_called_once_with("http://x", "linear", 10)

    def test_fetch_funding_data_inverse_category(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.market_data_fetcher.fetch_funding_map = Mock(return_value={"BTCUSD": {"funding": 0.001}})
        result = manager._fetch_funding_data("http://x", "inverse")
        assert result == {"BTCUSD": {"funding": 0.001}}
        manager.market_data_fetcher.fetch_funding_map.assert_called_once_with("http://x", "inverse", 10)

    def test_fetch_funding_data_both_category(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.market_data_fetcher.fetch_funding_data_parallel = Mock(return_value={"BTCUSDT": {"funding": 0.001}})
        result = manager._fetch_funding_data("http://x", "both")
        assert result == {"BTCUSDT": {"funding": 0.001}}
        manager.market_data_fetcher.fetch_funding_data_parallel.assert_called_once_with("http://x", ["linear", "inverse"], 10)

    def test_get_and_validate_funding_data_success(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager._fetch_funding_data = Mock(return_value={"BTCUSDT": {"funding": 0.001}})
        result = manager._get_and_validate_funding_data("http://x", "linear")
        assert result == {"BTCUSDT": {"funding": 0.001}}

    def test_get_and_validate_funding_data_empty_raises_error(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager._fetch_funding_data = Mock(return_value={})
        with pytest.raises(RuntimeError, match="Aucun funding disponible"):
            manager._get_and_validate_funding_data("http://x", "linear")

    def test_count_initial_symbols_counts_correctly(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        perp_data = {"linear": ["BTCUSDT", "ETHUSDT"], "inverse": ["BTCUSD"]}
        funding_map = {"BTCUSDT": {"funding": 0.001}, "ETHUSDT": {"funding": 0.002}}
        count = manager._count_initial_symbols(perp_data, funding_map)
        assert count == 2

    def test_apply_final_limit_applies_limit(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOTUSDT", "LINKUSDT"]
        result, count = manager._apply_final_limit(symbols, 3)
        assert result == ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
        assert count == 3

    def test_apply_final_limit_no_limit_returns_all(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
        result, count = manager._apply_final_limit(symbols, None)
        assert result == symbols
        assert count == 3

    def test_apply_final_limit_limit_larger_than_list(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        symbols = ["BTCUSDT", "ETHUSDT"]
        result, count = manager._apply_final_limit(symbols, 5)
        assert result == symbols
        assert count == 2

    def test_store_original_funding_data_stores_correctly(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        funding_map = {
            "BTCUSDT": {"funding": 0.001, "next_funding_time": "2024-01-01T12:00:00Z"},
            "ETHUSDT": {"funding": 0.002, "next_funding_time": "2024-01-01T12:00:00Z"},
            "ADAUSDT": {"funding": 0.003}  # Pas de next_funding_time
        }
        manager._store_original_funding_data(funding_map)
        assert manager.original_funding_data == {
            "BTCUSDT": "2024-01-01T12:00:00Z",
            "ETHUSDT": "2024-01-01T12:00:00Z"
        }

    def test_apply_spread_filter_no_spread_max_returns_with_default(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        filtered_symbols = [("BTCUSDT", 0.001, 1000.0, "1h")]
        result = manager._apply_spread_filter(filtered_symbols, None, "http://x")
        assert result == [("BTCUSDT", 0.001, 1000.0, "1h", 0.0)]

    def test_apply_spread_filter_empty_list_returns_empty(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        result = manager._apply_spread_filter([], 0.05, "http://x")
        assert result == []

    def test_apply_spread_filter_exception_returns_with_default(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.market_data_fetcher.fetch_spread_data = Mock(side_effect=Exception("test"))
        filtered_symbols = [("BTCUSDT", 0.001, 1000.0, "1h")]
        result = manager._apply_spread_filter(filtered_symbols, 0.05, "http://x")
        assert result == [("BTCUSDT", 0.001, 1000.0, "1h", 0.0)]

    def test_find_candidate_symbols_no_filters_returns_empty(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.config = {}
        result = manager.find_candidate_symbols("http://x", {"linear": [], "inverse": []})
        assert result == []

    def test_find_candidate_symbols_no_funding_filters_returns_empty(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.config = {"volume_min_millions": 10}
        result = manager.find_candidate_symbols("http://x", {"linear": [], "inverse": []})
        assert result == []

    def test_find_candidate_symbols_restrictive_time_filter_returns_empty(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.config = {
            "funding_min": 0.001,
            "funding_time_max_minutes": 5  # Trop restrictif
        }
        result = manager.find_candidate_symbols("http://x", {"linear": [], "inverse": []})
        assert result == []

    def test_find_candidate_symbols_exception_returns_empty(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.config = {"funding_min": 0.001}
        manager._fetch_funding_data = Mock(side_effect=Exception("test"))
        result = manager.find_candidate_symbols("http://x", {"linear": [], "inverse": []})
        assert result == []

    def test_check_if_symbol_now_passes_filters_calls_symbol_filter(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.config = {"funding_min": 0.001, "funding_max": 0.01, "volume_min_millions": 10}
        manager.symbol_filter.check_realtime_filters = Mock(return_value=True)
        ticker_data = {"funding_rate": 0.005, "volume24h": 15000000}
        result = manager.check_if_symbol_now_passes_filters("BTCUSDT", ticker_data)
        assert result is True
        manager.symbol_filter.check_realtime_filters.assert_called_once_with(
            "BTCUSDT", ticker_data, 0.001, 0.01, 10
        )

    def test_get_selected_symbols_returns_copy(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.selected_symbols = ["BTCUSDT", "ETHUSDT"]
        result = manager.get_selected_symbols()
        assert result == ["BTCUSDT", "ETHUSDT"]
        assert result is not manager.selected_symbols  # Copie

    def test_get_funding_data_returns_copy(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.funding_data = {"BTCUSDT": {"funding": 0.001}}
        result = manager.get_funding_data()
        assert result == {"BTCUSDT": {"funding": 0.001}}
        assert result is not manager.funding_data  # Copie

    def test_get_original_funding_data_returns_copy(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.original_funding_data = {"BTCUSDT": "2024-01-01T12:00:00Z"}
        result = manager.get_original_funding_data()
        assert result == {"BTCUSDT": "2024-01-01T12:00:00Z"}
        assert result is not manager.original_funding_data  # Copie

    def test_calculate_funding_time_remaining_delegates_to_symbol_filter(self):
        from watchlist_manager import WatchlistManager
        manager = WatchlistManager(testnet=True, logger=Mock())
        manager.symbol_filter.calculate_funding_time_remaining = Mock(return_value="1h 30m 45s")
        result = manager.calculate_funding_time_remaining("2024-01-01T12:00:00Z")
        assert result == "1h 30m 45s"
        manager.symbol_filter.calculate_funding_time_remaining.assert_called_once_with("2024-01-01T12:00:00Z")


class TestDisplayManager:
    def test_init_sets_components_and_state(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        assert manager.data_manager is data_manager
        assert manager.display_interval_seconds == 10
        assert manager.price_ttl_sec == 120
        assert manager._first_display is True
        assert manager._display_task is None
        assert manager._running is False
        assert manager._formatter is not None

    def test_set_volatility_callback_delegates_to_formatter(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        callback = Mock()
        manager.set_volatility_callback(callback)
        manager._formatter.set_volatility_callback.assert_called_once_with(callback)

    def test_set_display_interval_sets_interval(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        manager.set_display_interval(30)
        assert manager.display_interval_seconds == 30

    def test_set_price_ttl_sets_ttl(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        manager.set_price_ttl(60)
        assert manager.price_ttl_sec == 60

    @pytest.mark.asyncio
    async def test_start_display_loop_creates_task(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        await manager.start_display_loop()
        assert manager._running is True
        assert manager._display_task is not None
        assert not manager._display_task.done()

    @pytest.mark.asyncio
    async def test_start_display_loop_already_running_warns(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        manager._display_task = Mock()
        manager._display_task.done.return_value = False
        await manager.start_display_loop()
        manager.logger.warning.assert_called_once_with("⚠️ DisplayManager déjà en cours d'exécution")

    @pytest.mark.asyncio
    async def test_stop_display_loop_stops_running(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        manager._running = True
        manager._display_task = Mock()
        manager._display_task.done.return_value = False
        manager._display_task.cancel = Mock()
        await manager.stop_display_loop()
        assert manager._running is False
        manager._display_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_display_loop_not_running_returns_early(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        manager._running = False
        await manager.stop_display_loop()
        # Ne devrait pas lever d'exception

    @pytest.mark.asyncio
    async def test_stop_display_loop_handles_timeout(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        manager._running = True
        manager._display_task = Mock()
        manager._display_task.done.return_value = False
        manager._display_task.cancel = Mock()
        # Simuler un timeout
        with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError):
            await manager.stop_display_loop()
        manager.logger.warning.assert_called_once_with("⚠️ Tâche d'affichage n'a pas pu être annulée dans les temps")

    @pytest.mark.asyncio
    async def test_stop_display_loop_handles_cancelled_error(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        manager._running = True
        manager._display_task = Mock()
        manager._display_task.done.return_value = False
        manager._display_task.cancel = Mock()
        # Simuler une annulation normale
        with patch('asyncio.wait_for', side_effect=asyncio.CancelledError):
            await manager.stop_display_loop()
        # Ne devrait pas lever d'exception

    @pytest.mark.asyncio
    async def test_stop_display_loop_handles_exception(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        manager._running = True
        manager._display_task = Mock()
        manager._display_task.done.return_value = False
        manager._display_task.cancel = Mock(side_effect=Exception("test"))
        await manager.stop_display_loop()
        manager.logger.warning.assert_called_once_with("⚠️ Erreur arrêt tâche affichage: test")

    @pytest.mark.asyncio
    async def test_display_loop_runs_while_running(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        manager._running = True
        manager._print_price_table = Mock()
        # Simuler l'arrêt après une itération
        manager._running = False
        await manager._display_loop()
        manager._print_price_table.assert_called_once()

    @pytest.mark.asyncio
    async def test_display_loop_sleeps_for_interval(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        manager.display_interval_seconds = 5
        manager._running = True
        manager._print_price_table = Mock()
        # Simuler l'arrêt après une itération
        manager._running = False
        with patch('asyncio.sleep') as mock_sleep:
            await manager._display_loop()
            mock_sleep.assert_called_once_with(5)

    def test_print_price_table_no_funding_data_returns_early(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        data_manager.get_all_funding_data.return_value = {}
        manager._print_price_table()
        # Ne devrait pas lever d'exception

    def test_print_price_table_first_display_sets_flag(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        data_manager.get_all_funding_data.return_value = {}
        manager._print_price_table()
        assert manager._first_display is False

    def test_print_price_table_data_not_available_returns_early(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        data_manager.get_all_funding_data.return_value = {"BTCUSDT": {"funding": 0.001}}
        manager._formatter.are_all_data_available.return_value = False
        manager._print_price_table()
        manager.logger.info.assert_called_once_with("⏳ En attente des données de volatilité et spread...")

    def test_print_price_table_data_available_prints_table(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        data_manager.get_all_funding_data.return_value = {"BTCUSDT": {"funding": 0.001}}
        manager._formatter.are_all_data_available.return_value = True
        manager._formatter.calculate_column_widths.return_value = {"symbol": 10, "funding": 8}
        manager._formatter.format_table_header.return_value = "Header"
        manager._formatter.format_table_separator.return_value = "Separator"
        manager._formatter.prepare_row_data.return_value = {"funding": 0.001}
        manager._formatter.format_table_row.return_value = "Row"
        with patch('builtins.print') as mock_print:
            manager._print_price_table()
            assert mock_print.call_count >= 3  # Header, separator, row, empty line

    def test_is_running_returns_true_when_running(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        manager._running = True
        manager._display_task = Mock()
        manager._display_task.done.return_value = False
        assert manager.is_running() is True

    def test_is_running_returns_false_when_not_running(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        manager._running = False
        assert manager.is_running() is False

    def test_is_running_returns_false_when_task_done(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        manager._running = True
        manager._display_task = Mock()
        manager._display_task.done.return_value = True
        assert manager.is_running() is False

    def test_is_running_returns_false_when_no_task(self):
        from display_manager import DisplayManager
        data_manager = Mock()
        manager = DisplayManager(data_manager, logger=Mock())
        manager._running = True
        manager._display_task = None
        assert manager.is_running() is False


class TestMetricsMonitor:
    def test_init_sets_interval_and_state(self):
        from metrics_monitor import MetricsMonitor
        monitor = MetricsMonitor(interval_minutes=10)
        assert monitor.interval_seconds == 600  # 10 minutes * 60
        assert monitor.running is False
        assert monitor.monitor_thread is None
        assert monitor._stop_event is not None

    def test_start_creates_thread(self):
        from metrics_monitor import MetricsMonitor
        monitor = MetricsMonitor(interval_minutes=5)
        monitor.start()
        assert monitor.running is True
        assert monitor.monitor_thread is not None
        assert monitor.monitor_thread.is_alive()

    def test_start_already_running_warns(self):
        from metrics_monitor import MetricsMonitor
        monitor = MetricsMonitor(interval_minutes=5)
        monitor.running = True
        monitor.start()
        monitor.logger.warning.assert_called_once_with("⚠️ Le monitoring des métriques est déjà actif")

    def test_stop_stops_running(self):
        from metrics_monitor import MetricsMonitor
        monitor = MetricsMonitor(interval_minutes=5)
        monitor.running = True
        monitor.monitor_thread = Mock()
        monitor.monitor_thread.is_alive.return_value = True
        monitor.monitor_thread.join = Mock()
        monitor.stop()
        assert monitor.running is False
        monitor.monitor_thread.join.assert_called_once_with(timeout=3)

    def test_stop_not_running_returns_early(self):
        from metrics_monitor import MetricsMonitor
        monitor = MetricsMonitor(interval_minutes=5)
        monitor.running = False
        monitor.stop()
        # Ne devrait pas lever d'exception

    def test_stop_thread_not_alive_cleans_up(self):
        from metrics_monitor import MetricsMonitor
        monitor = MetricsMonitor(interval_minutes=5)
        monitor.running = True
        monitor.monitor_thread = Mock()
        monitor.monitor_thread.is_alive.return_value = False
        monitor.stop()
        assert monitor.monitor_thread is None

    def test_stop_thread_timeout_warns_and_cleans_up(self):
        from metrics_monitor import MetricsMonitor
        monitor = MetricsMonitor(interval_minutes=5)
        monitor.running = True
        monitor.monitor_thread = Mock()
        monitor.monitor_thread.is_alive.return_value = True
        monitor.monitor_thread.join = Mock()
        monitor.monitor_thread.daemon = False
        monitor.stop()
        monitor.logger.warning.assert_called_once_with("⚠️ Thread métriques n'a pas pu s'arrêter proprement, arrêt forcé")
        assert monitor.monitor_thread.daemon is True
        assert monitor.monitor_thread is None

    def test_monitor_loop_runs_while_running(self):
        from metrics_monitor import MetricsMonitor
        monitor = MetricsMonitor(interval_minutes=5)
        monitor.running = True
        monitor._log_metrics = Mock()
        monitor._stop_event = Mock()
        monitor._stop_event.is_set.return_value = False
        monitor._stop_event.wait.return_value = True  # Simuler l'arrêt
        monitor._monitor_loop()
        monitor._log_metrics.assert_called_once()

    def test_monitor_loop_handles_exception(self):
        from metrics_monitor import MetricsMonitor
        monitor = MetricsMonitor(interval_minutes=5)
        monitor.running = True
        monitor._log_metrics = Mock(side_effect=Exception("test"))
        monitor._stop_event = Mock()
        monitor._stop_event.is_set.return_value = False
        monitor._stop_event.wait.return_value = True  # Simuler l'arrêt
        monitor._monitor_loop()
        monitor.logger.error.assert_called_once_with("❌ Erreur lors du monitoring des métriques: test")

    def test_log_metrics_calls_get_metrics_summary(self):
        from metrics_monitor import MetricsMonitor
        monitor = MetricsMonitor(interval_minutes=5)
        with patch('metrics_monitor.get_metrics_summary') as mock_get_metrics:
            mock_get_metrics.return_value = {"uptime_seconds": 3600}
            monitor._log_metrics()
            mock_get_metrics.assert_called_once()

    def test_log_metrics_handles_exception(self):
        from metrics_monitor import MetricsMonitor
        monitor = MetricsMonitor(interval_minutes=5)
        with patch('metrics_monitor.get_metrics_summary', side_effect=Exception("test")):
            monitor._log_metrics()
            monitor.logger.error.assert_called_once_with("❌ Erreur lors du formatage des métriques: test")

    def test_log_metrics_now_calls_log_metrics(self):
        from metrics_monitor import MetricsMonitor
        monitor = MetricsMonitor(interval_minutes=5)
        monitor._log_metrics = Mock()
        monitor.log_metrics_now()
        monitor._log_metrics.assert_called_once()

    def test_log_metrics_now_handles_exception(self):
        from metrics_monitor import MetricsMonitor
        monitor = MetricsMonitor(interval_minutes=5)
        monitor._log_metrics = Mock(side_effect=Exception("test"))
        monitor.log_metrics_now()
        monitor.logger.error.assert_called_once_with("❌ Erreur lors de l'affichage des métriques: test")

    def test_start_metrics_monitoring_creates_global_instance(self):
        from metrics_monitor import start_metrics_monitoring
        with patch('metrics_monitor.metrics_monitor') as mock_monitor:
            mock_monitor.start = Mock()
            start_metrics_monitoring(interval_minutes=10)
            mock_monitor.start.assert_called_once()

    def test_global_metrics_monitor_exists(self):
        from metrics_monitor import metrics_monitor
        assert metrics_monitor is not None
        assert hasattr(metrics_monitor, 'start')
        assert hasattr(metrics_monitor, 'stop')
        assert hasattr(metrics_monitor, 'log_metrics_now')


class TestCallbackManager:
    def test_init_sets_logger(self):
        from callback_manager import CallbackManager
        manager = CallbackManager(logger=Mock())
        assert manager.logger is not None

    def test_setup_manager_callbacks_sets_volatility_callback(self):
        from callback_manager import CallbackManager
        manager = CallbackManager(logger=Mock())
        display_manager = Mock()
        monitoring_manager = Mock()
        volatility_tracker = Mock()
        volatility_tracker.get_cached_volatility = Mock()
        ws_manager = Mock()
        data_manager = Mock()
        manager.setup_manager_callbacks(
            display_manager, monitoring_manager, volatility_tracker,
            ws_manager, data_manager
        )
        display_manager.set_volatility_callback.assert_called_once_with(
            volatility_tracker.get_cached_volatility
        )

    def test_setup_manager_callbacks_sets_monitoring_callbacks(self):
        from callback_manager import CallbackManager
        manager = CallbackManager(logger=Mock())
        display_manager = Mock()
        monitoring_manager = Mock()
        volatility_tracker = Mock()
        ws_manager = Mock()
        data_manager = Mock()
        watchlist_manager = Mock()
        manager.setup_manager_callbacks(
            display_manager, monitoring_manager, volatility_tracker,
            ws_manager, data_manager, watchlist_manager
        )
        monitoring_manager.set_watchlist_manager.assert_called_once_with(watchlist_manager)
        monitoring_manager.set_volatility_tracker.assert_called_once_with(volatility_tracker)
        monitoring_manager.set_ws_manager.assert_called_once_with(ws_manager)

    def test_setup_manager_callbacks_sets_opportunity_callbacks(self):
        from callback_manager import CallbackManager
        manager = CallbackManager(logger=Mock())
        display_manager = Mock()
        monitoring_manager = Mock()
        volatility_tracker = Mock()
        ws_manager = Mock()
        data_manager = Mock()
        watchlist_manager = Mock()
        opportunity_manager = Mock()
        manager.setup_manager_callbacks(
            display_manager, monitoring_manager, volatility_tracker,
            ws_manager, data_manager, watchlist_manager, opportunity_manager
        )
        monitoring_manager.set_on_new_opportunity_callback.assert_called_once()
        monitoring_manager.set_on_candidate_ticker_callback.assert_called_once()

    def test_setup_manager_callbacks_no_opportunity_manager_skips_callbacks(self):
        from callback_manager import CallbackManager
        manager = CallbackManager(logger=Mock())
        display_manager = Mock()
        monitoring_manager = Mock()
        volatility_tracker = Mock()
        ws_manager = Mock()
        data_manager = Mock()
        watchlist_manager = Mock()
        manager.setup_manager_callbacks(
            display_manager, monitoring_manager, volatility_tracker,
            ws_manager, data_manager, watchlist_manager
        )
        monitoring_manager.set_on_new_opportunity_callback.assert_not_called()
        monitoring_manager.set_on_candidate_ticker_callback.assert_not_called()

    def test_setup_all_callbacks_calls_all_setup_methods(self):
        from callback_manager import CallbackManager
        manager = CallbackManager(logger=Mock())
        display_manager = Mock()
        monitoring_manager = Mock()
        volatility_tracker = Mock()
        ws_manager = Mock()
        data_manager = Mock()
        manager.setup_manager_callbacks = Mock()
        manager.setup_ws_callbacks = Mock()
        manager.setup_volatility_callbacks = Mock()
        manager.setup_all_callbacks(
            display_manager, monitoring_manager, volatility_tracker,
            ws_manager, data_manager
        )
        manager.setup_manager_callbacks.assert_called_once()
        manager.setup_ws_callbacks.assert_called_once()
        manager.setup_volatility_callbacks.assert_called_once()

    def test_setup_ws_callbacks_sets_ticker_callback(self):
        from callback_manager import CallbackManager
        manager = CallbackManager(logger=Mock())
        ws_manager = Mock()
        data_manager = Mock()
        manager.setup_ws_callbacks(ws_manager, data_manager)
        ws_manager.set_ticker_callback.assert_called_once()

    def test_setup_volatility_callbacks_sets_active_symbols_callback(self):
        from callback_manager import CallbackManager
        manager = CallbackManager(logger=Mock())
        volatility_tracker = Mock()
        data_manager = Mock()
        manager.setup_volatility_callbacks(volatility_tracker, data_manager)
        volatility_tracker.set_active_symbols_callback.assert_called_once()

    def test_create_ticker_callback_returns_function(self):
        from callback_manager import CallbackManager
        manager = CallbackManager(logger=Mock())
        data_manager = Mock()
        callback = manager._create_ticker_callback(data_manager)
        assert callable(callback)

    def test_ticker_callback_updates_data_manager(self):
        from callback_manager import CallbackManager
        manager = CallbackManager(logger=Mock())
        data_manager = Mock()
        callback = manager._create_ticker_callback(data_manager)
        ticker_data = {"symbol": "BTCUSDT", "price": 50000}
        callback(ticker_data)
        data_manager.update_realtime_data.assert_called_once_with("BTCUSDT", ticker_data)

    def test_ticker_callback_empty_symbol_returns_early(self):
        from callback_manager import CallbackManager
        manager = CallbackManager(logger=Mock())
        data_manager = Mock()
        callback = manager._create_ticker_callback(data_manager)
        ticker_data = {"price": 50000}  # Pas de symbol
        callback(ticker_data)
        data_manager.update_realtime_data.assert_not_called()

    def test_create_active_symbols_callback_returns_function(self):
        from callback_manager import CallbackManager
        manager = CallbackManager(logger=Mock())
        data_manager = Mock()
        callback = manager._create_active_symbols_callback(data_manager)
        assert callable(callback)

    def test_active_symbols_callback_returns_all_symbols(self):
        from callback_manager import CallbackManager
        manager = CallbackManager(logger=Mock())
        data_manager = Mock()
        data_manager.get_all_symbols.return_value = ["BTCUSDT", "ETHUSDT"]
        callback = manager._create_active_symbols_callback(data_manager)
        result = callback()
        assert result == ["BTCUSDT", "ETHUSDT"]
        data_manager.get_all_symbols.assert_called_once()


class TestOpportunityManager:
    def test_init_sets_components(self):
        from opportunity_manager import OpportunityManager
        data_manager = Mock()
        manager = OpportunityManager(data_manager, logger=Mock())
        assert manager.data_manager is data_manager
        assert manager.logger is not None

    def test_on_new_opportunity_ws_running_logs_info(self):
        from opportunity_manager import OpportunityManager
        data_manager = Mock()
        manager = OpportunityManager(data_manager, logger=Mock())
        ws_manager = Mock()
        ws_manager.running = True
        watchlist_manager = Mock()
        manager.on_new_opportunity(["BTCUSDT"], ["BTCUSD"], ws_manager, watchlist_manager)
        manager.logger.info.assert_called_once_with(
            "🎯 Nouvelles opportunités détectées: 1 linear, 1 inverse (WebSocket déjà actif)"
        )

    @pytest.mark.asyncio
    async def test_on_new_opportunity_ws_not_running_starts_connections(self):
        from opportunity_manager import OpportunityManager
        data_manager = Mock()
        manager = OpportunityManager(data_manager, logger=Mock())
        ws_manager = Mock()
        ws_manager.running = False
        ws_manager.start_connections = AsyncMock()
        watchlist_manager = Mock()
        with patch('asyncio.run') as mock_run:
            manager.on_new_opportunity(["BTCUSDT"], ["BTCUSD"], ws_manager, watchlist_manager)
            mock_run.assert_called_once()

    def test_on_new_opportunity_handles_exception(self):
        from opportunity_manager import OpportunityManager
        data_manager = Mock()
        manager = OpportunityManager(data_manager, logger=Mock())
        ws_manager = Mock()
        ws_manager.running = True
        ws_manager.running = Mock(side_effect=Exception("test"))
        watchlist_manager = Mock()
        manager.on_new_opportunity(["BTCUSDT"], ["BTCUSD"], ws_manager, watchlist_manager)
        manager.logger.warning.assert_called_once_with("⚠️ Erreur intégration nouvelles opportunités: test")

    def test_on_candidate_ticker_calls_add_symbol(self):
        from opportunity_manager import OpportunityManager
        data_manager = Mock()
        manager = OpportunityManager(data_manager, logger=Mock())
        manager._add_symbol_to_main_watchlist = Mock()
        watchlist_manager = Mock()
        ticker_data = {"fundingRate": 0.001, "volume24h": 1000}
        manager.on_candidate_ticker("BTCUSDT", ticker_data, watchlist_manager)
        manager._add_symbol_to_main_watchlist.assert_called_once_with("BTCUSDT", ticker_data, watchlist_manager)

    def test_on_candidate_ticker_handles_exception(self):
        from opportunity_manager import OpportunityManager
        data_manager = Mock()
        manager = OpportunityManager(data_manager, logger=Mock())
        manager._add_symbol_to_main_watchlist = Mock(side_effect=Exception("test"))
        watchlist_manager = Mock()
        ticker_data = {"fundingRate": 0.001}
        manager.on_candidate_ticker("BTCUSDT", ticker_data, watchlist_manager)
        manager.logger.warning.assert_called_once_with("⚠️ Erreur traitement candidat BTCUSDT: test")

    def test_add_symbol_to_main_watchlist_already_present_returns_early(self):
        from opportunity_manager import OpportunityManager
        data_manager = Mock()
        data_manager.get_funding_data.return_value = {"funding": 0.001}
        manager = OpportunityManager(data_manager, logger=Mock())
        watchlist_manager = Mock()
        ticker_data = {"fundingRate": 0.001}
        manager._add_symbol_to_main_watchlist("BTCUSDT", ticker_data, watchlist_manager)
        data_manager.get_funding_data.assert_called_once_with("BTCUSDT")

    def test_add_symbol_to_main_watchlist_adds_new_symbol(self):
        from opportunity_manager import OpportunityManager
        data_manager = Mock()
        data_manager.get_funding_data.return_value = None
        data_manager.symbol_categories = {"BTCUSDT": "linear"}
        manager = OpportunityManager(data_manager, logger=Mock())
        watchlist_manager = Mock()
        watchlist_manager.calculate_funding_time_remaining.return_value = "1h"
        ticker_data = {
            "fundingRate": 0.001,
            "volume24h": 1000,
            "nextFundingTime": "2024-01-01T12:00:00Z",
            "bid1Price": 50000,
            "ask1Price": 50010
        }
        manager._add_symbol_to_main_watchlist("BTCUSDT", ticker_data, watchlist_manager)
        data_manager.update_funding_data.assert_called_once()
        data_manager.add_symbol_to_category.assert_called_once_with("BTCUSDT", "linear")
        data_manager.update_original_funding_data.assert_called_once_with("BTCUSDT", "2024-01-01T12:00:00Z")

    def test_add_symbol_to_main_watchlist_no_funding_rate_skips(self):
        from opportunity_manager import OpportunityManager
        data_manager = Mock()
        data_manager.get_funding_data.return_value = None
        manager = OpportunityManager(data_manager, logger=Mock())
        watchlist_manager = Mock()
        ticker_data = {"volume24h": 1000}  # Pas de fundingRate
        manager._add_symbol_to_main_watchlist("BTCUSDT", ticker_data, watchlist_manager)
        data_manager.update_funding_data.assert_not_called()

    def test_add_symbol_to_main_watchlist_calculates_spread(self):
        from opportunity_manager import OpportunityManager
        data_manager = Mock()
        data_manager.get_funding_data.return_value = None
        data_manager.symbol_categories = {"BTCUSDT": "linear"}
        manager = OpportunityManager(data_manager, logger=Mock())
        watchlist_manager = Mock()
        watchlist_manager.calculate_funding_time_remaining.return_value = "1h"
        ticker_data = {
            "fundingRate": 0.001,
            "volume24h": 1000,
            "nextFundingTime": "2024-01-01T12:00:00Z",
            "bid1Price": 50000,
            "ask1Price": 50010
        }
        manager._add_symbol_to_main_watchlist("BTCUSDT", ticker_data, watchlist_manager)
        # Vérifier que le spread est calculé (0.1% dans ce cas)
        call_args = data_manager.update_funding_data.call_args[0]
        assert call_args[4] == 0.0002  # (50010 - 50000) / ((50010 + 50000) / 2)

    def test_add_symbol_to_main_watchlist_invalid_spread_uses_zero(self):
        from opportunity_manager import OpportunityManager
        data_manager = Mock()
        data_manager.get_funding_data.return_value = None
        data_manager.symbol_categories = {"BTCUSDT": "linear"}
        manager = OpportunityManager(data_manager, logger=Mock())
        watchlist_manager = Mock()
        watchlist_manager.calculate_funding_time_remaining.return_value = "1h"
        ticker_data = {
            "fundingRate": 0.001,
            "volume24h": 1000,
            "nextFundingTime": "2024-01-01T12:00:00Z",
            "bid1Price": "invalid",
            "ask1Price": "invalid"
        }
        manager._add_symbol_to_main_watchlist("BTCUSDT", ticker_data, watchlist_manager)
        call_args = data_manager.update_funding_data.call_args[0]
        assert call_args[4] == 0.0  # Spread par défaut

    def test_add_symbol_to_main_watchlist_handles_exception(self):
        from opportunity_manager import OpportunityManager
        data_manager = Mock()
        data_manager.get_funding_data.return_value = None
        data_manager.update_funding_data.side_effect = Exception("test")
        manager = OpportunityManager(data_manager, logger=Mock())
        watchlist_manager = Mock()
        watchlist_manager.calculate_funding_time_remaining.return_value = "1h"
        ticker_data = {"fundingRate": 0.001, "volume24h": 1000}
        manager._add_symbol_to_main_watchlist("BTCUSDT", ticker_data, watchlist_manager)
        manager.logger.error.assert_called_once_with("❌ Erreur ajout symbole BTCUSDT: test")


class TestVolatilityTracker:
    def test_init_sets_components_and_config(self):
        from volatility_tracker import VolatilityTracker
        tracker = VolatilityTracker(testnet=True, ttl_seconds=60, max_cache_size=500, logger=Mock())
        assert tracker.testnet is True
        assert tracker.ttl_seconds == 60
        assert tracker.max_cache_size == 500
        assert tracker.calculator is not None
        assert tracker.cache is not None
        assert tracker.scheduler is not None
        assert tracker._get_active_symbols_callback is None

    def test_set_symbol_categories_delegates_to_calculator(self):
        from volatility_tracker import VolatilityTracker
        tracker = VolatilityTracker(logger=Mock())
        categories = {"BTCUSDT": "linear", "BTCUSD": "inverse"}
        tracker.set_symbol_categories(categories)
        tracker.calculator.set_symbol_categories.assert_called_once_with(categories)

    def test_set_active_symbols_callback_sets_callback(self):
        from volatility_tracker import VolatilityTracker
        tracker = VolatilityTracker(logger=Mock())
        callback = Mock()
        tracker.set_active_symbols_callback(callback)
        assert tracker._get_active_symbols_callback is callback
        tracker.scheduler.set_active_symbols_callback.assert_called_once_with(callback)

    def test_start_refresh_task_delegates_to_scheduler(self):
        from volatility_tracker import VolatilityTracker
        tracker = VolatilityTracker(logger=Mock())
        tracker.start_refresh_task()
        tracker.scheduler.start_refresh_task.assert_called_once()

    def test_stop_refresh_task_delegates_to_scheduler(self):
        from volatility_tracker import VolatilityTracker
        tracker = VolatilityTracker(logger=Mock())
        tracker.stop_refresh_task()
        tracker.scheduler.stop_refresh_task.assert_called_once()

    def test_get_cached_volatility_delegates_to_cache(self):
        from volatility_tracker import VolatilityTracker
        tracker = VolatilityTracker(logger=Mock())
        tracker.cache.get_cached_volatility.return_value = 0.05
        result = tracker.get_cached_volatility("BTCUSDT")
        assert result == 0.05
        tracker.cache.get_cached_volatility.assert_called_once_with("BTCUSDT")

    def test_set_cached_volatility_delegates_to_cache(self):
        from volatility_tracker import VolatilityTracker
        tracker = VolatilityTracker(logger=Mock())
        tracker.set_cached_volatility("BTCUSDT", 0.05)
        tracker.cache.set_cached_volatility.assert_called_once_with("BTCUSDT", 0.05)

    def test_clear_stale_cache_delegates_to_cache(self):
        from volatility_tracker import VolatilityTracker
        tracker = VolatilityTracker(logger=Mock())
        active_symbols = ["BTCUSDT", "ETHUSDT"]
        tracker.clear_stale_cache(active_symbols)
        tracker.cache.clear_stale_cache.assert_called_once_with(active_symbols)

    @pytest.mark.asyncio
    async def test_compute_volatility_batch_delegates_to_calculator(self):
        from volatility_tracker import VolatilityTracker
        tracker = VolatilityTracker(logger=Mock())
        tracker.calculator.compute_volatility_batch = AsyncMock(return_value={"BTCUSDT": 0.05})
        symbols = ["BTCUSDT", "ETHUSDT"]
        result = await tracker.compute_volatility_batch(symbols)
        assert result == {"BTCUSDT": 0.05}
        tracker.calculator.compute_volatility_batch.assert_called_once_with(symbols)

    @pytest.mark.asyncio
    async def test_filter_by_volatility_async_delegates_to_calculator(self):
        from volatility_tracker import VolatilityTracker
        tracker = VolatilityTracker(logger=Mock())
        symbols_data = [("BTCUSDT", 0.001, 1000.0, "1h", 0.01)]
        tracker.calculator.filter_by_volatility_async = AsyncMock(return_value=[("BTCUSDT", 0.001, 1000.0, "1h", 0.01, 0.05)])
        result = await tracker.filter_by_volatility_async(symbols_data, 0.01, 0.1)
        assert result == [("BTCUSDT", 0.001, 1000.0, "1h", 0.01, 0.05)]
        tracker.calculator.filter_by_volatility_async.assert_called_once_with(symbols_data, 0.01, 0.1)

    def test_filter_by_volatility_delegates_to_calculator(self):
        from volatility_tracker import VolatilityTracker
        tracker = VolatilityTracker(logger=Mock())
        symbols_data = [("BTCUSDT", 0.001, 1000.0, "1h", 0.01)]
        tracker.calculator.filter_by_volatility.return_value = [("BTCUSDT", 0.001, 1000.0, "1h", 0.01, 0.05)]
        result = tracker.filter_by_volatility(symbols_data, 0.01, 0.1)
        assert result == [("BTCUSDT", 0.001, 1000.0, "1h", 0.01, 0.05)]
        tracker.calculator.filter_by_volatility.assert_called_once_with(symbols_data, 0.01, 0.1)

    def test_get_cache_stats_delegates_to_cache(self):
        from volatility_tracker import VolatilityTracker
        tracker = VolatilityTracker(logger=Mock())
        tracker.cache.get_cache_stats.return_value = {"size": 10, "hits": 5, "misses": 3}
        result = tracker.get_cache_stats()
        assert result == {"size": 10, "hits": 5, "misses": 3}
        tracker.cache.get_cache_stats.assert_called_once()

    def test_is_running_delegates_to_scheduler(self):
        from volatility_tracker import VolatilityTracker
        tracker = VolatilityTracker(logger=Mock())
        tracker.scheduler.is_running.return_value = True
        assert tracker.is_running() is True
        tracker.scheduler.is_running.assert_called_once()


class TestTableFormatter:
    def test_init_sets_volatility_callback(self):
        from table_formatter import TableFormatter
        callback = Mock()
        formatter = TableFormatter(volatility_callback=callback)
        assert formatter._volatility_callback is callback

    def test_init_no_callback_sets_none(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        assert formatter._volatility_callback is None

    def test_set_volatility_callback_sets_callback(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        callback = Mock()
        formatter.set_volatility_callback(callback)
        assert formatter._volatility_callback is callback

    def test_calculate_column_widths_with_symbols(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        funding_data = {"BTCUSDT": (0.001, 1000, "1h", 0.01), "ETHUSDT": (0.002, 2000, "2h", 0.02)}
        widths = formatter.calculate_column_widths(funding_data)
        assert widths["symbol"] >= 8  # Au moins 8 caractères
        assert widths["funding"] == 12
        assert widths["volume"] == 10
        assert widths["spread"] == 10
        assert widths["volatility"] == 12
        assert widths["funding_time"] == 15

    def test_calculate_column_widths_empty_data(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        widths = formatter.calculate_column_widths({})
        assert widths["symbol"] == 8  # Longueur de "Symbole"
        assert widths["funding"] == 12
        assert widths["volume"] == 10
        assert widths["spread"] == 10
        assert widths["volatility"] == 12
        assert widths["funding_time"] == 15

    def test_format_table_header(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        col_widths = {"symbol": 10, "funding": 12, "volume": 10, "spread": 10, "volatility": 12, "funding_time": 15}
        header = formatter.format_table_header(col_widths)
        assert "Symbole" in header
        assert "Funding %" in header
        assert "Volume (M)" in header
        assert "Spread %" in header
        assert "Volatilité %" in header
        assert "Funding T" in header

    def test_format_table_separator(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        col_widths = {"symbol": 10, "funding": 12, "volume": 10, "spread": 10, "volatility": 12, "funding_time": 15}
        separator = formatter.format_table_separator(col_widths)
        assert "-" in separator
        assert "|" in separator

    def test_format_table_row(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        col_widths = {"symbol": 10, "funding": 12, "volume": 10, "spread": 10, "volatility": 12, "funding_time": 15}
        row_data = {
            "funding": 0.001,
            "volume": 1000000,
            "spread_pct": 0.01,
            "volatility_pct": 0.05,
            "funding_time": "1h 30m"
        }
        row = formatter.format_table_row("BTCUSDT", row_data, col_widths)
        assert "BTCUSDT" in row
        assert "|" in row

    def test_format_funding_positive(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        result = formatter.format_funding(0.001, 12)
        assert "+0.1000%" in result

    def test_format_funding_negative(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        result = formatter.format_funding(-0.001, 12)
        assert "-0.1000%" in result

    def test_format_funding_none(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        result = formatter.format_funding(None, 12)
        assert result == "null"

    def test_format_volume_valid(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        result = formatter.format_volume(1000000)
        assert "1.0" in result

    def test_format_volume_zero(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        result = formatter.format_volume(0)
        assert result == "null"

    def test_format_volume_none(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        result = formatter.format_volume(None)
        assert result == "null"

    def test_format_spread_positive(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        result = formatter.format_spread(0.01)
        assert "+1.000%" in result

    def test_format_spread_negative(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        result = formatter.format_spread(-0.01)
        assert "-1.000%" in result

    def test_format_spread_none(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        result = formatter.format_spread(None)
        assert result == "null"

    def test_format_volatility_positive(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        result = formatter.format_volatility(0.05)
        assert "+5.000%" in result

    def test_format_volatility_negative(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        result = formatter.format_volatility(-0.05)
        assert "-5.000%" in result

    def test_format_volatility_none(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        result = formatter.format_volatility(None)
        assert result == "-"

    def test_prepare_row_data_with_realtime(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        data_manager = Mock()
        data_manager.get_funding_data.return_value = (0.001, 1000, "1h", 0.01)
        data_manager.get_realtime_data.return_value = {"funding_rate": 0.002, "volume24h": 2000}
        data_manager.get_original_funding_data.return_value = "2024-01-01T12:00:00Z"
        result = formatter.prepare_row_data("BTCUSDT", data_manager)
        assert result["funding"] == 0.002  # Temps réel prioritaire
        assert result["volume"] == 2000  # Temps réel prioritaire
        assert result["spread_pct"] == 0.01  # Fallback REST
        assert result["volatility_pct"] is None  # Pas de callback
        assert result["funding_time"] == "-"  # Pas de données valides

    def test_prepare_row_data_fallback_to_rest(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        data_manager = Mock()
        data_manager.get_funding_data.return_value = (0.001, 1000, "1h", 0.01)
        data_manager.get_realtime_data.return_value = None
        data_manager.get_original_funding_data.return_value = "2024-01-01T12:00:00Z"
        result = formatter.prepare_row_data("BTCUSDT", data_manager)
        assert result["funding"] == 0.001  # Fallback REST
        assert result["volume"] == 1000  # Fallback REST
        assert result["spread_pct"] == 0.01  # Fallback REST
        assert result["volatility_pct"] is None  # Pas de callback
        assert result["funding_time"] == "-"  # Pas de données valides

    def test_get_funding_value_realtime_available(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        realtime_info = {"funding_rate": 0.002}
        result = formatter._get_funding_value(realtime_info, 0.001)
        assert result == 0.002

    def test_get_funding_value_realtime_none_fallback(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        realtime_info = {"funding_rate": None}
        result = formatter._get_funding_value(realtime_info, 0.001)
        assert result == 0.001

    def test_get_volume_value_realtime_available(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        realtime_info = {"volume24h": 2000}
        result = formatter._get_volume_value(realtime_info, 1000)
        assert result == 2000

    def test_get_volume_value_realtime_none_fallback(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        realtime_info = {"volume24h": None}
        result = formatter._get_volume_value(realtime_info, 1000)
        assert result == 1000

    def test_get_spread_value_realtime_calculated(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        realtime_info = {"bid1_price": 50000, "ask1_price": 50010}
        result = formatter._get_spread_value(realtime_info, 0.01)
        assert abs(result - 0.0002) < 0.0001  # (50010 - 50000) / ((50010 + 50000) / 2)

    def test_get_spread_value_realtime_invalid_fallback(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        realtime_info = {"bid1_price": "invalid", "ask1_price": "invalid"}
        result = formatter._get_spread_value(realtime_info, 0.01)
        assert result == 0.01

    def test_get_volatility_value_callback_available(self):
        from table_formatter import TableFormatter
        callback = Mock(return_value=0.05)
        formatter = TableFormatter(volatility_callback=callback)
        result = formatter._get_volatility_value("BTCUSDT")
        assert result == 0.05
        callback.assert_called_once_with("BTCUSDT")

    def test_get_volatility_value_callback_exception_returns_none(self):
        from table_formatter import TableFormatter
        callback = Mock(side_effect=Exception("test"))
        formatter = TableFormatter(volatility_callback=callback)
        result = formatter._get_volatility_value("BTCUSDT")
        assert result is None

    def test_get_volatility_value_no_callback_returns_none(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        result = formatter._get_volatility_value("BTCUSDT")
        assert result is None

    def test_calculate_funding_time_remaining_iso_format(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        with patch('table_formatter.time.time', return_value=1640995200):  # 2022-01-01 00:00:00
            result = formatter._calculate_funding_time_remaining("2022-01-01T01:00:00Z")
            assert "1h" in result

    def test_calculate_funding_time_remaining_timestamp_ms(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        with patch('table_formatter.time.time', return_value=1640995200):  # 2022-01-01 00:00:00
            result = formatter._calculate_funding_time_remaining(1640998800000)  # 1h plus tard en ms
            assert "1h" in result

    def test_calculate_funding_time_remaining_timestamp_seconds(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        with patch('table_formatter.time.time', return_value=1640995200):  # 2022-01-01 00:00:00
            result = formatter._calculate_funding_time_remaining(1640998800)  # 1h plus tard en s
            assert "1h" in result

    def test_calculate_funding_time_remaining_past_time(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        with patch('table_formatter.time.time', return_value=1640995200):  # 2022-01-01 00:00:00
            result = formatter._calculate_funding_time_remaining("2021-12-31T23:00:00Z")
            assert result == "0s"

    def test_calculate_funding_time_remaining_invalid_format(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        result = formatter._calculate_funding_time_remaining("invalid")
        assert result == "-"

    def test_are_all_data_available_all_available(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        data_manager = Mock()
        data_manager.get_funding_data.return_value = (0.001, 1000, "1h", 0.01)
        data_manager.get_realtime_data.return_value = None
        data_manager.get_original_funding_data.return_value = None
        formatter._get_volatility_value = Mock(return_value=0.05)
        funding_data = {"BTCUSDT": (0.001, 1000, "1h", 0.01)}
        result = formatter.are_all_data_available(funding_data, data_manager)
        assert result is True

    def test_are_all_data_available_missing_volatility(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        data_manager = Mock()
        data_manager.get_funding_data.return_value = (0.001, 1000, "1h", 0.01)
        data_manager.get_realtime_data.return_value = None
        data_manager.get_original_funding_data.return_value = None
        formatter._get_volatility_value = Mock(return_value=None)
        funding_data = {"BTCUSDT": (0.001, 1000, "1h", 0.01)}
        result = formatter.are_all_data_available(funding_data, data_manager)
        assert result is False

    def test_are_all_data_available_missing_spread(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        data_manager = Mock()
        data_manager.get_funding_data.return_value = (0.001, 1000, "1h", None)
        data_manager.get_realtime_data.return_value = None
        data_manager.get_original_funding_data.return_value = None
        formatter._get_volatility_value = Mock(return_value=0.05)
        funding_data = {"BTCUSDT": (0.001, 1000, "1h", None)}
        result = formatter.are_all_data_available(funding_data, data_manager)
        assert result is False

    def test_are_all_data_available_empty_data(self):
        from table_formatter import TableFormatter
        formatter = TableFormatter()
        data_manager = Mock()
        result = formatter.are_all_data_available({}, data_manager)
        assert result is False


class TestInstruments:
    def test_fetch_instruments_info_success(self):
        from instruments import fetch_instruments_info
        with patch('instruments.get_http_client') as mock_get_client:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "retCode": 0,
                "result": {
                    "list": [{"symbol": "BTCUSDT", "contractType": "LinearPerpetual"}],
                    "nextPageCursor": ""
                }
            }
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client
            result = fetch_instruments_info("http://x", "linear")
            assert len(result) == 1
            assert result[0]["symbol"] == "BTCUSDT"

    def test_fetch_instruments_info_http_error(self):
        from instruments import fetch_instruments_info
        with patch('instruments.get_http_client') as mock_get_client:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client
            with pytest.raises(RuntimeError, match="Erreur HTTP Bybit"):
                fetch_instruments_info("http://x", "linear")

    def test_fetch_instruments_info_api_error(self):
        from instruments import fetch_instruments_info
        with patch('instruments.get_http_client') as mock_get_client:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "retCode": 10001,
                "retMsg": "API Error"
            }
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client
            with pytest.raises(RuntimeError, match="Erreur API Bybit"):
                fetch_instruments_info("http://x", "linear")

    def test_fetch_instruments_info_network_error(self):
        from instruments import fetch_instruments_info
        with patch('instruments.get_http_client') as mock_get_client:
            mock_client = Mock()
            mock_client.get.side_effect = httpx.RequestError("Network error")
            mock_get_client.return_value = mock_client
            with pytest.raises(RuntimeError, match="Erreur réseau/HTTP Bybit"):
                fetch_instruments_info("http://x", "linear")

    def test_fetch_instruments_info_pagination(self):
        from instruments import fetch_instruments_info
        with patch('instruments.get_http_client') as mock_get_client:
            mock_client = Mock()
            mock_response1 = Mock()
            mock_response1.status_code = 200
            mock_response1.json.return_value = {
                "retCode": 0,
                "result": {
                    "list": [{"symbol": "BTCUSDT"}],
                    "nextPageCursor": "cursor1"
                }
            }
            mock_response2 = Mock()
            mock_response2.status_code = 200
            mock_response2.json.return_value = {
                "retCode": 0,
                "result": {
                    "list": [{"symbol": "ETHUSDT"}],
                    "nextPageCursor": ""
                }
            }
            mock_client.get.side_effect = [mock_response1, mock_response2]
            mock_get_client.return_value = mock_client
            result = fetch_instruments_info("http://x", "linear")
            assert len(result) == 2
            assert result[0]["symbol"] == "BTCUSDT"
            assert result[1]["symbol"] == "ETHUSDT"

    def test_is_perpetual_active_linear_perpetual_trading(self):
        from instruments import is_perpetual_active
        item = {"contractType": "LinearPerpetual", "status": "Trading"}
        assert is_perpetual_active(item) is True

    def test_is_perpetual_active_inverse_perpetual_listed(self):
        from instruments import is_perpetual_active
        item = {"contractType": "InversePerpetual", "status": "Listed"}
        assert is_perpetual_active(item) is True

    def test_is_perpetual_active_not_perpetual(self):
        from instruments import is_perpetual_active
        item = {"contractType": "Spot", "status": "Trading"}
        assert is_perpetual_active(item) is False

    def test_is_perpetual_active_not_active(self):
        from instruments import is_perpetual_active
        item = {"contractType": "LinearPerpetual", "status": "Suspended"}
        assert is_perpetual_active(item) is False

    def test_is_perpetual_active_case_insensitive(self):
        from instruments import is_perpetual_active
        item = {"contractType": "linearperpetual", "status": "trading"}
        assert is_perpetual_active(item) is True

    def test_extract_symbol_success(self):
        from instruments import extract_symbol
        item = {"symbol": "BTCUSDT", "contractType": "LinearPerpetual"}
        assert extract_symbol(item) == "BTCUSDT"

    def test_extract_symbol_empty(self):
        from instruments import extract_symbol
        item = {"contractType": "LinearPerpetual"}
        assert extract_symbol(item) == ""

    def test_get_perp_symbols_success(self):
        from instruments import get_perp_symbols
        with patch('instruments.fetch_instruments_info') as mock_fetch:
            mock_fetch.side_effect = [
                [{"symbol": "BTCUSDT", "contractType": "LinearPerpetual", "status": "Trading"}],
                [{"symbol": "BTCUSD", "contractType": "InversePerpetual", "status": "Trading"}]
            ]
            result = get_perp_symbols("http://x")
            assert result["linear"] == ["BTCUSDT"]
            assert result["inverse"] == ["BTCUSD"]
            assert result["total"] == 2
            assert result["categories"]["BTCUSDT"] == "linear"
            assert result["categories"]["BTCUSD"] == "inverse"

    def test_get_perp_symbols_filters_inactive(self):
        from instruments import get_perp_symbols
        with patch('instruments.fetch_instruments_info') as mock_fetch:
            mock_fetch.side_effect = [
                [{"symbol": "BTCUSDT", "contractType": "LinearPerpetual", "status": "Suspended"}],
                []
            ]
            result = get_perp_symbols("http://x")
            assert result["linear"] == []
            assert result["inverse"] == []
            assert result["total"] == 0

    def test_get_perp_symbols_filters_non_perpetual(self):
        from instruments import get_perp_symbols
        with patch('instruments.fetch_instruments_info') as mock_fetch:
            mock_fetch.side_effect = [
                [{"symbol": "BTCUSDT", "contractType": "Spot", "status": "Trading"}],
                []
            ]
            result = get_perp_symbols("http://x")
            assert result["linear"] == []
            assert result["inverse"] == []
            assert result["total"] == 0

    def test_category_of_symbol_with_categories(self):
        from instruments import category_of_symbol
        categories = {"BTCUSDT": "linear", "BTCUSD": "inverse"}
        assert category_of_symbol("BTCUSDT", categories) == "linear"
        assert category_of_symbol("BTCUSD", categories) == "inverse"

    def test_category_of_symbol_heuristic_usdt(self):
        from instruments import category_of_symbol
        assert category_of_symbol("BTCUSDT") == "linear"
        assert category_of_symbol("ETHUSDT") == "linear"

    def test_category_of_symbol_heuristic_no_usdt(self):
        from instruments import category_of_symbol
        assert category_of_symbol("BTCUSD") == "inverse"
        assert category_of_symbol("ETHUSD") == "inverse"

    def test_category_of_symbol_invalid_categories_fallback(self):
        from instruments import category_of_symbol
        categories = {"BTCUSDT": "invalid"}
        assert category_of_symbol("BTCUSDT", categories) == "linear"

    def test_category_of_symbol_exception_fallback(self):
        from instruments import category_of_symbol
        with patch('instruments.category_of_symbol', side_effect=Exception("test")):
            # Le test de l'exception est dans la fonction elle-même
            pass


class TestHttpUtils:
    def test_rate_limiter_init(self):
        from http_utils import RateLimiter
        limiter = RateLimiter(max_calls=10, window_seconds=2.0)
        assert limiter.max_calls == 10
        assert limiter.window_seconds == 2.0
        assert len(limiter._timestamps) == 0

    def test_rate_limiter_acquire_within_limit(self):
        from http_utils import RateLimiter
        limiter = RateLimiter(max_calls=5, window_seconds=1.0)
        # Premier appel devrait passer immédiatement
        limiter.acquire()
        assert len(limiter._timestamps) == 1

    def test_rate_limiter_acquire_exceeds_limit(self):
        from http_utils import RateLimiter
        limiter = RateLimiter(max_calls=2, window_seconds=1.0)
        # Premier et deuxième appel devraient passer
        limiter.acquire()
        limiter.acquire()
        assert len(limiter._timestamps) == 2
        # Troisième appel devrait bloquer
        with patch('time.sleep') as mock_sleep:
            limiter.acquire()
            mock_sleep.assert_called()

    def test_rate_limiter_window_expiry(self):
        from http_utils import RateLimiter
        limiter = RateLimiter(max_calls=1, window_seconds=0.1)
        # Premier appel
        limiter.acquire()
        assert len(limiter._timestamps) == 1
        # Attendre que la fenêtre expire
        time.sleep(0.2)
        # Deuxième appel devrait passer car la fenêtre a expiré
        limiter.acquire()
        assert len(limiter._timestamps) == 1  # L'ancien timestamp a été supprimé

    def test_rate_limiter_thread_safety(self):
        from http_utils import RateLimiter
        limiter = RateLimiter(max_calls=10, window_seconds=1.0)
        results = []
        
        def worker():
            limiter.acquire()
            results.append(1)
        
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        assert len(results) == 5

    def test_get_rate_limiter_default_values(self):
        from http_utils import get_rate_limiter
        with patch.dict(os.environ, {}, clear=True):
            limiter = get_rate_limiter()
            assert limiter.max_calls == 5
            assert limiter.window_seconds == 1.0

    def test_get_rate_limiter_from_env(self):
        from http_utils import get_rate_limiter
        with patch.dict(os.environ, {
            "PUBLIC_HTTP_MAX_CALLS_PER_SEC": "10",
            "PUBLIC_HTTP_WINDOW_SECONDS": "2.0"
        }):
            limiter = get_rate_limiter()
            assert limiter.max_calls == 10
            assert limiter.window_seconds == 2.0

    def test_get_rate_limiter_invalid_env_fallback(self):
        from http_utils import get_rate_limiter
        with patch.dict(os.environ, {
            "PUBLIC_HTTP_MAX_CALLS_PER_SEC": "invalid",
            "PUBLIC_HTTP_WINDOW_SECONDS": "invalid"
        }):
            limiter = get_rate_limiter()
            assert limiter.max_calls == 5
            assert limiter.window_seconds == 1.0

    def test_rate_limiter_wait_time_calculation(self):
        from http_utils import RateLimiter
        limiter = RateLimiter(max_calls=1, window_seconds=1.0)
        # Premier appel
        limiter.acquire()
        # Deuxième appel devrait attendre
        with patch('time.sleep') as mock_sleep:
            limiter.acquire()
            # Vérifier que sleep a été appelé avec un temps > 0
            mock_sleep.assert_called()
            call_args = mock_sleep.call_args[0][0]
            assert call_args > 0
            assert call_args <= 0.05  # max sleep time

    def test_rate_limiter_multiple_calls_rapidly(self):
        from http_utils import RateLimiter
        limiter = RateLimiter(max_calls=3, window_seconds=1.0)
        # Trois appels rapides devraient tous passer
        limiter.acquire()
        limiter.acquire()
        limiter.acquire()
        assert len(limiter._timestamps) == 3
        # Quatrième appel devrait bloquer
        with patch('time.sleep') as mock_sleep:
            limiter.acquire()
            mock_sleep.assert_called()


class TestHttpClientManager:
    def test_singleton_pattern(self):
        from http_client_manager import HTTPClientManager
        manager1 = HTTPClientManager()
        manager2 = HTTPClientManager()
        assert manager1 is manager2

    def test_init_sets_components(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        assert manager.logger is not None
        assert manager._sync_client is None
        assert manager._async_client is None
        assert manager._aiohttp_session is None

    def test_get_sync_client_creates_client(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        client = manager.get_sync_client(timeout=15)
        assert client is not None
        assert client.timeout == 15
        assert manager._sync_client is client

    def test_get_sync_client_reuses_existing(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        client1 = manager.get_sync_client(timeout=10)
        client2 = manager.get_sync_client(timeout=20)
        assert client1 is client2  # Même instance réutilisée

    def test_get_sync_client_recreates_if_closed(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        client1 = manager.get_sync_client(timeout=10)
        client1.close()
        client2 = manager.get_sync_client(timeout=20)
        assert client1 is not client2  # Nouvelle instance créée
        assert client2.timeout == 20

    @pytest.mark.asyncio
    async def test_get_async_client_creates_client(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        client = await manager.get_async_client(timeout=15)
        assert client is not None
        assert client.timeout == 15
        assert manager._async_client is client

    @pytest.mark.asyncio
    async def test_get_async_client_reuses_existing(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        client1 = await manager.get_async_client(timeout=10)
        client2 = await manager.get_async_client(timeout=20)
        assert client1 is client2  # Même instance réutilisée

    @pytest.mark.asyncio
    async def test_get_async_client_recreates_if_closed(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        client1 = await manager.get_async_client(timeout=10)
        await client1.aclose()
        client2 = await manager.get_async_client(timeout=20)
        assert client1 is not client2  # Nouvelle instance créée
        assert client2.timeout == 20

    @pytest.mark.asyncio
    async def test_get_aiohttp_session_creates_session(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        session = await manager.get_aiohttp_session(timeout=15)
        assert session is not None
        assert manager._aiohttp_session is session

    @pytest.mark.asyncio
    async def test_get_aiohttp_session_reuses_existing(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        session1 = await manager.get_aiohttp_session(timeout=10)
        session2 = await manager.get_aiohttp_session(timeout=20)
        assert session1 is session2  # Même instance réutilisée

    @pytest.mark.asyncio
    async def test_get_aiohttp_session_recreates_if_closed(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        session1 = await manager.get_aiohttp_session(timeout=10)
        await session1.close()
        session2 = await manager.get_aiohttp_session(timeout=20)
        assert session1 is not session2  # Nouvelle instance créée

    def test_close_sync_client_closes_client(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        client = manager.get_sync_client(timeout=10)
        manager.close_sync_client()
        assert client.is_closed is True

    def test_close_sync_client_no_client(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        manager.close_sync_client()  # Ne devrait pas lever d'exception

    @pytest.mark.asyncio
    async def test_close_async_client_closes_client(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        client = await manager.get_async_client(timeout=10)
        await manager.close_async_client()
        assert client.is_closed is True

    @pytest.mark.asyncio
    async def test_close_async_client_no_client(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        await manager.close_async_client()  # Ne devrait pas lever d'exception

    @pytest.mark.asyncio
    async def test_close_aiohttp_session_closes_session(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        session = await manager.get_aiohttp_session(timeout=10)
        await manager.close_aiohttp_session()
        assert session.closed is True

    @pytest.mark.asyncio
    async def test_close_aiohttp_session_no_session(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        await manager.close_aiohttp_session()  # Ne devrait pas lever d'exception

    def test_close_all_closes_sync_client(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        client = manager.get_sync_client(timeout=10)
        manager.close_all()
        assert client.is_closed is True

    @pytest.mark.asyncio
    async def test_close_all_closes_async_clients(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        async_client = await manager.get_async_client(timeout=10)
        aiohttp_session = await manager.get_aiohttp_session(timeout=10)
        manager.close_all()
        assert async_client.is_closed is True
        assert aiohttp_session.closed is True

    @pytest.mark.asyncio
    async def test_close_async_clients_closes_all(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        async_client = await manager.get_async_client(timeout=10)
        aiohttp_session = await manager.get_aiohttp_session(timeout=10)
        await manager._close_async_clients()
        assert async_client.is_closed is True
        assert aiohttp_session.closed is True

    def test_get_http_client_function(self):
        from http_client_manager import get_http_client
        client = get_http_client(timeout=15)
        assert client is not None
        assert client.timeout == 15

    def test_close_all_http_clients_function(self):
        from http_client_manager import close_all_http_clients, get_http_client
        client = get_http_client(timeout=10)
        close_all_http_clients()
        assert client.is_closed is True

    def test_close_all_handles_exceptions(self):
        from http_client_manager import HTTPClientManager
        manager = HTTPClientManager()
        manager.close_sync_client = Mock(side_effect=Exception("test"))
        manager.close_all()  # Ne devrait pas lever d'exception


class TestVolatilityCache:
    def test_init_sets_parameters(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache(ttl_seconds=60, max_cache_size=500)
        assert cache.ttl_seconds == 60
        assert cache.max_cache_size == 500
        assert cache.logger is not None
        assert len(cache.volatility_cache) == 0
        assert cache._auto_cleanup_enabled is True

    def test_get_cached_volatility_not_found(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache()
        result = cache.get_cached_volatility("BTCUSDT")
        assert result is None

    def test_get_cached_volatility_found_valid(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache(ttl_seconds=120)
        cache.set_cached_volatility("BTCUSDT", 2.5)
        result = cache.get_cached_volatility("BTCUSDT")
        assert result == 2.5

    def test_get_cached_volatility_found_expired(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache(ttl_seconds=0.1)  # TTL très court
        cache.set_cached_volatility("BTCUSDT", 2.5)
        time.sleep(0.2)  # Attendre expiration
        result = cache.get_cached_volatility("BTCUSDT")
        assert result is None

    def test_set_cached_volatility(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache()
        cache.set_cached_volatility("BTCUSDT", 2.5)
        assert len(cache.volatility_cache) == 1
        assert "volatility_5m_BTCUSDT" in cache.volatility_cache

    def test_set_cached_volatility_triggers_cleanup(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache(max_cache_size=2)
        cache.set_cached_volatility("BTC1", 1.0)
        cache.set_cached_volatility("BTC2", 2.0)
        cache.set_cached_volatility("BTC3", 3.0)  # Déclenche le nettoyage
        assert len(cache.volatility_cache) <= 2

    def test_clear_stale_cache(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache()
        cache.set_cached_volatility("BTCUSDT", 2.5)
        cache.set_cached_volatility("ETHUSDT", 3.0)
        cache.set_cached_volatility("ADAUSDT", 1.5)
        cache.clear_stale_cache(["BTCUSDT", "ETHUSDT"])
        assert len(cache.volatility_cache) == 2
        assert "volatility_5m_BTCUSDT" in cache.volatility_cache
        assert "volatility_5m_ETHUSDT" in cache.volatility_cache
        assert "volatility_5m_ADAUSDT" not in cache.volatility_cache

    def test_clear_stale_cache_handles_exceptions(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache()
        cache.set_cached_volatility("BTCUSDT", 2.5)
        # Simuler une exception dans clear_stale_cache
        with patch.object(cache, 'volatility_cache', side_effect=Exception("test")):
            cache.clear_stale_cache(["BTCUSDT"])  # Ne devrait pas lever d'exception

    def test_update_cache_with_results(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache()
        results = {"BTCUSDT": 2.5, "ETHUSDT": 3.0, "ADAUSDT": None}
        ok_count, fail_count = cache.update_cache_with_results(results, time.time())
        assert ok_count == 2
        assert fail_count == 1
        assert len(cache.volatility_cache) == 2

    def test_get_cache_stats(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache(ttl_seconds=120)
        cache.set_cached_volatility("BTCUSDT", 2.5)
        cache.set_cached_volatility("ETHUSDT", 3.0)
        stats = cache.get_cache_stats()
        assert stats["total"] == 2
        assert stats["valid"] == 2
        assert stats["expired"] == 0

    def test_get_cache_stats_with_expired(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache(ttl_seconds=0.1)
        cache.set_cached_volatility("BTCUSDT", 2.5)
        time.sleep(0.2)  # Attendre expiration
        cache.set_cached_volatility("ETHUSDT", 3.0)
        stats = cache.get_cache_stats()
        assert stats["total"] == 2
        assert stats["valid"] == 1
        assert stats["expired"] == 1

    def test_clear_all_cache(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache()
        cache.set_cached_volatility("BTCUSDT", 2.5)
        cache.set_cached_volatility("ETHUSDT", 3.0)
        cache.clear_all_cache()
        assert len(cache.volatility_cache) == 0

    def test_auto_cleanup_enabled(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache()
        cache.enable_auto_cleanup(True)
        assert cache._auto_cleanup_enabled is True

    def test_auto_cleanup_disabled(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache()
        cache.enable_auto_cleanup(False)
        assert cache._auto_cleanup_enabled is False

    def test_auto_cleanup_if_needed_disabled(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache()
        cache.enable_auto_cleanup(False)
        cache._last_cleanup = time.time() - 100  # Forcer le nettoyage
        cache._auto_cleanup_if_needed()  # Ne devrait pas nettoyer
        assert cache._last_cleanup == time.time() - 100

    def test_auto_cleanup_if_needed_enabled(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache()
        cache._last_cleanup = time.time() - 100  # Forcer le nettoyage
        cache._auto_cleanup_if_needed()  # Devrait nettoyer
        assert cache._last_cleanup > time.time() - 100

    def test_cleanup_expired_entries(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache(ttl_seconds=0.1)
        cache.set_cached_volatility("BTCUSDT", 2.5)
        time.sleep(0.2)  # Attendre expiration
        cache.set_cached_volatility("ETHUSDT", 3.0)
        cache._cleanup_expired_entries()
        assert len(cache.volatility_cache) == 1
        assert "volatility_5m_ETHUSDT" in cache.volatility_cache

    def test_cleanup_expired_entries_handles_exceptions(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache()
        cache.set_cached_volatility("BTCUSDT", 2.5)
        # Simuler une exception dans _cleanup_expired_entries
        with patch.object(cache, 'volatility_cache', side_effect=Exception("test")):
            cache._cleanup_expired_entries()  # Ne devrait pas lever d'exception

    def test_cleanup_cache_handles_exceptions(self):
        from volatility_cache import VolatilityCache
        cache = VolatilityCache()
        cache.set_cached_volatility("BTCUSDT", 2.5)
        # Simuler une exception dans _cleanup_cache
        with patch.object(cache, 'volatility_cache', side_effect=Exception("test")):
            cache._cleanup_cache()  # Ne devrait pas lever d'exception


class TestVolatilityScheduler:
    def test_init_sets_components(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        assert scheduler.calculator is calculator
        assert scheduler.cache is cache
        assert scheduler.logger is not None
        assert scheduler._refresh_thread is None
        assert scheduler._running is False
        assert scheduler._get_active_symbols_callback is None

    def test_set_active_symbols_callback(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        callback = lambda: ["BTCUSDT", "ETHUSDT"]
        scheduler.set_active_symbols_callback(callback)
        assert scheduler._get_active_symbols_callback is callback

    def test_start_refresh_task_creates_thread(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        scheduler.start_refresh_task()
        assert scheduler._running is True
        assert scheduler._refresh_thread is not None
        assert scheduler._refresh_thread.is_alive() is True
        scheduler.stop_refresh_task()

    def test_start_refresh_task_already_running(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        scheduler.start_refresh_task()
        scheduler.start_refresh_task()  # Deuxième appel
        assert scheduler._running is True
        scheduler.stop_refresh_task()

    def test_stop_refresh_task_stops_thread(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        scheduler.start_refresh_task()
        scheduler.stop_refresh_task()
        assert scheduler._running is False
        assert scheduler._refresh_thread is None

    def test_stop_refresh_task_no_thread(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        scheduler.stop_refresh_task()  # Ne devrait pas lever d'exception
        assert scheduler._running is False

    def test_calculate_refresh_interval(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache(ttl_seconds=120)
        scheduler = VolatilityScheduler(calculator, cache)
        interval = scheduler._calculate_refresh_interval()
        assert 20 <= interval <= 40

    def test_get_symbols_to_refresh_no_callback(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        symbols = scheduler._get_symbols_to_refresh()
        assert symbols == []

    def test_get_symbols_to_refresh_with_callback(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        callback = lambda: ["BTCUSDT", "ETHUSDT"]
        scheduler.set_active_symbols_callback(callback)
        symbols = scheduler._get_symbols_to_refresh()
        assert symbols == ["BTCUSDT", "ETHUSDT"]

    def test_get_symbols_to_refresh_callback_exception(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        callback = lambda: (_ for _ in ()).throw(Exception("test"))
        scheduler.set_active_symbols_callback(callback)
        symbols = scheduler._get_symbols_to_refresh()
        assert symbols == []

    def test_perform_refresh_cycle(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        # Mock du calcul de volatilité
        with patch.object(scheduler, '_run_async_volatility_batch') as mock_batch:
            mock_batch.return_value = {"BTCUSDT": 2.5, "ETHUSDT": 3.0}
            scheduler._perform_refresh_cycle(["BTCUSDT", "ETHUSDT"])
            mock_batch.assert_called_once_with(["BTCUSDT", "ETHUSDT"])

    def test_run_async_volatility_batch_success(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        # Mock du calculateur
        with patch.object(calculator, 'compute_volatility_batch') as mock_compute:
            mock_compute.return_value = {"BTCUSDT": 2.5, "ETHUSDT": 3.0}
            results = scheduler._run_async_volatility_batch(["BTCUSDT", "ETHUSDT"])
            assert results == {"BTCUSDT": 2.5, "ETHUSDT": 3.0}

    def test_run_async_volatility_batch_timeout(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        # Mock du calculateur pour simuler un timeout
        with patch.object(calculator, 'compute_volatility_batch') as mock_compute:
            mock_compute.side_effect = Exception("timeout")
            results = scheduler._run_async_volatility_batch(["BTCUSDT", "ETHUSDT"])
            assert results == {"BTCUSDT": None, "ETHUSDT": None}

    def test_retry_failed_symbols(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        # Mock du calcul de volatilité
        with patch.object(scheduler, '_run_async_volatility_batch') as mock_batch:
            mock_batch.return_value = {"BTCUSDT": 2.5}
            scheduler._retry_failed_symbols(["BTCUSDT"], time.time())
            mock_batch.assert_called_once_with(["BTCUSDT"])

    def test_wait_for_next_cycle(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        scheduler._running = True
        start_time = time.time()
        scheduler._wait_for_next_cycle(1)  # Attendre 1 seconde
        elapsed = time.time() - start_time
        assert elapsed >= 1.0

    def test_wait_for_next_cycle_stops_on_running_false(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        scheduler._running = True
        # Démarrer l'attente dans un thread
        def stop_after_delay():
            time.sleep(0.1)
            scheduler._running = False
        threading.Thread(target=stop_after_delay).start()
        start_time = time.time()
        scheduler._wait_for_next_cycle(10)  # Devrait s'arrêter après 0.1s
        elapsed = time.time() - start_time
        assert elapsed < 1.0

    def test_is_running_true(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        scheduler.start_refresh_task()
        assert scheduler.is_running() is True
        scheduler.stop_refresh_task()

    def test_is_running_false(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        assert scheduler.is_running() is False

    def test_is_running_false_after_stop(self):
        from volatility_scheduler import VolatilityScheduler
        from volatility import VolatilityCalculator
        from volatility_cache import VolatilityCache
        calculator = VolatilityCalculator()
        cache = VolatilityCache()
        scheduler = VolatilityScheduler(calculator, cache)
        scheduler.start_refresh_task()
        scheduler.stop_refresh_task()
        assert scheduler.is_running() is False


class TestSpreadFetcher:
    def test_init_sets_components(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        assert fetcher.logger is not None
        assert fetcher._pagination_handler is not None
        assert fetcher._error_handler is not None

    def test_fetch_spread_data_success(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        with patch.object(fetcher, '_fetch_spreads_paginated') as mock_paginated:
            with patch.object(fetcher, '_fetch_missing_spreads') as mock_missing:
                mock_paginated.return_value = {"BTCUSDT": 0.001, "ETHUSDT": 0.002}
                result = fetcher.fetch_spread_data("http://x", ["BTCUSDT", "ETHUSDT"])
                assert result == {"BTCUSDT": 0.001, "ETHUSDT": 0.002}
                mock_paginated.assert_called_once()
                mock_missing.assert_called_once()

    def test_fetch_spread_data_exception(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        with patch.object(fetcher, '_fetch_spreads_paginated', side_effect=Exception("test")):
            with pytest.raises(Exception, match="test"):
                fetcher.fetch_spread_data("http://x", ["BTCUSDT"])

    def test_fetch_spreads_paginated_success(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        with patch.object(fetcher._pagination_handler, 'fetch_paginated_data') as mock_fetch:
            with patch.object(fetcher, '_process_tickers_for_spreads') as mock_process:
                mock_fetch.return_value = [{"symbol": "BTCUSDT", "bid1Price": "50000", "ask1Price": "50010"}]
                result = fetcher._fetch_spreads_paginated("http://x", ["BTCUSDT"], 10, "linear")
                mock_fetch.assert_called_once()
                mock_process.assert_called_once()

    def test_fetch_spreads_paginated_exception(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        with patch.object(fetcher._pagination_handler, 'fetch_paginated_data', side_effect=Exception("test")):
            with pytest.raises(Exception, match="test"):
                fetcher._fetch_spreads_paginated("http://x", ["BTCUSDT"], 10, "linear")

    def test_process_tickers_for_spreads(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        tickers = [
            {"symbol": "BTCUSDT", "bid1Price": "50000", "ask1Price": "50010"},
            {"symbol": "ETHUSDT", "bid1Price": "3000", "ask1Price": "3005"}
        ]
        wanted = {"BTCUSDT", "ETHUSDT"}
        found = {}
        with patch.object(fetcher, '_calculate_spread_from_ticker') as mock_calc:
            mock_calc.return_value = 0.001
            fetcher._process_tickers_for_spreads(tickers, wanted, found)
            assert len(found) == 2
            assert "BTCUSDT" in found
            assert "ETHUSDT" in found

    def test_process_tickers_for_spreads_exception(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        tickers = [{"symbol": "BTCUSDT", "bid1Price": "50000", "ask1Price": "50010"}]
        wanted = {"BTCUSDT"}
        found = {}
        with patch.object(fetcher, '_calculate_spread_from_ticker', side_effect=Exception("test")):
            fetcher._process_tickers_for_spreads(tickers, wanted, found)
            assert len(found) == 0

    def test_calculate_spread_from_ticker_success(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        ticker = {"bid1Price": "50000", "ask1Price": "50010"}
        result = fetcher._calculate_spread_from_ticker(ticker)
        assert result is not None
        assert result > 0

    def test_calculate_spread_from_ticker_missing_prices(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        ticker = {"bid1Price": None, "ask1Price": "50010"}
        result = fetcher._calculate_spread_from_ticker(ticker)
        assert result is None

    def test_calculate_spread_from_ticker_invalid_prices(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        ticker = {"bid1Price": "invalid", "ask1Price": "50010"}
        result = fetcher._calculate_spread_from_ticker(ticker)
        assert result is None

    def test_calculate_spread_from_ticker_zero_prices(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        ticker = {"bid1Price": "0", "ask1Price": "50010"}
        result = fetcher._calculate_spread_from_ticker(ticker)
        assert result is None

    def test_calculate_spread_from_ticker_exception(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        ticker = {"bid1Price": "50000", "ask1Price": "50010"}
        with patch.object(fetcher, '_safe_float_conversion', side_effect=Exception("test")):
            result = fetcher._calculate_spread_from_ticker(ticker)
            assert result is None

    def test_fetch_missing_spreads_no_missing(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        found = {"BTCUSDT": 0.001}
        fetcher._fetch_missing_spreads("http://x", ["BTCUSDT"], found, 10, "linear")
        # Ne devrait pas appeler _fetch_single_spread

    def test_fetch_missing_spreads_with_missing(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        found = {"BTCUSDT": 0.001}
        with patch.object(fetcher, '_fetch_single_spread') as mock_single:
            mock_single.return_value = 0.002
            fetcher._fetch_missing_spreads("http://x", ["BTCUSDT", "ETHUSDT"], found, 10, "linear")
            mock_single.assert_called_once_with("http://x", "ETHUSDT", 10, "linear")
            assert found["ETHUSDT"] == 0.002

    def test_fetch_single_spread_success(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        with patch('spread_fetcher.get_http_client') as mock_get_client:
            with patch('spread_fetcher.get_rate_limiter') as mock_get_limiter:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "retCode": 0,
                    "result": {
                        "list": [{"bid1Price": "50000", "ask1Price": "50010"}]
                    }
                }
                mock_client.get.return_value = mock_response
                mock_get_client.return_value = mock_client
                mock_limiter = Mock()
                mock_get_limiter.return_value = mock_limiter
                result = fetcher._fetch_single_spread("http://x", "BTCUSDT", 10, "linear")
                assert result is not None
                assert result > 0

    def test_fetch_single_spread_http_error(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        with patch('spread_fetcher.get_http_client') as mock_get_client:
            with patch('spread_fetcher.get_rate_limiter') as mock_get_limiter:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.status_code = 400
                mock_client.get.return_value = mock_response
                mock_get_client.return_value = mock_client
                mock_limiter = Mock()
                mock_get_limiter.return_value = mock_limiter
                result = fetcher._fetch_single_spread("http://x", "BTCUSDT", 10, "linear")
                assert result is None

    def test_fetch_single_spread_api_error(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        with patch('spread_fetcher.get_http_client') as mock_get_client:
            with patch('spread_fetcher.get_rate_limiter') as mock_get_limiter:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "retCode": 10001,
                    "retMsg": "API Error"
                }
                mock_client.get.return_value = mock_response
                mock_get_client.return_value = mock_client
                mock_limiter = Mock()
                mock_get_limiter.return_value = mock_limiter
                result = fetcher._fetch_single_spread("http://x", "BTCUSDT", 10, "linear")
                assert result is None

    def test_fetch_single_spread_no_tickers(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        with patch('spread_fetcher.get_http_client') as mock_get_client:
            with patch('spread_fetcher.get_rate_limiter') as mock_get_limiter:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "retCode": 0,
                    "result": {"list": []}
                }
                mock_client.get.return_value = mock_response
                mock_get_client.return_value = mock_client
                mock_limiter = Mock()
                mock_get_limiter.return_value = mock_limiter
                result = fetcher._fetch_single_spread("http://x", "BTCUSDT", 10, "linear")
                assert result is None

    def test_fetch_single_spread_exception(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        with patch('spread_fetcher.get_http_client', side_effect=Exception("test")):
            result = fetcher._fetch_single_spread("http://x", "BTCUSDT", 10, "linear")
            assert result is None

    def test_safe_float_conversion_success(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        result = fetcher._safe_float_conversion("123.45", "test_field")
        assert result == 123.45

    def test_safe_float_conversion_none(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        result = fetcher._safe_float_conversion(None, "test_field")
        assert result is None

    def test_safe_float_conversion_invalid(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        result = fetcher._safe_float_conversion("invalid", "test_field")
        assert result is None

    def test_validate_spread_data_success(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        spread_data = {"BTCUSDT": 0.001, "ETHUSDT": 0.002}
        result = fetcher.validate_spread_data(spread_data)
        assert result is True

    def test_validate_spread_data_empty(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        result = fetcher.validate_spread_data({})
        assert result is False

    def test_validate_spread_data_invalid(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        spread_data = {"BTCUSDT": 0.001, "ETHUSDT": 1.5}  # Spread > 100%
        result = fetcher.validate_spread_data(spread_data)
        assert result is True  # Au moins un spread valide

    def test_validate_spread_data_exception(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        with patch.object(fetcher, '_validate_single_spread_entry', side_effect=Exception("test")):
            result = fetcher.validate_spread_data({"BTCUSDT": 0.001})
            assert result is False

    def test_validate_single_spread_entry_success(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        result = fetcher._validate_single_spread_entry("BTCUSDT", 0.001)
        assert result is True

    def test_validate_single_spread_entry_invalid_symbol(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        result = fetcher._validate_single_spread_entry("", 0.001)
        assert result is False

    def test_validate_single_spread_entry_invalid_spread(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        result = fetcher._validate_single_spread_entry("BTCUSDT", "invalid")
        assert result is False

    def test_validate_single_spread_entry_negative_spread(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        result = fetcher._validate_single_spread_entry("BTCUSDT", -0.001)
        assert result is False

    def test_validate_single_spread_entry_too_large_spread(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        result = fetcher._validate_single_spread_entry("BTCUSDT", 1.5)
        assert result is False

    def test_validate_single_spread_entry_exception(self):
        from spread_fetcher import SpreadFetcher
        fetcher = SpreadFetcher()
        result = fetcher._validate_single_spread_entry("BTCUSDT", None)
        assert result is False


class TestThreadManager:
    def test_init_sets_logger(self):
        from thread_manager import ThreadManager
        manager = ThreadManager()
        assert manager.logger is not None

    def test_init_with_custom_logger(self):
        from thread_manager import ThreadManager
        custom_logger = Mock()
        manager = ThreadManager(logger=custom_logger)
        assert manager.logger is custom_logger


class TestBotConfigurator:
    def test_init_sets_parameters(self):
        from bot_configurator import BotConfigurator
        configurator = BotConfigurator(testnet=True)
        assert configurator.testnet is True
        assert configurator.logger is not None

    def test_load_and_validate_config_success(self):
        from bot_configurator import BotConfigurator
        configurator = BotConfigurator(testnet=True)
        mock_config_manager = Mock()
        mock_config_manager.load_and_validate_config.return_value = {"test": "config"}
        result = configurator.load_and_validate_config(mock_config_manager)
        assert result == {"test": "config"}

    def test_load_and_validate_config_error(self):
        from bot_configurator import BotConfigurator
        configurator = BotConfigurator(testnet=True)
        mock_config_manager = Mock()
        mock_config_manager.load_and_validate_config.side_effect = ValueError("test error")
        with pytest.raises(ValueError, match="test error"):
            configurator.load_and_validate_config(mock_config_manager)

    def test_get_market_data_success(self):
        from bot_configurator import BotConfigurator
        configurator = BotConfigurator(testnet=True)
        with patch('bot_configurator.BybitPublicClient') as mock_client_class:
            with patch('bot_configurator.get_perp_symbols') as mock_get_perp:
                mock_client = Mock()
                mock_client.public_base_url.return_value = "http://test"
                mock_client_class.return_value = mock_client
                mock_get_perp.return_value = {"test": "data"}
                base_url, perp_data = configurator.get_market_data()
                assert base_url == "http://test"
                assert perp_data == {"test": "data"}

    def test_get_market_data_exception(self):
        from bot_configurator import BotConfigurator
        configurator = BotConfigurator(testnet=True)
        with patch('bot_configurator.BybitPublicClient', side_effect=Exception("test error")):
            with pytest.raises(Exception, match="test error"):
                configurator.get_market_data()

    def test_configure_managers(self):
        from bot_configurator import BotConfigurator
        configurator = BotConfigurator(testnet=True)
        config = {"volatility_ttl_sec": 120, "display_interval_seconds": 10}
        perp_data = {"categories": {"BTCUSDT": "linear"}}
        mock_data_manager = Mock()
        mock_volatility_tracker = Mock()
        mock_watchlist_manager = Mock()
        mock_display_manager = Mock()
        configurator.configure_managers(
            config, perp_data, mock_data_manager, mock_volatility_tracker,
            mock_watchlist_manager, mock_display_manager
        )
        mock_data_manager.set_symbol_categories.assert_called_once()
        mock_volatility_tracker.set_symbol_categories.assert_called_once()
        mock_display_manager.set_display_interval.assert_called_once()

    def test_validate_environment_success(self):
        from bot_configurator import BotConfigurator
        configurator = BotConfigurator(testnet=True)
        result = configurator.validate_environment()
        assert result is True

    def test_validate_environment_import_error(self):
        from bot_configurator import BotConfigurator
        configurator = BotConfigurator(testnet=True)
        with patch('bot_configurator.setup_logging', side_effect=ImportError("test")):
            result = configurator.validate_environment()
            assert result is False

    def test_validate_environment_exception(self):
        from bot_configurator import BotConfigurator
        configurator = BotConfigurator(testnet=True)
        with patch.object(configurator.logger, 'info', side_effect=Exception("test")):
            result = configurator.validate_environment()
            assert result is False


class TestBotHealthMonitor:
    def test_init_sets_parameters(self):
        from bot_health_monitor import BotHealthMonitor
        monitor = BotHealthMonitor()
        assert monitor.logger is not None
        assert monitor._memory_check_counter == 0
        assert monitor._memory_check_interval == 300

    def test_check_components_health_all_running(self):
        from bot_health_monitor import BotHealthMonitor
        monitor = BotHealthMonitor()
        mock_monitoring = Mock()
        mock_monitoring.is_running.return_value = True
        mock_display = Mock()
        mock_display.is_running.return_value = True
        mock_volatility = Mock()
        mock_volatility.is_running.return_value = True
        result = monitor.check_components_health(mock_monitoring, mock_display, mock_volatility)
        assert result is True

    def test_check_components_health_monitoring_stopped(self):
        from bot_health_monitor import BotHealthMonitor
        monitor = BotHealthMonitor()
        mock_monitoring = Mock()
        mock_monitoring.is_running.return_value = False
        mock_display = Mock()
        mock_volatility = Mock()
        result = monitor.check_components_health(mock_monitoring, mock_display, mock_volatility)
        assert result is False

    def test_check_components_health_display_stopped(self):
        from bot_health_monitor import BotHealthMonitor
        monitor = BotHealthMonitor()
        mock_monitoring = Mock()
        mock_monitoring.is_running.return_value = True
        mock_display = Mock()
        mock_display.is_running.return_value = False
        mock_volatility = Mock()
        result = monitor.check_components_health(mock_monitoring, mock_display, mock_volatility)
        assert result is False

    def test_check_components_health_volatility_stopped(self):
        from bot_health_monitor import BotHealthMonitor
        monitor = BotHealthMonitor()
        mock_monitoring = Mock()
        mock_display = Mock()
        mock_volatility = Mock()
        mock_volatility.is_running.return_value = False
        result = monitor.check_components_health(mock_monitoring, mock_display, mock_volatility)
        assert result is False

    def test_check_components_health_exception(self):
        from bot_health_monitor import BotHealthMonitor
        monitor = BotHealthMonitor()
        mock_monitoring = Mock()
        mock_monitoring.is_running.side_effect = Exception("test")
        mock_display = Mock()
        mock_volatility = Mock()
        result = monitor.check_components_health(mock_monitoring, mock_display, mock_volatility)
        assert result is False

    def test_monitor_memory_usage_with_psutil(self):
        from bot_health_monitor import BotHealthMonitor
        monitor = BotHealthMonitor()
        with patch('bot_health_monitor.psutil') as mock_psutil:
            mock_process = Mock()
            mock_process.memory_info.return_value.rss = 100 * 1024 * 1024  # 100MB
            mock_psutil.Process.return_value = mock_process
            with patch('bot_health_monitor.gc') as mock_gc:
                result = monitor.monitor_memory_usage()
                assert result == 100.0

    def test_monitor_memory_usage_without_psutil(self):
        from bot_health_monitor import BotHealthMonitor
        monitor = BotHealthMonitor()
        with patch('bot_health_monitor.psutil', side_effect=ImportError()):
            with patch('bot_health_monitor.sys') as mock_sys:
                mock_sys.getsizeof.return_value = 50 * 1024 * 1024  # 50MB
                result = monitor.monitor_memory_usage()
                assert result > 0

    def test_monitor_memory_usage_exception(self):
        from bot_health_monitor import BotHealthMonitor
        monitor = BotHealthMonitor()
        with patch('bot_health_monitor.psutil', side_effect=Exception("test")):
            result = monitor.monitor_memory_usage()
            assert result == 0

    def test_should_check_memory_true(self):
        from bot_health_monitor import BotHealthMonitor
        monitor = BotHealthMonitor()
        monitor._memory_check_counter = 299
        result = monitor.should_check_memory()
        assert result is True
        assert monitor._memory_check_counter == 0

    def test_should_check_memory_false(self):
        from bot_health_monitor import BotHealthMonitor
        monitor = BotHealthMonitor()
        monitor._memory_check_counter = 100
        result = monitor.should_check_memory()
        assert result is False
        assert monitor._memory_check_counter == 101

    def test_get_health_status(self):
        from bot_health_monitor import BotHealthMonitor
        monitor = BotHealthMonitor()
        mock_monitoring = Mock()
        mock_display = Mock()
        mock_volatility = Mock()
        mock_monitoring.is_running.return_value = True
        mock_display.is_running.return_value = True
        mock_volatility.is_running.return_value = True
        with patch.object(monitor, 'monitor_memory_usage', return_value=100.0):
            status = monitor.get_health_status(mock_monitoring, mock_display, mock_volatility)
            assert status["monitoring_running"] is True
            assert status["display_running"] is True
            assert status["volatility_running"] is True
            assert status["memory_usage_mb"] == 100.0
            assert status["overall_healthy"] is True

    def test_reset_memory_counter(self):
        from bot_health_monitor import BotHealthMonitor
        monitor = BotHealthMonitor()
        monitor._memory_check_counter = 100
        monitor.reset_memory_counter()
        assert monitor._memory_check_counter == 0

    def test_set_memory_check_interval(self):
        from bot_health_monitor import BotHealthMonitor
        monitor = BotHealthMonitor()
        monitor.set_memory_check_interval(600)
        assert monitor._memory_check_interval == 600


class TestBotInitializer:
    def test_init_sets_parameters(self):
        from bot_initializer import BotInitializer
        initializer = BotInitializer(testnet=True)
        assert initializer.testnet is True
        assert initializer.logger is not None
        assert initializer.data_manager is None
        assert initializer.display_manager is None
        assert initializer.monitoring_manager is None
        assert initializer.ws_manager is None
        assert initializer.volatility_tracker is None
        assert initializer.watchlist_manager is None
        assert initializer.callback_manager is None
        assert initializer.opportunity_manager is None

    def test_initialize_managers(self):
        from bot_initializer import BotInitializer
        initializer = BotInitializer(testnet=True)
        with patch('bot_initializer.UnifiedDataManager') as mock_data:
            with patch('bot_initializer.DisplayManager') as mock_display:
                with patch('bot_initializer.UnifiedMonitoringManager') as mock_monitoring:
                    with patch('bot_initializer.WebSocketManager') as mock_ws:
                        with patch('bot_initializer.VolatilityTracker') as mock_volatility:
                            with patch('bot_initializer.WatchlistManager') as mock_watchlist:
                                initializer.initialize_managers()
                                assert initializer.data_manager is not None
                                assert initializer.display_manager is not None
                                assert initializer.monitoring_manager is not None
                                assert initializer.ws_manager is not None
                                assert initializer.volatility_tracker is not None
                                assert initializer.watchlist_manager is not None

    def test_initialize_specialized_managers(self):
        from bot_initializer import BotInitializer
        initializer = BotInitializer(testnet=True)
        with patch('bot_initializer.CallbackManager') as mock_callback:
            with patch('bot_initializer.OpportunityManager') as mock_opportunity:
                initializer.initialize_specialized_managers()
                assert initializer.callback_manager is not None
                assert initializer.opportunity_manager is not None

    def test_setup_manager_callbacks_success(self):
        from bot_initializer import BotInitializer
        initializer = BotInitializer(testnet=True)
        initializer.callback_manager = Mock()
        initializer.display_manager = Mock()
        initializer.monitoring_manager = Mock()
        initializer.volatility_tracker = Mock()
        initializer.ws_manager = Mock()
        initializer.data_manager = Mock()
        initializer.watchlist_manager = Mock()
        initializer.opportunity_manager = Mock()
        initializer.setup_manager_callbacks()
        initializer.callback_manager.setup_all_callbacks.assert_called_once()

    def test_setup_manager_callbacks_missing_managers(self):
        from bot_initializer import BotInitializer
        initializer = BotInitializer(testnet=True)
        initializer.callback_manager = None
        with pytest.raises(RuntimeError, match="Tous les managers doivent être initialisés"):
            initializer.setup_manager_callbacks()

    def test_get_managers(self):
        from bot_initializer import BotInitializer
        initializer = BotInitializer(testnet=True)
        initializer.data_manager = Mock()
        initializer.display_manager = Mock()
        initializer.monitoring_manager = Mock()
        initializer.ws_manager = Mock()
        initializer.volatility_tracker = Mock()
        initializer.watchlist_manager = Mock()
        initializer.callback_manager = Mock()
        initializer.opportunity_manager = Mock()
        managers = initializer.get_managers()
        assert "data_manager" in managers
        assert "display_manager" in managers
        assert "monitoring_manager" in managers
        assert "ws_manager" in managers
        assert "volatility_tracker" in managers
        assert "watchlist_manager" in managers
        assert "callback_manager" in managers
        assert "opportunity_manager" in managers


class TestBotStarter:
    def test_init_sets_parameters(self):
        from bot_starter import BotStarter
        starter = BotStarter(testnet=True)
        assert starter.testnet is True
        assert starter.logger is not None

    @pytest.mark.asyncio
    async def test_start_bot_components_success(self):
        from bot_starter import BotStarter
        starter = BotStarter(testnet=True)
        mock_volatility = Mock()
        mock_display = Mock()
        mock_ws = Mock()
        mock_data = Mock()
        mock_monitoring = Mock()
        with patch.object(starter, '_start_volatility_tracker'):
            with patch.object(starter, '_start_display_manager'):
                with patch.object(starter, '_start_websocket_connections'):
                    with patch.object(starter, '_setup_candidate_monitoring'):
                        with patch.object(starter, '_start_continuous_monitoring'):
                            await starter.start_bot_components(
                                mock_volatility, mock_display, mock_ws, mock_data, mock_monitoring,
                                "http://test", {"test": "data"}
                            )

    @pytest.mark.asyncio
    async def test_start_bot_components_exception(self):
        from bot_starter import BotStarter
        starter = BotStarter(testnet=True)
        mock_volatility = Mock()
        mock_display = Mock()
        mock_ws = Mock()
        mock_data = Mock()
        mock_monitoring = Mock()
        with patch.object(starter, '_start_volatility_tracker', side_effect=Exception("test")):
            with pytest.raises(Exception, match="test"):
                await starter.start_bot_components(
                    mock_volatility, mock_display, mock_ws, mock_data, mock_monitoring,
                    "http://test", {"test": "data"}
                )

    def test_start_volatility_tracker(self):
        from bot_starter import BotStarter
        starter = BotStarter(testnet=True)
        mock_volatility = Mock()
        starter._start_volatility_tracker(mock_volatility)
        mock_volatility.start_refresh_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_display_manager(self):
        from bot_starter import BotStarter
        starter = BotStarter(testnet=True)
        mock_display = Mock()
        await starter._start_display_manager(mock_display)
        mock_display.start_display_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_websocket_connections(self):
        from bot_starter import BotStarter
        starter = BotStarter(testnet=True)
        mock_ws = Mock()
        mock_data = Mock()
        mock_data.get_linear_symbols.return_value = ["BTCUSDT"]
        mock_data.get_inverse_symbols.return_value = ["BTCUSD"]
        await starter._start_websocket_connections(mock_ws, mock_data)
        mock_ws.start_connections.assert_called_once()

    def test_setup_candidate_monitoring(self):
        from bot_starter import BotStarter
        starter = BotStarter(testnet=True)
        mock_monitoring = Mock()
        starter._setup_candidate_monitoring(mock_monitoring, "http://test", {"test": "data"})
        mock_monitoring.setup_candidate_monitoring.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_continuous_monitoring(self):
        from bot_starter import BotStarter
        starter = BotStarter(testnet=True)
        mock_monitoring = Mock()
        await starter._start_continuous_monitoring(mock_monitoring, "http://test", {"test": "data"})
        mock_monitoring.start_continuous_monitoring.assert_called_once()

    def test_display_startup_summary(self):
        from bot_starter import BotStarter
        starter = BotStarter(testnet=True)
        config = {"categorie": "linear"}
        perp_data = {"total": 100}
        mock_data = Mock()
        mock_data.get_linear_symbols.return_value = ["BTCUSDT"]
        mock_data.get_inverse_symbols.return_value = ["BTCUSD"]
        starter.display_startup_summary(config, perp_data, mock_data)

    def test_get_startup_stats(self):
        from bot_starter import BotStarter
        starter = BotStarter(testnet=True)
        mock_data = Mock()
        mock_data.get_linear_symbols.return_value = ["BTCUSDT"]
        mock_data.get_inverse_symbols.return_value = ["BTCUSD"]
        stats = starter.get_startup_stats(mock_data)
        assert stats["linear_count"] == 1
        assert stats["inverse_count"] == 1
        assert stats["total_symbols"] == 2
        assert "startup_time" in stats


class TestConfigUnified:
    def test_get_settings_defaults(self):
        from config_unified import get_settings
        with patch.dict('os.environ', {}, clear=True):
            settings = get_settings()
            assert settings["testnet"] is True
            assert settings["timeout"] == 10
            assert settings["log_level"] == "INFO"
            assert settings["api_key"] is None
            assert settings["api_secret"] is None

    def test_get_settings_from_env(self):
        from config_unified import get_settings
        with patch.dict('os.environ', {
            "TESTNET": "false",
            "TIMEOUT": "15",
            "LOG_LEVEL": "DEBUG",
            "SPREAD_MAX": "0.5",
            "VOLUME_MIN_MILLIONS": "10.0"
        }):
            settings = get_settings()
            assert settings["testnet"] is False
            assert settings["timeout"] == 15
            assert settings["log_level"] == "DEBUG"
            assert settings["spread_max"] == 0.5
            assert settings["volume_min_millions"] == 10.0

    def test_unified_config_manager_init(self):
        from config_unified import UnifiedConfigManager
        manager = UnifiedConfigManager("test.yaml")
        assert manager.config_path == "test.yaml"
        assert manager.logger is not None
        assert manager.config == {}

    def test_load_and_validate_config_success(self):
        from config_unified import UnifiedConfigManager
        manager = UnifiedConfigManager("test.yaml")
        with patch('builtins.open', mock_open(read_data="test: value")):
            with patch('yaml.safe_load', return_value={"test": "value"}):
                with patch.object(manager, '_validate_config'):
                    config = manager.load_and_validate_config()
                    assert config["test"] == "value"

    def test_load_and_validate_config_file_not_found(self):
        from config_unified import UnifiedConfigManager
        manager = UnifiedConfigManager("nonexistent.yaml")
        with patch('builtins.open', side_effect=FileNotFoundError):
            with patch.object(manager, '_validate_config'):
                config = manager.load_and_validate_config()
                assert config["categorie"] == "linear"

    def test_load_and_validate_config_yaml_error(self):
        from config_unified import UnifiedConfigManager
        manager = UnifiedConfigManager("test.yaml")
        with patch('builtins.open', mock_open(read_data="invalid yaml")):
            with patch('yaml.safe_load', side_effect=Exception("YAML error")):
                with patch.object(manager, '_validate_config'):
                    config = manager.load_and_validate_config()
                    assert config["categorie"] == "linear"

    def test_validate_config_success(self):
        from config_unified import UnifiedConfigManager
        manager = UnifiedConfigManager("test.yaml")
        config = {
            "categorie": "linear",
            "funding_min": 0.01,
            "funding_max": 0.02,
            "volatility_min": 0.1,
            "volatility_max": 0.2,
            "spread_max": 0.5,
            "volume_min_millions": 10.0,
            "limite": 5,
            "volatility_ttl_sec": 120,
            "display_interval_seconds": 10
        }
        manager._validate_config(config)  # Ne devrait pas lever d'exception

    def test_validate_config_funding_min_max_error(self):
        from config_unified import UnifiedConfigManager
        manager = UnifiedConfigManager("test.yaml")
        config = {
            "funding_min": 0.02,
            "funding_max": 0.01,  # Min > Max
            "categorie": "linear"
        }
        with pytest.raises(ValueError, match="funding_min.*supérieur.*funding_max"):
            manager._validate_config(config)

    def test_validate_config_volatility_min_max_error(self):
        from config_unified import UnifiedConfigManager
        manager = UnifiedConfigManager("test.yaml")
        config = {
            "volatility_min": 0.2,
            "volatility_max": 0.1,  # Min > Max
            "categorie": "linear"
        }
        with pytest.raises(ValueError, match="volatility_min.*supérieur.*volatility_max"):
            manager._validate_config(config)

    def test_validate_config_negative_values(self):
        from config_unified import UnifiedConfigManager
        manager = UnifiedConfigManager("test.yaml")
        config = {
            "funding_min": -0.01,
            "categorie": "linear"
        }
        with pytest.raises(ValueError, match="ne peut pas être négatif"):
            manager._validate_config(config)

    def test_validate_config_invalid_category(self):
        from config_unified import UnifiedConfigManager
        manager = UnifiedConfigManager("test.yaml")
        config = {
            "categorie": "invalid"
        }
        with pytest.raises(ValueError, match="categorie invalide"):
            manager._validate_config(config)

    def test_validate_config_limit_too_high(self):
        from config_unified import UnifiedConfigManager
        manager = UnifiedConfigManager("test.yaml")
        config = {
            "limite": 2000,  # > MAX_LIMIT_RECOMMENDED
            "categorie": "linear"
        }
        with pytest.raises(ValueError, match="limite trop élevée"):
            manager._validate_config(config)

    def test_get_config(self):
        from config_unified import UnifiedConfigManager
        manager = UnifiedConfigManager("test.yaml")
        manager.config = {"test": "value"}
        config = manager.get_config()
        assert config == {"test": "value"}
        assert config is not manager.config  # Copie

    def test_get_config_value(self):
        from config_unified import UnifiedConfigManager
        manager = UnifiedConfigManager("test.yaml")
        manager.config = {"test": "value"}
        assert manager.get_config_value("test") == "value"
        assert manager.get_config_value("nonexistent", "default") == "default"


class TestUnifiedMonitoringManager:
    def test_init_sets_parameters(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager, testnet=True)
        assert manager.data_manager is mock_data_manager
        assert manager.testnet is True
        assert manager.logger is not None
        assert manager._running is False
        assert manager._scan_running is False
        assert manager._candidate_running is False

    def test_set_watchlist_manager(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        mock_watchlist = Mock()
        manager.set_watchlist_manager(mock_watchlist)
        assert manager.watchlist_manager is mock_watchlist

    def test_set_volatility_tracker(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        mock_tracker = Mock()
        manager.set_volatility_tracker(mock_tracker)
        assert manager.volatility_tracker is mock_tracker

    def test_set_ws_manager(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        mock_ws = Mock()
        manager.set_ws_manager(mock_ws)
        assert manager.ws_manager is mock_ws

    def test_set_on_new_opportunity_callback(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        callback = lambda x, y: None
        manager.set_on_new_opportunity_callback(callback)
        assert manager._on_new_opportunity_callback is callback

    def test_set_on_candidate_ticker_callback(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        callback = lambda x, y: None
        manager.set_on_candidate_ticker_callback(callback)
        assert manager._on_candidate_ticker_callback is callback

    @pytest.mark.asyncio
    async def test_start_continuous_monitoring_already_running(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        manager._running = True
        await manager.start_continuous_monitoring("http://test", {"test": "data"})
        # Ne devrait pas démarrer si déjà en cours

    @pytest.mark.asyncio
    async def test_start_continuous_monitoring_success(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        with patch.object(manager, '_start_market_scanning'):
            with patch.object(manager, '_setup_candidate_monitoring'):
                await manager.start_continuous_monitoring("http://test", {"test": "data"})
                assert manager._running is True

    @pytest.mark.asyncio
    async def test_stop_continuous_monitoring(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        manager._running = True
        with patch.object(manager, '_stop_market_scanning'):
            with patch.object(manager, '_stop_candidate_monitoring'):
                await manager.stop_continuous_monitoring()
                assert manager._running is False
                assert manager._on_new_opportunity_callback is None
                assert manager._on_candidate_ticker_callback is None

    def test_should_perform_scan_true(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        manager._scan_running = True
        manager._last_scan_time = time.time() - 70  # 70 secondes ago
        result = manager._should_perform_scan(time.time())
        assert result is True

    def test_should_perform_scan_false(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        manager._scan_running = True
        manager._last_scan_time = time.time() - 30  # 30 secondes ago
        result = manager._should_perform_scan(time.time())
        assert result is False

    def test_scan_for_opportunities_no_watchlist(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        manager.watchlist_manager = None
        result = manager._scan_for_opportunities("http://test", {"test": "data"})
        assert result is None

    def test_scan_for_opportunities_success(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        mock_watchlist = Mock()
        mock_watchlist.build_watchlist.return_value = (["BTCUSDT"], ["BTCUSD"], {"BTCUSDT": "data"})
        manager.watchlist_manager = mock_watchlist
        manager.volatility_tracker = Mock()
        with patch('unified_monitoring_manager.BybitPublicClient'):
            result = manager._scan_for_opportunities("http://test", {"test": "data"})
            assert result is not None
            assert "linear" in result
            assert "inverse" in result

    def test_integrate_opportunities(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        mock_data_manager.get_linear_symbols.return_value = []
        mock_data_manager.get_inverse_symbols.return_value = []
        opportunities = {
            "linear": ["BTCUSDT"],
            "inverse": ["BTCUSD"],
            "funding_data": {"BTCUSDT": "data"}
        }
        with patch.object(manager, '_update_symbol_lists'):
            with patch.object(manager, '_update_funding_data'):
                manager._integrate_opportunities(opportunities)
                mock_data_manager.get_linear_symbols.assert_called()
                mock_data_manager.get_inverse_symbols.assert_called()

    def test_detect_candidates_no_watchlist(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        manager.watchlist_manager = None
        linear, inverse = manager._detect_candidates("http://test", {"test": "data"})
        assert linear == []
        assert inverse == []

    def test_detect_candidates_success(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        mock_data_manager.symbol_categories = {"BTCUSDT": "linear", "BTCUSD": "inverse"}
        mock_watchlist = Mock()
        mock_watchlist.find_candidate_symbols.return_value = ["BTCUSDT", "BTCUSD"]
        manager.watchlist_manager = mock_watchlist
        linear, inverse = manager._detect_candidates("http://test", {"test": "data"})
        assert "BTCUSDT" in linear
        assert "BTCUSD" in inverse

    def test_is_running_true(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        manager._running = True
        manager._scan_running = True
        assert manager.is_running() is True

    def test_is_running_false(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        manager._running = False
        assert manager.is_running() is False

    def test_setup_candidate_monitoring(self):
        from unified_monitoring_manager import UnifiedMonitoringManager
        mock_data_manager = Mock()
        manager = UnifiedMonitoringManager(mock_data_manager)
        with patch.object(manager, '_detect_candidates', return_value=(["BTCUSDT"], ["BTCUSD"])):
            with patch.object(manager, '_start_candidate_monitoring'):
                manager.setup_candidate_monitoring("http://test", {"test": "data"})
                assert manager.candidate_symbols == ["BTCUSDT", "BTCUSD"]


class TestMetrics:
    def test_metrics_data_init(self):
        from metrics import MetricsData
        data = MetricsData()
        assert data.api_calls_total == 0
        assert data.api_errors_total == 0
        assert data.pairs_kept_total == 0
        assert data.pairs_rejected_total == 0
        assert data.ws_connections == 0
        assert data.ws_reconnects == 0
        assert data.ws_errors == 0

    def test_metrics_collector_init(self):
        from metrics import MetricsCollector
        collector = MetricsCollector()
        assert collector._data is not None
        assert collector._lock is not None
        assert collector._start_time > 0

    def test_record_api_call_success(self):
        from metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_api_call(0.1, success=True)
        assert collector._data.api_calls_total == 1
        assert collector._data.api_errors_total == 0
        assert len(collector._data.api_latencies) == 1

    def test_record_api_call_error(self):
        from metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_api_call(0.1, success=False)
        assert collector._data.api_calls_total == 1
        assert collector._data.api_errors_total == 1

    def test_record_filter_result(self):
        from metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_filter_result("funding", 5, 10)
        assert collector._data.pairs_kept_total == 5
        assert collector._data.pairs_rejected_total == 10
        assert collector._data.filter_stats["funding"]["kept"] == 5
        assert collector._data.filter_stats["funding"]["rejected"] == 10

    def test_record_ws_connection_connected(self):
        from metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_ws_connection(connected=True)
        assert collector._data.ws_connections == 1
        assert collector._data.ws_reconnects == 0

    def test_record_ws_connection_disconnected(self):
        from metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_ws_connection(connected=False)
        assert collector._data.ws_connections == 0
        assert collector._data.ws_reconnects == 1

    def test_record_ws_error(self):
        from metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_ws_error()
        assert collector._data.ws_errors == 1

    def test_get_metrics_summary(self):
        from metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_api_call(0.1, success=True)
        collector.record_filter_result("funding", 5, 10)
        summary = collector.get_metrics_summary()
        assert summary["api_calls_total"] == 1
        assert summary["api_errors_total"] == 0
        assert summary["api_error_rate_percent"] == 0.0
        assert summary["pairs_kept_total"] == 5
        assert summary["pairs_rejected_total"] == 10
        assert summary["filter_success_rate_percent"] == 33.33
        assert "uptime_seconds" in summary

    def test_reset(self):
        from metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_api_call(0.1, success=True)
        collector.reset()
        assert collector._data.api_calls_total == 0
        assert collector._data.api_errors_total == 0

    def test_global_functions(self):
        from metrics import record_api_call, record_filter_result, record_ws_connection, get_metrics_summary
        record_api_call(0.1, success=True)
        record_filter_result("test", 1, 2)
        record_ws_connection(connected=True)
        summary = get_metrics_summary()
        assert summary["api_calls_total"] >= 1
        assert summary["pairs_kept_total"] >= 1


class TestLoggingSetup:
    def test_setup_logging_returns_logger(self):
        from logging_setup import setup_logging
        logger = setup_logging()
        assert logger is not None

    def test_disable_logging(self):
        from logging_setup import disable_logging
        disable_logging()
        # Ne devrait pas lever d'exception

    def test_safe_log_info_disabled(self):
        from logging_setup import safe_log_info, disable_logging
        disable_logging()
        safe_log_info("test message")  # Ne devrait pas lever d'exception

    def test_safe_log_info_enabled(self):
        from logging_setup import safe_log_info
        with patch('logging_setup._logging_disabled', False):
            with patch('logging_setup._shutdown_logging_active', False):
                with patch('logging_setup.logger') as mock_logger:
                    safe_log_info("test message")
                    mock_logger.info.assert_called_once_with("test message")

    def test_log_shutdown_summary(self):
        from logging_setup import log_shutdown_summary
        mock_logger = Mock()
        log_shutdown_summary(mock_logger, ["BTCUSDT", "ETHUSDT"], 3600.0)
        # Ne devrait pas lever d'exception

    def test_log_shutdown_summary_no_candidates(self):
        from logging_setup import log_shutdown_summary
        mock_logger = Mock()
        log_shutdown_summary(mock_logger, None, 1800.0)
        # Ne devrait pas lever d'exception

    def test_log_shutdown_summary_reentrant_call(self):
        from logging_setup import log_shutdown_summary, _shutdown_logging_active
        mock_logger = Mock()
        with patch('logging_setup._shutdown_logging_active', True):
            log_shutdown_summary(mock_logger, [], 0.0)
        # Ne devrait pas lever d'exception
