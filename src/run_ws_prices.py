#!/usr/bin/env python3
"""
Script pour filtrer les contrats perpétuels par funding ET suivre leurs prix en temps réel.

Usage:
    python src/run_ws_prices.py
"""

import os
import sys
import json
import time
import signal
import threading
import yaml
import httpx
import websocket
from config import get_settings
from logging_setup import setup_logging
from bybit_client import BybitClient
from instruments import get_perp_symbols
from price_store import update, get_snapshot, get_age_seconds


def load_config() -> dict:
    """
    Charge la configuration depuis le fichier YAML ou utilise les valeurs par défaut.
    
    Returns:
        dict: Configuration avec categorie, funding_min, funding_max, limite
    """
    config_path = "src/watchlist_config.fr.yaml"
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        # Valeurs par défaut si le fichier n'existe pas
        return {
            "categorie": "linear",
            "funding_min": None,
            "funding_max": None,
            "volume_min": None,
            "limite": 10
        }


def fetch_funding_map(base_url: str, category: str, timeout: int) -> dict[str, float]:
    """
    Récupère les taux de funding pour une catégorie donnée.
    
    Args:
        base_url (str): URL de base de l'API Bybit
        category (str): Catégorie (linear ou inverse)
        timeout (int): Timeout pour les requêtes HTTP
        
    Returns:
        dict[str, float]: Dictionnaire {symbol: funding_rate}
        
    Raises:
        RuntimeError: En cas d'erreur HTTP ou API
    """
    funding_map = {}
    cursor = ""
    
    while True:
        # Construire l'URL avec pagination
        url = f"{base_url}/v5/market/tickers"
        params = {
            "category": category,
            "limit": 1000
        }
        if cursor:
            params["cursor"] = cursor
            
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(url, params=params)
                
                # Vérifier le statut HTTP
                if response.status_code >= 400:
                    raise RuntimeError(f"Erreur HTTP Bybit: status={response.status_code} detail=\"{response.text[:100]}\"")
                
                data = response.json()
                
                # Vérifier le retCode
                if data.get("retCode") != 0:
                    ret_code = data.get("retCode")
                    ret_msg = data.get("retMsg", "")
                    raise RuntimeError(f"Erreur API Bybit: retCode={ret_code} retMsg=\"{ret_msg}\"")
                
                result = data.get("result", {})
                tickers = result.get("list", [])
                
                # Extraire les funding rates et volumes
                for ticker in tickers:
                    symbol = ticker.get("symbol", "")
                    funding_rate = ticker.get("fundingRate")
                    volume_24h = ticker.get("volume24h")
                    
                    if symbol and funding_rate is not None:
                        try:
                            funding_map[symbol] = {
                                "funding": float(funding_rate),
                                "volume": float(volume_24h) if volume_24h is not None else 0.0
                            }
                        except (ValueError, TypeError):
                            # Ignorer si les données ne sont pas convertibles en float
                            pass
                
                # Vérifier s'il y a une page suivante
                next_page_cursor = result.get("nextPageCursor")
                if not next_page_cursor:
                    break
                cursor = next_page_cursor
                
        except httpx.RequestError as e:
            raise RuntimeError(f"Erreur réseau/HTTP Bybit: {e}")
        except Exception as e:
            if "Erreur" in str(e):
                raise
            else:
                raise RuntimeError(f"Erreur réseau/HTTP Bybit: {e}")
    
    return funding_map


def filter_by_funding(perp_data: dict, funding_map: dict, funding_min: float | None, funding_max: float | None, volume_min: float | None, limite: int | None) -> list[tuple[str, float, float]]:
    """
    Filtre les symboles par funding et volume, puis trie par |funding| décroissant.
    
    Args:
        perp_data (dict): Données des perpétuels (linear, inverse, total)
        funding_map (dict): Dictionnaire des funding rates et volumes
        funding_min (float | None): Funding minimum
        funding_max (float | None): Funding maximum
        volume_min (float | None): Volume minimum
        limite (int | None): Limite du nombre d'éléments
        
    Returns:
        list[tuple[str, float, float]]: Liste des (symbol, funding, volume) triés
    """
    # Récupérer tous les symboles perpétuels
    all_symbols = list(set(perp_data["linear"] + perp_data["inverse"]))
    
    # Filtrer par funding et volume
    filtered_symbols = []
    for symbol in all_symbols:
        if symbol in funding_map:
            data = funding_map[symbol]
            funding = data["funding"]
            volume = data["volume"]
            
            # Appliquer les bornes
            if funding_min is not None and funding < funding_min:
                continue
            if funding_max is not None and funding > funding_max:
                continue
            if volume_min is not None and volume < volume_min:
                continue
                
            filtered_symbols.append((symbol, funding, volume))
    
    # Trier par |funding| décroissant
    filtered_symbols.sort(key=lambda x: abs(x[1]), reverse=True)
    
    # Appliquer la limite
    if limite is not None:
        filtered_symbols = filtered_symbols[:limite]
    
    return filtered_symbols


