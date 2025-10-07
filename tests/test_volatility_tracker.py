#!/usr/bin/env python3
"""
Tests pour VolatilityTracker (volatility_tracker.py)

Couvre:
- Initialisation et configuration
- Gestion du cache de volatilité
- Démarrage/arrêt des tâches de rafraîchissement
- Filtrage par volatilité
- Callbacks et intégration
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from volatility_tracker import VolatilityTracker


class TestVolatilityTracker:
    """Tests pour la classe VolatilityTracker."""

    @pytest.fixture
    def tracker(self):
        """Instance de VolatilityTracker pour les tests."""
        return VolatilityTracker(testnet=True, ttl_seconds=120, max_cache_size=1000, logger=Mock())

    def test_initialization(self, tracker):
        """Test de l'initialisation du tracker."""
        assert tracker.testnet is True
        assert tracker.ttl_seconds == 120
        assert tracker.max_cache_size == 1000
        assert hasattr(tracker, 'calculator')
        assert hasattr(tracker, 'cache')
        assert hasattr(tracker, 'scheduler')
        assert tracker._get_active_symbols_callback is None

    def test_set_symbol_categories(self, tracker):
        """Test de la définition des catégories de symboles."""
        categories = {"BTCUSDT": "linear", "BTCUSD": "inverse"}
        
        with patch.object(tracker.calculator, 'set_symbol_categories') as mock_set:
            tracker.set_symbol_categories(categories)
            mock_set.assert_called_once_with(categories)

    def test_set_active_symbols_callback(self, tracker):
        """Test de la définition du callback de symboles actifs."""
        callback = Mock()
        
        with patch.object(tracker.scheduler, 'set_active_symbols_callback') as mock_set:
            tracker.set_active_symbols_callback(callback)
            
            assert tracker._get_active_symbols_callback == callback
            mock_set.assert_called_once_with(callback)

    def test_start_refresh_task(self, tracker):
        """Test du démarrage de la tâche de rafraîchissement."""
        with patch.object(tracker.scheduler, 'start_refresh_task') as mock_start:
            tracker.start_refresh_task()
            mock_start.assert_called_once()

    def test_stop_refresh_task(self, tracker):
        """Test de l'arrêt de la tâche de rafraîchissement."""
        with patch.object(tracker.scheduler, 'stop_refresh_task') as mock_stop:
            tracker.stop_refresh_task()
            mock_stop.assert_called_once()

    def test_get_cached_volatility(self, tracker):
        """Test de la récupération de volatilité en cache."""
        with patch.object(tracker.cache, 'get_cached_volatility') as mock_get:
            mock_get.return_value = 2.5
            
            result = tracker.get_cached_volatility("BTCUSDT")
            
            assert result == 2.5
            mock_get.assert_called_once_with("BTCUSDT")

    def test_set_cached_volatility(self, tracker):
        """Test de la mise en cache de volatilité."""
        with patch.object(tracker.cache, 'set_cached_volatility') as mock_set:
            tracker.set_cached_volatility("BTCUSDT", 2.5)
            mock_set.assert_called_once_with("BTCUSDT", 2.5)

    def test_clear_stale_cache(self, tracker):
        """Test du nettoyage du cache des symboles non actifs."""
        active_symbols = ["BTCUSDT", "ETHUSDT"]
        
        with patch.object(tracker.cache, 'clear_stale_cache') as mock_clear:
            tracker.clear_stale_cache(active_symbols)
            mock_clear.assert_called_once_with(active_symbols)

    @pytest.mark.asyncio
    async def test_compute_volatility_batch(self, tracker):
        """Test du calcul de volatilité en batch."""
        symbols = ["BTCUSDT", "ETHUSDT"]
        expected_result = {"BTCUSDT": 2.5, "ETHUSDT": 3.0}
        
        with patch.object(tracker.calculator, 'compute_volatility_batch') as mock_compute:
            mock_compute.return_value = expected_result
            
            result = await tracker.compute_volatility_batch(symbols)
            
            assert result == expected_result
            mock_compute.assert_called_once_with(symbols)

    @pytest.mark.asyncio
    async def test_filter_by_volatility_async(self, tracker):
        """Test du filtrage par volatilité asynchrone."""
        symbols_data = [
            ("BTCUSDT", 0.0001, 1000000, "1h", 0.001),
            ("ETHUSDT", 0.0002, 2000000, "1h", 0.002),
        ]
        expected_result = [
            ("BTCUSDT", 0.0001, 1000000, "1h", 0.001, 2.5),
            ("ETHUSDT", 0.0002, 2000000, "1h", 0.002, 3.0),
        ]
        
        with patch.object(tracker.calculator, 'filter_by_volatility_async') as mock_filter:
            mock_filter.return_value = expected_result
            
            result = await tracker.filter_by_volatility_async(
                symbols_data, 2.0, 4.0
            )
            
            assert result == expected_result
            mock_filter.assert_called_once_with(symbols_data, 2.0, 4.0)

    def test_filter_by_volatility_sync(self, tracker):
        """Test du filtrage par volatilité synchrone."""
        symbols_data = [
            ("BTCUSDT", 0.0001, 1000000, "1h", 0.001),
            ("ETHUSDT", 0.0002, 2000000, "1h", 0.002),
        ]
        expected_result = [
            ("BTCUSDT", 0.0001, 1000000, "1h", 0.001, 2.5),
            ("ETHUSDT", 0.0002, 2000000, "1h", 0.002, 3.0),
        ]
        
        with patch.object(tracker.calculator, 'filter_by_volatility') as mock_filter:
            mock_filter.return_value = expected_result
            
            result = tracker.filter_by_volatility(symbols_data, 2.0, 4.0)
            
            assert result == expected_result
            mock_filter.assert_called_once_with(symbols_data, 2.0, 4.0)

    def test_get_cache_stats(self, tracker):
        """Test de la récupération des statistiques du cache."""
        expected_stats = {"size": 10, "hits": 50, "misses": 5}
        
        with patch.object(tracker.cache, 'get_cache_stats') as mock_stats:
            mock_stats.return_value = expected_stats
            
            result = tracker.get_cache_stats()
            
            assert result == expected_stats
            mock_stats.assert_called_once()

    def test_is_running(self, tracker):
        """Test de la vérification de l'état d'exécution."""
        with patch.object(tracker.scheduler, 'is_running') as mock_running:
            mock_running.return_value = True
            
            result = tracker.is_running()
            
            assert result is True
            mock_running.assert_called_once()


