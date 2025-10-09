#!/usr/bin/env python3
"""
Tests pour DataStorage avec Value Objects.
"""

import pytest
import sys
sys.path.insert(0, 'src')

from data_storage import DataStorage
from models.funding_data import FundingData


class TestDataStorageWithValueObjects:
    """Tests pour DataStorage avec les Value Objects."""
    
    def test_set_and_get_funding_data_object(self):
        """Test de stockage et récupération d'un FundingData."""
        storage = DataStorage()
        
        funding = FundingData(
            symbol="BTCUSDT",
            funding_rate=0.0001,
            volume_24h=1000000.0,
            next_funding_time="1h 30m",
            spread_pct=0.001,
            volatility_pct=0.005,
        )
        
        # Stocker
        storage.set_funding_data_object(funding)
        
        # Récupérer
        retrieved = storage.get_funding_data_object("BTCUSDT")
        
        assert retrieved is not None
        assert retrieved.symbol == "BTCUSDT"
        assert retrieved.funding_rate == 0.0001
        assert retrieved.volume_24h == 1000000.0
        assert retrieved.volatility_pct == 0.005
    
    def test_set_funding_data_object_updates_both_formats(self):
        """Test que set_funding_data_object stocke le Value Object et expose via la propriété."""
        storage = DataStorage()
        
        funding = FundingData(
            symbol="BTCUSDT",
            funding_rate=0.0001,
            volume_24h=1000000.0,
            next_funding_time="1h 30m",
            spread_pct=0.001,
        )
        
        storage.set_funding_data_object(funding)
        
        # Vérifier que le Value Object est stocké
        retrieved = storage.get_funding_data_object("BTCUSDT")
        assert retrieved is not None
        assert retrieved.symbol == "BTCUSDT"
        
        # Vérifier la compatibilité via la propriété funding_data
        assert "BTCUSDT" in storage.funding_data
        old_format = storage.funding_data["BTCUSDT"]
        assert old_format == (0.0001, 1000000.0, "1h 30m", 0.001, None)
    
    def test_get_all_funding_data_objects(self):
        """Test de récupération de tous les FundingData."""
        storage = DataStorage()
        
        funding1 = FundingData(
            symbol="BTCUSDT",
            funding_rate=0.0001,
            volume_24h=1000000.0,
            next_funding_time="1h 30m",
            spread_pct=0.001,
        )
        
        funding2 = FundingData(
            symbol="ETHUSDT",
            funding_rate=0.0002,
            volume_24h=500000.0,
            next_funding_time="2h 15m",
            spread_pct=0.002,
        )
        
        storage.set_funding_data_object(funding1)
        storage.set_funding_data_object(funding2)
        
        all_funding = storage.get_all_funding_data_objects()
        
        assert len(all_funding) == 2
        assert "BTCUSDT" in all_funding
        assert "ETHUSDT" in all_funding
        assert all_funding["BTCUSDT"].funding_rate == 0.0001
        assert all_funding["ETHUSDT"].funding_rate == 0.0002
    
    def test_get_funding_data_object_fallback_from_old_format(self):
        """Test de récupération via update_funding_data (méthode de compatibilité)."""
        storage = DataStorage()
        
        # Utiliser l'ancienne méthode qui crée maintenant un Value Object en interne
        storage.update_funding_data("BTCUSDT", 0.0001, 1000000.0, "1h 30m", 0.001, 0.005)
        
        # Récupérer en tant que Value Object
        retrieved = storage.get_funding_data_object("BTCUSDT")
        
        assert retrieved is not None
        assert retrieved.symbol == "BTCUSDT"
        assert retrieved.funding_rate == 0.0001
        assert retrieved.volatility_pct == 0.005
    
    def test_get_all_funding_data_objects_fallback_from_old_format(self):
        """Test de récupération de tous les FundingData via méthodes de compatibilité."""
        storage = DataStorage()
        
        # Utiliser l'ancienne méthode qui crée maintenant des Value Objects en interne
        storage.update_funding_data("BTCUSDT", 0.0001, 1000000.0, "1h 30m", 0.001, None)
        storage.update_funding_data("ETHUSDT", 0.0002, 500000.0, "2h 15m", 0.002, None)
        
        # Récupérer en tant que Value Objects
        all_funding = storage.get_all_funding_data_objects()
        
        assert len(all_funding) == 2
        assert all_funding["BTCUSDT"].funding_rate == 0.0001
        assert all_funding["ETHUSDT"].funding_rate == 0.0002
    
    def test_clear_all_data_clears_both_formats(self):
        """Test que clear_all_data vide toutes les données."""
        storage = DataStorage()
        
        funding = FundingData(
            symbol="BTCUSDT",
            funding_rate=0.0001,
            volume_24h=1000000.0,
            next_funding_time="1h 30m",
            spread_pct=0.001,
        )
        
        storage.set_funding_data_object(funding)
        
        # Vérifier que les données sont présentes
        assert len(storage.funding_data) > 0
        assert len(storage.get_all_funding_data_objects()) > 0
        
        # Nettoyer
        storage.clear_all_data()
        
        # Vérifier que tout est vide
        assert len(storage.funding_data) == 0
        assert len(storage.get_all_funding_data_objects()) == 0
    
    def test_get_data_stats_includes_value_objects(self):
        """Test que get_data_stats inclut le compteur de Value Objects."""
        storage = DataStorage()
        
        funding = FundingData(
            symbol="BTCUSDT",
            funding_rate=0.0001,
            volume_24h=1000000.0,
            next_funding_time="1h 30m",
            spread_pct=0.001,
        )
        
        storage.set_funding_data_object(funding)
        
        stats = storage.get_data_stats()
        
        assert "funding_data_objects" in stats
        assert stats["funding_data_objects"] == 1
    
    def test_backward_compatibility_update_funding_data(self):
        """Test de rétrocompatibilité avec update_funding_data."""
        storage = DataStorage()
        
        # Utiliser l'ancienne méthode
        storage.update_funding_data(
            symbol="BTCUSDT",
            funding=0.0001,
            volume=1000000.0,
            funding_time="1h 30m",
            spread=0.001,
            volatility=0.005,
        )
        
        # Vérifier que les données sont accessibles
        old_format = storage.get_funding_data("BTCUSDT")
        assert old_format == (0.0001, 1000000.0, "1h 30m", 0.001, 0.005)
        
        # Vérifier que les données sont convertibles en Value Object
        value_object = storage.get_funding_data_object("BTCUSDT")
        assert value_object is not None
        assert value_object.funding_rate == 0.0001

