"""Point d'entrée principal du bot Bybit."""

import sys
import atexit

try:
    from .config_unified import get_settings
    from .logging_setup import setup_logging
    from .bybit_client import BybitClient
    from .http_client_manager import close_all_http_clients
except ImportError:
    from config_unified import get_settings
    from logging_setup import setup_logging
    from bybit_client import BybitClient
    from http_client_manager import close_all_http_clients


def main():
    """Fonction principale du bot."""
    # Configurer le logging
    logger = setup_logging()

    # S'assurer que les clients HTTP sont fermés à l'arrêt
    atexit.register(close_all_http_clients)

    # Étape 1: Lancement du bot
    logger.info("🚀 Lancement du bot (mode privé uniquement)")

    # Étape 2: Chargement de la configuration
    settings = get_settings()
    logger.info(
        f"📂 Configuration chargée (testnet={settings['testnet']}, "
        f"timeout={settings['timeout']})"
    )

    # Étape 3: Vérification des clés API
    if not settings["api_key"] or not settings["api_secret"]:
        logger.error(
            "⛔ Clés API manquantes : ajoute BYBIT_API_KEY et "
            "BYBIT_API_SECRET dans .env"
        )
        sys.exit(1)

    try:
        # Étape 4: Initialisation du client Bybit
        logger.info("🔐 Initialisation de la connexion privée Bybit…")
        client = BybitClient(
            testnet=settings["testnet"],
            timeout=settings["timeout"],
            api_key=settings["api_key"],
            api_secret=settings["api_secret"],
        )

        # Étape 5: Lecture du solde
        logger.info("💼 Lecture du solde (compte UNIFIED) en cours…")
        data = client.get_wallet_balance("UNIFIED")

        # Extraire la structure typique v5
        accounts = data.get("list", [])
        acct = accounts[0] if accounts else {}
        coin_list = acct.get("coin", [])
        usdt = next(
            (c for c in coin_list if str(c.get("coin")).upper() == "USDT"),
            None,
        )

        # Afficher les totaux du compte si disponibles
        if acct.get("totalEquity") or acct.get("totalWalletBalance"):
            logger.info(
                f"ℹ️ Totaux compte UNIFIED | "
                f"totalEquity={acct.get('totalEquity')} | "
                f"totalWalletBalance={acct.get('totalWalletBalance')}"
            )

        if usdt is None:
            logger.info("ℹ️ Aucun solde USDT détecté sur le compte UNIFIED")
        else:
            equity = float(usdt.get("equity", 0) or 0)
            wallet = float(usdt.get("walletBalance", 0) or 0)
            avail = float(usdt.get("availableToWithdraw", 0) or 0)

            logger.info(
                f"✅ Solde USDT | equity={equity:.4f} | "
                f"walletBalance={wallet:.4f} | "
                f"availableToWithdraw={avail:.4f}"
            )

        # Étape 6: Fin du programme
        logger.info("🏁 Fin du programme (API privée)")

        # Afficher OK et sortir proprement
        print("OK")
        sys.exit(0)

    except RuntimeError as e:
        error_msg = str(e)
        if "Clés API manquantes" in error_msg:
            logger.error(f"⛔ {error_msg}")
        elif "Authentification échouée" in error_msg:
            logger.error(f"⛔ {error_msg}")
        elif "Accès refusé" in error_msg:
            logger.error(f"⛔ {error_msg}")
        elif "Horodatage invalide" in error_msg:
            logger.error(f"⛔ {error_msg}")
        elif "Limite de requêtes" in error_msg:
            logger.error(f"⛔ {error_msg}")
        elif "Erreur API Bybit" in error_msg:
            logger.error(f"⛔ {error_msg}")
        elif "Erreur réseau/HTTP" in error_msg:
            logger.error(f"⛔ {error_msg}")
        else:
            logger.error(f"⛔ Erreur inattendue : {error_msg}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"⛔ Erreur inattendue : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
