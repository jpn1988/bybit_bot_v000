#!/usr/bin/env python3
"""Tests pour VolatilityTracker."""

import pytest
import unittest.mock as mock
import time
from src.volatility_tracker import VolatilityTracker


class TestVolatilityTracker:
    """Tests pour la classe VolatilityTracker."""
    
    def test_init(self):
        """Test de l'initialisation du VolatilityTracker."""
        vt = VolatilityTracker(testnet=True, ttl_seconds=60)
        
        assert vt.testnet is True
        assert vt.ttl_seconds == 60
        assert vt.volatility_cache == {}
        assert vt._running is False
        assert vt._refresh_thread is None
        assert vt._symbols_to_track == []
        assert vt._client is None
        assert vt._symbol_categories == {}
        assert vt._get_active_symbols_callback is None
    
    def test_set_symbol_categories(self):
        """Test de la définition des catégories de symboles."""
        vt = VolatilityTracker()
        categories = {"BTCUSDT": "linear", "ETHUSDT": "linear"}
        
        vt.set_symbol_categories(categories)
        assert vt._symbol_categories == categories
    
    def test_set_active_symbols_callback(self):
        """Test de la définition du callback symboles actifs."""
        vt = VolatilityTracker()
        
        def dummy_callback():
            return ["BTCUSDT"]
        
        vt.set_active_symbols_callback(dummy_callback)
        assert vt._get_active_symbols_callback == dummy_callback
    
    def test_cache_operations(self):
        """Test des opérations de cache."""
        vt = VolatilityTracker(ttl_seconds=60)
        
        # Test cache vide
        assert vt.get_cached_volatility("BTCUSDT") is None
        
        # Test ajout au cache
        vt.set_cached_volatility("BTCUSDT", 0.05)
        cached = vt.get_cached_volatility("BTCUSDT")
        assert cached == 0.05
        
        # Test cache expiré (simuler un TTL très court)
        vt.ttl_seconds = 0.001
        time.sleep(0.002)
        cached_expired = vt.get_cached_volatility("BTCUSDT")
        assert cached_expired is None
    
    def test_get_cache_stats(self):
        """Test des statistiques du cache."""
        vt = VolatilityTracker(ttl_seconds=60)
        
        # Cache vide
        stats = vt.get_cache_stats()
        assert stats["total"] == 0
        assert stats["valid"] == 0
        assert stats["expired"] == 0
        
        # Ajouter des données
        vt.set_cached_volatility("BTCUSDT", 0.05)
        vt.set_cached_volatility("ETHUSDT", 0.03)
        
        stats = vt.get_cache_stats()
        assert stats["total"] == 2
        assert stats["valid"] == 2
        assert stats["expired"] == 0
    
    def test_clear_stale_cache(self):
        """Test du nettoyage du cache."""
        vt = VolatilityTracker()
        
        # Ajouter des données au cache
        vt.set_cached_volatility("BTCUSDT", 0.05)
        vt.set_cached_volatility("ETHUSDT", 0.03)
        vt.set_cached_volatility("ADAUSDT", 0.02)
        
        # Nettoyer en gardant seulement BTCUSDT et ETHUSDT
        active_symbols = ["BTCUSDT", "ETHUSDT"]
        vt.clear_stale_cache(active_symbols)
        
        # Vérifier que ADAUSDT a été supprimé
        assert vt.get_cached_volatility("BTCUSDT") == 0.05
        assert vt.get_cached_volatility("ETHUSDT") == 0.03
        assert vt.get_cached_volatility("ADAUSDT") is None
    
    def test_filter_by_volatility_sync(self):
        """Test du filtrage synchrone par volatilité."""
        vt = VolatilityTracker()
        
        # Données de test
        symbols_data = [
            ("BTCUSDT", 0.01, 1000000, "8h", 0.001),
            ("ETHUSDT", 0.02, 2000000, "7h", 0.002),
            ("ADAUSDT", 0.005, 500000, "6h", 0.0005),
        ]
        
        # Pré-remplir le cache
        vt.set_cached_volatility("BTCUSDT", 0.05)  # 5%
        vt.set_cached_volatility("ETHUSDT", 0.02)  # 2%
        vt.set_cached_volatility("ADAUSDT", 0.08)  # 8%
        
        # Test sans filtres (tous passent)
        filtered = vt.filter_by_volatility(symbols_data, None, None)
        assert len(filtered) == 3
        
        # Test avec filtre minimum (≥ 3%)
        filtered = vt.filter_by_volatility(symbols_data, 0.03, None)
        assert len(filtered) == 2  # BTCUSDT (5%) et ADAUSDT (8%)
        
        # Test avec filtre maximum (≤ 6%)
        filtered = vt.filter_by_volatility(symbols_data, None, 0.06)
        assert len(filtered) == 2  # BTCUSDT (5%) et ETHUSDT (2%)
        
        # Test avec filtre min et max (3% ≤ vol ≤ 6%)
        filtered = vt.filter_by_volatility(symbols_data, 0.03, 0.06)
        assert len(filtered) == 1  # Seul BTCUSDT (5%)
        assert filtered[0][0] == "BTCUSDT"
        assert len(filtered[0]) == 6  # Doit inclure la volatilité
    
    def test_is_running_initial_state(self):
        """Test de l'état initial running."""
        vt = VolatilityTracker()
        assert vt.is_running() is False
    
    @pytest.mark.asyncio
    @mock.patch('src.volatility_tracker.BybitPublicClient')
    @mock.patch('src.volatility_tracker.compute_volatility_batch_async')
    async def test_compute_volatility_batch(self, mock_compute, mock_client):
        """Test du calcul de volatilité en batch."""
        # Mock des résultats
        mock_compute.return_value = {"BTCUSDT": 0.05, "ETHUSDT": 0.03}
        
        vt = VolatilityTracker(testnet=True)
        symbols = ["BTCUSDT", "ETHUSDT"]
        
        result = await vt.compute_volatility_batch(symbols)
        
        assert result == {"BTCUSDT": 0.05, "ETHUSDT": 0.03}
        mock_compute.assert_called_once()
    
    def test_start_stop_refresh_task(self):
        """Test de démarrage/arrêt de la tâche de rafraîchissement."""
        mock_logger = mock.MagicMock()
        vt = VolatilityTracker(logger=mock_logger)
        
        # Test démarrage
        assert vt.is_running() is False
        
        # Mock du thread pour éviter l'exécution réelle
        with mock.patch('threading.Thread') as mock_thread:
            mock_thread_instance = mock.MagicMock()
            mock_thread.return_value = mock_thread_instance
            
            vt.start_refresh_task()
            
            assert vt._running is True
            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()
        
        # Test arrêt
        vt.stop_refresh_task()
        assert vt._running is False
    
    def test_filter_by_volatility_without_cache(self):
        """Test du filtrage quand le cache est vide."""
        vt = VolatilityTracker()
        
        symbols_data = [
            ("BTCUSDT", 0.01, 1000000, "8h", 0.001),
        ]
        
        # Mock pour éviter les appels réseau réels
        with mock.patch.object(vt, 'compute_volatility_batch') as mock_compute:
            # Simuler un échec de calcul (None)
            mock_compute.return_value = {"BTCUSDT": None}
            
            # Avec filtres actifs, les symboles sans volatilité sont rejetés
            filtered = vt.filter_by_volatility(symbols_data, 0.01, None)
            assert len(filtered) == 0
            
            # Sans filtres, les symboles passent même sans volatilité
            filtered = vt.filter_by_volatility(symbols_data, None, None)
            assert len(filtered) == 1
            assert filtered[0][5] is None  # Volatilité None
