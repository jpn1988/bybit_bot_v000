#!/usr/bin/env python3
"""
Gestionnaire d'affichage pour le bot Bybit avec mécanisme de fallback intelligent.

╔═══════════════════════════════════════════════════════════════════╗
║                    📖 GUIDE DE LECTURE                            ║
╚═══════════════════════════════════════════════════════════════════╝

Ce fichier implémente un gestionnaire d'affichage qui affiche les prix en temps réel
avec un mécanisme de fallback automatique vers les données REST si nécessaire.

🔍 COMPRENDRE CE FICHIER EN 5 MINUTES :

1. Boucle d'affichage (lignes 79-91)
   └─> Affiche le tableau toutes les N secondes

2. Mécanisme de fallback (lignes 120-180)
   └─> WebSocket (temps réel) → REST API (si stale)

3. Calcul du staleness (lignes 140-160)
   └─> Détecte si les données sont trop anciennes

4. Formatage des tableaux (via TableFormatter)
   └─> Affichage formaté avec colonnes alignées

🔄 MÉCANISME DE FALLBACK INTELLIGENT :

Le DisplayManager utilise un système de fallback à 2 niveaux pour garantir
l'affichage de données fraîches même si le WebSocket rencontre des problèmes.

Priorité 1 : Données WebSocket (temps réel)
    ├─> Si disponibles ET récentes (< 120s)
    └─> Utiliser directement (plus rapides, plus précises)

Priorité 2 : Fallback vers REST API
    ├─> Si WebSocket stale (> 120s) OU indisponible
    └─> Récupérer depuis l'API REST (plus lent mais fiable)

Exemple de flux :
    Temps = 0s → WebSocket reçoit BTCUSDT à $43,500
    Temps = 10s → Affichage utilise WebSocket ($43,500) ✅ Frais
    Temps = 60s → Affichage utilise WebSocket ($43,505) ✅ Frais
    Temps = 130s → WebSocket bloqué, aucune mise à jour
    Temps = 140s → Affichage détecte staleness (140s > 120s)
    Temps = 140s → Fallback → Récupère depuis REST API ($43,510) ✅ Frais

Pourquoi ce mécanisme ?
- ✅ Résilience : Continue à afficher même si WebSocket down
- ✅ Précision : Préfère temps réel quand disponible
- ✅ Fiabilité : Garantit des données récentes (< 120s)

⏱️ GESTION DU STALENESS (FRAÎCHEUR DES DONNÉES) :

Le staleness mesure l'ancienneté des données pour décider du fallback.

Calcul :
    staleness = now() - timestamp_dernière_mise_à_jour

Exemple :
    Dernière mise à jour : 10:00:00
    Heure actuelle : 10:02:30
    Staleness : 150 secondes → ⚠️ STALE (> 120s)

Seuils :
- < 120s : ✅ Données FRAÎCHES (utiliser WebSocket)
- >= 120s : ⚠️ Données STALES (fallback REST)

Configuration :
- price_ttl_sec (défaut: 120s) : Seuil de staleness
- Modifiable via set_price_ttl()

📊 INTERVALLE D'AFFICHAGE :

L'affichage est rafraîchi périodiquement dans une boucle asyncio :

display_interval_seconds = 10  # Afficher toutes les 10 secondes (défaut)

Ajustable via set_display_interval() :
- Trop court (< 1s) : Charge CPU, spam de logs
- Trop long (> 60s) : Données semblent figées
- Recommandé : 5-15 secondes

📚 EXEMPLE D'UTILISATION :

```python
from display_manager import DisplayManager

# Créer le manager
display = DisplayManager(data_manager=dm)

# Configurer
display.set_display_interval(10)  # Afficher toutes les 10s
display.set_price_ttl(120)  # Fallback si > 120s

# Démarrer l'affichage (asynchrone)
await display.start_display_loop()

# Attendre...
await asyncio.sleep(300)

# Arrêter
await display.stop_display_loop()
```

🎨 FORMAT DU TABLEAU :

Le tableau affiché contient les colonnes suivantes :
- Symbole : Nom du contrat (BTCUSDT, ETHUSDT, etc.)
- Funding % : Taux de funding (ex: +0.0100%)
- Volume M$ : Volume 24h en millions de dollars
- Spread % : Écart bid/ask en pourcentage
- Volatilité % : Volatilité 5 minutes
- Temps restant : Temps avant le prochain funding

📖 RÉFÉRENCES :
- asyncio tasks: https://docs.python.org/3/library/asyncio-task.html
"""

