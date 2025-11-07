#!/usr/bin/env python3
"""
Gestionnaire de données unifié pour le bot Bybit - Version simplifiée.

Cette classe expose les composants spécialisés via des propriétés publiques
et ne garde que les méthodes de coordination de haut niveau :
- fetcher : Récupération des données de marché (DataFetcher)
- storage : Stockage thread-safe des données (DataStorage)
- validator : Validation de l'intégrité des données (DataValidator)

Architecture simplifiée :
    data_manager.fetcher.fetch_funding_map()  # Accès direct
    data_manager.storage.get_funding_data_object()   # Accès direct
    data_manager.load_watchlist_data()        # Coordination de haut niveau
"""

# ============================================================================
# IMPORTS STANDARD LIBRARY
# ============================================================================
from typing import Dict, List, Optional, Tuple, Any, Union, TYPE_CHECKING

# ============================================================================
# IMPORTS CONFIGURATION ET UTILITAIRES
# ============================================================================
from logging_setup import setup_logging
from utils.validators import validate_string_param, validate_dict_param

# ============================================================================
# IMPORTS COMPOSANTS DE DONNÉES
# ============================================================================
from data_fetcher import DataFetcher
from data_storage import DataStorage
from data_validator import DataValidator

# ============================================================================
# IMPORTS MODELS ET FACTORIES
# ============================================================================
from models.funding_data import FundingData
from factories.funding_factory import FundingDataFactory

# ============================================================================
# IMPORTS INTERFACES
# ============================================================================
from interfaces.data_manager_interface import DataManagerInterface

# ============================================================================
# IMPORTS TYPE CHECKING (Éviter les imports circulaires)
# ============================================================================
if TYPE_CHECKING:
    from typing_imports import WatchlistManager, VolatilityTracker


