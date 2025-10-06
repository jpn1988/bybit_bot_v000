#!/usr/bin/env python3
"""
Gestionnaire d'affichage pour le bot Bybit - Version refactorisée.

Cette classe gère uniquement :
- L'affichage des données de prix en temps réel
- La gestion de la boucle d'affichage
- La coordination avec le TableFormatter
"""

import asyncio
from typing import Optional
from logging_setup import setup_logging
from unified_data_manager import UnifiedDataManager
from table_formatter import TableFormatter


class DisplayManager:
    """
    Gestionnaire d'affichage pour le bot Bybit - Version refactorisée.

    Responsabilités :
    - Affichage des données de prix en temps réel
    - Gestion de la boucle d'affichage périodique
    - Coordination avec le TableFormatter
    """

    def __init__(self, data_manager: UnifiedDataManager, logger=None):
        """
        Initialise le gestionnaire d'affichage.

        Args:
            data_manager: Gestionnaire de données
            logger: Logger pour les messages (optionnel)
        """
        self.data_manager = data_manager
        self.logger = logger or setup_logging()

        # Configuration d'affichage
        self.display_interval_seconds = 10
        self.price_ttl_sec = 120

        # État d'affichage
        self._first_display = True
        self._display_task: Optional[asyncio.Task] = None
        self._running = False

        # Formateur de tableaux
        self._formatter = TableFormatter()

    def set_volatility_callback(self, callback: callable):
        """
        Définit le callback pour récupérer la volatilité.

        Args:
            callback: Fonction qui retourne la volatilité pour un symbole
        """
        self._formatter.set_volatility_callback(callback)

    def set_display_interval(self, interval_seconds: int):
        """
        Définit l'intervalle d'affichage.

        Args:
            interval_seconds: Intervalle en secondes
        """
        self.display_interval_seconds = interval_seconds

    def set_price_ttl(self, ttl_seconds: int):
        """
        Définit le TTL des prix.

        Args:
            ttl_seconds: TTL en secondes
        """
        self.price_ttl_sec = ttl_seconds

    async def start_display_loop(self):
        """
        Démarre la boucle d'affichage.
        """
        if self._display_task and not self._display_task.done():
            self.logger.warning("⚠️ DisplayManager déjà en cours d'exécution")
            return

        self._running = True
        self._display_task = asyncio.create_task(self._display_loop())

        self.logger.info("📊 Boucle d'affichage démarrée")

    async def stop_display_loop(self):
        """
        Arrête la boucle d'affichage.
        """
        if not self._running:
            return

        self._running = False
        if self._display_task and not self._display_task.done():
            try:
                self._display_task.cancel()
                # Attendre l'annulation avec timeout
                try:
                    await asyncio.wait_for(self._display_task, timeout=2.0)
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "⚠️ Tâche d'affichage n'a pas pu être annulée dans les temps"
                    )
                except asyncio.CancelledError:
                    pass  # Annulation normale
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur arrêt tâche affichage: {e}")

        self.logger.info("📊 Boucle d'affichage arrêtée")

    async def _display_loop(self):
        """
        Boucle d'affichage avec intervalle configurable.
        """
        while self._running:
            # Vérifier immédiatement si on doit s'arrêter
            if not self._running:
                break

            self._print_price_table()

            # Attendre selon l'intervalle configuré
            await asyncio.sleep(self.display_interval_seconds)

        # Boucle d'affichage arrêtée

    def _print_price_table(self):
        """
        Affiche le tableau des prix aligné avec funding, volume en millions,
        spread et volatilité.
        """
        # Si aucune opportunité n'est trouvée, retourner
        funding_data = self.data_manager.get_all_funding_data()
        if not funding_data:
            if self._first_display:
                self._first_display = False
            return

        # Vérifier si toutes les données sont disponibles avant d'afficher
        if not self._formatter.are_all_data_available(funding_data, self.data_manager):
            if self._first_display:
                self.logger.info(
                    "⏳ En attente des données de volatilité et spread..."
                )
                self._first_display = False
            return

        # Calculer les largeurs de colonnes
        col_widths = self._formatter.calculate_column_widths(funding_data)

        # Afficher l'en-tête
        header = self._formatter.format_table_header(col_widths)
        separator = self._formatter.format_table_separator(col_widths)
        print("\n" + header)
        print(separator)

        # Afficher les données
        for symbol in funding_data.keys():
            row_data = self._formatter.prepare_row_data(symbol, self.data_manager)
            line = self._formatter.format_table_row(symbol, row_data, col_widths)
            print(line)

        print()  # Ligne vide après le tableau

    def is_running(self) -> bool:
        """
        Vérifie si le gestionnaire d'affichage est en cours d'exécution.

        Returns:
            True si en cours d'exécution
        """
        return (self._running and self._display_task and
                not self._display_task.done())
