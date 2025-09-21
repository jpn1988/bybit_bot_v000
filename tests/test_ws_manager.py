#!/usr/bin/env python3
"""Tests pour WebSocketManager."""

import pytest
import unittest.mock as mock
from src.ws_manager import WebSocketManager


class TestWebSocketManager:
    """Tests pour la classe WebSocketManager."""
    
    def test_init(self):
        """Test de l'initialisation du WebSocketManager."""
        ws_manager = WebSocketManager(testnet=True)
        
        assert ws_manager.testnet is True
        assert ws_manager.running is False
        assert ws_manager.linear_symbols == []
        assert ws_manager.inverse_symbols == []
        assert ws_manager._ws_conns == []
        assert ws_manager._ws_threads == []
        assert ws_manager._ticker_callback is None
    
    def test_set_ticker_callback(self):
        """Test de la définition du callback ticker."""
        ws_manager = WebSocketManager(testnet=True)
        
        def dummy_callback(ticker_data):
            pass
        
        ws_manager.set_ticker_callback(dummy_callback)
        assert ws_manager._ticker_callback == dummy_callback
    
    def test_get_connected_symbols_empty(self):
        """Test de récupération des symboles connectés (vide)."""
        ws_manager = WebSocketManager(testnet=True)
        
        symbols = ws_manager.get_connected_symbols()
        expected = {"linear": [], "inverse": []}
        assert symbols == expected
    
    def test_get_connected_symbols_with_data(self):
        """Test de récupération des symboles connectés (avec données)."""
        ws_manager = WebSocketManager(testnet=True)
        ws_manager.linear_symbols = ["BTCUSDT", "ETHUSDT"]
        ws_manager.inverse_symbols = ["BTCUSD"]
        
        symbols = ws_manager.get_connected_symbols()
        expected = {"linear": ["BTCUSDT", "ETHUSDT"], "inverse": ["BTCUSD"]}
        assert symbols == expected
    
    def test_is_running_initial_state(self):
        """Test de l'état initial running."""
        ws_manager = WebSocketManager(testnet=True)
        assert ws_manager.is_running() is False
    
    @mock.patch('src.ws_manager.PublicWSClient')
    def test_start_connections_no_symbols_warning(self, mock_ws_client):
        """Test de démarrage sans symboles (doit afficher un warning)."""
        mock_logger = mock.MagicMock()
        ws_manager = WebSocketManager(testnet=True, logger=mock_logger)
        
        ws_manager.start_connections([], [])
        
        # Vérifier que le warning est affiché
        mock_logger.warning.assert_called_once_with("⚠️ Aucun symbole fourni pour les connexions WebSocket")
    
    def test_handle_ticker_with_valid_data(self):
        """Test du gestionnaire de ticker avec des données valides."""
        callback_called = False
        received_data = None
        
        def test_callback(ticker_data):
            nonlocal callback_called, received_data
            callback_called = True
            received_data = ticker_data
        
        ws_manager = WebSocketManager(testnet=True)
        ws_manager.set_ticker_callback(test_callback)
        
        ticker_data = {
            "symbol": "BTCUSDT",
            "markPrice": "50000.0",
            "lastPrice": "50001.0",
            "fundingRate": "0.0001"
        }
        
        # Appeler directement le gestionnaire (simulation)
        ws_manager._handle_ticker(ticker_data)
        
        # Vérifier que le callback a été appelé
        assert callback_called is True
        assert received_data == ticker_data
    
    def test_handle_ticker_without_callback(self):
        """Test du gestionnaire de ticker sans callback défini."""
        ws_manager = WebSocketManager(testnet=True)
        
        ticker_data = {
            "symbol": "BTCUSDT",
            "markPrice": "50000.0",
            "lastPrice": "50001.0"
        }
        
        # Ne doit pas lever d'exception
        try:
            ws_manager._handle_ticker(ticker_data)
        except Exception as e:
            pytest.fail(f"_handle_ticker a levé une exception inattendue: {e}")
    
    def test_handle_ticker_with_invalid_data(self):
        """Test du gestionnaire de ticker avec des données invalides."""
        mock_logger = mock.MagicMock()
        ws_manager = WebSocketManager(testnet=True, logger=mock_logger)
        
        # Données invalides (pas de symbol)
        ticker_data = {
            "markPrice": "invalid_price",
            "lastPrice": None
        }
        
        # Ne doit pas lever d'exception mais peut logger un warning
        try:
            ws_manager._handle_ticker(ticker_data)
        except Exception as e:
            pytest.fail(f"_handle_ticker a levé une exception inattendue: {e}")
    
    def test_stop_when_not_running(self):
        """Test d'arrêt quand pas en cours d'exécution."""
        mock_logger = mock.MagicMock()
        ws_manager = WebSocketManager(testnet=True, logger=mock_logger)
        
        # Ne doit pas lever d'exception
        try:
            ws_manager.stop()
        except Exception as e:
            pytest.fail(f"stop() a levé une exception inattendue: {e}")
        
        # Vérifier que l'état est mis à jour
        assert ws_manager.running is False
