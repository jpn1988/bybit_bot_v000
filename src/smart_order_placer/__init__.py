"""
Smart Order Placer Package - Système de placement d'ordres maker intelligent.

Ce package fournit un système modulaire de placement d'ordres avec :
- Classification de liquidité
- Calcul dynamique des prix
- Formatage et validation des ordres
- Gestion des retries
"""

from .smart_order_placer import SmartOrderPlacer, OrderResult
from .liquidity_classifier import LiquidityClassifier
from .price_calculator import DynamicPriceCalculator

__all__ = [
    'SmartOrderPlacer',
    'OrderResult',
    'LiquidityClassifier',
    'DynamicPriceCalculator',
]