class TestVolatilityTrackerIntegration:
    """Tests d'intégration pour VolatilityTracker."""

    @pytest.fixture
    def tracker_with_mocks(self):
        """Tracker avec tous les composants mockés."""
        tracker = VolatilityTracker(testnet=True, logger=Mock())
        
        # Mock des composants
        tracker.calculator = Mock()
        tracker.cache = Mock()
        tracker.scheduler = Mock()
        
        return tracker

    def test_full_workflow_sync(self, tracker_with_mocks):
        """Test du workflow complet en mode synchrone."""
        # Configuration
        categories = {"BTCUSDT": "linear", "ETHUSDT": "linear"}
        tracker_with_mocks.set_symbol_categories(categories)
        
        # Cache
        tracker_with_mocks.set_cached_volatility("BTCUSDT", 2.5)
        tracker_with_mocks.get_cached_volatility("BTCUSDT")
        
        # Filtrage
        symbols_data = [
            ("BTCUSDT", 0.0001, 1000000, "1h", 0.001),
            ("ETHUSDT", 0.0002, 2000000, "1h", 0.002),
        ]
        filtered_result = [
            ("BTCUSDT", 0.0001, 1000000, "1h", 0.001, 2.5),
        ]
        
        tracker_with_mocks.calculator.filter_by_volatility.return_value = filtered_result
        
        result = tracker_with_mocks.filter_by_volatility(symbols_data, 2.0, 3.0)
        
        assert result == filtered_result
        tracker_with_mocks.calculator.set_symbol_categories.assert_called_once_with(categories)
        tracker_with_mocks.cache.set_cached_volatility.assert_called_once_with("BTCUSDT", 2.5)
        tracker_with_mocks.cache.get_cached_volatility.assert_called_once_with("BTCUSDT")

    @pytest.mark.asyncio
    async def test_full_workflow_async(self, tracker_with_mocks):
        """Test du workflow complet en mode asynchrone."""
        # Calcul batch
        symbols = ["BTCUSDT", "ETHUSDT"]
        volatility_result = {"BTCUSDT": 2.5, "ETHUSDT": 3.0}
        tracker_with_mocks.calculator.compute_volatility_batch = AsyncMock(return_value=volatility_result)
        
        result = await tracker_with_mocks.compute_volatility_batch(symbols)
        
        assert result == volatility_result
        tracker_with_mocks.calculator.compute_volatility_batch.assert_called_once_with(symbols)
        
        # Filtrage async
        symbols_data = [
            ("BTCUSDT", 0.0001, 1000000, "1h", 0.001),
            ("ETHUSDT", 0.0002, 2000000, "1h", 0.002),
        ]
        filtered_result = [
            ("BTCUSDT", 0.0001, 1000000, "1h", 0.001, 2.5),
        ]
        
        tracker_with_mocks.calculator.filter_by_volatility_async = AsyncMock(return_value=filtered_result)
        
        result = await tracker_with_mocks.filter_by_volatility_async(
            symbols_data, 2.0, 3.0
        )
        
        assert result == filtered_result
        tracker_with_mocks.calculator.filter_by_volatility_async.assert_called_once_with(
            symbols_data, 2.0, 3.0
        )

    def test_lifecycle_management(self, tracker_with_mocks):
        """Test de la gestion du cycle de vie."""
        # Démarrage
        tracker_with_mocks.start_refresh_task()
        tracker_with_mocks.scheduler.start_refresh_task.assert_called_once()
        
        # Vérification de l'état
        tracker_with_mocks.scheduler.is_running.return_value = True
        assert tracker_with_mocks.is_running() is True
        
        # Arrêt
        tracker_with_mocks.stop_refresh_task()
        tracker_with_mocks.scheduler.stop_refresh_task.assert_called_once()
        
        # Nettoyage du cache
        active_symbols = ["BTCUSDT"]
        tracker_with_mocks.clear_stale_cache(active_symbols)
        tracker_with_mocks.cache.clear_stale_cache.assert_called_once_with(active_symbols)

    def test_callback_integration(self, tracker_with_mocks):
        """Test de l'intégration des callbacks."""
        callback = Mock()
        
        # Définition du callback
        tracker_with_mocks.set_active_symbols_callback(callback)
        
        assert tracker_with_mocks._get_active_symbols_callback == callback
        tracker_with_mocks.scheduler.set_active_symbols_callback.assert_called_once_with(callback)
        
        # Appel du callback
        callback.return_value = ["BTCUSDT", "ETHUSDT"]
        result = callback()
        
        assert result == ["BTCUSDT", "ETHUSDT"]
        callback.assert_called_once()
