#!/usr/bin/env python3
"""
Intégrateur d'opportunités pour le bot Bybit.

Cette classe est responsable uniquement de :
- L'intégration des nouvelles opportunités détectées dans la watchlist
- La mise à jour des données et listes de symboles
- La gestion de l'ajout de symboles individuels à la watchlist

Responsabilité unique : Intégrer les opportunités dans la watchlist.
"""

from typing import List, Dict, Optional, Callable
from logging_setup import setup_logging
from data_manager import DataManager
from watchlist_manager import WatchlistManager
from instruments import category_of_symbol
from models.funding_data import FundingData
from factories.funding_factory import FundingDataFactory


class OpportunityIntegrator:
    """
    Intégrateur d'opportunités pour le bot Bybit.

    Responsabilités :
    - Intégration des nouvelles opportunités dans la watchlist
    - Mise à jour des données et listes de symboles
    - Gestion de l'ajout de symboles individuels
    """

    def __init__(
        self,
        data_manager: DataManager,
        watchlist_manager: Optional[WatchlistManager] = None,
        logger=None,
    ):
        """
        Initialise l'intégrateur d'opportunités.

        Args:
            data_manager: Gestionnaire de données
            watchlist_manager: Gestionnaire de watchlist (optionnel)
            logger: Logger pour les messages (optionnel)
        """
        self.data_manager = data_manager
        self.watchlist_manager = watchlist_manager
        self.logger = logger or setup_logging()

        # Callback pour les nouvelles opportunités
        self._on_new_opportunity_callback: Optional[Callable] = None

    def set_on_new_opportunity_callback(self, callback: Callable):
        """
        Définit le callback pour les nouvelles opportunités.

        Args:
            callback: Fonction à appeler lors de nouvelles opportunités
        """
        self._on_new_opportunity_callback = callback

    def integrate_opportunities(self, opportunities: Dict):
        """
        Intègre les nouvelles opportunités détectées.

        Args:
            opportunities: Dict avec les opportunités à intégrer
        """
        linear_symbols = opportunities.get("linear", [])
        inverse_symbols = opportunities.get("inverse", [])
        funding_data = opportunities.get("funding_data", {})

        # Récupérer les symboles existants
        existing_linear = set(self.data_manager.storage.get_linear_symbols())
        existing_inverse = set(self.data_manager.storage.get_inverse_symbols())

        # Identifier les nouveaux symboles
        new_linear = set(linear_symbols) - existing_linear
        new_inverse = set(inverse_symbols) - existing_inverse

        if new_linear or new_inverse:
            # Mettre à jour les listes de symboles
            self._update_symbol_lists(linear_symbols, inverse_symbols)

            # Mettre à jour les données de funding
            self._update_funding_data(funding_data)

            # Notifier les nouvelles opportunités
            self._notify_new_opportunities(linear_symbols, inverse_symbols)

    def add_symbol_to_watchlist(
        self,
        symbol: str,
        ticker_data: dict,
        watchlist_manager: WatchlistManager,
    ) -> bool:
        """
        Ajoute un symbole individuel à la watchlist.

        Args:
            symbol: Symbole à ajouter
            ticker_data: Données du ticker
            watchlist_manager: Gestionnaire de watchlist

        Returns:
            bool: True si l'ajout a réussi
        """
        try:
            # Vérifier que le symbole n'est pas déjà dans la watchlist
            if self.data_manager.storage.get_funding_data_object(symbol):
                return False  # Déjà présent

            # Construire les données du symbole
            funding_rate = ticker_data.get("fundingRate")
            volume24h = ticker_data.get("volume24h")
            next_funding_time = ticker_data.get("nextFundingTime")

            if funding_rate is not None:
                # Utiliser la factory centralisée pour créer FundingData
                funding_obj = FundingDataFactory.from_ticker_data(
                    symbol, ticker_data, watchlist_manager
                )

                if funding_obj is None:
                    return False  # Données invalides

                # Ajouter à la watchlist via le DataStorage
                self.data_manager.storage.set_funding_data_object(funding_obj)

                # Ajouter aux listes par catégorie
                category = category_of_symbol(
                    symbol, self.data_manager.storage.symbol_categories
                )
                self.data_manager.storage.add_symbol_to_category(symbol, category)

                # Mettre à jour les données originales
                if next_funding_time:
                    self.data_manager.storage.update_original_funding_data(
                        symbol, next_funding_time
                    )

                self.logger.info(
                    f"✅ Symbole {symbol} ajouté à la watchlist principale"
                )
                return True

        except (ValueError, TypeError) as e:
            self.logger.error(f"❌ Erreur création FundingData pour {symbol}: {e}")
        except Exception as e:
            self.logger.error(f"❌ Erreur ajout symbole {symbol}: {e}")

        return False

    def _update_symbol_lists(self, linear_symbols: List[str], inverse_symbols: List[str]):
        """Met à jour les listes de symboles avec les nouvelles opportunités."""
        # Utiliser la méthode publique de DataManager pour éviter le couplage
        self.data_manager.update_symbol_lists_from_opportunities(
            linear_symbols, inverse_symbols
        )

    def _update_funding_data(self, new_funding_data: Dict):
        """
        Met à jour les données de funding avec les nouvelles opportunités.

        Args:
            new_funding_data: Dictionnaire des données de funding à mettre à jour
        """
        # Utiliser la méthode publique de DataManager pour éviter l'accès aux méthodes privées
        self.data_manager.update_funding_data_from_dict(new_funding_data)

        # Mettre à jour les données originales si disponible
        self._update_original_funding_data()

    def _update_original_funding_data(self):
        """Met à jour les données de funding originales."""
        if not self.watchlist_manager:
            return

        try:
            original_data = self.watchlist_manager.get_original_funding_data()
            for symbol, next_funding_time in original_data.items():
                self.data_manager.storage.update_original_funding_data(
                    symbol, next_funding_time
                )
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur mise à jour données originales: {e}")

    def _notify_new_opportunities(
        self, linear_symbols: List[str], inverse_symbols: List[str]
    ):
        """Notifie les nouvelles opportunités via callback."""
        if self._on_new_opportunity_callback:
            try:
                self._on_new_opportunity_callback(linear_symbols, inverse_symbols)
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Erreur callback nouvelles opportunités: {e}"
                )
