"""Tests pour DataManager."""

import pytest
from unittest.mock import Mock, patch
from data_manager import DataManager


class TestDataManager:
    """Tests pour DataManager."""

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

    def test_init(self, mock_logger):
        """Test d'initialisation."""
        with patch('unified_data_manager.DataFetcher') as mock_fetcher, \
             patch('unified_data_manager.DataStorage') as mock_storage, \
             patch('unified_data_manager.DataValidator') as mock_validator:
            
            manager = DataManager(testnet=True, logger=mock_logger)
            
            assert manager.testnet is True
            assert manager.logger == mock_logger
            mock_fetcher.assert_called_once_with(logger=mock_logger)
            mock_storage.assert_called_once_with(logger=mock_logger)
            mock_validator.assert_called_once_with(logger=mock_logger)

    def test_init_defaults(self):
        """Test d'initialisation avec valeurs par défaut."""
        with patch('unified_data_manager.DataFetcher'), \
             patch('unified_data_manager.DataStorage'), \
             patch('unified_data_manager.DataValidator'), \
             patch('unified_data_manager.setup_logging') as mock_setup:
            
            mock_logger = Mock()
            mock_setup.return_value = mock_logger
            
            manager = DataManager()
            
            assert manager.testnet is True
            assert manager.logger == mock_logger

    def test_load_watchlist_data_success(self, data_manager):
        """Test de chargement réussi des données de watchlist."""
        # Mock des composants
        mock_watchlist_manager = Mock()
        mock_volatility_tracker = Mock()
        
        # Mock des méthodes
        mock_watchlist_manager.build_watchlist.return_value = (
            ["BTCUSDT", "ETHUSDT"],  # linear_symbols
            ["BTCUSD"],              # inverse_symbols
            {"BTCUSDT": {"funding": 0.0001, "volume": 1000000}}  # funding_data
        )
        
        with patch.object(data_manager, '_validate_input_parameters', return_value=True), \
             patch.object(data_manager, '_build_watchlist', return_value=(["BTCUSDT"], ["BTCUSD"], {"BTCUSDT": (0.0001, 1000000, "1h", 0.001, None)})), \
             patch.object(data_manager, '_update_data_from_watchlist'), \
             patch.object(data_manager, '_validate_loaded_data', return_value=True):
            
            result = data_manager.load_watchlist_data(
                "https://api-testnet.bybit.com",
                {"test": "data"},
                mock_watchlist_manager,
                mock_volatility_tracker
            )
            
            assert result is True

    def test_load_watchlist_data_validation_failure(self, data_manager):
        """Test d'échec de validation des paramètres d'entrée."""
        with patch.object(data_manager, '_validate_input_parameters', return_value=False):
            result = data_manager.load_watchlist_data(
                "",  # URL invalide
                {},
                None,
                None
            )
            assert result is False

    def test_load_watchlist_data_build_failure(self, data_manager):
        """Test d'échec de construction de la watchlist."""
        mock_watchlist_manager = Mock()
        mock_volatility_tracker = Mock()
        
        with patch.object(data_manager, '_validate_input_parameters', return_value=True), \
             patch.object(data_manager, '_build_watchlist', return_value=None):
            
            result = data_manager.load_watchlist_data(
                "https://api-testnet.bybit.com",
                {"test": "data"},
                mock_watchlist_manager,
                mock_volatility_tracker
            )
            assert result is False

    def test_load_watchlist_data_validation_data_failure(self, data_manager):
        """Test d'échec de validation des données chargées."""
        mock_watchlist_manager = Mock()
        mock_volatility_tracker = Mock()
        
        with patch.object(data_manager, '_validate_input_parameters', return_value=True), \
             patch.object(data_manager, '_build_watchlist', return_value=(["BTCUSDT"], [], {})), \
             patch.object(data_manager, '_update_data_from_watchlist'), \
             patch.object(data_manager, '_validate_loaded_data', return_value=False):
            
            result = data_manager.load_watchlist_data(
                "https://api-testnet.bybit.com",
                {"test": "data"},
                mock_watchlist_manager,
                mock_volatility_tracker
            )
            assert result is False

    def test_validate_input_parameters_success(self, data_manager):
        """Test de validation réussie des paramètres."""
        mock_watchlist_manager = Mock()
        mock_volatility_tracker = Mock()
        
        result = data_manager._validate_input_parameters(
            "https://api-testnet.bybit.com",
            {"test": "data"},
            mock_watchlist_manager,
            mock_volatility_tracker
        )
        assert result is True

    def test_validate_input_parameters_invalid_url(self, data_manager):
        """Test de validation avec URL invalide."""
        result = data_manager._validate_input_parameters(
            "",  # URL vide
            {"test": "data"},
            Mock(),
            Mock()
        )
        assert result is False

    def test_validate_input_parameters_invalid_perp_data(self, data_manager):
        """Test de validation avec données perpétuels invalides."""
        result = data_manager._validate_input_parameters(
            "https://api-testnet.bybit.com",
            None,  # Données None
            Mock(),
            Mock()
        )
        assert result is False

    def test_validate_input_parameters_missing_watchlist_manager(self, data_manager):
        """Test de validation sans gestionnaire de watchlist."""
        result = data_manager._validate_input_parameters(
            "https://api-testnet.bybit.com",
            {"test": "data"},
            None,  # Pas de gestionnaire
            Mock()
        )
        assert result is False

    def test_validate_input_parameters_missing_volatility_tracker(self, data_manager):
        """Test de validation sans tracker de volatilité."""
        result = data_manager._validate_input_parameters(
            "https://api-testnet.bybit.com",
            {"test": "data"},
            Mock(),
            None  # Pas de tracker
        )
        assert result is False

    def test_build_watchlist_success(self, data_manager):
        """Test de construction réussie de la watchlist."""
        mock_watchlist_manager = Mock()
        mock_volatility_tracker = Mock()
        
        mock_watchlist_manager.build_watchlist.return_value = (
            ["BTCUSDT"], ["BTCUSD"], {"BTCUSDT": {"funding": 0.0001}}
        )
        
        result = data_manager._build_watchlist(
            "https://api-testnet.bybit.com",
            {"test": "data"},
            mock_watchlist_manager,
            mock_volatility_tracker
        )
        
        assert result == (["BTCUSDT"], ["BTCUSD"], {"BTCUSDT": {"funding": 0.0001}})
        mock_watchlist_manager.build_watchlist.assert_called_once_with(
            "https://api-testnet.bybit.com",
            {"test": "data"},
            mock_volatility_tracker
        )

    def test_build_watchlist_no_symbols(self, data_manager):
        """Test de construction de watchlist sans symboles."""
        mock_watchlist_manager = Mock()
        mock_volatility_tracker = Mock()
        
        mock_watchlist_manager.build_watchlist.return_value = ([], [], {})
        
        result = data_manager._build_watchlist(
            "https://api-testnet.bybit.com",
            {"test": "data"},
            mock_watchlist_manager,
            mock_volatility_tracker
        )
        
        assert result is None

    def test_build_watchlist_exception(self, data_manager):
        """Test de construction de watchlist avec exception."""
        mock_watchlist_manager = Mock()
        mock_volatility_tracker = Mock()
        
        mock_watchlist_manager.build_watchlist.side_effect = Exception("Test error")
        
        result = data_manager._build_watchlist(
            "https://api-testnet.bybit.com",
            {"test": "data"},
            mock_watchlist_manager,
            mock_volatility_tracker
        )
        
        assert result is None

    def test_validate_loaded_data(self, data_manager):
        """Test de validation des données chargées."""
        with patch.object(data_manager._storage, 'get_linear_symbols', return_value=["BTCUSDT"]), \
             patch.object(data_manager._storage, 'get_inverse_symbols', return_value=["BTCUSD"]), \
             patch.object(data_manager._storage, 'get_all_funding_data', return_value={"BTCUSDT": (0.0001, 1000000, "1h", 0.001, None)}), \
             patch.object(data_manager._validator, 'validate_data_integrity', return_value=True):
            
            result = data_manager._validate_loaded_data()
            assert result is True

    def test_fetch_funding_map_delegation(self, data_manager):
        """Test d'accès direct au DataFetcher pour fetch_funding_map."""
        with patch.object(data_manager._fetcher, 'fetch_funding_map', return_value={"BTCUSDT": {"funding": 0.0001}}) as mock_fetch:
            result = data_manager.fetcher.fetch_funding_map("https://api-testnet.bybit.com", "linear", 10)
            
            assert result == {"BTCUSDT": {"funding": 0.0001}}
            mock_fetch.assert_called_once_with("https://api-testnet.bybit.com", "linear", 10)

    def test_fetch_spread_data_delegation(self, data_manager):
        """Test d'accès direct au DataFetcher pour fetch_spread_data."""
        with patch.object(data_manager._fetcher, 'fetch_spread_data', return_value={"BTCUSDT": 0.001}) as mock_fetch:
            result = data_manager.fetcher.fetch_spread_data("https://api-testnet.bybit.com", ["BTCUSDT"], 10, "linear")
            
            assert result == {"BTCUSDT": 0.001}
            mock_fetch.assert_called_once_with("https://api-testnet.bybit.com", ["BTCUSDT"], 10, "linear")

    def test_update_realtime_data_delegation(self, data_manager):
        """Test d'accès direct au DataStorage pour update_realtime_data."""
        ticker_data = {"markPrice": 50000, "lastPrice": 50001}
        with patch.object(data_manager._storage, 'update_realtime_data') as mock_update:
            data_manager.storage.update_realtime_data("BTCUSDT", ticker_data)
            mock_update.assert_called_once_with("BTCUSDT", ticker_data)

    def test_get_realtime_data_delegation(self, data_manager):
        """Test d'accès direct au DataStorage pour get_realtime_data."""
        expected_data = {"markPrice": 50000, "lastPrice": 50001}
        with patch.object(data_manager._storage, 'get_realtime_data', return_value=expected_data) as mock_get:
            result = data_manager.storage.get_realtime_data("BTCUSDT")
            
            assert result == expected_data
            mock_get.assert_called_once_with("BTCUSDT")

    def test_direct_storage_access(self, data_manager):
        """Test d'accès direct au DataStorage via la propriété storage."""
        # Simuler les données directement sur l'instance storage
        data_manager._storage.symbol_categories = {"BTCUSDT": "linear"}
        data_manager._storage.linear_symbols = ["BTCUSDT"]
        data_manager._storage.inverse_symbols = ["BTCUSD"]
        data_manager._storage.funding_data = {"BTCUSDT": (0.0001, 1000000, "1h", 0.001, None)}
        data_manager._storage.realtime_data = {"BTCUSDT": {"markPrice": 50000}}
        
        # Accès direct via storage
        assert data_manager.storage.symbol_categories == {"BTCUSDT": "linear"}
        assert data_manager.storage.linear_symbols == ["BTCUSDT"]
        assert data_manager.storage.inverse_symbols == ["BTCUSD"]
        assert data_manager.storage.funding_data == {"BTCUSDT": (0.0001, 1000000, "1h", 0.001, None)}
        assert data_manager.storage.realtime_data == {"BTCUSDT": {"markPrice": 50000}}

    def test_get_loading_summary(self, data_manager):
        """Test de récupération du résumé de chargement."""
        expected_summary = {"symbols_count": 2, "funding_count": 1}
        with patch.object(data_manager._storage, 'get_linear_symbols', return_value=["BTCUSDT"]), \
             patch.object(data_manager._storage, 'get_inverse_symbols', return_value=["ETHUSDT"]), \
             patch.object(data_manager._storage, 'get_all_funding_data', return_value={"BTCUSDT": (0.0001, 1000000, "1h", 0.001, None)}), \
             patch.object(data_manager._validator, 'get_loading_summary', return_value=expected_summary):
            
            result = data_manager.get_loading_summary()
            assert result == expected_summary
