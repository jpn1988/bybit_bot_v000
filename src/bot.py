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
from typing import List, Dict
from logging_setup import setup_logging
from config import get_settings
from bybit_client import BybitPublicClient
from instruments import get_perp_symbols
from price_store import get_snapshot, purge_expired
from volatility import get_volatility_cache_key, is_cache_valid
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
        self.realtime_data = {}  # Données en temps réel via WebSocket {symbol: {funding_rate, volume24h, bid1, ask1, next_funding_time, ...}}
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
        
        # Configuration du signal handler pour Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        
        self.logger.info("🚀 Orchestrateur du bot (filters + WebSocket prix)")
        self.logger.info("📂 Configuration chargée")
        
        # Démarrer le monitoring des métriques
        start_metrics_monitoring(interval_minutes=5)
    
    def _signal_handler(self, signum, frame):
        """Gestionnaire de signal pour Ctrl+C."""
        self.logger.info("🧹 Arrêt demandé, fermeture de la WebSocket…")
        self.running = False
        # Arrêter le gestionnaire WebSocket
        try:
            self.ws_manager.stop()
        except Exception:
            pass
        # Arrêter le tracker de volatilité
        try:
            self.volatility_tracker.stop_refresh_task()
        except Exception:
            pass
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
                
            # Construire un diff et fusionner avec l'état précédent pour ne pas écraser des valeurs valides par None
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
            important_keys = ['funding_rate', 'volume24h', 'bid1_price', 'ask1_price', 'next_funding_time']
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
        """Affiche le tableau des prix aligné avec funding, volume en millions, spread et volatilité."""
        # Purger les données de prix trop anciennes et récupérer un snapshot
        try:
            purge_expired(ttl_seconds=getattr(self, "price_ttl_sec", 120))
        except Exception:
            pass
        snapshot = get_snapshot()
        
        if not snapshot:
            if self._first_display:
                self.logger.info("⏳ En attente de la première donnée WS…")
                self._first_display = False  # Ne plus afficher ce message
            return
        
        # Calculer les largeurs de colonnes
        all_symbols = list(self.funding_data.keys())
        max_symbol_len = max(len("Symbole"), max(len(s) for s in all_symbols)) if all_symbols else len("Symbole")
        symbol_w = max(8, max_symbol_len)
        funding_w = 12  # Largeur pour le funding
        volume_w = 10  # Largeur pour le volume en millions
        spread_w = 10  # Largeur pour le spread
        volatility_w = 12  # Largeur pour la volatilité
        funding_time_w = 15  # Largeur pour le temps de funding (avec secondes)
        
        # En-tête
        header = (
            f"{'Symbole':<{symbol_w}} | {'Funding %':>{funding_w}} | "
            f"{'Volume (M)':>{volume_w}} | {'Spread %':>{spread_w}} | "
            f"{'Volatilité %':>{volatility_w}} | {'Funding T':>{funding_time_w}}"
        )
        sep = (
            f"{'-'*symbol_w}-+-{'-'*funding_w}-+-{'-'*volume_w}-+-"
            f"{'-'*spread_w}-+-{'-'*volatility_w}-+-{'-'*funding_time_w}"
        )
        
        print("\n" + header)
        print(sep)
        
        # Données
        for symbol, data in self.funding_data.items():
            # Récupérer les données en temps réel si disponibles
            realtime_info = self.realtime_data.get(symbol, {})
            # Récupérer les valeurs initiales (REST) comme fallbacks
            # data format: (funding, volume, funding_time_remaining, spread_pct, volatility_pct)
            try:
                original_funding = data[0]
                original_volume = data[1]
                original_funding_time = data[2]
            except Exception:
                original_funding = None
                original_volume = None
                original_funding_time = "-"
            
            # Utiliser les données en temps réel si disponibles, sinon fallback vers REST initial
            if realtime_info:
                # Données en temps réel disponibles - gérer les valeurs None
                funding_rate = realtime_info.get('funding_rate')
                funding = float(funding_rate) if funding_rate is not None else original_funding
                
                volume24h = realtime_info.get('volume24h')
                volume = float(volume24h) if volume24h is not None else original_volume
                
                # On ne remplace pas la valeur initiale si la donnée WS est absente
                funding_time_remaining = original_funding_time
                
                # Calculer le spread en temps réel si on a bid/ask
                spread_pct = None
                if realtime_info.get('bid1_price') and realtime_info.get('ask1_price'):
                    try:
                        bid_price = float(realtime_info['bid1_price'])
                        ask_price = float(realtime_info['ask1_price'])
                        if bid_price > 0 and ask_price > 0:
                            mid_price = (ask_price + bid_price) / 2
                            if mid_price > 0:
                                spread_pct = (ask_price - bid_price) / mid_price
                    except (ValueError, TypeError):
                        pass  # Garder spread_pct = None en cas d'erreur
                # Fallback: utiliser la valeur REST calculée au filtrage si le temps réel est indisponible
                if spread_pct is None:
                    try:
                        # data[3] contient spread_pct (ou 0.0 si absent lors du filtrage)
                        spread_pct = data[3]
                    except Exception:
                        pass
                
                # Volatilité: lecture via le tracker dédié
                volatility_pct = self.volatility_tracker.get_cached_volatility(symbol)
            else:
                # Pas de données en temps réel disponibles - utiliser les valeurs initiales REST
                funding = original_funding
                volume = original_volume
                funding_time_remaining = original_funding_time
                # Fallback: utiliser la valeur REST calculée au filtrage
                spread_pct = None
                volatility_pct = None
                
                # Volatilité: lecture via le tracker dédié
                if volatility_pct is None:
                    volatility_pct = self.volatility_tracker.get_cached_volatility(symbol)
                # Essayer de récupérer le spread initial calculé lors du filtrage
                if spread_pct is None:
                    try:
                        spread_pct = data[3]
                    except Exception:
                        pass
            
            # Recalculer le temps de funding (priorité WS, fallback REST)
            current_funding_time = self._recalculate_funding_time(symbol)
            if current_funding_time is None:
                current_funding_time = "-"
            
            # Gérer l'affichage des valeurs null
            if funding is not None:
                funding_pct = funding * 100.0
                funding_str = f"{funding_pct:+{funding_w-1}.4f}%"
            else:
                funding_str = "null"
            
            if volume is not None and volume > 0:
                volume_millions = volume / 1_000_000
                volume_str = f"{volume_millions:,.1f}"
            else:
                volume_str = "null"
            
            if spread_pct is not None:
                spread_pct_display = spread_pct * 100.0
                spread_str = f"{spread_pct_display:+.3f}%"
            else:
                spread_str = "null"
            
            # Formatage de la volatilité
            if volatility_pct is not None:
                volatility_pct_display = volatility_pct * 100.0
                volatility_str = f"{volatility_pct_display:+.3f}%"
            else:
                volatility_str = "-"
            
            line = (
                f"{symbol:<{symbol_w}} | {funding_str:>{funding_w}} | "
                f"{volume_str:>{volume_w}} | {spread_str:>{spread_w}} | "
                f"{volatility_str:>{volatility_w}} | {current_funding_time:>{funding_time_w}}"
            )
            print(line)
        
        print()  # Ligne vide après le tableau
    
    def _display_loop(self):
        """Boucle d'affichage toutes les 15 secondes."""
        while self.running:
            self._print_price_table()
            
            # Attendre 15 secondes
            for _ in range(150):  # 150 * 0.1s = 15s
                if not self.running:
                    break
                time.sleep(0.1)
    
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
        if not os.path.exists(config_path):
            self.logger.info("ℹ️ Aucun fichier de paramètres trouvé (src/parameters.yaml) → utilisation des valeurs par défaut.")
        else:
            self.logger.info("ℹ️ Configuration chargée depuis src/parameters.yaml")
        
        # Créer un client PUBLIC pour récupérer l'URL publique (aucune clé requise)
        client = BybitPublicClient(
            testnet=self.testnet,
            timeout=10,
        )
        
        base_url = client.public_base_url()
        
        # Récupérer l'univers perp
        perp_data = get_perp_symbols(base_url, timeout=10)
        self.logger.info(f"🗺️ Univers perp récupéré : linear={len(perp_data['linear'])} | inverse={len(perp_data['inverse'])} | total={perp_data['total']}")
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
        
        # Afficher les filtres (délégué au watchlist manager)
        self._log_filter_config(config, volatility_ttl_sec)
        
        # Construire la watchlist via le gestionnaire dédié
        try:
            self.linear_symbols, self.inverse_symbols, self.funding_data = self.watchlist_manager.build_watchlist(
                base_url, perp_data, self.volatility_tracker
            )
            # Récupérer les données originales de funding
            self.original_funding_data = self.watchlist_manager.get_original_funding_data()
        except Exception as e:
            if "Aucun symbole" in str(e) or "Aucun funding" in str(e):
                # Convertir en exceptions spécifiques
                if "Aucun symbole" in str(e):
                    raise NoSymbolsError(str(e))
                else:
                    from errors import FundingUnavailableError
                    raise FundingUnavailableError(str(e))
            else:
                raise
        
        self.logger.info(f"📊 Symboles linear: {len(self.linear_symbols)}, inverse: {len(self.inverse_symbols)}")
        
        # Démarrer le tracker de volatilité (arrière-plan) AVANT les WS bloquantes
        self.volatility_tracker.start_refresh_task()
        
        # Démarrer l'affichage
        self.display_thread = threading.Thread(target=self._display_loop)
        self.display_thread.daemon = True
        self.display_thread.start()

        # Démarrer les connexions WebSocket via le gestionnaire dédié
        if self.linear_symbols or self.inverse_symbols:
            self.ws_manager.start_connections(self.linear_symbols, self.inverse_symbols)
        else:
            self.logger.warning("⚠️ Aucun symbole valide trouvé")
            raise NoSymbolsError("Aucun symbole valide trouvé")
    
    def _get_active_symbols(self) -> List[str]:
        """Retourne la liste des symboles actuellement actifs."""
        return list(self.funding_data.keys())
    
    def _log_filter_config(self, config: Dict, volatility_ttl_sec: int):
        """Affiche la configuration des filtres."""
        # Extraire les paramètres pour l'affichage
        categorie = config.get("categorie", "both")
        funding_min = config.get("funding_min")
        funding_max = config.get("funding_max")
        volume_min_millions = config.get("volume_min_millions")
        spread_max = config.get("spread_max")
        volatility_min = config.get("volatility_min")
        volatility_max = config.get("volatility_max")
        limite = config.get("limite")
        funding_time_min_minutes = config.get("funding_time_min_minutes")
        funding_time_max_minutes = config.get("funding_time_max_minutes")
        
        # Formater pour l'affichage
        min_display = f"{funding_min:.6f}" if funding_min is not None else "none"
        max_display = f"{funding_max:.6f}" if funding_max is not None else "none"
        volume_display = f"{volume_min_millions:.1f}" if volume_min_millions is not None else "none"
        spread_display = f"{spread_max:.4f}" if spread_max is not None else "none"
        volatility_min_display = f"{volatility_min:.3f}" if volatility_min is not None else "none"
        volatility_max_display = f"{volatility_max:.3f}" if volatility_max is not None else "none"
        limite_display = str(limite) if limite is not None else "none"
        ft_min_display = str(funding_time_min_minutes) if funding_time_min_minutes is not None else "none"
        ft_max_display = str(funding_time_max_minutes) if funding_time_max_minutes is not None else "none"
        
        self.logger.info(
            f"🎛️ Filtres | catégorie={categorie} | funding_min={min_display} | "
            f"funding_max={max_display} | volume_min_millions={volume_display} | "
            f"spread_max={spread_display} | volatility_min={volatility_min_display} | "
            f"volatility_max={volatility_max_display} | ft_min(min)={ft_min_display} | "
            f"ft_max(min)={ft_max_display} | limite={limite_display} | vol_ttl={volatility_ttl_sec}s"
        )


def main():
    """Fonction principale."""
    tracker = PriceTracker()
    try:
        tracker.start()
    except Exception as e:
        tracker.logger.error(f"❌ Erreur : {e}")
        tracker.running = False
        # Laisser le code appelant décider (ne pas sys.exit ici)


if __name__ == "__main__":
    main()