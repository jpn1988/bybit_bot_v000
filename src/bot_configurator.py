#!/usr/bin/env python3
"""
Configurateur du bot Bybit - Version refactorisée.

🎯 RESPONSABILITÉ : Charger la configuration et récupérer les données de marché

Cette classe est appelée au démarrage par BotOrchestrator pour préparer
tout ce qui est nécessaire avant de construire la watchlist.

📝 CE QUE FAIT CE FICHIER :
1. load_and_validate_config() : Charge parameters.yaml + ENV
   - Charge les paramètres depuis YAML
   - Applique les variables d'environnement
   - Valide la cohérence (ex: funding_min ≤ funding_max)
   - Retourne la configuration validée ou lève ValueError

2. get_market_data() : Récupère les données de marché via API
   - Détermine l'URL de l'API (testnet ou mainnet)
   - Récupère tous les contrats perpétuels
   - Retourne (base_url, perp_data)
   - Exemple: perp_data = {"linear": [...], "inverse": [...], "total": 761}

3. configure_managers() : Configure les managers avec les paramètres
   - Configure data_manager avec symbol_categories
   - Configure volatility_tracker avec TTL du cache
   - Configure watchlist_manager (rien à faire, déjà configuré)
   - Configure display_manager avec intervalle d'affichage

🔗 APPELÉ PAR : bot.py (BotOrchestrator.start(), lignes 114-135)

📚 POUR EN SAVOIR PLUS : Consultez GUIDE_DEMARRAGE_BOT.md
"""

from typing import Dict, Tuple
from logging_setup import setup_logging
from interfaces.bybit_client_interface import BybitClientInterface
from bybit_client import BybitPublicClient
from instruments import get_perp_symbols
from data_manager import DataManager
from volatility_tracker import VolatilityTracker
from watchlist_manager import WatchlistManager
from display_manager import DisplayManager
from config.timeouts import TimeoutConfig


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
            client: BybitClientInterface = BybitPublicClient(testnet=self.testnet, timeout=TimeoutConfig.HTTP_REQUEST)
            base_url = client.public_base_url()

            # Récupérer l'univers perp
            perp_data = get_perp_symbols(base_url, timeout=TimeoutConfig.HTTP_REQUEST)

            return base_url, perp_data

        except Exception as e:
            self.logger.error(f"❌ Erreur récupération données marché : {e}")
            raise

    def configure_managers(
        self,
        config: Dict,
        perp_data: Dict,
        data_manager: DataManager,
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
        data_manager.storage.set_symbol_categories(symbol_categories)

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

