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
    data_manager.storage.get_funding_data()   # Accès direct
    data_manager.load_watchlist_data()        # Coordination de haut niveau
"""

from typing import Dict, List, Optional, Tuple, Any
from logging_setup import setup_logging
from volatility_tracker import VolatilityTracker
from data_fetcher import DataFetcher
from data_storage import DataStorage
from data_validator import DataValidator
from models.funding_data import FundingData
from factories.funding_factory import FundingDataFactory


class DataManager:
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
        data_manager.storage.get_funding_data("BTCUSDT")

        # Coordination de haut niveau
        data_manager.load_watchlist_data(url, perp_data, wm, vt)
    """

    def __init__(
        self,
        testnet: bool = True,
        logger=None,
        fetcher: Optional["DataFetcher"] = None,
        storage: Optional["DataStorage"] = None,
        validator: Optional["DataValidator"] = None,
    ):
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

    # ===== MÉTHODES DE COORDINATION =====

    def load_watchlist_data(
        self,
        base_url: str,
        perp_data: Dict,
        watchlist_manager,
        volatility_tracker: VolatilityTracker,
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
        """
        try:
            self.logger.info("📊 Chargement des données de la watchlist...")

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

            self.logger.info("✅ Données de la watchlist chargées avec succès")
            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur chargement watchlist: {e}")
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

    def _update_funding_data(self, funding_data: Dict):
        """Met à jour les données de funding dans le stockage (utilise Value Objects)."""
        self.logger.info(f"🔍 [DEBUG] Mise à jour de {len(funding_data)} symboles de funding")
        
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
        
        self.logger.info(f"✅ [DEBUG] {success_count}/{len(funding_data)} FundingData créés avec succès")

    def _update_original_funding_data(self, watchlist_manager):
        """Met à jour les données originales de funding."""
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