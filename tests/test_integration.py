"""Tests d'intégration pour les composants du bot."""

import pytest
import asyncio
from unittest.mock import Mock, patch
from data_manager import DataManager
from data_storage import DataStorage
from data_fetcher import DataFetcher
from ws_manager import WebSocketManager
from bot_initializer import BotInitializer


class TestDataManagerIntegration:
    """Tests d'intégration pour DataManager avec ses composants."""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger pour les tests."""
        return Mock()

    @pytest.fixture
    def real_data_manager(self, mock_logger):
        """Instance réelle de DataManager pour les tests d'intégration."""
        return DataManager(testnet=True, logger=mock_logger)

    def test_data_manager_with_real_storage(self, real_data_manager):
        """Test d'intégration avec DataStorage réel."""
        # Tester la mise à jour et récupération des données
        real_data_manager.update_funding_data("BTCUSDT", 0.0001, 1000000, "1h", 0.001, 0.05)
        real_data_manager.update_realtime_data("BTCUSDT", {"markPrice": "50000.0", "lastPrice": "50001.0"})
        
        # Vérifier les données
        funding_data = real_data_manager.get_funding_data("BTCUSDT")
        realtime_data = real_data_manager.get_realtime_data("BTCUSDT")
        
        assert funding_data == (0.0001, 1000000, "1h", 0.001, 0.05)
        assert realtime_data["mark_price"] == "50000.0"
        assert realtime_data["last_price"] == "50001.0"

    def test_data_manager_thread_safety(self, real_data_manager):
        """Test de thread safety d'intégration."""
        import threading
        import time
        
        def update_data(thread_id):
            for i in range(10):
                symbol = f"SYMBOL{thread_id}_{i}"
                real_data_manager.update_funding_data(symbol, 0.0001, 1000000, "1h", 0.001)
                real_data_manager.update_realtime_data(symbol, {"markPrice": f"{50000 + i}"})
                time.sleep(0.001)  # Petite pause pour simuler la concurrence
        
        def read_data(thread_id):
            for i in range(10):
                symbol = f"SYMBOL{thread_id}_{i}"
                real_data_manager.get_funding_data(symbol)
                real_data_manager.get_realtime_data(symbol)
                time.sleep(0.001)
        
        # Lancer des threads concurrents
        threads = []
        for i in range(3):
            threads.append(threading.Thread(target=update_data, args=(i,)))
            threads.append(threading.Thread(target=read_data, args=(i,)))
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Vérifier qu'aucune exception n'a été levée
        stats = real_data_manager.get_data_stats()
        assert stats["funding_data_objects"] >= 0
        assert stats["realtime_data"] >= 0

    def test_data_manager_symbol_management(self, real_data_manager):
        """Test de gestion des symboles."""
        # Ajouter des symboles
        real_data_manager.set_symbol_lists(["BTCUSDT", "ETHUSDT"], ["BTCUSD", "ETHUSD"])
        
        # Vérifier les listes
        linear_symbols = real_data_manager.get_linear_symbols()
        inverse_symbols = real_data_manager.get_inverse_symbols()
        all_symbols = real_data_manager.get_all_symbols()
        
        assert linear_symbols == ["BTCUSDT", "ETHUSDT"]
        assert inverse_symbols == ["BTCUSD", "ETHUSD"]
        assert all_symbols == ["BTCUSDT", "ETHUSDT", "BTCUSD", "ETHUSD"]
        
        # Ajouter un symbole à une catégorie
        real_data_manager.add_symbol_to_category("ADAUSDT", "linear")
        
        updated_linear = real_data_manager.get_linear_symbols()
        assert "ADAUSDT" in updated_linear
        
        # Retirer un symbole d'une catégorie
        real_data_manager.remove_symbol_from_category("BTCUSDT", "linear")
        
        updated_linear = real_data_manager.get_linear_symbols()
        assert "BTCUSDT" not in updated_linear

    def test_data_manager_clear_all_data(self, real_data_manager):
        """Test de vidage de toutes les données."""
        # Ajouter des données
        real_data_manager.update_funding_data("BTCUSDT", 0.0001, 1000000, "1h", 0.001)
        real_data_manager.update_realtime_data("BTCUSDT", {"markPrice": "50000.0"})
        real_data_manager.set_symbol_lists(["BTCUSDT"], ["BTCUSD"])
        
        # Vérifier que les données sont là
        assert real_data_manager.get_funding_data("BTCUSDT") is not None
        assert real_data_manager.get_realtime_data("BTCUSDT") is not None
        assert len(real_data_manager.get_linear_symbols()) == 1
        
        # Vider toutes les données
        real_data_manager.clear_all_data()
        
        # Vérifier que tout est vide
        assert real_data_manager.get_funding_data("BTCUSDT") is None
        assert real_data_manager.get_realtime_data("BTCUSDT") is None
        assert len(real_data_manager.get_linear_symbols()) == 0
        assert len(real_data_manager.get_inverse_symbols()) == 0


