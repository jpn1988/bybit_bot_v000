#!/usr/bin/env python3
"""
Tests pour les composants de surveillance refactorisés.
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from market_scanner import MarketScanner
from opportunity_detector import OpportunityDetector
from candidate_monitor import CandidateMonitor
from unified_monitoring_manager import UnifiedMonitoringManager


class TestMarketScanner:
    """Tests pour MarketScanner"""

    def test_init_sets_parameters(self):
        """Test que l'initialisation configure correctement les paramètres"""
        scanner = MarketScanner(scan_interval=120)
        assert scanner._scan_interval == 120
        assert scanner._scan_running is False
        assert scanner._scan_task is None

    def test_set_scan_callback(self):
        """Test que le callback de scan peut être défini"""
        scanner = MarketScanner()
        callback = Mock()
        scanner.set_scan_callback(callback)
        assert scanner._scan_callback == callback

    @pytest.mark.asyncio
    async def test_start_scanning(self):
        """Test le démarrage du scan"""
        scanner = MarketScanner(scan_interval=120)
        scanner.set_scan_callback(AsyncMock())
        
        await scanner.start_scanning("http://test", {"test": "data"})
        assert scanner._scan_running is True
        assert scanner._scan_task is not None
        
        await scanner.stop_scanning()

    @pytest.mark.asyncio
    async def test_stop_scanning(self):
        """Test l'arrêt du scan"""
        scanner = MarketScanner(scan_interval=120)
        scanner.set_scan_callback(AsyncMock())
        
        await scanner.start_scanning("http://test", {"test": "data"})
        await scanner.stop_scanning()
        
        assert scanner._scan_running is False

    def test_should_perform_scan_true(self):
        """Test que should_perform_scan retourne True après l'intervalle"""
        import time
        scanner = MarketScanner(scan_interval=60)
        scanner._scan_running = True
        scanner._last_scan_time = time.time() - 70  # 70 secondes ago
        
        assert scanner._should_perform_scan(time.time()) is True

    def test_should_perform_scan_false(self):
        """Test que should_perform_scan retourne False avant l'intervalle"""
        import time
        scanner = MarketScanner(scan_interval=60)
        scanner._scan_running = True
        scanner._last_scan_time = time.time() - 30  # 30 secondes ago
        
        assert scanner._should_perform_scan(time.time()) is False

    def test_is_running_returns_correct_state(self):
        """Test que is_running retourne le bon état"""
        scanner = MarketScanner()
        assert scanner.is_running() is False
        
        scanner._scan_running = True
        assert scanner.is_running() is True


