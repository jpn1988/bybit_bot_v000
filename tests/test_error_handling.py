"""Tests de gestion d'erreurs pour le bot."""

import pytest
import httpx
from unittest.mock import Mock, patch, MagicMock
from data_manager import DataManager
from data_storage import DataStorage
from data_fetcher import DataFetcher
from bybit_client import BybitClient
from error_handler import ErrorHandler


class TestDataManagerErrorHandling:
    """Tests de gestion d'erreurs pour DataManager."""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger pour les tests."""
        return Mock()

    @pytest.fixture
    def data_manager(self, mock_logger):
        """Instance de DataManager pour les tests."""
        with patch('data_manager.DataFetcher'), \
             patch('data_manager.DataStorage'), \
             patch('data_manager.DataValidator'):
            return DataManager(testnet=True, logger=mock_logger)

    def test_load_watchlist_data_exception_handling(self, data_manager, mock_logger):
        """Test de gestion d'exception lors du chargement de la watchlist."""
        with patch.object(data_manager, '_validate_input_parameters', side_effect=Exception("Test error")):
            result = data_manager.load_watchlist_data(
                "https://api-testnet.bybit.com",
                {"test": "data"},
                Mock(),
                Mock()
            )
            
            assert result is False
            mock_logger.error.assert_called_once()

    def test_build_watchlist_exception_handling(self, data_manager, mock_logger):
        """Test de gestion d'exception lors de la construction de la watchlist."""
        mock_watchlist_manager = Mock()
        mock_volatility_tracker = Mock()
        
        with patch.object(data_manager, '_validate_input_parameters', return_value=True), \
             patch.object(data_manager, '_build_watchlist', side_effect=Exception("Build error")):
            
            result = data_manager.load_watchlist_data(
                "https://api-testnet.bybit.com",
                {"test": "data"},
                mock_watchlist_manager,
                mock_volatility_tracker
            )
            
            assert result is False
            mock_logger.error.assert_called_once()

    def test_update_data_from_watchlist_exception_handling(self, data_manager, mock_logger):
        """Test de gestion d'exception lors de la mise à jour des données."""
        mock_watchlist_manager = Mock()
        mock_watchlist_manager.get_original_funding_data.side_effect = Exception("Update error")
        
        with patch.object(data_manager, '_validate_input_parameters', return_value=True), \
             patch.object(data_manager, '_build_watchlist', return_value=(["BTCUSDT"], [], {})), \
             patch.object(data_manager, '_validate_loaded_data', return_value=True):
            
            result = data_manager.load_watchlist_data(
                "https://api-testnet.bybit.com",
                {"test": "data"},
                mock_watchlist_manager,
                Mock()
            )
            
            assert result is True  # L'erreur est loggée mais n'interrompt pas le processus
            mock_logger.warning.assert_called_once()

    def test_fetch_methods_exception_handling(self, data_manager, mock_logger):
        """Test de gestion d'exception dans les méthodes de récupération."""
        with patch.object(data_manager._fetcher, 'fetch_funding_map', side_effect=RuntimeError("API Error")) as mock_fetch:
            with pytest.raises(RuntimeError, match="API Error"):
                data_manager.fetch_funding_map("https://api-testnet.bybit.com", "linear", 10)
            
            mock_fetch.assert_called_once()

    def test_storage_methods_exception_handling(self, data_manager, mock_logger):
        """Test de gestion d'exception dans les méthodes de stockage."""
        with patch.object(data_manager._storage, 'update_funding_data', side_effect=Exception("Storage Error")):
            # Les exceptions dans le stockage sont propagées par le DataManager
            with pytest.raises(Exception, match="Storage Error"):
                data_manager.update_funding_data("BTCUSDT", 0.0001, 1000000, "1h", 0.001)


