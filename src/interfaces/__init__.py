#!/usr/bin/env python3
"""
Package des interfaces pour le bot Bybit.

Ce package contient les interfaces (contrats) pour les composants principaux
du bot, permettant une meilleure testabilité et une architecture plus flexible.
"""

from .bybit_client_interface import BybitClientInterface
from .websocket_manager_interface import WebSocketManagerInterface

__all__ = [
    "BybitClientInterface",
    "WebSocketManagerInterface",
]