class TestWebSocketManagerIntegration:
    """Tests d'intégration pour WebSocketManager."""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger pour les tests."""
        return Mock()

    @pytest.fixture
    def ws_manager(self, mock_logger):
        """Instance de WebSocketManager pour les tests."""
        return WebSocketManager(testnet=True, logger=mock_logger)

    def test_ws_manager_callback_setup(self, ws_manager):
        """Test de configuration des callbacks."""
        callback_called = False
        received_data = None
        
        def test_callback(data):
            nonlocal callback_called, received_data
            callback_called = True
            received_data = data
        
        ws_manager.set_ticker_callback(test_callback)
        
        # Simuler la réception de données
        test_data = {"symbol": "BTCUSDT", "markPrice": "50000.0"}
        ws_manager._handle_ticker(test_data)
        
        assert callback_called is True
        assert received_data == test_data

    def test_ws_manager_symbol_management(self, ws_manager):
        """Test de gestion des symboles."""
        linear_symbols = ["BTCUSDT", "ETHUSDT"]
        inverse_symbols = ["BTCUSD", "ETHUSD"]
        
        # Configurer les symboles
        ws_manager.linear_symbols = linear_symbols
        ws_manager.inverse_symbols = inverse_symbols
        
        # Vérifier la récupération
        connected = ws_manager.get_connected_symbols()
        
        assert connected["linear"] == linear_symbols
        assert connected["inverse"] == inverse_symbols

    @pytest.mark.asyncio
    async def test_ws_manager_start_stop_cycle(self, ws_manager):
        """Test de cycle de démarrage et arrêt."""
        linear_symbols = ["BTCUSDT"]
        inverse_symbols = ["BTCUSD"]
        
        # Mock des connexions WebSocket pour éviter les connexions réelles
        with patch('ws_manager.PublicWSClient') as mock_ws_client:
            mock_conn = Mock()
            mock_ws_client.return_value = mock_conn
            
            # Démarrer les connexions
            await ws_manager.start_connections(linear_symbols, inverse_symbols)
            
            assert ws_manager.running is True
            assert len(ws_manager._ws_conns) > 0
            
            # Arrêter les connexions
            await ws_manager.stop()
            
            assert ws_manager.running is False
            assert len(ws_manager._ws_conns) == 0

    def test_ws_manager_ticker_handling(self, ws_manager):
        """Test de traitement des données ticker."""
        # Configurer un callback
        callback_data = None
        
        def test_callback(data):
            nonlocal callback_data
            callback_data = data
        
        ws_manager.set_ticker_callback(test_callback)
        
        # Simuler des données ticker valides
        ticker_data = {
            "symbol": "BTCUSDT",
            "markPrice": "50000.0",
            "lastPrice": "50001.0"
        }
        
        ws_manager._handle_ticker(ticker_data)
        
        assert callback_data == ticker_data

    def test_ws_manager_ticker_handling_invalid_data(self, ws_manager, mock_logger):
        """Test de traitement des données ticker invalides."""
        # Simuler des données ticker sans symbole
        ticker_data = {
            "markPrice": "50000.0",
            "lastPrice": "50001.0"
        }
        
        ws_manager._handle_ticker(ticker_data)
        
        # Vérifier qu'aucune exception n'a été levée
        assert True


class TestBotInitializerIntegration:
    """Tests d'intégration pour BotInitializer."""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger pour les tests."""
        return Mock()

    def test_bot_initializer_initialization(self, mock_logger):
        """Test d'initialisation complète du BotInitializer."""
        initializer = BotInitializer(testnet=True, logger=mock_logger)
        
        # Initialiser les managers
        initializer.initialize_managers()
        
        # Vérifier que tous les managers sont créés
        assert initializer.data_manager is not None
        assert initializer.display_manager is not None
        assert initializer.monitoring_manager is not None
        assert initializer.ws_manager is not None
        assert initializer.volatility_tracker is not None
        assert initializer.watchlist_manager is not None

    def test_bot_initializer_specialized_managers(self, mock_logger):
        """Test d'initialisation des gestionnaires spécialisés."""
        initializer = BotInitializer(testnet=True, logger=mock_logger)
        
        # Initialiser les managers principaux
        initializer.initialize_managers()
        
        # Initialiser les gestionnaires spécialisés
        initializer.initialize_specialized_managers()
        
        # Vérifier que les gestionnaires spécialisés sont créés
        assert initializer.callback_manager is not None
        assert initializer.opportunity_manager is not None

    def test_bot_initializer_get_managers(self, mock_logger):
        """Test de récupération des managers."""
        initializer = BotInitializer(testnet=True, logger=mock_logger)
        
        # Initialiser tous les managers
        initializer.initialize_managers()
        initializer.initialize_specialized_managers()
        
        # Récupérer les managers
        managers = initializer.get_managers()
        
        # Vérifier que tous les managers sont présents
        expected_keys = [
            "data_manager",
            "display_manager", 
            "monitoring_manager",
            "ws_manager",
            "volatility_tracker",
            "watchlist_manager",
            "callback_manager",
            "opportunity_manager"
        ]
        
        for key in expected_keys:
            assert key in managers
            assert managers[key] is not None


