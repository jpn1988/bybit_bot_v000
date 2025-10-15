#!/usr/bin/env python3
"""
Tests pour les composants de surveillance refactorisés.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from opportunity_manager import OpportunityManager
from candidate_monitor import CandidateMonitor
from monitoring_manager import MonitoringManager


class TestOpportunityManager:
    """Tests pour OpportunityManager"""

    def test_init_sets_parameters(self):
        """Test que l'initialisation configure correctement les paramètres"""
        data_manager = Mock()
        watchlist_manager = Mock()
        volatility_tracker = Mock()
        
        manager = OpportunityManager(
            data_manager=data_manager,
            watchlist_manager=watchlist_manager,
            volatility_tracker=volatility_tracker,
            testnet=True
        )
        
        assert manager.data_manager == data_manager
        assert manager.watchlist_manager == watchlist_manager
        assert manager.volatility_tracker == volatility_tracker
        assert manager.testnet is True

    def test_set_ws_manager(self):
        """Test que le ws_manager peut être défini"""
        manager = OpportunityManager(Mock(), Mock(), Mock())
        ws_manager = Mock()
        manager.set_ws_manager(ws_manager)
        assert manager.ws_manager == ws_manager

    def test_set_on_new_opportunity_callback(self):
        """Test que le callback peut être défini"""
        manager = OpportunityManager(Mock(), Mock(), Mock())
        callback = Mock()
        manager.set_on_new_opportunity_callback(callback)
        assert manager._on_new_opportunity_callback == callback

    def test_scan_for_opportunities_no_websocket(self):
        """Test le scan d'opportunités quand WebSocket n'est pas actif"""
        data_manager = Mock()
        watchlist_manager = Mock()
        watchlist_manager.build_watchlist.return_value = (["BTCUSDT"], [], {})
        volatility_tracker = Mock()
        
        manager = OpportunityManager(
            data_manager=data_manager,
            watchlist_manager=watchlist_manager,
            volatility_tracker=volatility_tracker,
            testnet=True
        )
        
        with patch('opportunity_manager.BybitPublicClient'):
            result = manager.scan_for_opportunities("http://test", {"test": "data"})
            assert result is not None
            assert "linear" in result

    def test_integrate_opportunities(self):
        """Test l'intégration des opportunités"""
        data_manager = Mock()
        data_manager.storage = Mock()
        data_manager.storage.get_linear_symbols.return_value = []
        data_manager.storage.get_inverse_symbols.return_value = []
        data_manager.storage.set_symbol_lists = Mock()
        data_manager.storage.set_funding_data_object = Mock()
        
        manager = OpportunityManager(
            data_manager=data_manager,
            watchlist_manager=Mock(),
            volatility_tracker=Mock(),
            testnet=True
        )
        
        opportunities = {
            "linear": ["BTCUSDT"],
            "inverse": [],
            "funding_data": {}
        }
        
        manager.integrate_opportunities(opportunities)
        data_manager.storage.set_symbol_lists.assert_called_once()


class TestCandidateMonitor:
    """Tests pour CandidateMonitor"""

    def test_init_sets_parameters(self):
        """Test que l'initialisation configure correctement les paramètres"""
        data_manager = Mock()
        watchlist_manager = Mock()
        
        monitor = CandidateMonitor(
            data_manager=data_manager,
            watchlist_manager=watchlist_manager,
            testnet=True
        )
        
        assert monitor.data_manager == data_manager
        assert monitor.watchlist_manager == watchlist_manager
        assert monitor.testnet is True
        assert monitor._candidate_running is False

    def test_set_on_candidate_ticker_callback(self):
        """Test que le callback peut être défini"""
        monitor = CandidateMonitor(Mock(), Mock())
        callback = Mock()
        monitor.set_on_candidate_ticker_callback(callback)
        assert monitor._on_candidate_ticker_callback == callback

    def test_setup_monitoring_no_candidates(self):
        """Test la configuration quand il n'y a pas de candidats"""
        watchlist_manager = Mock()
        watchlist_manager.find_candidate_symbols.return_value = []
        
        monitor = CandidateMonitor(
            data_manager=Mock(),
            watchlist_manager=watchlist_manager,
            testnet=True
        )
        
        monitor.setup_monitoring("http://test", {"test": "data"})
        assert monitor.candidate_symbols == []

    def test_is_running_returns_correct_state(self):
        """Test que is_running retourne le bon état"""
        monitor = CandidateMonitor(Mock(), Mock())
        assert monitor.is_running() is False
        
        monitor._candidate_running = True
        assert monitor.is_running() is True

    def test_get_candidate_symbols(self):
        """Test que get_candidate_symbols retourne les bons symboles"""
        monitor = CandidateMonitor(Mock(), Mock())
        monitor.candidate_symbols = ["BTCUSDT", "ETHUSDT"]
        
        result = monitor.get_candidate_symbols()
        assert result == ["BTCUSDT", "ETHUSDT"]


