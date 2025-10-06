"""Tests pour le module de configuration."""

import pytest
import os
from unittest.mock import patch
from config_unified import get_settings


class TestConfig:
    """Tests pour la configuration."""
    
    def test_get_settings_with_valid_env_vars(self, mock_env_vars):
        """Test de récupération des paramètres avec des variables d'environnement valides."""
        settings = get_settings()
        
        assert settings['testnet'] is True
        assert settings['timeout'] == 10
        assert settings['log_level'] == 'INFO'
        assert settings['api_key'] == 'test_api_key'
        assert settings['api_secret'] == 'test_api_secret'
    
    def test_get_settings_defaults(self):
        """Test des valeurs par défaut."""
        with patch.dict(os.environ, {}, clear=True):
            settings = get_settings()
            
            assert settings['testnet'] is True  # Par défaut
            assert settings['timeout'] == 10  # Par défaut
            assert settings['log_level'] == 'INFO'  # Par défaut
            assert settings['api_key'] is None
            assert settings['api_secret'] is None
    
    def test_get_settings_with_env_overrides(self):
        """Test des overrides via variables d'environnement."""
        with patch.dict(os.environ, {
            'TESTNET': 'false',
            'TIMEOUT': '30',
            'LOG_LEVEL': 'DEBUG',
            'BYBIT_API_KEY': 'env_key',
            'BYBIT_API_SECRET': 'env_secret',
            'SPREAD_MAX': '0.005',
            'VOLUME_MIN_MILLIONS': '10.0',
            'VOLATILITY_MIN': '0.001',
            'VOLATILITY_MAX': '0.01',
            'FUNDING_MIN': '0.0001',
            'FUNDING_MAX': '0.0005',
            'CATEGORY': 'linear',
            'LIMIT': '20',
            'VOLATILITY_TTL_SEC': '300',
            'FUNDING_TIME_MIN_MINUTES': '30',
            'FUNDING_TIME_MAX_MINUTES': '120'
        }):
            settings = get_settings()
            
            assert settings['testnet'] is False
            assert settings['timeout'] == 30
            assert settings['log_level'] == 'DEBUG'
            assert settings['api_key'] == 'env_key'
            assert settings['api_secret'] == 'env_secret'
            assert settings['spread_max'] == 0.005
            assert settings['volume_min_millions'] == 10.0
            assert settings['volatility_min'] == 0.001
            assert settings['volatility_max'] == 0.01
            assert settings['funding_min'] == 0.0001
            assert settings['funding_max'] == 0.0005
            assert settings['category'] == 'linear'
            assert settings['limit'] == 20
            assert settings['volatility_ttl_sec'] == 300
            assert settings['funding_time_min_minutes'] == 30
            assert settings['funding_time_max_minutes'] == 120
    
    def test_get_settings_with_empty_strings(self):
        """Test que les chaînes vides sont converties en None."""
        with patch.dict(os.environ, {
            'BYBIT_API_KEY': '',
            'BYBIT_API_SECRET': '',
            'SPREAD_MAX': '',
            'VOLUME_MIN_MILLIONS': ''
        }):
            settings = get_settings()
            
            assert settings['api_key'] is None
            assert settings['api_secret'] is None
            assert settings['spread_max'] is None
            assert settings['volume_min_millions'] is None
    
    def test_get_settings_invalid_numeric_values(self):
        """Test avec des valeurs numériques invalides."""
        with patch.dict(os.environ, {
            'TIMEOUT': 'invalid',
            'SPREAD_MAX': 'not_a_number'
        }):
            # Les valeurs invalides devraient être ignorées et utiliser les valeurs par défaut
            settings = get_settings()
            
            assert settings['timeout'] == 10  # Valeur par défaut
            assert settings['spread_max'] is None  # Chaîne vide convertie en None
    
    def test_get_settings_unknown_env_vars_warning(self, capsys):
        """Test que les variables d'environnement inconnues génèrent un avertissement."""
        with patch.dict(os.environ, {
            'BYBIT_UNKNOWN_VAR': 'test',
            'FUNDING_UNKNOWN': 'test'
        }):
            settings = get_settings()
            
            # Vérifier que les variables inconnues liées au bot génèrent un avertissement
            captured = capsys.readouterr()
            assert "Variable d'environnement inconnue ignorée" in captured.err
            assert "BYBIT_UNKNOWN_VAR" in captured.err or "FUNDING_UNKNOWN" in captured.err
