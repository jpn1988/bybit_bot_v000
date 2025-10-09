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
try:
    from .logging_setup import setup_logging
    from .volatility_tracker import VolatilityTracker
    from .data_fetcher import DataFetcher
    from .data_storage import DataStorage
    from .data_validator import DataValidator
    from .models.funding_data import FundingData
except ImportError:
    from logging_setup import setup_logging
    from volatility_tracker import VolatilityTracker
    from data_fetcher import DataFetcher
    from data_storage import DataStorage
    from data_validator import DataValidator
    from models.funding_data import FundingData


class UnifiedDataManager:
    """
    Gestionnaire de données unifié pour le bot Bybit - Version simplifiée.

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

    def __init__(self, testnet: bool = True, logger=None):
        """
        Initialise le gestionnaire de données unifié.

        Args:
            testnet: Utiliser le testnet (True) ou le marché réel (False)
            logger: Logger pour les messages (optionnel)
        """
        self.testnet = testnet
        self.logger = logger or setup_logging()

        # Initialiser les composants spécialisés (accès public via properties)
        self._fetcher = DataFetcher(logger=logger)
        self._storage = DataStorage(logger=logger)
        self._validator = DataValidator(logger=logger)

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
        for symbol, data in funding_data.items():
            try:
                # Créer un FundingData Value Object
                if isinstance(data, (list, tuple)) and len(data) >= 4:
                    # Format tuple: (funding, volume, funding_time, spread, volatility?)
                    funding, volume, funding_time, spread = data[:4]
                    volatility = data[4] if len(data) > 4 else None
                    
                    funding_obj = FundingData(
                        symbol=symbol,
                        funding_rate=funding,
                        volume_24h=volume,
                        next_funding_time=funding_time,
                        spread_pct=spread,
                        volatility_pct=volatility
                    )
                    
                elif isinstance(data, dict):
                    # Format dict: {funding, volume, funding_time_remaining, spread_pct, volatility_pct}
                    funding = data.get("funding", 0.0)
                    volume = data.get("volume", 0.0)
                    funding_time = data.get("funding_time_remaining", "-")
                    spread = data.get("spread_pct", 0.0)
                    volatility = data.get("volatility_pct", None)
                    
                    funding_obj = FundingData(
                        symbol=symbol,
                        funding_rate=funding,
                        volume_24h=volume,
                        next_funding_time=funding_time,
                        spread_pct=spread,
                        volatility_pct=volatility
                    )
                else:
                    continue
                
                # Stocker le Value Object
                self.storage.set_funding_data_object(funding_obj)
                
            except (ValueError, TypeError) as e:
                self.logger.warning(f"⚠️ Erreur création FundingData pour {symbol}: {e}")

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

    def get_loading_summary(self) -> Dict[str, Any]:
        """
        Retourne un résumé du chargement des données (utilise Value Objects).

        Returns:
            Dict[str, Any]: Résumé des données chargées
        """
        linear_symbols = self.storage.get_linear_symbols()
        inverse_symbols = self.storage.get_inverse_symbols()
        funding_data_objects = self.storage.get_all_funding_data_objects()
        
        # Convertir les Value Objects en tuples pour le résumé (compatibilité)
        funding_data = {
            symbol: obj.to_tuple() 
            for symbol, obj in funding_data_objects.items()
        }

        return self.validator.get_loading_summary(
            linear_symbols, inverse_symbols, funding_data
        )

    # ===== ALIAS DE COMPATIBILITÉ (DÉLÉGATION VERS LES COMPOSANTS) =====
    # Les méthodes ci-dessous sont des alias pour maintenir la compatibilité
    # avec l'ancien code. Préférez l'accès direct via les propriétés :
    # data_manager.fetcher.fetch_funding_map() au lieu de data_manager.fetch_funding_map()
    # data_manager.storage.get_funding_data() au lieu de data_manager.get_funding_data()

    def fetch_funding_map(self, base_url: str, category: str, timeout: int = 10) -> Dict[str, Dict]:
        """Alias de compatibilité → Préférez: data_manager.fetcher.fetch_funding_map()"""
        return self.fetcher.fetch_funding_map(base_url, category, timeout)

    def fetch_spread_data(self, base_url: str, symbols: List[str], timeout: int = 10, category: str = "linear") -> Dict[str, float]:
        """Alias de compatibilité → Préférez: data_manager.fetcher.fetch_spread_data()"""
        return self.fetcher.fetch_spread_data(base_url, symbols, timeout, category)

    def fetch_funding_data_parallel(self, base_url: str, categories: List[str], timeout: int = 10) -> Dict[str, Dict]:
        """Alias de compatibilité → Préférez: data_manager.fetcher.fetch_funding_data_parallel()"""
        return self.fetcher.fetch_funding_data_parallel(base_url, categories, timeout)

    def set_symbol_categories(self, symbol_categories: Dict[str, str]):
        """Alias de compatibilité → Préférez: data_manager.storage.set_symbol_categories()"""
        self.storage.set_symbol_categories(symbol_categories)

    def update_funding_data(self, symbol: str, funding: float, volume: float, funding_time: str, spread: float, volatility: Optional[float] = None):
        """
        Alias de compatibilité (DÉPRÉCIÉ) → Préférez: data_manager.storage.set_funding_data_object()
        
        Cette méthode crée automatiquement un FundingData Value Object.
        """
        try:
            funding_obj = FundingData(
                symbol=symbol,
                funding_rate=funding,
                volume_24h=volume,
                next_funding_time=funding_time,
                spread_pct=spread,
                volatility_pct=volatility
            )
            self.storage.set_funding_data_object(funding_obj)
        except (ValueError, TypeError) as e:
            self.logger.warning(f"⚠️ Erreur création FundingData pour {symbol}: {e}")

    def get_funding_data(self, symbol: str) -> Optional[Tuple[float, float, str, float, Optional[float]]]:
        """
        Alias de compatibilité (DÉPRÉCIÉ) → Préférez: data_manager.storage.get_funding_data_object()
        
        Cette méthode retourne un tuple pour compatibilité avec l'ancien code.
        """
        funding_obj = self.storage.get_funding_data_object(symbol)
        return funding_obj.to_tuple() if funding_obj else None

    def get_all_funding_data(self) -> Dict[str, Tuple[float, float, str, float, Optional[float]]]:
        """
        Alias de compatibilité (DÉPRÉCIÉ) → Préférez: data_manager.storage.get_all_funding_data_objects()
        
        Cette méthode retourne des tuples pour compatibilité avec l'ancien code.
        """
        funding_data_objects = self.storage.get_all_funding_data_objects()
        return {
            symbol: obj.to_tuple() 
            for symbol, obj in funding_data_objects.items()
        }
    
    # ===== NOUVELLES MÉTHODES UTILISANT LES VALUE OBJECTS =====
    
    def set_funding_data_object(self, funding_data: FundingData):
        """Stocke un FundingData Value Object → Préférez: data_manager.storage.set_funding_data_object()"""
        self.storage.set_funding_data_object(funding_data)
    
    def get_funding_data_object(self, symbol: str) -> Optional[FundingData]:
        """Récupère un FundingData Value Object → Préférez: data_manager.storage.get_funding_data_object()"""
        return self.storage.get_funding_data_object(symbol)
    
    def get_all_funding_data_objects(self) -> Dict[str, FundingData]:
        """Récupère tous les FundingData Value Objects → Préférez: data_manager.storage.get_all_funding_data_objects()"""
        return self.storage.get_all_funding_data_objects()

    def update_realtime_data(self, symbol: str, ticker_data: Dict[str, Any]):
        """Alias de compatibilité → Préférez: data_manager.storage.update_realtime_data()"""
        self.storage.update_realtime_data(symbol, ticker_data)

    def update_price_data(self, symbol: str, mark_price: float, last_price: float, timestamp: float):
        """Alias de compatibilité → Préférez: data_manager.storage.update_price_data()"""
        self.storage.update_price_data(symbol, mark_price, last_price, timestamp)

    def get_price_data(self, symbol: str) -> Optional[Dict[str, float]]:
        """Alias de compatibilité → Préférez: data_manager.storage.get_price_data()"""
        return self.storage.get_price_data(symbol)

    def get_realtime_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Alias de compatibilité → Préférez: data_manager.storage.get_realtime_data()"""
        return self.storage.get_realtime_data(symbol)

    def get_all_realtime_data(self) -> Dict[str, Dict[str, Any]]:
        """Alias de compatibilité → Préférez: data_manager.storage.get_all_realtime_data()"""
        return self.storage.get_all_realtime_data()

    def update_original_funding_data(self, symbol: str, next_funding_time: str):
        """Alias de compatibilité → Préférez: data_manager.storage.update_original_funding_data()"""
        self.storage.update_original_funding_data(symbol, next_funding_time)

    def get_original_funding_data(self, symbol: str) -> Optional[str]:
        """Alias de compatibilité → Préférez: data_manager.storage.get_original_funding_data()"""
        return self.storage.get_original_funding_data(symbol)

    def get_all_original_funding_data(self) -> Dict[str, str]:
        """Alias de compatibilité → Préférez: data_manager.storage.get_all_original_funding_data()"""
        return self.storage.get_all_original_funding_data()

    def set_symbol_lists(self, linear_symbols: List[str], inverse_symbols: List[str]):
        """Alias de compatibilité → Préférez: data_manager.storage.set_symbol_lists()"""
        self.storage.set_symbol_lists(linear_symbols, inverse_symbols)

    def get_linear_symbols(self) -> List[str]:
        """Alias de compatibilité → Préférez: data_manager.storage.get_linear_symbols()"""
        return self.storage.get_linear_symbols()

    def get_inverse_symbols(self) -> List[str]:
        """Alias de compatibilité → Préférez: data_manager.storage.get_inverse_symbols()"""
        return self.storage.get_inverse_symbols()

    def get_all_symbols(self) -> List[str]:
        """Alias de compatibilité → Préférez: data_manager.storage.get_all_symbols()"""
        return self.storage.get_all_symbols()

    def add_symbol_to_category(self, symbol: str, category: str):
        """Alias de compatibilité → Préférez: data_manager.storage.add_symbol_to_category()"""
        self.storage.add_symbol_to_category(symbol, category)

    def remove_symbol_from_category(self, symbol: str, category: str):
        """Alias de compatibilité → Préférez: data_manager.storage.remove_symbol_from_category()"""
        self.storage.remove_symbol_from_category(symbol, category)

    def clear_all_data(self):
        """Alias de compatibilité → Préférez: data_manager.storage.clear_all_data()"""
        self.storage.clear_all_data()

    def get_data_stats(self) -> Dict[str, int]:
        """Alias de compatibilité → Préférez: data_manager.storage.get_data_stats()"""
        return self.storage.get_data_stats()

    def validate_data_integrity(self) -> bool:
        """Alias de compatibilité → Préférez: data_manager.storage.validate_data_integrity()"""
        return self.storage.validate_data_integrity()

    # ===== PROPRIÉTÉS LEGACY POUR LA COMPATIBILITÉ =====
    # Propriétés historiques maintenues pour l'ancien code

    @property
    def symbol_categories(self) -> Dict[str, str]:
        """Propriété legacy → Préférez: data_manager.storage.symbol_categories"""
        return self.storage.symbol_categories

    @property
    def linear_symbols(self) -> List[str]:
        """Propriété legacy → Préférez: data_manager.storage.linear_symbols"""
        return self.storage.linear_symbols

    @property
    def inverse_symbols(self) -> List[str]:
        """Propriété legacy → Préférez: data_manager.storage.inverse_symbols"""
        return self.storage.inverse_symbols

    @property
    def funding_data(self) -> Dict:
        """Propriété legacy → Préférez: data_manager.storage.funding_data"""
        return self.storage.funding_data

    @property
    def realtime_data(self) -> Dict:
        """Propriété legacy → Préférez: data_manager.storage.realtime_data"""
        return self.storage.realtime_data