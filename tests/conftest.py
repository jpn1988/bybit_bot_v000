"""Configuration pytest pour bybit_bot_v0."""

import os
import sys
import pytest
from unittest.mock import Mock, patch
from pathlib import Path

# Ajouter le répertoire src au path pour les imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

@pytest.fixture
def mock_env_vars():
    """Mock des variables d'environnement pour les tests."""
    with patch.dict(os.environ, {
        'BYBIT_API_KEY': 'test_api_key',
        'BYBIT_API_SECRET': 'test_api_secret',
        'TESTNET': 'true',
        'TIMEOUT': '10',
        'LOG_LEVEL': 'INFO'
    }):
        yield

@pytest.fixture
def mock_bybit_response():
    """Mock d'une réponse API Bybit typique."""
    return {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "list": [
                {
                    "symbol": "BTCUSDT",
                    "fundingRate": "0.0001",
                    "volume24h": "1000000.0",
                    "nextFundingTime": "1640995200000",
                    "bid1Price": "50000.0",
                    "ask1Price": "50001.0"
                },
                {
                    "symbol": "ETHUSDT", 
                    "fundingRate": "0.0002",
                    "volume24h": "2000000.0",
                    "nextFundingTime": "1640995200000",
                    "bid1Price": "3000.0",
                    "ask1Price": "3001.0"
                }
            ]
        }
    }

@pytest.fixture
def mock_wallet_balance_response():
    """Mock d'une réponse de solde de portefeuille."""
    return {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "list": [
                {
                    "accountType": "UNIFIED",
                    "accountId": "123456",
                    "totalWalletBalance": "1000.0",
                    "totalUnrealizedPnl": "0.0",
                    "totalMarginBalance": "1000.0",
                    "totalAvailableBalance": "1000.0",
                    "totalPerpUPL": "0.0",
                    "totalInitialMargin": "0.0",
                    "totalMaintenanceMargin": "0.0",
                    "coin": [
                        {
                            "coin": "USDT",
                            "walletBalance": "1000.0",
                            "availableBalance": "1000.0"
                        }
                    ]
                }
            ]
        }
    }
