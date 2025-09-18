"""Tests pour le module de filtrage."""

import pytest
from filtering import FilterCriteria, build_watchlist


class TestFilterCriteria:
    """Tests pour FilterCriteria."""
    
    def test_default_values(self):
        """Test des valeurs par défaut."""
        criteria = FilterCriteria()
        
        assert criteria.category == "both"
        assert criteria.include is None
        assert criteria.exclude is None
        assert criteria.regex is None
        assert criteria.limit is None
    
    def test_custom_values(self):
        """Test avec des valeurs personnalisées."""
        criteria = FilterCriteria(
            category="linear",
            include=["BTCUSDT", "ETHUSDT"],
            exclude=["DOGEUSDT"],
            regex="^BTC.*",
            limit=5
        )
        
        assert criteria.category == "linear"
        assert criteria.include == ["BTCUSDT", "ETHUSDT"]
        assert criteria.exclude == ["DOGEUSDT"]
        assert criteria.regex == "^BTC.*"
        assert criteria.limit == 5


class TestBuildWatchlist:
    """Tests pour build_watchlist."""
    
    def test_linear_category(self):
        """Test avec la catégorie linear."""
        perp_data = {
            "linear": ["BTCUSDT", "ETHUSDT", "ADAUSDT"],
            "inverse": ["BTCUSD", "ETHUSD"],
            "total": 5
        }
        criteria = FilterCriteria(category="linear")
        
        result = build_watchlist(perp_data, criteria)
        
        assert result == ["ADAUSDT", "BTCUSDT", "ETHUSDT"]
    
    def test_inverse_category(self):
        """Test avec la catégorie inverse."""
        perp_data = {
            "linear": ["BTCUSDT", "ETHUSDT"],
            "inverse": ["BTCUSD", "ETHUSD", "ADAUSD"],
            "total": 5
        }
        criteria = FilterCriteria(category="inverse")
        
        result = build_watchlist(perp_data, criteria)
        
        assert result == ["ADAUSD", "BTCUSD", "ETHUSD"]
    
    def test_both_category(self):
        """Test avec la catégorie both."""
        perp_data = {
            "linear": ["BTCUSDT", "ETHUSDT"],
            "inverse": ["BTCUSD", "ETHUSD"],
            "total": 4
        }
        criteria = FilterCriteria(category="both")
        
        result = build_watchlist(perp_data, criteria)
        
        # Les deux listes sont fusionnées et triées
        expected = ["BTCUSD", "BTCUSDT", "ETHUSD", "ETHUSDT"]
        assert result == expected
    
    def test_include_filter(self):
        """Test du filtre include."""
        perp_data = {
            "linear": ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOTUSDT"],
            "inverse": ["BTCUSD", "ETHUSD"],
            "total": 6
        }
        criteria = FilterCriteria(
            category="linear",
            include=["BTCUSDT", "ADAUSDT"]
        )
        
        result = build_watchlist(perp_data, criteria)
        
        assert result == ["ADAUSDT", "BTCUSDT"]
    
    def test_exclude_filter(self):
        """Test du filtre exclude."""
        perp_data = {
            "linear": ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOTUSDT"],
            "inverse": ["BTCUSD", "ETHUSD"],
            "total": 6
        }
        criteria = FilterCriteria(
            category="linear",
            exclude=["ADAUSDT", "DOTUSDT"]
        )
        
        result = build_watchlist(perp_data, criteria)
        
        assert result == ["BTCUSDT", "ETHUSDT"]
    
    def test_regex_filter(self):
        """Test du filtre regex."""
        perp_data = {
            "linear": ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOTUSDT"],
            "inverse": ["BTCUSD", "ETHUSD"],
            "total": 6
        }
        criteria = FilterCriteria(
            category="linear",
            regex="^BTC.*"
        )
        
        result = build_watchlist(perp_data, criteria)
        
        assert result == ["BTCUSDT"]
    
    def test_regex_case_insensitive(self):
        """Test que le filtre regex est insensible à la casse."""
        perp_data = {
            "linear": ["BTCUSDT", "btcusdt", "ETHUSDT"],
            "inverse": ["BTCUSD", "ETHUSD"],
            "total": 5
        }
        criteria = FilterCriteria(
            category="linear",
            regex="^btc.*"
        )
        
        result = build_watchlist(perp_data, criteria)
        
        assert result == ["BTCUSDT", "btcusdt"]
    
    def test_invalid_regex(self):
        """Test avec une regex invalide."""
        perp_data = {
            "linear": ["BTCUSDT", "ETHUSDT"],
            "inverse": ["BTCUSD", "ETHUSD"],
            "total": 4
        }
        criteria = FilterCriteria(
            category="linear",
            regex="[invalid regex"
        )
        
        # Ne devrait pas lever d'erreur, juste ignorer le filtre
        result = build_watchlist(perp_data, criteria)
        
        assert result == ["BTCUSDT", "ETHUSDT"]
    
    def test_limit_filter(self):
        """Test du filtre limit."""
        perp_data = {
            "linear": ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOTUSDT", "LINKUSDT"],
            "inverse": ["BTCUSD", "ETHUSD"],
            "total": 7
        }
        criteria = FilterCriteria(
            category="linear",
            limit=3
        )
        
        result = build_watchlist(perp_data, criteria)
        
        assert len(result) == 3
        assert result == ["ADAUSDT", "BTCUSDT", "DOTUSDT"]
    
    def test_combined_filters(self):
        """Test avec plusieurs filtres combinés."""
        perp_data = {
            "linear": ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOTUSDT", "LINKUSDT"],
            "inverse": ["BTCUSD", "ETHUSD"],
            "total": 7
        }
        criteria = FilterCriteria(
            category="linear",
            include=["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOTUSDT", "LINKUSDT"],
            exclude=["ADAUSDT", "DOTUSDT"],
            regex="^[BE].*",
            limit=2
        )
        
        result = build_watchlist(perp_data, criteria)
        
        # include: garde tous
        # exclude: retire ADAUSDT, DOTUSDT → reste BTCUSDT, ETHUSDT, LINKUSDT
        # regex: garde ceux qui commencent par B ou E → BTCUSDT, ETHUSDT
        # limit: garde les 2 premiers → BTCUSDT, ETHUSDT
        assert result == ["BTCUSDT", "ETHUSDT"]
    
    def test_empty_result(self):
        """Test avec un résultat vide."""
        perp_data = {
            "linear": ["BTCUSDT", "ETHUSDT"],
            "inverse": ["BTCUSD", "ETHUSD"],
            "total": 4
        }
        criteria = FilterCriteria(
            category="linear",
            include=["NONEXISTENT"]
        )
        
        result = build_watchlist(perp_data, criteria)
        
        assert result == []
