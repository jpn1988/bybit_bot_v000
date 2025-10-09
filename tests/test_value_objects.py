#!/usr/bin/env python3
"""
Tests pour les Value Objects du bot Bybit.
"""

import pytest
import sys
sys.path.insert(0, 'src')

from models.funding_data import FundingData
from models.ticker_data import TickerData
from models.symbol_data import SymbolData


class TestFundingData:
    """Tests pour FundingData Value Object."""
    
    def test_create_valid_funding_data(self):
        """Test de création d'un FundingData valide."""
        funding = FundingData(
            symbol="BTCUSDT",
            funding_rate=0.0001,
            volume_24h=1000000.0,
            next_funding_time="1h 30m",
            spread_pct=0.001,
            volatility_pct=0.005,
        )
        
        assert funding.symbol == "BTCUSDT"
        assert funding.funding_rate == 0.0001
        assert funding.volume_24h == 1000000.0
        assert funding.next_funding_time == "1h 30m"
        assert funding.spread_pct == 0.001
        assert funding.volatility_pct == 0.005
    
    def test_funding_data_is_immutable(self):
        """Test que FundingData est immutable."""
        funding = FundingData(
            symbol="BTCUSDT",
            funding_rate=0.0001,
            volume_24h=1000000.0,
            next_funding_time="1h 30m",
            spread_pct=0.001,
        )
        
        with pytest.raises(Exception):  # dataclass frozen
            funding.funding_rate = 0.0002
    
    def test_funding_data_validation_invalid_symbol(self):
        """Test de validation avec un symbole invalide."""
        with pytest.raises(ValueError, match="Symbol invalide"):
            FundingData(
                symbol="",
                funding_rate=0.0001,
                volume_24h=1000000.0,
                next_funding_time="1h 30m",
                spread_pct=0.001,
            )
    
    def test_funding_data_validation_invalid_funding_rate(self):
        """Test de validation avec un funding rate invalide."""
        with pytest.raises(ValueError, match="Funding rate hors limites"):
            FundingData(
                symbol="BTCUSDT",
                funding_rate=2.0,  # Hors limites
                volume_24h=1000000.0,
                next_funding_time="1h 30m",
                spread_pct=0.001,
            )
    
    def test_funding_data_validation_negative_volume(self):
        """Test de validation avec un volume négatif."""
        with pytest.raises(ValueError, match="Volume négatif"):
            FundingData(
                symbol="BTCUSDT",
                funding_rate=0.0001,
                volume_24h=-1000.0,  # Négatif
                next_funding_time="1h 30m",
                spread_pct=0.001,
            )
    
    def test_funding_data_validation_invalid_spread(self):
        """Test de validation avec un spread invalide."""
        with pytest.raises(ValueError, match="Spread hors limites"):
            FundingData(
                symbol="BTCUSDT",
                funding_rate=0.0001,
                volume_24h=1000000.0,
                next_funding_time="1h 30m",
                spread_pct=2.0,  # Hors limites
            )
    
    def test_funding_data_properties(self):
        """Test des propriétés calculées."""
        funding = FundingData(
            symbol="BTCUSDT",
            funding_rate=0.0001,
            volume_24h=5000000.0,
            next_funding_time="1h 30m",
            spread_pct=0.001,
            volatility_pct=0.005,
        )
        
        assert funding.funding_rate_pct == 0.01  # 0.0001 * 100
        assert funding.volume_millions == 5.0  # 5000000 / 1000000
        assert funding.has_volatility is True
    
    def test_funding_data_to_tuple(self):
        """Test de conversion en tuple."""
        funding = FundingData(
            symbol="BTCUSDT",
            funding_rate=0.0001,
            volume_24h=1000000.0,
            next_funding_time="1h 30m",
            spread_pct=0.001,
            volatility_pct=0.005,
        )
        
        result = funding.to_tuple()
        assert result == (0.0001, 1000000.0, "1h 30m", 0.001, 0.005)
    
    def test_funding_data_from_tuple(self):
        """Test de création depuis un tuple."""
        data = (0.0001, 1000000.0, "1h 30m", 0.001, 0.005)
        funding = FundingData.from_tuple("BTCUSDT", data)
        
        assert funding.symbol == "BTCUSDT"
        assert funding.funding_rate == 0.0001
        assert funding.volatility_pct == 0.005
    
    def test_funding_data_to_dict(self):
        """Test de conversion en dictionnaire."""
        funding = FundingData(
            symbol="BTCUSDT",
            funding_rate=0.0001,
            volume_24h=1000000.0,
            next_funding_time="1h 30m",
            spread_pct=0.001,
            volatility_pct=0.005,
        )
        
        result = funding.to_dict()
        assert result["symbol"] == "BTCUSDT"
        assert result["funding_rate"] == 0.0001
        assert result["funding_rate_pct"] == 0.01