class DataManager(DataManagerInterface):
    """
    Gestionnaire de données pour le bot Bybit - Version simplifiée.

    Cette classe coordonne les opérations de haut niveau et expose les
    composants spécialisés via des propriétés publiques pour un accès direct.

    Composants exposés :
    - fetcher : Récupération des données de marché (DataFetcher)
    - storage : Stockage thread-safe des données (DataStorage)
    - validator : Validation de l'intégrité des données (DataValidator)

    Exemple d'utilisation :
        # Accès direct aux composants
        data_manager.fetcher.fetch_funding_map(url, "linear", 10)
        data_manager.storage.get_funding_data_object("BTCUSDT")

        # Coordination de haut niveau
        data_manager.load_watchlist_data(url, perp_data, wm, vt)
    """

    def __init__(
        self,
        testnet: bool = True,
        logger: Optional[Any] = None,
        fetcher: Optional["DataFetcher"] = None,
        storage: Optional["DataStorage"] = None,
        validator: Optional["DataValidator"] = None,
    ) -> None:
        """
        Initialise le gestionnaire de données unifié.

        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
            fetcher: Composant de récupération de données (optionnel, créé
            automatiquement si non fourni)
            storage: Composant de stockage de données (optionnel, créé
            automatiquement si non fourni)
            validator: Composant de validation de données (optionnel, créé
            automatiquement si non fourni)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()

        # Initialiser les composants spécialisés (injection avec fallback)
        self._fetcher = fetcher or DataFetcher(logger=self.logger)
        self._storage = storage or DataStorage(logger=self.logger)
        self._validator = validator or DataValidator(logger=self.logger)

    # ===== PROPRIÉTÉS D'ACCÈS DIRECT AUX COMPOSANTS =====

    @property
    def fetcher(self) -> DataFetcher:
        """
        Accès direct au composant de récupération de données.

        Returns:
            DataFetcher: Instance du récupérateur de données
        """
        return self._fetcher

    @property
    def storage(self) -> DataStorage:
        """
        Accès direct au composant de stockage de données.

        Returns:
            DataStorage: Instance du stockage de données
        """
        return self._storage

    @property
    def validator(self) -> DataValidator:
        """
        Accès direct au composant de validation de données.

        Returns:
            DataValidator: Instance du validateur de données
        """
        return self._validator

    # ===== MÉTHODES DÉLÉGUÉES POUR DÉCOUPLAGE =====

    def get_linear_symbols(self) -> List[str]:
        """
        Récupère la liste des symboles linear.

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Returns:
            List[str]: Liste des symboles linear (copie pour éviter les modifications)
        """
        return self._storage.get_linear_symbols()

    def get_inverse_symbols(self) -> List[str]:
        """
        Récupère la liste des symboles inverse.

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Returns:
            List[str]: Liste des symboles inverse (copie pour éviter les modifications)
        """
        return self._storage.get_inverse_symbols()

    def get_all_funding_data_objects(self) -> Dict[str, "FundingData"]:
        """
        Récupère toutes les données de funding en tant que Value Objects.

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Returns:
            Dict[str, FundingData]: Dictionnaire {symbol: FundingData} (copie pour éviter les modifications)
        """
        return self._storage.get_all_funding_data_objects()

    def get_funding_data_object(self, symbol: str) -> Optional["FundingData"]:
        """
        Récupère un FundingData Value Object pour un symbole.

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Args:
            symbol: Symbole à récupérer

        Returns:
            FundingData ou None si absent
        """
        return self._storage.get_funding_data_object(symbol)

    def set_funding_data_object(self, funding_data: "FundingData") -> None:
        """
        Stocke un FundingData Value Object pour un symbole.

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Args:
            funding_data: Objet FundingData à stocker
        """
        self._storage.set_funding_data_object(funding_data)

    def update_original_funding_data(self, symbol: str, next_funding_time: str) -> None:
        """
        Met à jour les données de funding originales pour un symbole.

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Args:
            symbol: Symbole à mettre à jour
            next_funding_time: Temps du prochain funding
        """
        self._storage.update_original_funding_data(symbol, next_funding_time)

    def get_symbol_categories(self) -> Dict[str, str]:
        """
        Récupère le mapping des catégories de symboles.

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Returns:
            Dict[str, str]: Dictionnaire {symbol: category}
        """
        return self._storage.symbol_categories.copy()

    def add_symbol_to_category(self, symbol: str, category: str) -> None:
        """
        Ajoute un symbole à une catégorie.

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Args:
            symbol: Symbole à ajouter
            category: Catégorie ("linear" ou "inverse")
        """
        self._storage.add_symbol_to_category(symbol, category)

    def remove_symbol_from_category(self, symbol: str, category: str) -> None:
        """Retire un symbole d'une catégorie dans le stockage."""
        self._storage.remove_symbol_from_category(symbol, category)

    def set_symbol_lists(self, linear_symbols: List[str], inverse_symbols: List[str]) -> None:
        """Définit explicitement les listes de symboles linear/inverse."""
        self._storage.set_symbol_lists(linear_symbols, inverse_symbols)

    def get_all_symbols(self) -> List[str]:
        """Retourne tous les symboles connus, toutes catégories confondues."""
        return self._storage.get_all_symbols()

    def get_data_stats(self) -> Dict[str, int]:
        """Expose les statistiques de stockage (funding, realtime, symboles)."""
        return self._storage.get_data_stats()

    def clear_all_data(self) -> None:
        """Vide complètement le stockage (funding, realtime, symboles)."""
        self._storage.clear_all_data()

    def update_realtime_data(self, symbol: str, ticker_data: Dict[str, Any]) -> None:
        """Met à jour les données temps réel pour un symbole donné."""
        self._storage.update_realtime_data(symbol, ticker_data)

    def get_realtime_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Retourne les données temps réel pour un symbole donné."""
        return self._storage.get_realtime_data(symbol)

    def update_price_data(
        self,
        symbol: str,
        mark_price: float,
        last_price: float,
        timestamp: float,
    ) -> None:
        """
        Met à jour les prix pour un symbole donné (compatibilité avec price_store.py).

        Cette méthode délègue à storage pour éviter l'accès direct à .storage.

        Args:
            symbol: Symbole du contrat (ex: BTCUSDT)
            mark_price: Prix de marque
            last_price: Dernier prix de transaction
            timestamp: Timestamp de la mise à jour
        """
        self._storage.update_price_data(symbol, mark_price, last_price, timestamp)

    # ===== MÉTHODES DE VALIDATION =====

    # Les méthodes de validation sont maintenant déléguées à utils.validators
    # pour éviter la duplication de code

    # ===== CONTEXT MANAGER SUPPORT =====

    def __enter__(self):
        """
        Context manager entry point pour DataManager.

        Initialise les ressources de données si nécessaire.

        Returns:
            DataManager: Instance du gestionnaire de données
        """
        self.logger.debug("📊 Entrée dans le contexte DataManager")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit point pour DataManager.

        Nettoie les ressources de données si nécessaire.

        Args:
            exc_type: Type d'exception (None si pas d'exception)
            exc_val: Valeur de l'exception
            exc_tb: Traceback de l'exception

        Returns:
            bool: False pour propager les exceptions
        """
        self.logger.debug("📊 Sortie du contexte DataManager")

        # Nettoyage des ressources si nécessaire
        try:
            # Ici on pourrait ajouter du nettoyage spécifique si nécessaire
            pass
        except Exception as e:
            self.logger.warning("⚠️ Erreur lors du nettoyage DataManager: {}", str(e))

        return False

    async def __aenter__(self):
        """
        Context manager asynchrone entry point pour DataManager.

        Initialise les ressources de données de manière asynchrone si nécessaire.

        Returns:
            DataManager: Instance du gestionnaire de données
        """
        self.logger.debug("📊 Entrée dans le contexte asynchrone DataManager")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager asynchrone exit point pour DataManager.

        Nettoie les ressources de données de manière asynchrone si nécessaire.

        Args:
            exc_type: Type d'exception (None si pas d'exception)
            exc_val: Valeur de l'exception
            exc_tb: Traceback de l'exception

        Returns:
            bool: False pour propager les exceptions
        """
        self.logger.debug("📊 Sortie du contexte asynchrone DataManager")

        # Nettoyage asynchrone des ressources si nécessaire
        try:
            # Ici on pourrait ajouter du nettoyage asynchrone spécifique si nécessaire
            pass
        except Exception as e:
            self.logger.warning("⚠️ Erreur lors du nettoyage asynchrone DataManager: {}", str(e))

        return False

    # ===== MÉTHODES DE COORDINATION =====

    def load_watchlist_data(
        self,
        base_url: str,
        perp_data: Dict[str, Any],
        watchlist_manager: "WatchlistManager",
        volatility_tracker: "VolatilityTracker",
    ) -> bool:
        """
        Interface pour charger les données de la watchlist via WatchlistManager.

        Cette méthode coordonne le chargement des données de la watchlist
        en utilisant les composants spécialisés.

        Args:
            base_url: URL de base de l'API
            perp_data: Données des perpétuels
            watchlist_manager: Gestionnaire de watchlist (WatchlistManager)
            volatility_tracker: Tracker de volatilité

        Returns:
            bool: True si le chargement a réussi

        Raises:
            ValueError: Si les paramètres sont invalides
            TypeError: Si les types de paramètres sont incorrects
        """
        # Validation des paramètres
        validate_string_param('base_url', base_url)
        validate_dict_param('perp_data', perp_data)

        if watchlist_manager is None:
            raise ValueError("Le paramètre 'watchlist_manager' ne peut pas être None")
        if volatility_tracker is None:
            raise ValueError("Le paramètre 'volatility_tracker' ne peut pas être None")

        try:
            self.logger.info("📊 Chargement des données de la watchlist... (URL: {}, symboles: {})",
                            base_url, len(perp_data) if perp_data else 0)

            # 1. Valider les paramètres d'entrée
            if not self._validate_input_parameters(
                base_url, perp_data, watchlist_manager, volatility_tracker
            ):
                return False

            # 2. Construire la watchlist
            watchlist_data = self._build_watchlist(
                base_url, perp_data, watchlist_manager, volatility_tracker
            )
            if not watchlist_data:
                return False

            # 3. Mettre à jour les données
            self._update_data_from_watchlist(watchlist_data, watchlist_manager)

            # 4. Valider l'intégrité des données
            if not self._validate_loaded_data():
                return False

            self.logger.info("✅ Données de la watchlist chargées avec succès (symboles: %d, funding: %d)",
                            len(watchlist_manager.get_selected_symbols()),
                            len(self.storage.get_all_funding_data_objects()))
            return True

        except Exception as e:
            self.logger.error("❌ Erreur chargement watchlist: {} (étape: {})",
                             str(e), "validation" if "validate" in str(e) else "chargement")
            return False

    def _validate_input_parameters(
        self, base_url: str, perp_data: Dict, watchlist_manager, volatility_tracker
    ) -> bool:
        """Valide les paramètres d'entrée pour le chargement."""
        if not base_url or not isinstance(base_url, str):
            self.logger.error("❌ URL de base invalide")
            return False

        if not perp_data or not isinstance(perp_data, dict):
            self.logger.error("❌ Données perpétuels invalides")
            return False

        if not watchlist_manager:
            self.logger.error("❌ Gestionnaire de watchlist manquant")
            return False

        if not volatility_tracker:
            self.logger.error("❌ Tracker de volatilité manquant")
            return False

        return True

    def _build_watchlist(
        self, base_url: str, perp_data: Dict, watchlist_manager, volatility_tracker
    ) -> Optional[Tuple[List[str], List[str], Dict]]:
        """Construit la watchlist via le gestionnaire."""
        try:
            linear_symbols, inverse_symbols, funding_data = watchlist_manager.build_watchlist(
                base_url, perp_data, volatility_tracker
            )

            if not linear_symbols and not inverse_symbols:
                self.logger.warning("⚠️ Aucun symbole trouvé pour la watchlist")
                return None

            return linear_symbols, inverse_symbols, funding_data

        except Exception as e:
            self.logger.error(f"❌ Erreur construction watchlist: {e}")
            return None

    def _update_data_from_watchlist(
        self, watchlist_data: Tuple[List[str], List[str], Dict], watchlist_manager
    ):
        """Met à jour les données à partir de la watchlist."""
        linear_symbols, inverse_symbols, funding_data = watchlist_data

        # Mettre à jour les listes de symboles
        self.storage.set_symbol_lists(linear_symbols, inverse_symbols)

        # Mettre à jour les données de funding
        self._update_funding_data(funding_data)

        # Mettre à jour les données originales
        self._update_original_funding_data(watchlist_manager)

    def _update_funding_data(self, funding_data: Dict[str, Any]) -> None:
        """
        Met à jour les données de funding dans le stockage (utilise Value Objects).

        Cette méthode traite les données de funding brutes et les convertit
        en objets FundingData via la factory centralisée. Elle gère les erreurs
        de conversion et calcule les statistiques de succès.

        Args:
            funding_data: Dict des données de funding brutes par symbole

        Side effects:
            - Met à jour le stockage avec les nouveaux objets FundingData
            - Log les erreurs de conversion individuelles
            - Calcule et log les statistiques de succès
        """
        self.logger.info("🔍 Mise à jour des données de funding (symboles: {}, source: {})",
                        len(funding_data), "API" if funding_data else "cache")

        success_count = 0
        for symbol, data in funding_data.items():
            try:
                # Utiliser la factory centralisée pour créer FundingData
                funding_obj = FundingDataFactory.from_raw_data(symbol, data)

                if funding_obj is not None:
                    # Stocker le Value Object
                    self.storage.set_funding_data_object(funding_obj)
                    success_count += 1
                else:
                    self.logger.warning(f"⚠️ Données invalides pour {symbol}: format non supporté - data={data}")

            except Exception as e:
                self.logger.warning(f"⚠️ Erreur création FundingData pour {symbol}: {e}")

        self.logger.info("✅ FundingData créés avec succès ({}/{}, taux: {:.1f}%)",
                        success_count, len(funding_data),
                        (success_count / len(funding_data) * 100) if funding_data else 0)

    def _update_original_funding_data(self, watchlist_manager: "WatchlistManager") -> None:
        """
        Met à jour les données originales de funding.

        Cette méthode synchronise les données de funding originales
        entre le WatchlistManager et le DataStorage pour maintenir
        la cohérence des données.

        Args:
            watchlist_manager: Instance du WatchlistManager

        Side effects:
            - Met à jour le stockage avec les données originales
            - Log les erreurs de synchronisation
        """
        try:
            original_data = watchlist_manager.get_original_funding_data()
            for symbol, next_funding_time in original_data.items():
                self.storage.update_original_funding_data(symbol, next_funding_time)
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur mise à jour données originales: {e}")

    def _validate_loaded_data(self) -> bool:
        """Valide l'intégrité des données chargées (utilise Value Objects)."""
        linear_symbols = self.storage.get_linear_symbols()
        inverse_symbols = self.storage.get_inverse_symbols()
        funding_data_objects = self.storage.get_all_funding_data_objects()

        # Convertir les Value Objects en tuples pour la validation (compatibilité)
        funding_data = {
            symbol: obj.to_tuple()
            for symbol, obj in funding_data_objects.items()
        }

        return self.validator.validate_data_integrity(
            linear_symbols, inverse_symbols, funding_data
        )

    def update_funding_data_from_dict(self, funding_data: Dict):
        """
        Met à jour les données de funding depuis un dictionnaire externe.

        Cette méthode publique permet aux autres managers de mettre à jour
        les données de funding sans accéder aux méthodes privées.

        Args:
            funding_data: Dictionnaire des données de funding à mettre à jour
        """
        self._update_funding_data(funding_data)

    def update_symbol_lists_from_opportunities(
        self,
        linear_symbols: List[str],
        inverse_symbols: List[str]
    ):
        """
        Met à jour les listes de symboles avec de nouvelles opportunités.

        Cette méthode publique permet aux autres managers de mettre à jour
        les listes de symboles sans accéder aux méthodes privées.

        Args:
            linear_symbols: Nouveaux symboles linear
            inverse_symbols: Nouveaux symboles inverse
        """
        # Récupérer les symboles existants
        existing_linear = set(self.storage.get_linear_symbols())
        existing_inverse = set(self.storage.get_inverse_symbols())

        # Fusionner les listes
        all_linear = list(existing_linear | set(linear_symbols))
        all_inverse = list(existing_inverse | set(inverse_symbols))

        # Mettre à jour dans le storage
        self.storage.set_symbol_lists(all_linear, all_inverse)

    def get_loading_summary(self) -> Dict[str, Any]:
        """
        Retourne un résumé du chargement des données.

        Cette méthode délègue au validator pour construire le résumé
        à partir des données stockées.

        Returns:
            Dict[str, Any]: Résumé des données chargées avec les statistiques
        """
        try:
            # Récupérer les données du storage
            linear_symbols = self.storage.get_linear_symbols()
            inverse_symbols = self.storage.get_inverse_symbols()
            funding_data_objects = self.storage.get_all_funding_data_objects()

            # Convertir les Value Objects en tuples pour la compatibilité
            funding_data = {
                symbol: obj.to_tuple()
                for symbol, obj in funding_data_objects.items()
            }

            # Déléguer au validator pour construire le résumé
            return self.validator.get_loading_summary(
                linear_symbols,
                inverse_symbols,
                funding_data
            )

        except Exception as e:
            self.logger.error(f"❌ Erreur récupération résumé chargement: {e}")
            return {
                "linear_count": 0,
                "inverse_count": 0,
                "total_symbols": 0,
                "funding_data_count": 0,
                "error": str(e),
            }