import asyncio
from typing import Optional, TYPE_CHECKING
from logging_setup import setup_logging
from interfaces.data_manager_interface import DataManagerInterface
from table_formatter import TableFormatter
from config.timeouts import TimeoutConfig

if TYPE_CHECKING:
    from data_manager import DataManager


class DisplayManager:
    """
    Gestionnaire d'affichage avec fallback intelligent WebSocket → REST API.

    Ce gestionnaire affiche périodiquement un tableau des symboles suivis avec
    leurs données en temps réel. Il utilise un mécanisme de fallback automatique
    pour garantir la fraîcheur des données affichées.

    Stratégie de données :
    1. Priorité : Données WebSocket (temps réel) si récentes
    2. Fallback : Données REST API si WebSocket stale ou indisponible
    3. Seuil : 120 secondes par défaut (configurable)

    Responsabilités :
    - Afficher le tableau des symboles périodiquement
    - Détecter et gérer les données stales (anciennes)
    - Fallback automatique vers REST API si nécessaire
    - Formater les données via TableFormatter

    Attributes:
        data_manager (DataManagerInterface): Gestionnaire de données (interface)
        logger: Logger pour les messages
        display_interval_seconds (int): Intervalle d'affichage (défaut: 10s)
        price_ttl_sec (int): Seuil de staleness pour fallback (défaut: 120s)
        _running (bool): État de la boucle d'affichage
        _display_task (asyncio.Task): Tâche d'affichage en cours
        _formatter (TableFormatter): Formateur de tableaux

    Example:
        ```python
        # Créer et configurer
        display = DisplayManager(data_manager=dm)
        display.set_display_interval(10)  # Afficher toutes les 10s
        display.set_price_ttl(120)  # Fallback si > 120s stale

        # Démarrer
        await display.start_display_loop()

        # Arrêter
        await display.stop_display_loop()
        ```

    Note:
        - La boucle d'affichage est non-bloquante (asyncio.Task)
        - Le fallback est transparent pour l'utilisateur
        - Les données REST sont mises en cache dans DataStorage
    """

    def __init__(self, data_manager: DataManagerInterface, logger=None):
        """
        Initialise le gestionnaire d'affichage.

        Args:
            data_manager (DataManagerInterface): Gestionnaire de données (interface)
                                                 Contient storage (WebSocket + REST)
            logger: Logger pour tracer les événements
                   Recommandé : logging.getLogger(__name__)

        Note:
            - display_interval_seconds contrôle la fréquence d'affichage
            - price_ttl_sec contrôle le seuil de fallback
            - Les deux sont configurables via les setters
        """
        self.data_manager = data_manager
        self.logger = logger or setup_logging()

        # Configuration d'affichage
        # Intervalle entre chaque affichage du tableau (en secondes)
        # Valeur recommandée : 5-15s (équilibre entre fraîcheur et spam)
        self.display_interval_seconds = 10

        # Seuil de staleness pour le fallback (en secondes)
        # Si les données WebSocket ont plus de 120s, on bascule sur REST
        # TTL = Time To Live = durée de validité des données
        self.price_ttl_sec = 120

        # État d'affichage
        self._first_display = True
        self._display_task: Optional[asyncio.Task] = None
        self._running = False

        # Formateur de tableaux
        self._formatter = TableFormatter()

        # Filtrage des symboles à afficher (pour mode position unique)
        self._filtered_symbols: Optional[set] = None

    def set_volatility_callback(self, callback: callable):
        """
        Définit le callback pour récupérer la volatilité.

        Args:
            callback: Fonction qui retourne la volatilité pour un symbole
        """
        self._formatter.set_volatility_callback(callback)

    def set_symbol_filter(self, symbols: Optional[set]):
        """
        Définit les symboles à afficher (filtrage).

        Args:
            symbols: Set des symboles à afficher, ou None pour afficher tous
        """
        self._filtered_symbols = symbols
        if symbols:
            self.logger.info(f"🎯 Affichage filtré vers {len(symbols)} symboles: {list(symbols)}")
        else:
            self.logger.info("📊 Affichage de tous les symboles")

    def clear_symbol_filter(self):
        """
        Supprime le filtre de symboles (affiche tous les symboles).
        """
        self._filtered_symbols = None
        self.logger.info("📊 Filtre de symboles supprimé - Affichage de tous les symboles")

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

        # Log de débogage pour vérifier que la tâche est bien créée
        self.logger.debug(f"Tâche d'affichage créée: {self._display_task}")
        self.logger.debug(f"État running: {self._running}")

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
                    await asyncio.wait_for(self._display_task, timeout=TimeoutConfig.DISPLAY_OPERATION)
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
        self.logger.debug("Boucle d'affichage démarrée")

        while self._running:
            # Vérifier immédiatement si on doit s'arrêter
            if not self._running:
                break

            self.logger.debug("Exécution de _print_price_table")
            self._print_price_table()

            # Attendre selon l'intervalle configuré
            await asyncio.sleep(self.display_interval_seconds)

        # Boucle d'affichage arrêtée
        self.logger.debug("Boucle d'affichage arrêtée")

    def _print_price_table(self):
        """
        Affiche le tableau des prix aligné avec funding, volume en millions,
        spread et volatilité.

        Utilise les FundingData Value Objects pour accéder aux données.
        """
        # Si aucune opportunité n'est trouvée, retourner
        # Utiliser la méthode déléguée de DataManagerInterface au lieu d'accéder à .storage
        funding_data_objects = self.data_manager.get_all_funding_data_objects()
        self.logger.debug(f"_print_price_table: {len(funding_data_objects) if funding_data_objects else 0} symboles")

        if not funding_data_objects:
            self.logger.debug("⏳ Aucune donnée de funding disponible - En attente...")
            return

        # Appliquer le filtre de symboles si défini
        if self._filtered_symbols is not None:
            funding_data_objects = {
                symbol: data for symbol, data in funding_data_objects.items()
                if symbol in self._filtered_symbols
            }
            if not funding_data_objects:
                self.logger.debug("⏳ Aucun symbole après filtrage")
                return

        # Pour la compatibilité avec calculate_column_widths qui attend un Dict
        funding_data_keys = funding_data_objects

        # Vérifier si toutes les données sont disponibles avant d'afficher
        # MODIFICATION: Permettre l'affichage même si certaines données manquent
        if not self._formatter.are_all_data_available(
            funding_data_keys, self.data_manager
        ):
            if self._first_display:
                self.logger.info(
                    "⏳ Certaines données de volatilité et spread manquantes - Affichage avec valeurs par défaut"
                )
                self._first_display = False
            # Ne pas retourner - continuer l'affichage avec les données disponibles

        # Calculer les largeurs de colonnes
        col_widths = self._formatter.calculate_column_widths(funding_data_keys)

        # Afficher l'en-tête
        header = self._formatter.format_table_header(col_widths)
        separator = self._formatter.format_table_separator(col_widths)
        print("\n" + header)
        print(separator)

        # Trier les symboles par poids (si disponible) avant affichage
        symbols_to_display = list(funding_data_objects.keys())

        # Essayer de récupérer les poids depuis les données de funding
        try:
            # Trier par poids décroissant si les données contiennent des poids
            symbols_with_weights = []
            for symbol in symbols_to_display:
                funding_data = funding_data_objects[symbol]
                # Vérifier si le FundingData contient un poids
                if hasattr(funding_data, 'weight') and funding_data.weight is not None:
                    symbols_with_weights.append((symbol, funding_data.weight))
                else:
                    # Fallback: utiliser la valeur absolue du funding comme critère de tri
                    funding_rate = funding_data.funding_rate if hasattr(funding_data, 'funding_rate') else 0.0
                    symbols_with_weights.append((symbol, abs(funding_rate)))

            # Trier par poids décroissant
            symbols_with_weights.sort(key=lambda x: x[1], reverse=True)
            symbols_to_display = [symbol for symbol, weight in symbols_with_weights]

        except Exception as e:
            # En cas d'erreur, utiliser l'ordre original
            self.logger.debug(f"Impossible de trier par poids: {e}")
            pass

        # Afficher les données dans l'ordre trié
        for symbol in symbols_to_display:
            row_data = self._formatter.prepare_row_data(
                symbol, self.data_manager
            )
            line = self._formatter.format_table_row(
                symbol, row_data, col_widths
            )
            print(line)

        print()  # Ligne vide après le tableau

    def is_running(self) -> bool:
        """
        Vérifie si le gestionnaire d'affichage est en cours d'exécution.

        Returns:
            True si en cours d'exécution
        """
        return (
            self._running
            and self._display_task
            and not self._display_task.done()
        )
