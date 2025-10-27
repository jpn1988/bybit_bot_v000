#!/usr/bin/env python3
"""
Package factories pour la création centralisée de Value Objects et composants.
"""

from .bot_component_factory import BotComponentFactory
from .bot_factory import BotFactory

__all__ = ['BotComponentFactory', 'BotFactory']