class TestMonitoringManagerRefactored:
    """Tests pour MonitoringManager refactorisé"""

    def test_init_sets_parameters(self):
        """Test que l'initialisation configure correctement les paramètres"""
        data_manager = Mock()
        manager = MonitoringManager(
            data_manager=data_manager,
            testnet=True
        )
        
        assert manager.data_manager == data_manager
        assert manager.testnet is True
        assert manager._running is False

    def test_set_watchlist_manager(self):
        """Test que le watchlist_manager peut être défini"""
        manager = MonitoringManager(Mock())
        watchlist_manager = Mock()
        manager.set_watchlist_manager(watchlist_manager)
        assert manager.watchlist_manager == watchlist_manager

    def test_set_volatility_tracker(self):
        """Test que le volatility_tracker peut être défini"""
        manager = MonitoringManager(Mock())
        volatility_tracker = Mock()
        manager.set_volatility_tracker(volatility_tracker)
        assert manager.volatility_tracker == volatility_tracker

    def test_set_ws_manager(self):
        """Test que le ws_manager peut être défini"""
        manager = MonitoringManager(Mock())
        ws_manager = Mock()
        manager.set_ws_manager(ws_manager)
        assert manager.ws_manager == ws_manager

    @pytest.mark.asyncio
    async def test_start_continuous_monitoring_success(self):
        """Test le démarrage de la surveillance continue"""
        data_manager = Mock()
        watchlist_manager = Mock()
        watchlist_manager.find_candidate_symbols.return_value = []
        volatility_tracker = Mock()
        
        manager = MonitoringManager(
            data_manager=data_manager,
            testnet=True
        )
        manager.set_watchlist_manager(watchlist_manager)
        manager.set_volatility_tracker(volatility_tracker)
        
        with patch('opportunity_manager.BybitPublicClient'):
            await manager.start_continuous_monitoring("http://test", {"linear": [], "inverse": []})
            assert manager._running is True
            
            await manager.stop_continuous_monitoring()

    @pytest.mark.asyncio
    async def test_stop_continuous_monitoring(self):
        """Test l'arrêt de la surveillance continue"""
        manager = MonitoringManager(Mock())
        manager._running = True
        manager._scan_running = True  # Simuler le scan actif
        
        # Créer des composants mockés
        manager.candidate_monitor = Mock()
        manager.candidate_monitor.stop_monitoring = Mock()
        
        await manager.stop_continuous_monitoring()
        
        assert manager._running is False
        manager.candidate_monitor.stop_monitoring.assert_called_once()

    def test_is_running_false_when_not_started(self):
        """Test que is_running retourne False quand pas démarré"""
        manager = MonitoringManager(Mock())
        assert manager.is_running() is False

    def test_candidate_symbols_property(self):
        """Test la propriété candidate_symbols"""
        manager = MonitoringManager(Mock())
        
        # Sans candidat monitor
        assert manager.candidate_symbols == []
        
        # Avec candidat monitor
        mock_monitor = Mock()
        mock_monitor.get_candidate_symbols.return_value = ["BTCUSDT"]
        manager.candidate_monitor = mock_monitor
        
        assert manager.candidate_symbols == ["BTCUSDT"]

