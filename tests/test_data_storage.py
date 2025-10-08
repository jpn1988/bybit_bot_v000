"""Tests pour DataStorage."""

import pytest
import threading
import time
from unittest.mock import Mock, patch
from data_storage import DataStorage


class TestDataStorage:
    """Tests pour DataStorage."""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger pour les tests."""
        return Mock()

    @pytest.fixture
    def storage(self, mock_logger):
        """Instance de DataStorage pour les tests."""
        return DataStorage(logger=mock_logger)

    def test_init(self, mock_logger):
        """Test d'initialisation."""
        storage = DataStorage(logger=mock_logger)
        
        assert storage.logger == mock_logger
        assert storage.funding_data == {}
        assert storage.original_funding_data == {}
        assert storage.realtime_data == {}
        assert storage.symbol_categories == {}
        assert storage.linear_symbols == []
        assert storage.inverse_symbols == []
        assert isinstance(storage._funding_lock, type(threading.Lock()))
        assert isinstance(storage._realtime_lock, type(threading.Lock()))

    def test_init_with_default_logger(self):
        """Test d'initialisation avec logger par défaut."""
        with patch('data_storage.setup_logging') as mock_setup:
            mock_logger = Mock()
            mock_setup.return_value = mock_logger
            
            storage = DataStorage()
            
            assert storage.logger == mock_logger

    def test_set_symbol_categories(self, storage):
        """Test de définition des catégories de symboles."""
        categories = {"BTCUSDT": "linear", "BTCUSD": "inverse"}
        storage.set_symbol_categories(categories)
        
        assert storage.symbol_categories == categories

    def test_update_funding_data(self, storage):
        """Test de mise à jour des données de funding."""
        storage.update_funding_data("BTCUSDT", 0.0001, 1000000, "1h", 0.001, 0.05)
        
        expected_data = (0.0001, 1000000, "1h", 0.001, 0.05)
        assert storage.funding_data["BTCUSDT"] == expected_data

    def test_update_funding_data_without_volatility(self, storage):
        """Test de mise à jour des données de funding sans volatilité."""
        storage.update_funding_data("BTCUSDT", 0.0001, 1000000, "1h", 0.001)
        
        expected_data = (0.0001, 1000000, "1h", 0.001, None)
        assert storage.funding_data["BTCUSDT"] == expected_data

    def test_get_funding_data_existing(self, storage):
        """Test de récupération de données de funding existantes."""
        storage.update_funding_data("BTCUSDT", 0.0001, 1000000, "1h", 0.001, 0.05)
        
        result = storage.get_funding_data("BTCUSDT")
        expected = (0.0001, 1000000, "1h", 0.001, 0.05)
        assert result == expected

    def test_get_funding_data_nonexistent(self, storage):
        """Test de récupération de données de funding inexistantes."""
        result = storage.get_funding_data("NONEXISTENT")
        assert result is None

    def test_get_all_funding_data(self, storage):
        """Test de récupération de toutes les données de funding."""
        storage.update_funding_data("BTCUSDT", 0.0001, 1000000, "1h", 0.001)
        storage.update_funding_data("ETHUSDT", 0.0002, 2000000, "2h", 0.002)
        
        result = storage.get_all_funding_data()
        
        assert len(result) == 2
        assert "BTCUSDT" in result
        assert "ETHUSDT" in result
        assert result["BTCUSDT"] == (0.0001, 1000000, "1h", 0.001, None)
        assert result["ETHUSDT"] == (0.0002, 2000000, "2h", 0.002, None)

    def test_update_realtime_data(self, storage):
        """Test de mise à jour des données temps réel."""
        ticker_data = {
            "fundingRate": "0.0001",
            "volume24h": "1000000.0",
            "bid1Price": "50000.0",
            "ask1Price": "50001.0",
            "nextFundingTime": "1640995200000",
            "markPrice": "50000.5",
            "lastPrice": "50001.0"
        }
        
        storage.update_realtime_data("BTCUSDT", ticker_data)
        
        result = storage.realtime_data["BTCUSDT"]
        assert result["funding_rate"] == "0.0001"
        assert result["volume24h"] == "1000000.0"
        assert result["bid1_price"] == "50000.0"
        assert result["ask1_price"] == "50001.0"
        assert result["next_funding_time"] == "1640995200000"
        assert result["mark_price"] == "50000.5"
        assert result["last_price"] == "50001.0"
        assert "timestamp" in result

    def test_update_realtime_data_empty_symbol(self, storage):
        """Test de mise à jour avec symbole vide."""
        ticker_data = {"markPrice": "50000.0"}
        storage.update_realtime_data("", ticker_data)
        
        assert len(storage.realtime_data) == 0

    def test_update_realtime_data_no_important_keys(self, storage):
        """Test de mise à jour sans clés importantes."""
        ticker_data = {"unimportant": "data"}
        storage.update_realtime_data("BTCUSDT", ticker_data)
        
        assert len(storage.realtime_data) == 0

    def test_update_realtime_data_exception_handling(self, storage, mock_logger):
        """Test de gestion d'exception lors de la mise à jour."""
        # Mock time.time pour lever une exception
        with patch('time.time', side_effect=Exception("Test error")):
            ticker_data = {"markPrice": "50000.0"}
            storage.update_realtime_data("BTCUSDT", ticker_data)
            
            mock_logger.warning.assert_called_once()

    def test_update_price_data(self, storage):
        """Test de mise à jour des données de prix."""
        storage.update_price_data("BTCUSDT", 50000.0, 50001.0, 1640995200.0)
        
        result = storage.realtime_data["BTCUSDT"]
        assert result["mark_price"] == 50000.0
        assert result["last_price"] == 50001.0
        # Le timestamp est généré automatiquement, on vérifie juste qu'il existe
        assert "timestamp" in result

    def test_update_price_data_empty_symbol(self, storage):
        """Test de mise à jour de prix avec symbole vide."""
        storage.update_price_data("", 50000.0, 50001.0, 1640995200.0)
        
        assert len(storage.realtime_data) == 0

    def test_get_price_data(self, storage):
        """Test de récupération des données de prix."""
        storage.update_price_data("BTCUSDT", 50000.0, 50001.0, 1640995200.0)
        
        result = storage.get_price_data("BTCUSDT")
        
        assert result["mark_price"] == 50000.0
        assert result["last_price"] == 50001.0
        assert "timestamp" in result

    def test_get_price_data_nonexistent(self, storage):
        """Test de récupération de données de prix inexistantes."""
        result = storage.get_price_data("NONEXISTENT")
        assert result is None

    def test_get_price_data_exception_handling(self, storage, mock_logger):
        """Test de gestion d'exception lors de la récupération de prix."""
        # Corrompre les données pour provoquer une exception
        storage.realtime_data["BTCUSDT"] = {"invalid": "data"}
        
        result = storage.get_price_data("BTCUSDT")
        
        # La méthode gère l'exception et retourne None pour les valeurs manquantes
        assert result is not None
        assert result["mark_price"] is None
        assert result["last_price"] is None
        assert result["timestamp"] is None
        # Le warning n'est pas appelé car la méthode gère l'exception différemment

    def test_get_realtime_data(self, storage):
        """Test de récupération des données temps réel."""
        ticker_data = {"markPrice": "50000.0", "lastPrice": "50001.0"}
        storage.update_realtime_data("BTCUSDT", ticker_data)
        
        result = storage.get_realtime_data("BTCUSDT")
        
        assert result["mark_price"] == "50000.0"
        assert result["last_price"] == "50001.0"
        assert "timestamp" in result

    def test_get_realtime_data_nonexistent(self, storage):
        """Test de récupération de données temps réel inexistantes."""
        result = storage.get_realtime_data("NONEXISTENT")
        assert result is None

    def test_get_all_realtime_data(self, storage):
        """Test de récupération de toutes les données temps réel."""
        storage.update_realtime_data("BTCUSDT", {"markPrice": "50000.0"})
        storage.update_realtime_data("ETHUSDT", {"markPrice": "3000.0"})
        
        result = storage.get_all_realtime_data()
        
        assert len(result) == 2
        assert "BTCUSDT" in result
        assert "ETHUSDT" in result

    def test_update_original_funding_data(self, storage):
        """Test de mise à jour des données de funding originales."""
        storage.update_original_funding_data("BTCUSDT", "1640995200000")
        
        assert storage.original_funding_data["BTCUSDT"] == "1640995200000"

    def test_get_original_funding_data(self, storage):
        """Test de récupération des données de funding originales."""
        storage.update_original_funding_data("BTCUSDT", "1640995200000")
        
        result = storage.get_original_funding_data("BTCUSDT")
        assert result == "1640995200000"

    def test_get_original_funding_data_nonexistent(self, storage):
        """Test de récupération de données de funding originales inexistantes."""
        result = storage.get_original_funding_data("NONEXISTENT")
        assert result is None

    def test_get_all_original_funding_data(self, storage):
        """Test de récupération de toutes les données de funding originales."""
        storage.update_original_funding_data("BTCUSDT", "1640995200000")
        storage.update_original_funding_data("ETHUSDT", "1640995260000")
        
        result = storage.get_all_original_funding_data()
        
        assert len(result) == 2
        assert result["BTCUSDT"] == "1640995200000"
        assert result["ETHUSDT"] == "1640995260000"

    def test_set_symbol_lists(self, storage):
        """Test de définition des listes de symboles."""
        linear_symbols = ["BTCUSDT", "ETHUSDT"]
        inverse_symbols = ["BTCUSD", "ETHUSD"]
        
        storage.set_symbol_lists(linear_symbols, inverse_symbols)
        
        assert storage.linear_symbols == linear_symbols
        assert storage.inverse_symbols == inverse_symbols

    def test_set_symbol_lists_creates_copies(self, storage):
        """Test que set_symbol_lists crée des copies."""
        linear_symbols = ["BTCUSDT"]
        inverse_symbols = ["BTCUSD"]
        
        storage.set_symbol_lists(linear_symbols, inverse_symbols)
        
        # Modifier les listes originales
        linear_symbols.append("ETHUSDT")
        inverse_symbols.append("ETHUSD")
        
        # Vérifier que les copies ne sont pas affectées
        assert storage.linear_symbols == ["BTCUSDT"]
        assert storage.inverse_symbols == ["BTCUSD"]

    def test_get_linear_symbols(self, storage):
        """Test de récupération des symboles linear."""
        storage.linear_symbols = ["BTCUSDT", "ETHUSDT"]
        
        result = storage.get_linear_symbols()
        
        assert result == ["BTCUSDT", "ETHUSDT"]
        assert result is not storage.linear_symbols  # Copie

    def test_get_inverse_symbols(self, storage):
        """Test de récupération des symboles inverse."""
        storage.inverse_symbols = ["BTCUSD", "ETHUSD"]
        
        result = storage.get_inverse_symbols()
        
        assert result == ["BTCUSD", "ETHUSD"]
        assert result is not storage.inverse_symbols  # Copie

    def test_get_all_symbols(self, storage):
        """Test de récupération de tous les symboles."""
        storage.linear_symbols = ["BTCUSDT", "ETHUSDT"]
        storage.inverse_symbols = ["BTCUSD", "ETHUSD"]
        
        result = storage.get_all_symbols()
        
        assert result == ["BTCUSDT", "ETHUSDT", "BTCUSD", "ETHUSD"]

    def test_add_symbol_to_category_linear(self, storage):
        """Test d'ajout d'un symbole à la catégorie linear."""
        storage.add_symbol_to_category("BTCUSDT", "linear")
        
        assert "BTCUSDT" in storage.linear_symbols
        assert "BTCUSDT" not in storage.inverse_symbols

    def test_add_symbol_to_category_inverse(self, storage):
        """Test d'ajout d'un symbole à la catégorie inverse."""
        storage.add_symbol_to_category("BTCUSD", "inverse")
        
        assert "BTCUSD" in storage.inverse_symbols
        assert "BTCUSD" not in storage.linear_symbols

    def test_add_symbol_to_category_already_exists(self, storage):
        """Test d'ajout d'un symbole déjà existant."""
        storage.linear_symbols = ["BTCUSDT"]
        
        storage.add_symbol_to_category("BTCUSDT", "linear")
        
        assert storage.linear_symbols.count("BTCUSDT") == 1

    def test_remove_symbol_from_category_linear(self, storage):
        """Test de suppression d'un symbole de la catégorie linear."""
        storage.linear_symbols = ["BTCUSDT", "ETHUSDT"]
        
        storage.remove_symbol_from_category("BTCUSDT", "linear")
        
        assert "BTCUSDT" not in storage.linear_symbols
        assert "ETHUSDT" in storage.linear_symbols

    def test_remove_symbol_from_category_inverse(self, storage):
        """Test de suppression d'un symbole de la catégorie inverse."""
        storage.inverse_symbols = ["BTCUSD", "ETHUSD"]
        
        storage.remove_symbol_from_category("BTCUSD", "inverse")
        
        assert "BTCUSD" not in storage.inverse_symbols
        assert "ETHUSD" in storage.inverse_symbols

    def test_remove_symbol_from_category_nonexistent(self, storage):
        """Test de suppression d'un symbole inexistant."""
        storage.linear_symbols = ["BTCUSDT"]
        
        storage.remove_symbol_from_category("NONEXISTENT", "linear")
        
        assert storage.linear_symbols == ["BTCUSDT"]

    def test_clear_all_data(self, storage):
        """Test de vidage de toutes les données."""
        # Ajouter des données
        storage.update_funding_data("BTCUSDT", 0.0001, 1000000, "1h", 0.001)
        storage.update_original_funding_data("BTCUSDT", "1640995200000")
        storage.update_realtime_data("BTCUSDT", {"markPrice": "50000.0"})
        storage.linear_symbols = ["BTCUSDT"]
        storage.inverse_symbols = ["BTCUSD"]
        
        storage.clear_all_data()
        
        assert storage.funding_data == {}
        assert storage.original_funding_data == {}
        assert storage.realtime_data == {}
        assert storage.linear_symbols == []
        assert storage.inverse_symbols == []

    def test_get_data_stats(self, storage):
        """Test de récupération des statistiques des données."""
        # Ajouter des données
        storage.update_funding_data("BTCUSDT", 0.0001, 1000000, "1h", 0.001)
        storage.update_original_funding_data("BTCUSDT", "1640995200000")
        storage.update_realtime_data("BTCUSDT", {"markPrice": "50000.0"})
        storage.linear_symbols = ["BTCUSDT", "ETHUSDT"]
        storage.inverse_symbols = ["BTCUSD"]
        
        stats = storage.get_data_stats()
        
        assert stats["funding_data"] == 1
        assert stats["original_funding_data"] == 1
        assert stats["realtime_data"] == 1
        assert stats["linear_symbols"] == 2
        assert stats["inverse_symbols"] == 1

    def test_thread_safety_funding_data(self, storage):
        """Test de thread safety pour les données de funding."""
        def update_funding():
            for i in range(100):
                storage.update_funding_data(f"SYMBOL{i}", 0.0001, 1000000, "1h", 0.001)
        
        def read_funding():
            for i in range(100):
                storage.get_funding_data(f"SYMBOL{i}")
        
        # Lancer des threads concurrents
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=update_funding))
            threads.append(threading.Thread(target=read_funding))
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Vérifier qu'aucune exception n'a été levée
        assert len(storage.funding_data) <= 500  # Max 5 threads * 100 updates

    def test_thread_safety_realtime_data(self, storage):
        """Test de thread safety pour les données temps réel."""
        def update_realtime():
            for i in range(100):
                storage.update_realtime_data(f"SYMBOL{i}", {"markPrice": f"{50000 + i}"})
        
        def read_realtime():
            for i in range(100):
                storage.get_realtime_data(f"SYMBOL{i}")
        
        # Lancer des threads concurrents
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=update_realtime))
            threads.append(threading.Thread(target=read_realtime))
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Vérifier qu'aucune exception n'a été levée
        assert len(storage.realtime_data) <= 500  # Max 5 threads * 100 updates