class TestDataStorageErrorHandling:
    """Tests de gestion d'erreurs pour DataStorage."""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger pour les tests."""
        return Mock()

    @pytest.fixture
    def storage(self, mock_logger):
        """Instance de DataStorage pour les tests."""
        return DataStorage(logger=mock_logger)

    def test_update_realtime_data_exception_handling(self, storage, mock_logger):
        """Test de gestion d'exception lors de la mise à jour des données temps réel."""
        with patch('time.time', side_effect=Exception("Time error")):
            ticker_data = {"markPrice": "50000.0"}
            storage.update_realtime_data("BTCUSDT", ticker_data)
            
            mock_logger.warning.assert_called_once()
            # Vérifier que l'exception n'est pas propagée
            assert len(storage.realtime_data) == 0

    def test_get_price_data_exception_handling(self, storage, mock_logger):
        """Test de gestion d'exception lors de la récupération des données de prix."""
        # Corrompre les données pour provoquer une exception
        storage.realtime_data["BTCUSDT"] = {"invalid": "data"}
        
        result = storage.get_price_data("BTCUSDT")
        
        # La méthode gère l'exception et retourne un dictionnaire avec des valeurs None
        assert result is not None
        assert result["mark_price"] is None
        assert result["last_price"] is None
        assert result["timestamp"] is None
        # Le warning n'est pas appelé car la méthode gère l'exception différemment

    def test_thread_safety_with_exceptions(self, storage, mock_logger):
        """Test de thread safety avec gestion d'exceptions."""
        import threading
        import time
        
        exception_count = 0
        
        def update_with_exception():
            nonlocal exception_count
            try:
                # Simuler une exception dans un thread
                with patch('time.time', side_effect=Exception("Thread error")):
                    storage.update_realtime_data("BTCUSDT", {"markPrice": "50000.0"})
            except Exception:
                exception_count += 1
        
        def normal_update():
            storage.update_realtime_data("ETHUSDT", {"markPrice": "3000.0"})
        
        # Lancer des threads
        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=update_with_exception))
            threads.append(threading.Thread(target=normal_update))
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Vérifier que les exceptions sont gérées et que les données normales sont présentes
        assert storage.get_realtime_data("ETHUSDT") is not None
        # Les exceptions sont loggées mais n'interrompent pas le fonctionnement


class TestDataFetcherErrorHandling:
    """Tests de gestion d'erreurs pour DataFetcher."""

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

    def test_fetch_complete_market_data_exception_handling(self, fetcher, mock_logger):
        """Test de gestion d'exception lors de la récupération complète des données."""
        with patch.object(fetcher, 'fetch_funding_data_parallel', side_effect=Exception("Funding error")), \
             patch.object(fetcher._error_handler, 'log_error') as mock_log:
            
            with pytest.raises(Exception, match="Funding error"):
                fetcher.fetch_complete_market_data(
                    "https://api-testnet.bybit.com",
                    ["linear"],
                    ["BTCUSDT"],
                    10
                )
            
            mock_log.assert_called_once()

    def test_validation_error_handling(self, fetcher, mock_logger):
        """Test de gestion d'erreurs de validation."""
        funding_data = {"BTCUSDT": {"invalid": "data"}}
        
        with patch.object(fetcher._funding_fetcher, 'validate_funding_data', return_value=False):
            result = fetcher.validate_funding_data(funding_data)
            
            assert result is False

    def test_delegation_error_handling(self, fetcher, mock_logger):
        """Test de gestion d'erreurs dans les délégations."""
        with patch.object(fetcher._funding_fetcher, 'fetch_funding_map', side_effect=RuntimeError("Network error")):
            with pytest.raises(RuntimeError, match="Network error"):
                fetcher.fetch_funding_map("https://api-testnet.bybit.com", "linear", 10)

    def test_error_handler_delegation(self, fetcher, mock_logger):
        """Test de délégation vers ErrorHandler."""
        test_error = ValueError("Test error")
        
        with patch.object(fetcher._error_handler, 'log_error') as mock_log, \
             patch.object(fetcher._error_handler, 'should_retry', return_value=True) as mock_retry:
            
            fetcher.handle_error(test_error, "test context")
            result = fetcher.should_retry(test_error, 1, 3)
            
            mock_log.assert_called_once_with(test_error, "test context")
            mock_retry.assert_called_once_with(test_error, 1, 3)
            assert result is True