class PriceTracker:
    """Suivi des prix en temps réel via WebSocket avec filtrage par funding."""
    
    def __init__(self):
        self.logger = setup_logging()
        self.running = True
        self.ws = None
        self.display_thread = None
        self.symbols = []
        self.funding_data = {}
        
        # Configuration
        settings = get_settings()
        self.testnet = settings['testnet']
        
        # Configuration du signal handler pour Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        
        self.logger.info("🚀 Filtrage par funding + Suivi de prix (WS)")
        self.logger.info("📂 Configuration chargée")
    
    def _signal_handler(self, signum, frame):
        """Gestionnaire de signal pour Ctrl+C."""
        self.logger.info("🧹 Arrêt demandé, fermeture de la WebSocket…")
        self.running = False
        if self.ws:
            self.ws.close()
        sys.exit(0)
    
    def _print_price_table(self):
        """Affiche le tableau des prix aligné avec funding."""
        snapshot = get_snapshot()
        
        if not snapshot:
            print("Aucune donnée de prix disponible")
            return
        
        # Calculer les largeurs de colonnes
        all_symbols = list(self.funding_data.keys())
        max_symbol_len = max(len("Symbole"), max(len(s) for s in all_symbols)) if all_symbols else len("Symbole")
        symbol_w = max(8, max_symbol_len)
        price_w = 15  # Largeur fixe pour les prix
        funding_w = 12  # Largeur pour le funding
        age_w = 8     # Largeur fixe pour l'âge
        
        # En-tête
        volume_w = 12  # Largeur pour le volume
        header = f"{'Symbole':<{symbol_w}} | {'Mark Price':>{price_w}} | {'Last Price':>{price_w}} | {'Funding %':>{funding_w}} | {'Volume 24h':>{volume_w}} | {'Âge (s)':>{age_w}}"
        sep = f"{'-'*symbol_w}-+-{'-'*price_w}-+-{'-'*price_w}-+-{'-'*funding_w}-+-{'-'*volume_w}-+-{'-'*age_w}"
        
        print("\n" + header)
        print(sep)
        
        # Données
        for symbol, (funding, volume) in self.funding_data.items():
            if symbol in snapshot:
                data = snapshot[symbol]
                mark_price = data["mark_price"]
                last_price = data["last_price"]
                age = get_age_seconds(symbol)
                age_str = f"{age:.0f}" if age >= 0 else "-"
                funding_pct = funding * 100.0
                volume_str = f"{volume:,.0f}" if volume > 0 else "-"
                
                line = f"{symbol:<{symbol_w}} | {mark_price:>{price_w}.2f} | {last_price:>{price_w}.2f} | {funding_pct:+{funding_w-1}.4f}% | {volume_str:>{volume_w}} | {age_str:>{age_w}}"
            else:
                funding_pct = funding * 100.0
                volume_str = f"{volume:,.0f}" if volume > 0 else "-"
                line = f"{symbol:<{symbol_w}} | {'-':>{price_w}} | {'-':>{price_w}} | {funding_pct:+{funding_w-1}.4f}% | {volume_str:>{volume_w}} | {'-':>{age_w}}"
            
            print(line)
        
        print()  # Ligne vide après le tableau
    
    def _display_loop(self):
        """Boucle d'affichage toutes les 5 secondes."""
        while self.running:
            self._print_price_table()
            
            # Attendre 5 secondes
            for _ in range(50):  # 50 * 0.1s = 5s
                if not self.running:
                    break
                time.sleep(0.1)
    
    def ws_on_open(self, ws, symbols):
        """Callback ouverture WebSocket."""
        category = "linear" if any("USDT" in s for s in symbols) else "inverse"
        self.logger.info(f"🌐 WS ouverte ({category})")
        
        # S'abonner aux tickers
        subscribe_message = {
            "op": "subscribe",
            "args": [f"tickers.{symbol}" for symbol in symbols]
        }
        
        ws.send(json.dumps(subscribe_message))
        self.logger.info(f"🧭 Souscription tickers → {len(symbols)} symboles")
    
    def ws_on_message(self, ws, message):
        """Callback message WebSocket."""
        try:
            data = json.loads(message)
            
            # Gestion des messages WebSocket
            if data.get("op") == "subscribe":
                success = data.get("success", False)
                if success:
                    self.logger.info(f"✅ Souscription confirmée: {data.get('ret_msg', '')}")
                else:
                    self.logger.warning(f"⚠️ Échec souscription: {data.get('ret_msg', '')}")
            elif data.get("topic", "").startswith("tickers."):
                ticker_data = data.get("data", {})
                if ticker_data:
                    symbol = ticker_data.get("symbol", "")
                    mark_price = ticker_data.get("markPrice")
                    last_price = ticker_data.get("lastPrice")
                    
                    if symbol and mark_price is not None and last_price is not None:
                        try:
                            mark_price = float(mark_price)
                            last_price = float(last_price)
                            timestamp = time.time()
                            
                            update(symbol, mark_price, last_price, timestamp)
                            # Log seulement la première mise à jour pour chaque symbole
                            if symbol not in getattr(self, '_logged_symbols', set()):
                                if not hasattr(self, '_logged_symbols'):
                                    self._logged_symbols = set()
                                self._logged_symbols.add(symbol)
                                self.logger.info(f"✅ Prix mis à jour: {symbol} = {mark_price:.2f} / {last_price:.2f}")
                        except (ValueError, TypeError) as e:
                            self.logger.warning(f"⚠️ Erreur parsing prix pour {symbol}: {e}")
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"⚠️ Erreur JSON: {e}")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur parsing: {e}")
    
    def ws_on_error(self, ws, error):
        """Callback erreur WebSocket."""
        if self.running:
            self.logger.warning(f"⚠️ WS erreur : {error}")
    
    def ws_on_close(self, ws, close_status_code, close_msg):
        """Callback fermeture WebSocket."""
        if self.running:
            self.logger.info(f"🔌 WS fermée (code={close_status_code}, reason={close_msg})")
    
    def start(self):
        """Démarre le suivi des prix avec filtrage par funding."""
        # Charger la configuration
        config = load_config()
        
        # Vérifier si le fichier de config existe
        config_path = "src/watchlist_config.fr.yaml"
        if not os.path.exists(config_path):
            self.logger.info("ℹ️ Aucun fichier de paramètres trouvé (src/watchlist_config.fr.yaml) → utilisation des valeurs par défaut.")
        
        # Créer un client Bybit pour récupérer l'URL publique
        client = BybitClient(
            testnet=self.testnet,
            timeout=10,
            api_key="dummy_key",
            api_secret="dummy_secret"
        )
        
        base_url = client.public_base_url()
        
        # Récupérer l'univers perp
        perp_data = get_perp_symbols(base_url, timeout=10)
        self.logger.info(f"🗺️ Univers perp récupéré : linear={len(perp_data['linear'])} | inverse={len(perp_data['inverse'])} | total={perp_data['total']}")
        
        # Extraire les paramètres de configuration
        categorie = config.get("categorie", "both")
        funding_min = config.get("funding_min")
        funding_max = config.get("funding_max")
        volume_min = config.get("volume_min")
        limite = config.get("limite")
        
        # Afficher les filtres
        min_display = f"{funding_min:.6f}" if funding_min is not None else "none"
        max_display = f"{funding_max:.6f}" if funding_max is not None else "none"
        volume_display = f"{volume_min:,.0f}" if volume_min is not None else "none"
        limite_display = str(limite) if limite is not None else "none"
        
        self.logger.info(f"🎛️ Filtres | catégorie={categorie} | funding_min={min_display} | funding_max={max_display} | volume_min={volume_display} | limite={limite_display}")
        
        # Récupérer les funding rates selon la catégorie
        funding_map = {}
        if categorie == "linear":
            self.logger.info("📡 Récupération des funding rates pour linear…")
            funding_map = fetch_funding_map(base_url, "linear", 10)
        elif categorie == "inverse":
            self.logger.info("📡 Récupération des funding rates pour inverse…")
            funding_map = fetch_funding_map(base_url, "inverse", 10)
        else:  # "both"
            self.logger.info("📡 Récupération des funding rates pour linear+inverse…")
            linear_funding = fetch_funding_map(base_url, "linear", 10)
            inverse_funding = fetch_funding_map(base_url, "inverse", 10)
            funding_map = {**linear_funding, **inverse_funding}  # Merger (priorité au dernier)
        
        if not funding_map:
            self.logger.warning("⚠️ Aucun funding disponible pour la catégorie sélectionnée")
            sys.exit(1)
        
        # Filtrer par funding et volume
        filtered_symbols = filter_by_funding(perp_data, funding_map, funding_min, funding_max, volume_min, limite)
        
        if not filtered_symbols:
            self.logger.warning("⚠️ Aucun symbole ne correspond aux critères de filtrage")
            sys.exit(1)
        
        # Séparer les symboles par catégorie
        linear_symbols = [symbol for symbol, _, _ in filtered_symbols if "USDT" in symbol]
        inverse_symbols = [symbol for symbol, _, _ in filtered_symbols if "USD" in symbol and "USDT" not in symbol]
        
        self.linear_symbols = linear_symbols
        self.inverse_symbols = inverse_symbols
        self.funding_data = {symbol: (funding, volume) for symbol, funding, volume in filtered_symbols}
        
        self.logger.info(f"📊 Symboles linear: {len(linear_symbols)}, inverse: {len(inverse_symbols)}")
        
        # Démarrer les connexions WebSocket selon les symboles disponibles
        if linear_symbols and inverse_symbols:
            # Les deux catégories : créer deux connexions
            self.logger.info("🔄 Démarrage des connexions WebSocket pour linear et inverse")
            self._start_dual_connections()
        elif linear_symbols:
            # Seulement linear
            self.logger.info("🔄 Démarrage de la connexion WebSocket linear")
            self._start_single_connection("linear", linear_symbols)
        elif inverse_symbols:
            # Seulement inverse
            self.logger.info("🔄 Démarrage de la connexion WebSocket inverse")
            self._start_single_connection("inverse", inverse_symbols)
        else:
            self.logger.warning("⚠️ Aucun symbole valide trouvé")
            sys.exit(1)
    
    def _start_single_connection(self, category: str, symbols: list):
        """Démarre une connexion WebSocket pour une seule catégorie."""
        # URL WebSocket selon la catégorie et l'environnement
        if category == "linear":
            url = "wss://stream-testnet.bybit.com/v5/public/linear" if self.testnet else "wss://stream.bybit.com/v5/public/linear"
        else:
            url = "wss://stream-testnet.bybit.com/v5/public/inverse" if self.testnet else "wss://stream.bybit.com/v5/public/inverse"
        
        # Créer la WebSocket
        self.ws = websocket.WebSocketApp(
            url,
            on_open=lambda ws: self.ws_on_open(ws, symbols),
            on_message=self.ws_on_message,
            on_error=self.ws_on_error,
            on_close=self.ws_on_close
        )
        
        # Démarrer le thread d'affichage
        self.display_thread = threading.Thread(target=self._display_loop)
        self.display_thread.daemon = True
        self.display_thread.start()
        
        # Démarrer la WebSocket (bloquant)
        self.ws.run_forever(ping_interval=20, ping_timeout=10)
    
    def _start_dual_connections(self):
        """Démarre deux connexions WebSocket (linear et inverse)."""
        # Démarrer le thread d'affichage
        self.display_thread = threading.Thread(target=self._display_loop)
        self.display_thread.daemon = True
        self.display_thread.start()
        
        # Démarrer les deux connexions en parallèle
        linear_thread = threading.Thread(target=self._run_linear_ws)
        inverse_thread = threading.Thread(target=self._run_inverse_ws)
        
        linear_thread.daemon = True
        inverse_thread.daemon = True
        
        linear_thread.start()
        inverse_thread.start()
        
        # Attendre que les threads se terminent
        linear_thread.join()
        inverse_thread.join()
    
    def _run_linear_ws(self):
        """Exécute la WebSocket linear."""
        url = "wss://stream-testnet.bybit.com/v5/public/linear" if self.testnet else "wss://stream.bybit.com/v5/public/linear"
        
        ws = websocket.WebSocketApp(
            url,
            on_open=lambda ws: self.ws_on_open(ws, self.linear_symbols),
            on_message=self.ws_on_message,
            on_error=self.ws_on_error,
            on_close=self.ws_on_close
        )
        
        ws.run_forever(ping_interval=20, ping_timeout=10)
    
    def _run_inverse_ws(self):
        """Exécute la WebSocket inverse."""
        url = "wss://stream-testnet.bybit.com/v5/public/inverse" if self.testnet else "wss://stream.bybit.com/v5/public/inverse"
        
        ws = websocket.WebSocketApp(
            url,
            on_open=lambda ws: self.ws_on_open(ws, self.inverse_symbols),
            on_message=self.ws_on_message,
            on_error=self.ws_on_error,
            on_close=self.ws_on_close
        )
        
        ws.run_forever(ping_interval=20, ping_timeout=10)


def main():
    """Fonction principale."""
    tracker = PriceTracker()
    try:
        tracker.start()
    except Exception as e:
        tracker.logger.error(f"❌ Erreur : {e}")
        tracker.running = False
        sys.exit(1)


if __name__ == "__main__":
    main()
