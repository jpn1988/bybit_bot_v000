#!/usr/bin/env python3
"""
Factory principale pour créer un bot Bybit complet.

Cette factory orchestre l'ensemble du processus de création d'un bot:
1. Création de tous les composants via BotComponentFactory
2. Configuration de tous les callbacks via BotCallbackConfigurator
3. Retour d'un BotOrchestrator configuré et prêt à démarrer

Point d'entrée simplifié pour créer un bot complet.
"""

from typing import Optional
from logging_setup import setup_logging
from config import get_settings
from .bot_component_factory import BotComponentFactory
from configuration.bot_callback_configurator import BotCallbackConfigurator

# Import BotOrchestrator sera fait localement pour éviter les imports circulaires


class BotFactory:
    """
    Factory principale pour créer un bot Bybit complet.
    
    Cette classe orchestre l'ensemble du processus de création et
    configuration d'un bot, fournissant un point d'entrée simple et uniforme.
    
    Responsabilité unique : Orchestrer la création complète d'un bot
    
    Exemple d'utilisation:
        # Création standard
        factory = BotFactory(logger=logger)
        orchestrator = factory.create_bot()
        
        # Création avec testnet
        orchestrator = factory.create_bot(testnet=True)
        
        # Démarrer le bot
        await orchestrator.start()
    """
    
    def __init__(self, logger=None):
        """
        Initialise la factory principale.
        
        Args:
            logger: Logger pour les messages (optionnel)
        """
        self.logger = logger or setup_logging()
    
    def create_bot(
        self,
        testnet: Optional[bool] = None,
        logger=None
    ):
        """
        Crée un bot Bybit complet et configuré.
        
        Cette méthode orchestre l'ensemble du processus:
        1. Création de tous les composants via BotComponentFactory
        2. Configuration de tous les callbacks via BotCallbackConfigurator
        3. Création du BotOrchestrator avec les composants configurés
        4. Retour du BotOrchestrator prêt à démarrer
        
        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
                    Si None, la valeur est lue depuis la configuration
            logger: Logger pour les messages (optionnel)
        
        Returns:
            BotOrchestrator: Bot configuré et prêt à démarrer
        
        Exemple:
            # Création standard
            factory = BotFactory(logger=logger)
            orchestrator = factory.create_bot()
            
            # Démarrer le bot
            await orchestrator.start()
        """
        # Déterminer testnet depuis la configuration si non spécifié
        if testnet is None:
            settings = get_settings()
            testnet = settings["testnet"]
        
        # Utiliser le logger fourni ou celui de l'instance
        active_logger = logger or self.logger
        
        self.logger.info(f"🏭 Création d'un bot Bybit ({'testnet' if testnet else 'mainnet'})...")
        
        try:
            # 1. Créer tous les composants
            self.logger.debug("→ Étape 1/3: Création des composants...")
            component_factory = BotComponentFactory(testnet=testnet, logger=active_logger)
            bundle = component_factory.create_all_components()
            
            # 2. Configurer tous les callbacks
            self.logger.debug("→ Étape 2/3: Configuration des callbacks...")
            callback_configurator = BotCallbackConfigurator(logger=active_logger)
            callback_configurator.configure_all_callbacks(bundle)
            
            # 3. Créer le BotOrchestrator avec les composants configurés
            self.logger.debug("→ Étape 3/3: Création du BotOrchestrator...")
            
            # Import local pour éviter les imports circulaires
            from bot import BotOrchestrator
            
            orchestrator = BotOrchestrator(
                components_bundle=bundle,
                logger=active_logger
            )
            
            self.logger.info("✅ Bot Bybit créé avec succès")
            return orchestrator
            
        except Exception as e:
            self.logger.error(f"❌ Erreur lors de la création du bot: {e}", exc_info=True)
            raise
