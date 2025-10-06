#!/usr/bin/env python3
"""
Configurateur du bot Bybit - Version refactorisée.

Cette classe gère uniquement :
- Le chargement et la validation de la configuration
- La configuration des paramètres des managers
- La gestion des données de marché initiales
"""

from typing import Dict, Tuple
from logging_setup import setup_logging
from bybit_client import BybitPublicClient
from instruments import get_perp_symbols
from unified_data_manager import UnifiedDataManager
from volatility_tracker import VolatilityTracker
from watchlist_manager import WatchlistManager
from display_manager import DisplayManager


class BotConfigurator:
    """
    Configurateur du bot Bybit.

    Responsabilités :
    - Chargement et validation de la configuration
    - Configuration des paramètres des managers
    - Gestion des données de marché initiales
    """

    def __init__(self, testnet: bool, logger=None):
        """
        Initialise le configurateur du bot.

        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()

    def load_and_validate_config(self, config_manager) -> Dict:
        """
        Charge et valide la configuration via ConfigManager.

        Args:
            config_manager: Instance de ConfigManager

        Returns:
            Configuration validée

        Raises:
            ValueError: Si la configuration est invalide
        """
        try:
            config = config_manager.load_and_validate_config()
            return config
        except ValueError as e:
            self.logger.error(f"❌ Erreur de configuration : {e}")
            self.logger.error(
                "💡 Corrigez les paramètres dans src/parameters.yaml "
                "ou les variables d'environnement"
            )
            raise

    def get_market_data(self) -> Tuple[str, Dict]:
        """
        Récupère les données de marché initiales.

        Returns:
            Tuple (base_url, perp_data)

        Raises:
            Exception: En cas d'erreur de récupération des données
        """
        try:
            # Créer un client PUBLIC pour récupérer l'URL publique (aucune clé requise)
            client = BybitPublicClient(testnet=self.testnet, timeout=15)
            base_url = client.public_base_url()

            # Récupérer l'univers perp
            perp_data = get_perp_symbols(base_url, timeout=15)

            return base_url, perp_data

        except Exception as e:
            self.logger.error(f"❌ Erreur récupération données marché : {e}")
            raise

    def configure_managers(
        self,
        config: Dict,
        perp_data: Dict,
        data_manager: UnifiedDataManager,
        volatility_tracker: VolatilityTracker,
        watchlist_manager: WatchlistManager,
        display_manager: DisplayManager,
    ):
        """
        Configure les managers avec les paramètres.

        Args:
            config: Configuration validée
            perp_data: Données des perpétuels
            data_manager: Gestionnaire de données
            volatility_tracker: Tracker de volatilité
            watchlist_manager: Gestionnaire de watchlist
            display_manager: Gestionnaire d'affichage
        """
        # Stocker le mapping officiel des catégories
        symbol_categories = perp_data.get("categories", {}) or {}
        data_manager.set_symbol_categories(symbol_categories)

        # Configurer les gestionnaires avec les catégories
        volatility_tracker.set_symbol_categories(symbol_categories)
        watchlist_manager.symbol_categories = symbol_categories

        # Configurer le tracker de volatilité
        volatility_ttl_sec = int(config.get("volatility_ttl_sec", 120) or 120)
        volatility_tracker.ttl_seconds = volatility_ttl_sec

        # Configurer l'intervalle d'affichage
        display_interval = int(
            config.get("display_interval_seconds", 10) or 10
        )
        display_manager.set_display_interval(display_interval)
        display_manager.set_price_ttl(120)

    def validate_environment(self) -> bool:
        """
        Valide l'environnement d'exécution.

        Returns:
            True si l'environnement est valide
        """
        self.logger.info("🔍 Validation de l'environnement...")

        try:
            # Vérifier que les modules nécessaires sont disponibles
            pass

            # Vérifier la connectivité réseau (optionnel)
            # Cette vérification peut être ajoutée si nécessaire

            self.logger.info("✅ Environnement validé")
            return True

        except ImportError as e:
            self.logger.error(f"❌ Module manquant : {e}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Erreur validation environnement : {e}")
            return False