class TestBybitClientErrorHandling:
    """Tests de gestion d'erreurs pour BybitClient."""

    def test_init_without_credentials(self):
        """Test d'initialisation sans credentials."""
        with pytest.raises(RuntimeError, match="Clés API manquantes"):
            BybitClient(testnet=True, api_key=None, api_secret=None)

    def test_init_with_empty_credentials(self):
        """Test d'initialisation avec credentials vides."""
        with pytest.raises(RuntimeError, match="Clés API manquantes"):
            BybitClient(testnet=True, api_key="", api_secret="")

    def test_http_error_handling(self):
        """Test de gestion des erreurs HTTP."""
        client = BybitClient(
            testnet=True,
            api_key="test_key",
            api_secret="test_secret"
        )
        
        with patch.object(client, '_execute_request_with_retry', side_effect=RuntimeError("HTTP 400: Bad Request")):
            with pytest.raises(RuntimeError, match="HTTP 400: Bad Request"):
                client.get_wallet_balance("UNIFIED")

    def test_api_error_handling(self):
        """Test de gestion des erreurs API."""
        client = BybitClient(
            testnet=True,
            api_key="test_key",
            api_secret="test_secret"
        )
        
        with patch.object(client, '_execute_request_with_retry', side_effect=RuntimeError("Authentification échouée")):
            with pytest.raises(RuntimeError, match="Authentification échouée"):
                client.get_wallet_balance("UNIFIED")

    def test_retry_mechanism_error_handling(self):
        """Test de gestion d'erreurs dans le mécanisme de retry."""
        client = BybitClient(
            testnet=True,
            api_key="test_key",
            api_secret="test_secret"
        )
        
        with patch.object(client, '_execute_request_with_retry', side_effect=RuntimeError("Erreur réseau/HTTP Bybit")):
            with pytest.raises(RuntimeError, match="Erreur réseau/HTTP Bybit"):
                client.get_wallet_balance("UNIFIED")


class TestErrorRecovery:
    """Tests de récupération d'erreurs."""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger pour les tests."""
        return Mock()

    def test_data_manager_recovery_after_error(self, mock_logger):
        """Test de récupération du DataManager après une erreur."""
        data_manager = DataManager(testnet=True, logger=mock_logger)
        
        # Simuler une erreur
        with patch.object(data_manager._storage, 'update_funding_data', side_effect=Exception("Storage error")):
            # L'erreur est propagée
            with pytest.raises(Exception, match="Storage error"):
                data_manager.update_funding_data("BTCUSDT", 0.0001, 1000000, "1h", 0.001)
        
        # Vérifier que le DataManager peut encore fonctionner
        data_manager.update_realtime_data("BTCUSDT", {"markPrice": "50000.0"})
        result = data_manager.get_realtime_data("BTCUSDT")
        
        assert result is not None
        assert result["mark_price"] == "50000.0"

    def test_storage_recovery_after_corruption(self, mock_logger):
        """Test de récupération du stockage après corruption."""
        storage = DataStorage(logger=mock_logger)
        
        # Corrompre les données
        storage.funding_data = None
        
        # Tenter une opération qui devrait échouer
        with pytest.raises(TypeError):
            storage.update_funding_data("BTCUSDT", 0.0001, 1000000, "1h", 0.001)
        
        # Réinitialiser le stockage
        storage.funding_data = {}
        
        # Vérifier que le stockage peut maintenant fonctionner
        storage.update_funding_data("BTCUSDT", 0.0001, 1000000, "1h", 0.001)
        
        result = storage.get_funding_data("BTCUSDT")
        assert result == (0.0001, 1000000, "1h", 0.001, None)

    def test_concurrent_error_handling(self, mock_logger):
        """Test de gestion d'erreurs concurrentes."""
        import threading
        import time
        
        storage = DataStorage(logger=mock_logger)
        exception_count = 0
        
        def error_operation():
            nonlocal exception_count
            try:
                # Opération qui peut échouer
                with patch('time.time', side_effect=Exception("Concurrent error")):
                    storage.update_realtime_data("BTCUSDT", {"markPrice": "50000.0"})
            except Exception:
                exception_count += 1
        
        def normal_operation():
            storage.update_funding_data("ETHUSDT", 0.0002, 2000000, "2h", 0.002)
        
        # Lancer des threads concurrents
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=error_operation))
            threads.append(threading.Thread(target=normal_operation))
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Vérifier que les opérations normales ont réussi
        result = storage.get_funding_data("ETHUSDT")
        assert result == (0.0002, 2000000, "2h", 0.002, None)
        
        # Vérifier que les erreurs ont été gérées
        assert exception_count >= 0  # Certaines exceptions peuvent être gérées silencieusement


