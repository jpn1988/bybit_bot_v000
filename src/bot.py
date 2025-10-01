#!/usr/bin/env python3
"""
🚀 Orchestrateur du bot (filters + WebSocket prix) - VERSION REFACTORISÉE

Script pour filtrer les contrats perpétuels par funding ET suivre leurs prix en temps réel.

Architecture modulaire :
- WatchlistManager : Gestion des filtres et sélection de symboles
- WebSocketManager : Gestion des connexions WebSocket publiques  
- VolatilityTracker : Calcul et cache de volatilité
- PriceTracker : Orchestration et affichage

Usage:
    python src/bot.py
"""

import os
import time
import signal
import threading
import atexit
from typing import List, Dict, Optional
from logging_setup import setup_logging, log_startup_summary, log_shutdown_summary
from config import get_settings
from bybit_client import BybitPublicClient
from instruments import get_perp_symbols, category_of_symbol
from price_store import get_snapshot, purge_expired
from volatility_tracker import VolatilityTracker
from watchlist_manager import WatchlistManager
from ws_manager import WebSocketManager
from errors import NoSymbolsError
from metrics_monitor import start_metrics_monitoring
from http_client_manager import close_all_http_clients


class PriceTracker:
    """Suivi des prix en temps réel via WebSocket avec filtrage par funding."""
    
    def __init__(self):
        self.logger = setup_logging()
        self.running = True
        
        # S'assurer que les clients HTTP sont fermés à l'arrêt
        atexit.register(close_all_http_clients)
        self.display_thread = None
        self.symbols = []
        self.funding_data = {}
        self.original_funding_data = {}  # Données de funding originales avec next_funding_time
        # self.start_time supprimé: on s'appuie uniquement sur nextFundingTime côté Bybit
        # Données en temps réel via WebSocket
        # Format: {symbol: {funding_rate, volume24h, bid1, ask1, next_funding_time, ...}}
        self.realtime_data = {}
        self._realtime_lock = threading.Lock()  # Verrou pour protéger realtime_data
        self._first_display = True  # Indicateur pour la première exécution de l'affichage
        self.symbol_categories: dict[str, str] = {}
        
        # Configuration
        settings = get_settings()
        self.testnet = settings['testnet']
        
        # Gestionnaire WebSocket dédié
        self.ws_manager = WebSocketManager(testnet=self.testnet, logger=self.logger)
        self.ws_manager.set_ticker_callback(self._update_realtime_data_from_ticker)
        
        # Gestionnaire de volatilité dédié
        self.volatility_tracker = VolatilityTracker(testnet=self.testnet, logger=self.logger)
        self.volatility_tracker.set_active_symbols_callback(self._get_active_symbols)
        
        # Gestionnaire de watchlist dédié
        self.watchlist_manager = WatchlistManager(testnet=self.testnet, logger=self.logger)
        
        # Surveillance des candidats
        self.candidate_symbols = []
        self.candidate_ws_client = None
        self.candidate_ws_thread = None
        
        # Surveillance continue
        self.continuous_monitoring_thread = None
        
        # Configuration du signal handler pour Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Initialiser le temps de démarrage pour l'uptime
        self.start_time = time.time()
        
        # Les logs de démarrage seront affichés via log_startup_summary dans start()
        
        # Démarrer le monitoring des métriques
        start_metrics_monitoring(interval_minutes=5)
    
    def _signal_handler(self, signum, frame):
        """Gestionnaire de signal pour Ctrl+C."""
        self.logger.info("🛑 Signal d'arrêt reçu (Ctrl+C)...")
        self.running = False
        
        # Arrêter le gestionnaire WebSocket principal
        try:
            self.ws_manager.stop()
        except Exception:
            pass
        
        # Arrêter la surveillance des candidats
        try:
            if self.candidate_ws_client:
                self.candidate_ws_client.close()
        except Exception:
            pass
        
        # Arrêter le tracker de volatilité
        try:
            self.volatility_tracker.stop_refresh_task()
        except Exception:
            pass
        
        # Arrêter le thread d'affichage rapidement
        try:
            if self.display_thread and self.display_thread.is_alive():
                self.display_thread.join(timeout=1)
        except Exception:
            pass
        
        # Arrêter le thread des candidats WebSocket
        try:
            if self.candidate_ws_thread and self.candidate_ws_thread.is_alive():
                self.candidate_ws_thread.join(timeout=1)
        except Exception:
            pass
        
        # Arrêter la surveillance continue (peut être en train de scanner)
        # Note: Ce thread est daemon, il se terminera automatiquement
        # On ne l'attend pas pour éviter de bloquer si build_watchlist() est en cours
        try:
            if self.continuous_monitoring_thread and self.continuous_monitoring_thread.is_alive():
                self.logger.debug("⏸️ Thread de surveillance en arrêt (daemon)...")
        except Exception:
            pass
        
        # Calculer l'uptime
        uptime_seconds = time.time() - self.start_time
        
        # Récupérer les derniers candidats surveillés
        last_candidates = getattr(self, 'candidate_symbols', [])
        
        # Afficher le résumé d'arrêt professionnel
        log_shutdown_summary(self.logger, last_candidates, uptime_seconds)
        return
    
    def _update_realtime_data_from_ticker(self, ticker_data: dict):
        """
        Met à jour les données en temps réel à partir des données ticker WebSocket.
        Callback appelé par WebSocketManager.
        
        Args:
            ticker_data (dict): Données du ticker reçues via WebSocket
        """
        try:
            symbol = ticker_data.get("symbol", "")
            if not symbol:
                return
                
            # Construire un diff et fusionner avec l'état précédent 
            # pour ne pas écraser des valeurs valides par None
            now_ts = time.time()
            incoming = {
                'funding_rate': ticker_data.get('fundingRate'),
                'volume24h': ticker_data.get('volume24h'),
                'bid1_price': ticker_data.get('bid1Price'),
                'ask1_price': ticker_data.get('ask1Price'),
                'next_funding_time': ticker_data.get('nextFundingTime'),
                'mark_price': ticker_data.get('markPrice'),
                'last_price': ticker_data.get('lastPrice'),
            }
            # Vérifier si des données importantes sont présentes
            important_keys = [
                'funding_rate', 'volume24h', 'bid1_price', 
                'ask1_price', 'next_funding_time'
            ]
            if any(incoming[key] is not None for key in important_keys):
                with self._realtime_lock:
                    current = self.realtime_data.get(symbol, {})
                    merged = dict(current) if current else {}
                    for k, v in incoming.items():
                        if v is not None:
                            merged[k] = v
                    merged['timestamp'] = now_ts
                    self.realtime_data[symbol] = merged
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur mise à jour données temps réel pour {symbol}: {e}")
    
    def _recalculate_funding_time(self, symbol: str) -> str:
        """Retourne le temps restant basé uniquement sur nextFundingTime (WS puis REST)."""
        try:
            with self._realtime_lock:
                realtime_info = self.realtime_data.get(symbol, {})
            ws_ts = realtime_info.get('next_funding_time')
            if ws_ts:
                return self.watchlist_manager.calculate_funding_time_remaining(ws_ts)
            rest_ts = self.original_funding_data.get(symbol)
            if rest_ts:
                return self.watchlist_manager.calculate_funding_time_remaining(rest_ts)
            return "-"
        except Exception:
            return "-"
    
    def _print_price_table(self):
        """
        Affiche le tableau des prix aligné avec funding, volume en millions, 
        spread et volatilité.
        """
        snapshot = self._prepare_snapshot()
        
        # Si aucune opportunité n'est trouvée ou pas de snapshot, retourner
        if not self.funding_data or not snapshot:
            if self._first_display:
                self._first_display = False
            return
        
        # Calculer les largeurs de colonnes
        col_widths = self._calculate_column_widths()
        
        # Afficher l'en-tête
        self._print_table_header(col_widths)
        
        # Afficher les données
        for symbol in self.funding_data.keys():
            row_data = self._prepare_row_data(symbol)
            line = self._format_table_row(symbol, row_data, col_widths)
            print(line)
        
        print()  # Ligne vide après le tableau
    
    def _prepare_snapshot(self) -> Optional[dict]:
        """Prépare et nettoie le snapshot de données."""
        try:
            purge_expired(ttl_seconds=getattr(self, "price_ttl_sec", 120))
        except Exception:
            pass
        return get_snapshot()
    
    def _calculate_column_widths(self) -> Dict[str, int]:
        """Calcule les largeurs des colonnes du tableau."""
        all_symbols = list(self.funding_data.keys())
        max_symbol_len = max(len("Symbole"), max(len(s) for s in all_symbols)) if all_symbols else len("Symbole")
        
        return {
            "symbol": max(8, max_symbol_len),
            "funding": 12,
            "volume": 10,
            "spread": 10,
            "volatility": 12,
            "funding_time": 15
        }
    
    def _print_table_header(self, col_widths: Dict[str, int]):
        """Affiche l'en-tête du tableau."""
        w = col_widths
        header = (
            f"{'Symbole':<{w['symbol']}} | {'Funding %':>{w['funding']}} | "
            f"{'Volume (M)':>{w['volume']}} | {'Spread %':>{w['spread']}} | "
            f"{'Volatilité %':>{w['volatility']}} | "
            f"{'Funding T':>{w['funding_time']}}"
        )
        sep = (
            f"{'-'*w['symbol']}-+-{'-'*w['funding']}-+-{'-'*w['volume']}-+-"
            f"{'-'*w['spread']}-+-{'-'*w['volatility']}-+-"
            f"{'-'*w['funding_time']}"
        )
        print("\n" + header)
        print(sep)
    
    def _prepare_row_data(self, symbol: str) -> Dict[str, any]:
        """
        Prépare les données d'une ligne avec fallback entre temps réel et REST.
        
        Returns:
            Dict avec les clés: funding, volume, spread_pct, volatility_pct, funding_time
        """
        data = self.funding_data[symbol]
        realtime_info = self.realtime_data.get(symbol, {})
        
        # Valeurs initiales (REST) comme fallbacks
        try:
            original_funding = data[0]
            original_volume = data[1]
            original_funding_time = data[2]
            original_spread = data[3]
        except Exception:
            original_funding = None
            original_volume = None
            original_funding_time = "-"
            original_spread = None
        
        # Récupérer les données avec priorité temps réel
        funding = self._get_funding_value(realtime_info, original_funding)
        volume = self._get_volume_value(realtime_info, original_volume)
        spread_pct = self._get_spread_value(realtime_info, original_spread)
        volatility_pct = self.volatility_tracker.get_cached_volatility(symbol)
        funding_time = self._recalculate_funding_time(symbol) or "-"
        
        return {
            "funding": funding,
            "volume": volume,
            "spread_pct": spread_pct,
            "volatility_pct": volatility_pct,
            "funding_time": funding_time
        }
    
    def _get_funding_value(self, realtime_info: dict, original: Optional[float]) -> Optional[float]:
        """Récupère la valeur de funding avec fallback."""
        if not realtime_info:
            return original
        
        funding_rate = realtime_info.get('funding_rate')
        if funding_rate is not None:
            return float(funding_rate)
        return original
    
    def _get_volume_value(self, realtime_info: dict, original: Optional[float]) -> Optional[float]:
        """Récupère la valeur de volume avec fallback."""
        if not realtime_info:
            return original
        
        volume24h = realtime_info.get('volume24h')
        if volume24h is not None:
            return float(volume24h)
        return original
    
    def _get_spread_value(self, realtime_info: dict, original: Optional[float]) -> Optional[float]:
        """Récupère la valeur de spread avec fallback."""
        if not realtime_info:
            return original
        
        # Calculer le spread en temps réel si on a bid/ask
        bid1_price = realtime_info.get('bid1_price')
        ask1_price = realtime_info.get('ask1_price')
        
        if bid1_price and ask1_price:
            try:
                bid = float(bid1_price)
                ask = float(ask1_price)
                if bid > 0 and ask > 0:
                    mid = (ask + bid) / 2
                    if mid > 0:
                        return (ask - bid) / mid
            except (ValueError, TypeError):
                pass
        
        return original
    
    def _format_table_row(self, symbol: str, row_data: Dict[str, any], col_widths: Dict[str, int]) -> str:
        """Formate une ligne du tableau."""
        w = col_widths
        
        # Formater chaque colonne
        funding_str = self._format_funding(row_data["funding"], w["funding"])
        volume_str = self._format_volume(row_data["volume"])
        spread_str = self._format_spread(row_data["spread_pct"])
        volatility_str = self._format_volatility(row_data["volatility_pct"])
        funding_time_str = row_data["funding_time"]
        
        return (
            f"{symbol:<{w['symbol']}} | {funding_str:>{w['funding']}} | "
            f"{volume_str:>{w['volume']}} | {spread_str:>{w['spread']}} | "
            f"{volatility_str:>{w['volatility']}} | "
            f"{funding_time_str:>{w['funding_time']}}"
        )
    
    def _format_funding(self, funding: Optional[float], width: int) -> str:
        """Formate la valeur de funding."""
        if funding is not None:
            funding_pct = funding * 100.0
            return f"{funding_pct:+{width-1}.4f}%"
        return "null"
    
    def _format_volume(self, volume: Optional[float]) -> str:
        """Formate la valeur de volume en millions."""
        if volume is not None and volume > 0:
            volume_millions = volume / 1_000_000
            return f"{volume_millions:,.1f}"
        return "null"
    
    def _format_spread(self, spread_pct: Optional[float]) -> str:
        """Formate la valeur de spread."""
        if spread_pct is not None:
            spread_pct_display = spread_pct * 100.0
            return f"{spread_pct_display:+.3f}%"
        return "null"
    
    def _format_volatility(self, volatility_pct: Optional[float]) -> str:
        """Formate la valeur de volatilité."""
        if volatility_pct is not None:
            volatility_pct_display = volatility_pct * 100.0
            return f"{volatility_pct_display:+.3f}%"
        return "-"
    
    def _display_loop(self):
        """Boucle d'affichage avec intervalle configurable."""
        while self.running:
            # Vérifier immédiatement si on doit s'arrêter
            if not self.running:
                break
                
            self._print_price_table()
            
            # Attendre selon l'intervalle configuré
            interval_seconds = getattr(self, 'display_interval_seconds', 10)
            steps = int(interval_seconds * 10)  # 10 * 0.1s = interval_seconds
            for _ in range(steps):
                if not self.running:
                    break
                time.sleep(0.1)
        
        # Boucle d'affichage arrêtée
    
    def start(self):
        """Démarre le suivi des prix avec filtrage par funding."""
        # Charger et valider la configuration via le watchlist manager
        try:
            config = self.watchlist_manager.load_and_validate_config()
        except ValueError as e:
            self.logger.error(f"❌ Erreur de configuration : {e}")
            self.logger.error("💡 Corrigez les paramètres dans src/parameters.yaml ou les variables d'environnement")
            return  # Arrêt propre sans sys.exit
        
        # Vérifier si le fichier de config existe
        config_path = "src/parameters.yaml"
        config_exists = os.path.exists(config_path)
        
        # Créer un client PUBLIC pour récupérer l'URL publique (aucune clé requise)
        client = BybitPublicClient(
            testnet=self.testnet,
            timeout=10,
        )
        
        base_url = client.public_base_url()
        
        # Récupérer l'univers perp
        perp_data = get_perp_symbols(base_url, timeout=10)
        # Stocker le mapping officiel des catégories
        try:
            self.symbol_categories = perp_data.get("categories", {}) or {}
        except Exception:
            self.symbol_categories = {}
        
        # Configurer les gestionnaires avec les catégories
        self.volatility_tracker.set_symbol_categories(self.symbol_categories)
        self.watchlist_manager.symbol_categories = self.symbol_categories
        
        # Configurer le tracker de volatilité
        volatility_ttl_sec = int(config.get("volatility_ttl_sec", 120) or 120)
        self.volatility_tracker.ttl_seconds = volatility_ttl_sec
        self.price_ttl_sec = 120
        
        # Configurer l'intervalle d'affichage
        display_interval = int(config.get("display_interval_seconds", 10) or 10)
        self.display_interval_seconds = display_interval
        
        # Les filtres seront affichés dans le résumé structuré
        
        # Construire la watchlist via le gestionnaire dédié
        try:
            self.linear_symbols, self.inverse_symbols, self.funding_data = self.watchlist_manager.build_watchlist(
                base_url, perp_data, self.volatility_tracker
            )
            # Récupérer les données originales de funding
            self.original_funding_data = self.watchlist_manager.get_original_funding_data()
        except Exception as e:
            if "Aucun symbole" in str(e) or "Aucun funding" in str(e):
                # Ne pas lever d'exception, continuer en mode surveillance
                # Initialiser les listes vides pour le mode surveillance
                self.linear_symbols = []
                self.inverse_symbols = []
                self.funding_data = {}
                self.original_funding_data = {}
            else:
                raise
        
        # Afficher le résumé de démarrage structuré
        self._display_startup_summary(config, perp_data)
        
        # Démarrer le tracker de volatilité (arrière-plan) AVANT les WS bloquantes
        self.volatility_tracker.start_refresh_task()
        
        # Démarrer l'affichage
        self.display_thread = threading.Thread(target=self._display_loop)
        self.display_thread.daemon = True
        self.display_thread.start()

        # Démarrer les connexions WebSocket via le gestionnaire dédié
        if self.linear_symbols or self.inverse_symbols:
            self.ws_manager.start_connections(self.linear_symbols, self.inverse_symbols)
        
        # Configurer la surveillance des candidats (en arrière-plan)
        self._setup_candidate_monitoring(base_url, perp_data)
        
        # Démarrer le mode surveillance continue (toujours actif pour détecter de nouvelles opportunités)
        self._start_continuous_monitoring(base_url, perp_data)
    
    def _get_active_symbols(self) -> List[str]:
        """Retourne la liste des symboles actuellement actifs."""
        return list(self.funding_data.keys())
    
    def _start_continuous_monitoring(self, base_url: str, perp_data: Dict):
        """Démarre le mode surveillance continue pour scanner le marché en permanence."""
        # Démarrage de la surveillance continue
        
        # Thread de re-scan périodique
        self.continuous_monitoring_thread = threading.Thread(
            target=self._continuous_monitoring_loop, 
            args=(base_url, perp_data)
        )
        self.continuous_monitoring_thread.daemon = True
        self.continuous_monitoring_thread.start()
    
    def _continuous_monitoring_loop(self, base_url: str, perp_data: Dict):
        """Boucle de surveillance continue qui re-scanne le marché périodiquement."""
        scan_interval = 60  # 1 minute entre chaque scan complet
        last_scan_time = 0
        
        while self.running:
            try:
                # Vérification immédiate pour arrêt rapide
                if not self.running:
                    self.logger.info("🛑 Arrêt de la surveillance continue demandé")
                    break
                
                current_time = time.time()
                
                # Effectuer un scan si l'intervalle est écoulé
                if self._should_perform_scan(current_time, last_scan_time, scan_interval):
                    self._perform_market_scan(base_url, perp_data)
                    last_scan_time = current_time
                    
                    # Vérifier après le scan pour arrêt rapide
                    if not self.running:
                        break
                
                # Attendre avec vérification d'interruption
                self._wait_with_interrupt_check(10)
                
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur dans la boucle de surveillance continue: {e}")
                if not self.running:
                    break
                time.sleep(10)
        
        # Boucle de surveillance continue arrêtée
    
    def _should_perform_scan(self, current_time: float, last_scan_time: float, interval: int) -> bool:
        """Vérifie s'il est temps d'effectuer un nouveau scan."""
        return self.running and (current_time - last_scan_time >= interval)
    
    def _perform_market_scan(self, base_url: str, perp_data: Dict):
        """Effectue un scan complet du marché pour détecter de nouvelles opportunités."""
        if not self.running:
            return
        
        try:
            # Construire la watchlist via le gestionnaire
            new_opportunities = self._scan_for_new_opportunities(base_url, perp_data)
            
            # Vérification après le scan qui peut être long
            if not self.running:
                return
            
            if new_opportunities and self.running:
                self._integrate_new_opportunities(new_opportunities)
                
        except Exception as e:
            # Ne pas logger si on est en train de s'arrêter
            if self.running:
                self.logger.warning(f"⚠️ Erreur lors du re-scan: {e}")
    
    def _scan_for_new_opportunities(self, base_url: str, perp_data: Dict) -> Optional[Dict]:
        """
        Scanne le marché pour trouver de nouvelles opportunités.
        
        Returns:
            Dict contenant linear_symbols, inverse_symbols et funding_data ou None
        """
        if not self.running:
            return None
        
        try:
            # Créer un nouveau client pour éviter les problèmes de futures
            client = BybitPublicClient(testnet=self.testnet, timeout=10)
            fresh_base_url = client.public_base_url()
            
            if not self.running:
                return None
            
            # Reconstruire la watchlist (peut prendre du temps)
            linear_symbols, inverse_symbols, funding_data = self.watchlist_manager.build_watchlist(
                fresh_base_url, perp_data, self.volatility_tracker
            )
            
            # Vérification immédiate après l'opération longue
            if not self.running:
                return None
            
            if linear_symbols or inverse_symbols:
                return {
                    "linear": linear_symbols,
                    "inverse": inverse_symbols,
                    "funding_data": funding_data
                }
            
        except Exception as e:
            # Ne pas logger si on est en train de s'arrêter
            if self.running:
                self.logger.warning(f"⚠️ Erreur scan opportunités: {e}")
        
        return None
    
    def _integrate_new_opportunities(self, opportunities: Dict):
        """
        Intègre les nouvelles opportunités détectées dans la watchlist existante.
        
        Args:
            opportunities: Dict avec linear, inverse et funding_data
        """
        if not self.running:
            return
        
        linear_symbols = opportunities.get("linear", [])
        inverse_symbols = opportunities.get("inverse", [])
        funding_data = opportunities.get("funding_data", {})
        
        # Récupérer les symboles existants
        existing_linear = set(getattr(self, 'linear_symbols', []))
        existing_inverse = set(getattr(self, 'inverse_symbols', []))
        
        # Identifier les nouveaux symboles
        new_linear = set(linear_symbols) - existing_linear
        new_inverse = set(inverse_symbols) - existing_inverse
        
        if new_linear or new_inverse:
            if not self.running:
                return
            
            # Mettre à jour les listes de symboles
            self._update_symbol_lists(linear_symbols, inverse_symbols, existing_linear, existing_inverse)
            
            if not self.running:
                return
            
            # Mettre à jour les données de funding
            self._update_funding_data(funding_data)
            
            if not self.running:
                return
            
            # Démarrer les connexions WebSocket pour les nouvelles opportunités
            try:
                self.ws_manager.start_connections(self.linear_symbols, self.inverse_symbols)
            except Exception:
                # Ignorer les erreurs lors de l'arrêt
                pass
    
    def _update_symbol_lists(self, linear_symbols: List[str], inverse_symbols: List[str], 
                            existing_linear: set, existing_inverse: set):
        """Met à jour les listes de symboles avec les nouvelles opportunités."""
        self.linear_symbols = list(existing_linear | set(linear_symbols))
        self.inverse_symbols = list(existing_inverse | set(inverse_symbols))
    
    def _update_funding_data(self, new_funding_data: Dict):
        """Met à jour les données de funding avec les nouvelles opportunités."""
        # Fusionner les données de funding
        self.funding_data.update(new_funding_data)
        
        # Mettre à jour les données originales
        new_original_data = self.watchlist_manager.get_original_funding_data()
        self.original_funding_data.update(new_original_data)
    
    def _wait_with_interrupt_check(self, seconds: int):
        """
        Attend pendant le nombre de secondes spécifié avec vérification d'interruption.
        
        Args:
            seconds: Nombre de secondes à attendre
        """
        for _ in range(seconds):
            if not self.running:
                break
            time.sleep(1)
    
    def _setup_candidate_monitoring(self, base_url: str, perp_data: Dict):
        """Configure la surveillance des symboles candidats."""
        try:
            # Détecter les candidats
            self.candidate_symbols = self.watchlist_manager.find_candidate_symbols(base_url, perp_data)
            
            if not self.candidate_symbols:
                # Aucun candidat détecté pour surveillance
                return
            
            # Séparer les candidats par catégorie
            linear_candidates = []
            inverse_candidates = []
            
            for symbol in self.candidate_symbols:
                category = category_of_symbol(symbol, self.symbol_categories)
                if category == "linear":
                    linear_candidates.append(symbol)
                elif category == "inverse":
                    inverse_candidates.append(symbol)
            
            # Démarrer la surveillance WebSocket des candidats
            if linear_candidates or inverse_candidates:
                self._start_candidate_websocket_monitoring(linear_candidates, inverse_candidates)
                
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur configuration surveillance candidats: {e}")
    
    def _start_candidate_websocket_monitoring(self, linear_candidates: List[str], inverse_candidates: List[str]):
        """Démarre la surveillance WebSocket des candidats."""
        try:
            from ws_public import PublicWSClient
            
            # Créer une connexion WebSocket pour les candidats
            if linear_candidates and inverse_candidates:
                # Si on a les deux catégories, utiliser linear (plus courant)
                symbols_to_monitor = linear_candidates + inverse_candidates
                category = "linear"
            elif linear_candidates:
                symbols_to_monitor = linear_candidates
                category = "linear"
            elif inverse_candidates:
                symbols_to_monitor = inverse_candidates
                category = "inverse"
            else:
                return
            
            self.candidate_ws_client = PublicWSClient(
                category=category,
                symbols=symbols_to_monitor,
                testnet=self.testnet,
                logger=self.logger,
                on_ticker_callback=self._on_candidate_ticker
            )
            
            # Lancer la surveillance dans un thread séparé
            self.candidate_ws_thread = threading.Thread(target=self._candidate_ws_runner)
            self.candidate_ws_thread.daemon = True
            self.candidate_ws_thread.start()
            
        except Exception as e:
            self.logger.error(f"❌ Erreur démarrage surveillance candidats: {e}")
    
    def _candidate_ws_runner(self):
        """Runner pour la WebSocket des candidats."""
        if self.candidate_ws_client:
            try:
                self.candidate_ws_client.run()
            except Exception as e:
                if self.running:
                    self.logger.warning(f"⚠️ Erreur WebSocket candidats: {e}")
    
    def _on_candidate_ticker(self, ticker_data: dict):
        """Callback appelé pour chaque ticker des candidats."""
        try:
            symbol = ticker_data.get("symbol", "")
            if not symbol:
                return
            
            # Vérifier si le candidat passe maintenant les filtres
            if self.watchlist_manager.check_if_symbol_now_passes_filters(symbol, ticker_data):
                # 🎯 NOUVELLE OPPORTUNITÉ DÉTECTÉE !
                funding_rate = ticker_data.get("fundingRate")
                volume24h = ticker_data.get("volume24h")
                
                # Nouvelle opportunité détectée
                # Funding et volume
                
                # Ajouter à la watchlist principale
                self._add_symbol_to_main_watchlist(symbol, ticker_data)
                
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur traitement candidat {symbol}: {e}")
    
    def _add_symbol_to_main_watchlist(self, symbol: str, ticker_data: dict):
        """Ajoute un symbole à la watchlist principale."""
        try:
            # Vérifier que le symbole n'est pas déjà dans la watchlist
            if symbol in self.funding_data:
                return  # Déjà présent
            
            # Construire les données du symbole
            funding_rate = ticker_data.get("fundingRate")
            volume24h = ticker_data.get("volume24h")
            next_funding_time = ticker_data.get("nextFundingTime")
            
            if funding_rate is not None:
                funding = float(funding_rate)
                volume = float(volume24h) if volume24h is not None else 0.0
                funding_time_remaining = self.watchlist_manager.calculate_funding_time_remaining(next_funding_time)
                
                # Calculer le spread si disponible
                spread_pct = 0.0
                bid1_price = ticker_data.get("bid1Price")
                ask1_price = ticker_data.get("ask1Price")
                if bid1_price and ask1_price:
                    try:
                        bid = float(bid1_price)
                        ask = float(ask1_price)
                        if bid > 0 and ask > 0:
                            mid = (ask + bid) / 2
                            if mid > 0:
                                spread_pct = (ask - bid) / mid
                    except (ValueError, TypeError):
                        pass
                
                # Ajouter à la watchlist
                self.funding_data[symbol] = (funding, volume, funding_time_remaining, spread_pct, None)
                
                # Ajouter aux listes par catégorie
                category = category_of_symbol(symbol, self.symbol_categories)
                if category == "linear":
                    if symbol not in self.linear_symbols:
                        self.linear_symbols.append(symbol)
                elif category == "inverse":
                    if symbol not in self.inverse_symbols:
                        self.inverse_symbols.append(symbol)
                
                # Mettre à jour les données originales
                if next_funding_time:
                    self.original_funding_data[symbol] = next_funding_time
                
                # Symbole ajouté à la watchlist principale
                # Watchlist mise à jour
                
        except Exception as e:
            self.logger.error(f"❌ Erreur ajout symbole {symbol}: {e}")
    
    def _display_startup_summary(self, config: Dict, perp_data: Dict):
        """Affiche le résumé de démarrage structuré."""
        # Informations du bot
        bot_info = {
            'name': 'BYBIT BOT',
            'version': '0.9.0',
            'environment': 'Testnet' if self.testnet else 'Mainnet',
            'mode': 'Funding Sniping'
        }
        
        # Statistiques de filtrage
        total_symbols = perp_data.get('total', 0)
        linear_count = len(self.linear_symbols)
        inverse_count = len(self.inverse_symbols)
        final_count = linear_count + inverse_count
        
        filter_results = {
            'stats': {
                'total_symbols': total_symbols,
                'after_funding_volume': final_count,  # Approximation
                'after_spread': final_count,
                'after_volatility': final_count,
                'final_count': final_count
            }
        }
        
        # Statut WebSocket
        ws_status = {
            'connected': bool(self.linear_symbols or self.inverse_symbols),
            'symbols_count': final_count,
            'category': config.get('categorie', 'linear')
        }
        
        # Ajouter l'intervalle de métriques à la config
        config['metrics_interval'] = 5
        
        # Afficher le résumé structuré
        log_startup_summary(self.logger, bot_info, config, filter_results, ws_status)


def main():
    """Fonction principale."""
    tracker = PriceTracker()
    try:
        tracker.start()
        
        # Boucle d'attente pour maintenir le bot actif
        while tracker.running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        tracker.logger.info("🛑 Arrêt demandé par l'utilisateur")
        tracker.running = False
        # Forcer l'arrêt de tous les threads
        tracker._signal_handler(signal.SIGINT, None)
    except Exception as e:
        tracker.logger.error(f"❌ Erreur : {e}")
        tracker.running = False
        # Forcer l'arrêt de tous les threads
        tracker._signal_handler(signal.SIGINT, None)
        # Laisser le code appelant décider (ne pas sys.exit ici)


if __name__ == "__main__":
    main()