class TestOpportunityDetector:
    """Tests pour OpportunityDetector"""

    def test_init_sets_parameters(self):
        """Test que l'initialisation configure correctement les paramètres"""
        data_manager = Mock()
        watchlist_manager = Mock()
        volatility_tracker = Mock()
        
        detector = OpportunityDetector(
            data_manager=data_manager,
            watchlist_manager=watchlist_manager,
            volatility_tracker=volatility_tracker,
            testnet=True
        )
        
        assert detector.data_manager == data_manager
        assert detector.watchlist_manager == watchlist_manager
        assert detector.volatility_tracker == volatility_tracker
        assert detector.testnet is True

    def test_set_ws_manager(self):
        """Test que le ws_manager peut être défini"""
        detector = OpportunityDetector(Mock(), Mock(), Mock())
        ws_manager = Mock()
        detector.set_ws_manager(ws_manager)
        assert detector.ws_manager == ws_manager

    def test_set_on_new_opportunity_callback(self):
        """Test que le callback peut être défini"""
        detector = OpportunityDetector(Mock(), Mock(), Mock())
        callback = Mock()
        detector.set_on_new_opportunity_callback(callback)
        assert detector._on_new_opportunity_callback == callback

    def test_scan_for_opportunities_no_websocket(self):
        """Test le scan d'opportunités quand WebSocket n'est pas actif"""
        data_manager = Mock()
        watchlist_manager = Mock()
        watchlist_manager.build_watchlist.return_value = (["BTCUSDT"], [], {})
        volatility_tracker = Mock()
        
        detector = OpportunityDetector(
            data_manager=data_manager,
            watchlist_manager=watchlist_manager,
            volatility_tracker=volatility_tracker,
            testnet=True
        )
        
        with patch('opportunity_detector.BybitPublicClient'):
            result = detector.scan_for_opportunities("http://test", {"test": "data"})
            assert result is not None
            assert "linear" in result

    def test_integrate_opportunities(self):
        """Test l'intégration des opportunités"""
        data_manager = Mock()
        data_manager.get_linear_symbols.return_value = []
        data_manager.get_inverse_symbols.return_value = []
        
        detector = OpportunityDetector(
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
        
        detector.integrate_opportunities(opportunities)
        data_manager.set_symbol_lists.assert_called_once()


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


class TestUnifiedMonitoringManagerRefactored:
    """Tests pour UnifiedMonitoringManager refactorisé"""

    def test_init_sets_parameters(self):
        """Test que l'initialisation configure correctement les paramètres"""
        data_manager = Mock()
        manager = UnifiedMonitoringManager(
            data_manager=data_manager,
            testnet=True
        )
        
        assert manager.data_manager == data_manager
        assert manager.testnet is True
        assert manager._running is False

    def test_set_watchlist_manager(self):
        """Test que le watchlist_manager peut être défini"""
        manager = UnifiedMonitoringManager(Mock())
        watchlist_manager = Mock()
        manager.set_watchlist_manager(watchlist_manager)
        assert manager.watchlist_manager == watchlist_manager

    def test_set_volatility_tracker(self):
        """Test que le volatility_tracker peut être défini"""
        manager = UnifiedMonitoringManager(Mock())
        volatility_tracker = Mock()
        manager.set_volatility_tracker(volatility_tracker)
        assert manager.volatility_tracker == volatility_tracker

    def test_set_ws_manager(self):
        """Test que le ws_manager peut être défini"""
        manager = UnifiedMonitoringManager(Mock())
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
        
        manager = UnifiedMonitoringManager(
            data_manager=data_manager,
            testnet=True
        )
        manager.set_watchlist_manager(watchlist_manager)
        manager.set_volatility_tracker(volatility_tracker)
        
        with patch('opportunity_detector.BybitPublicClient'):
            await manager.start_continuous_monitoring("http://test", {"test": "data"})
            assert manager._running is True
            
            await manager.stop_continuous_monitoring()

    @pytest.mark.asyncio
    async def test_stop_continuous_monitoring(self):
        """Test l'arrêt de la surveillance continue"""
        manager = UnifiedMonitoringManager(Mock())
        manager._running = True
        
        # Créer des composants mockés
        manager.market_scanner = Mock()
        manager.market_scanner.stop_scanning = AsyncMock()
        manager.candidate_monitor = Mock()
        manager.candidate_monitor.stop_monitoring = Mock()
        
        await manager.stop_continuous_monitoring()
        
        assert manager._running is False
        manager.market_scanner.stop_scanning.assert_called_once()
        manager.candidate_monitor.stop_monitoring.assert_called_once()

    def test_is_running_false_when_not_started(self):
        """Test que is_running retourne False quand pas démarré"""
        manager = UnifiedMonitoringManager(Mock())
        assert manager.is_running() is False

    def test_candidate_symbols_property(self):
        """Test la propriété candidate_symbols"""
        manager = UnifiedMonitoringManager(Mock())
        
        # Sans candidat monitor
        assert manager.candidate_symbols == []
        
        # Avec candidat monitor
        mock_monitor = Mock()
        mock_monitor.get_candidate_symbols.return_value = ["BTCUSDT"]
        manager.candidate_monitor = mock_monitor
        
        assert manager.candidate_symbols == ["BTCUSDT"]