class TestTickerData:
    """Tests pour TickerData Value Object."""
    
    def test_create_valid_ticker_data(self):
        """Test de création d'un TickerData valide."""
        ticker = TickerData(
            symbol="BTCUSDT",
            last_price=50000.0,
            mark_price=50001.0,
            timestamp=1234567890.0,
            bid1_price=49999.0,
            ask1_price=50001.0,
        )
        
        assert ticker.symbol == "BTCUSDT"
        assert ticker.last_price == 50000.0
        assert ticker.mark_price == 50001.0
        assert ticker.timestamp == 1234567890.0
    
    def test_ticker_data_is_immutable(self):
        """Test que TickerData est immutable."""
        ticker = TickerData(
            symbol="BTCUSDT",
            last_price=50000.0,
            mark_price=50001.0,
            timestamp=1234567890.0,
        )
        
        with pytest.raises(Exception):  # dataclass frozen
            ticker.last_price = 51000.0
    
    def test_ticker_data_validation_invalid_last_price(self):
        """Test de validation avec un last price invalide."""
        with pytest.raises(ValueError, match="Last price invalide"):
            TickerData(
                symbol="BTCUSDT",
                last_price=-50000.0,  # Négatif
                mark_price=50001.0,
                timestamp=1234567890.0,
            )
    
    def test_ticker_data_spread_calculation(self):
        """Test du calcul du spread."""
        ticker = TickerData(
            symbol="BTCUSDT",
            last_price=50000.0,
            mark_price=50001.0,
            timestamp=1234567890.0,
            bid1_price=49999.0,
            ask1_price=50001.0,
        )
        
        # Spread = (50001 - 49999) / 49999 ≈ 0.00004
        assert ticker.spread_pct is not None
        assert abs(ticker.spread_pct - 0.00004) < 0.000001
    
    def test_ticker_data_from_dict(self):
        """Test de création depuis un dictionnaire."""
        data = {
            "symbol": "BTCUSDT",
            "lastPrice": "50000.0",
            "markPrice": "50001.0",
            "timestamp": "1234567890",
            "bid1Price": "49999.0",
            "ask1Price": "50001.0",
        }
        
        ticker = TickerData.from_dict(data)
        assert ticker.symbol == "BTCUSDT"
        assert ticker.last_price == 50000.0
        assert ticker.mark_price == 50001.0


class TestSymbolData:
    """Tests pour SymbolData Value Object."""
    
    def test_create_valid_symbol_data(self):
        """Test de création d'un SymbolData valide."""
        symbol = SymbolData(
            symbol="BTCUSDT",
            category="linear",
            base_coin="BTC",
            quote_coin="USDT",
        )
        
        assert symbol.symbol == "BTCUSDT"
        assert symbol.category == "linear"
        assert symbol.base_coin == "BTC"
        assert symbol.quote_coin == "USDT"
    
    def test_symbol_data_is_immutable(self):
        """Test que SymbolData est immutable."""
        symbol = SymbolData(
            symbol="BTCUSDT",
            category="linear",
        )
        
        with pytest.raises(Exception):  # dataclass frozen
            symbol.category = "inverse"
    
    def test_symbol_data_validation_invalid_category(self):
        """Test de validation avec une catégorie invalide."""
        with pytest.raises(ValueError, match="Catégorie invalide"):
            SymbolData(
                symbol="BTCUSDT",
                category="invalid",
            )
    
    def test_symbol_data_properties(self):
        """Test des propriétés."""
        linear_symbol = SymbolData(
            symbol="BTCUSDT",
            category="linear",
        )
        
        inverse_symbol = SymbolData(
            symbol="BTCUSD",
            category="inverse",
        )
        
        assert linear_symbol.is_linear is True
        assert linear_symbol.is_inverse is False
        assert inverse_symbol.is_linear is False
        assert inverse_symbol.is_inverse is True
    
    def test_symbol_data_from_dict(self):
        """Test de création depuis un dictionnaire."""
        data = {
            "symbol": "BTCUSDT",
            "category": "linear",
            "baseCoin": "BTC",
            "quoteCoin": "USDT",
            "status": "Trading",
        }
        
        symbol = SymbolData.from_dict(data)
        assert symbol.symbol == "BTCUSDT"
        assert symbol.category == "linear"
        assert symbol.base_coin == "BTC"
        assert symbol.is_trading is True