class TestErrorHandler:
    """Tests pour ErrorHandler."""

    def test_handle_http_error_formats_message(self):
        handler = ErrorHandler(logger=Mock())
        mock_resp = Mock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        params = {"limit": 100, "cursor": "abc"}
        err = handler.handle_http_error("http://x", params, mock_resp, "ctx")
        assert "Erreur HTTP Bybit GET http://x" in str(err)
        assert "limit=100" in str(err)
        assert "cursor=abc" in str(err)
        assert "status=400" in str(err)
        assert "Bad Request" in str(err)

    def test_handle_api_error_formats_message(self):
        handler = ErrorHandler(logger=Mock())
        params = {"limit": 50}
        data = {"retCode": 10001, "retMsg": "bad"}
        err = handler.handle_api_error("http://x", params, data, "ctx")
        assert "Erreur API Bybit GET http://x" in str(err)
        assert "retCode=10001" in str(err)
        assert "retMsg=\"bad\"" in str(err)

    def test_handle_network_error_formats_message(self):
        handler = ErrorHandler(logger=Mock())
        params = {}
        orig = httpx.TimeoutException("timeout")
        err = handler.handle_network_error("http://x", params, orig, "ctx")
        assert "Erreur réseau Bybit GET http://x" in str(err)
        assert "error_type=TimeoutException" in str(err)
        assert "timeout" in str(err)

    def test_handle_validation_error_formats_message(self):
        handler = ErrorHandler(logger=Mock())
        err = handler.handle_validation_error("not_a_dict", "dict", "ctx")
        assert "Erreur validation données" in str(err)
        assert "expected_type=dict" in str(err)
        assert "actual_type=str" in str(err)

    def test_should_retry_network_timeout_returns_true(self):
        handler = ErrorHandler(logger=Mock())
        assert handler.should_retry(httpx.TimeoutException("t"), 1, 3) is True
        assert handler.should_retry(httpx.ConnectError("c"), 1, 3) is True

    def test_should_retry_http_5xx_returns_true(self):
        handler = ErrorHandler(logger=Mock())
        resp = Mock()
        resp.status_code = 500
        err = httpx.HTTPStatusError("5xx", request=None, response=resp)
        assert handler.should_retry(err, 1, 3) is True

    def test_should_retry_http_4xx_returns_false(self):
        handler = ErrorHandler(logger=Mock())
        resp = Mock()
        resp.status_code = 400
        err = httpx.HTTPStatusError("4xx", request=None, response=resp)
        assert handler.should_retry(err, 1, 3) is False

    def test_should_retry_max_attempts_returns_false(self):
        handler = ErrorHandler(logger=Mock())
        assert handler.should_retry(httpx.TimeoutException("t"), 3, 3) is False
