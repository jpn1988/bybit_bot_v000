"""Tests pour le client Bybit."""

import pytest
from unittest.mock import Mock, patch
import httpx
from bybit_client import BybitClient, BybitPublicClient


class TestBybitClient:
    """Tests pour BybitClient."""
    
    def test_init_with_valid_credentials(self):
        """Test d'initialisation avec des credentials valides."""
        client = BybitClient(
            testnet=True,
            timeout=10,
            api_key="test_key",
            api_secret="test_secret"
        )
        
        assert client.testnet is True
        assert client.timeout == 10
        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        assert client.base_url == "https://api-testnet.bybit.com"
    
    def test_init_without_credentials_raises_error(self):
        """Test qu'une erreur est levée sans credentials."""
        with pytest.raises(RuntimeError, match="Clés API manquantes"):
            BybitClient(testnet=True, timeout=10, api_key=None, api_secret=None)
    
    def test_init_mainnet_url(self):
        """Test de l'URL mainnet."""
        client = BybitClient(
            testnet=False,
            timeout=10,
            api_key="test_key",
            api_secret="test_secret"
        )
        assert client.base_url == "https://api.bybit.com"
    
    @patch('httpx.Client')
    def test_get_wallet_balance_success(self, mock_client_class, mock_wallet_balance_response):
        """Test de récupération du solde avec succès."""
        # Mock de la réponse HTTP
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_wallet_balance_response
        
        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        client = BybitClient(
            testnet=True,
            timeout=10,
            api_key="test_key",
            api_secret="test_secret"
        )
        
        result = client.get_wallet_balance("UNIFIED")
        
        assert result == mock_wallet_balance_response["result"]
        mock_client.get.assert_called_once()
    
    @patch('httpx.Client')
    def test_get_wallet_balance_http_error(self, mock_client_class):
        """Test de gestion d'erreur HTTP."""
        # Mock d'une erreur HTTP
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        
        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        client = BybitClient(
            testnet=True,
            timeout=10,
            api_key="test_key",
            api_secret="test_secret"
        )
        
        with pytest.raises(RuntimeError, match="Erreur HTTP Bybit"):
            client.get_wallet_balance("UNIFIED")
    
    @patch('httpx.Client')
    def test_get_wallet_balance_api_error(self, mock_client_class):
        """Test de gestion d'erreur API."""
        # Mock d'une erreur API
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "retCode": 10005,
            "retMsg": "Invalid API key"
        }
        
        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        client = BybitClient(
            testnet=True,
            timeout=10,
            api_key="test_key",
            api_secret="test_secret"
        )
        
        with pytest.raises(RuntimeError, match="Authentification échouée"):
            client.get_wallet_balance("UNIFIED")


class TestBybitPublicClient:
    """Tests pour BybitPublicClient."""
    
    def test_init_testnet(self):
        """Test d'initialisation en mode testnet."""
        client = BybitPublicClient(testnet=True, timeout=10)
        assert client.testnet is True
        assert client.timeout == 10
        assert client.public_base_url() == "https://api-testnet.bybit.com"
    
    def test_init_mainnet(self):
        """Test d'initialisation en mode mainnet."""
        client = BybitPublicClient(testnet=False, timeout=10)
        assert client.testnet is False
        assert client.timeout == 10
        assert client.public_base_url() == "https://api.bybit.com"