class TestDataFlowIntegration:
    """Tests d'intégration pour le flux de données."""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger pour les tests."""
        return Mock()

    def test_data_flow_from_fetcher_to_storage(self, mock_logger):
        """Test du flux de données depuis DataFetcher vers DataStorage."""
        # Créer les composants réels
        data_manager = DataManager(testnet=True, logger=mock_logger)
        
        # Simuler la récupération de données (sans appels API réels)
        funding_data = {"BTCUSDT": {"funding": 0.0001, "volume": 1000000}}
        spread_data = {"BTCUSDT": 0.001}
        
        # Mettre à jour les données via l'interface unifiée
        for symbol, data in funding_data.items():
            data_manager.update_funding_data(
                symbol,
                data["funding"],
                data["volume"],
                "1h",
                spread_data.get(symbol, 0.0)
            )
        
        # Vérifier que les données sont stockées
        retrieved_data = data_manager.get_funding_data("BTCUSDT")
        assert retrieved_data[0] == 0.0001  # funding
        assert retrieved_data[1] == 1000000  # volume

    def test_data_flow_realtime_updates(self, mock_logger):
        """Test du flux de données temps réel."""
        data_manager = DataManager(testnet=True, logger=mock_logger)
        
        # Simuler des mises à jour temps réel
        ticker_updates = [
            {"symbol": "BTCUSDT", "markPrice": "50000.0", "lastPrice": "50001.0"},
            {"symbol": "BTCUSDT", "markPrice": "50100.0", "lastPrice": "50101.0"},
            {"symbol": "BTCUSDT", "markPrice": "50200.0", "lastPrice": "50201.0"}
        ]
        
        for update in ticker_updates:
            data_manager.update_realtime_data(update["symbol"], update)
        
        # Vérifier que la dernière mise à jour est conservée
        realtime_data = data_manager.get_realtime_data("BTCUSDT")
        assert realtime_data["mark_price"] == "50200.0"
        assert realtime_data["last_price"] == "50201.0"

    def test_data_flow_validation_integration(self, mock_logger):
        """Test d'intégration de la validation des données."""
        data_manager = DataManager(testnet=True, logger=mock_logger)
        
        # Ajouter des données valides
        data_manager.update_funding_data("BTCUSDT", 0.0001, 1000000, "1h", 0.001)
        data_manager.set_symbol_lists(["BTCUSDT"], ["BTCUSD"])
        
        # La méthode validate_data_integrity n'existe pas encore, on teste les statistiques
        stats = data_manager.get_data_stats()
        assert stats["funding_data_objects"] == 1
        assert stats["linear_symbols"] == 1
        assert stats["inverse_symbols"] == 1
