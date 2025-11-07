#!/usr/bin/env python3
"""
Surveillant d'ordres pour le bot Bybit.

Ce module gère la surveillance et l'annulation automatique des ordres maker
qui ne sont pas exécutés dans le délai imparti.
"""

import asyncio
import time
import logging
from typing import Dict, Set, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from utils.async_wrappers import run_in_thread


@dataclass
class PendingOrder:
    """Représente un ordre en attente d'exécution."""
    order_id: str
    symbol: str
    side: str
    qty: str
    price: float
    placed_at: datetime
    timeout_minutes: int

    @property
    def is_expired(self) -> bool:
        """Vérifie si l'ordre a expiré."""
        timeout_delta = timedelta(minutes=self.timeout_minutes)
        is_expired = datetime.now() > self.placed_at + timeout_delta

        # Log de debug pour voir le calcul
        if is_expired:
            logger = logging.getLogger(__name__)
            now = datetime.now()
            time_since_placed = now - self.placed_at
            logger.debug(
                f"🔍 [ORDER_EXPIRED] Ordre {self.order_id} expiré - "
                f"Placé: {self.placed_at.strftime('%H:%M:%S')}, "
                f"Maintenant: {now.strftime('%H:%M:%S')}, "
                f"Durée: {time_since_placed.total_seconds():.1f}s, "
                f"Timeout: {self.timeout_minutes}min"
            )

        return is_expired

    @property
    def remaining_minutes(self) -> float:
        """Retourne le nombre de minutes restantes avant expiration."""
        timeout_delta = timedelta(minutes=self.timeout_minutes)
        expiration_time = self.placed_at + timeout_delta
        remaining = expiration_time - datetime.now()
        return max(0, remaining.total_seconds() / 60)


class OrderMonitor:
    """
    Surveillant d'ordres pour gérer l'annulation automatique.

    Cette classe surveille les ordres maker placés et les annule
    automatiquement s'ils ne sont pas exécutés dans le délai imparti.
    """

    def __init__(self, bybit_client, logger: Optional[logging.Logger] = None,
                 on_order_timeout: Optional[Callable[[str, str, str, str, float], None]] = None):
        """
        Initialise le surveillant d'ordres.

        Args:
            bybit_client: Client Bybit pour les opérations API
            logger: Logger pour les messages (optionnel)
            on_order_timeout: Callback appelé quand un ordre expire (order_id, symbol, side, qty, price)
        """
        self.bybit_client = bybit_client
        self.logger = logger or logging.getLogger(__name__)
        self.on_order_timeout = on_order_timeout

        # Dictionnaire des ordres en attente : order_id -> PendingOrder
        self.pending_orders: Dict[str, PendingOrder] = {}

        # Set des ordres en cours d'annulation pour éviter les doublons
        self.cancelling_orders: Set[str] = set()

        # Journalisation synthétique
        self._summary_interval = 60
        self._last_summary_ts = 0.0

    def add_order(self, order_id: str, symbol: str, side: str, qty: str,
                  price: float, timeout_minutes: int) -> None:
        """
        Ajoute un ordre à la surveillance.

        Args:
            order_id: ID de l'ordre
            symbol: Symbole de la paire
            side: Côté de l'ordre (Buy/Sell)
            qty: Quantité
            price: Prix de l'ordre
            timeout_minutes: Délai d'attente en minutes
        """
        pending_order = PendingOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            placed_at=datetime.now(),
            timeout_minutes=timeout_minutes
        )

        self.pending_orders[order_id] = pending_order
        self.logger.info(
            f"[ORDER] 🔍 Ordre ajouté à la surveillance: {symbol} {side} {qty} @ {price:.4f} "
            f"(ID: {order_id}, timeout: {timeout_minutes}min)"
        )

    def remove_order(self, order_id: str) -> None:
        """
        Retire un ordre de la surveillance (exécuté ou annulé manuellement).

        Args:
            order_id: ID de l'ordre à retirer
        """
        if order_id in self.pending_orders:
            order = self.pending_orders.pop(order_id)
            self.logger.info(
                f"[ORDER] ✅ Ordre retiré de la surveillance: {order.symbol} "
                f"(ID: {order_id})"
            )

        # Retirer aussi de la liste des ordres en cours d'annulation
        self.cancelling_orders.discard(order_id)

    async def check_orders_status(self) -> None:
        """
        Vérifie le statut des ordres en attente et annule ceux qui ont expiré.

        Cette méthode doit être appelée périodiquement pour surveiller les ordres.
        """
        if not self.pending_orders:
            return

        # Log de debug pour voir quand cette méthode est appelée
        self.logger.debug(f"🔍 [ORDER] Vérification de {len(self.pending_orders)} ordre(s) en attente")

        # Log synthétique périodique
        self._log_periodic_summary()

        # Identifier les ordres expirés
        expired_orders = [
            order for order in self.pending_orders.values()
            if order.is_expired
        ]

        if not expired_orders:
            return

        self.logger.warning(
            f"[ORDER] ⏰ {len(expired_orders)} ordre(s) expiré(s) détecté(s)"
        )

        # Annuler les ordres expirés
        for order in expired_orders:
            await self._cancel_expired_order(order)

    async def _cancel_expired_order(self, order: PendingOrder) -> None:
        """
        Annule un ordre expiré.

        Args:
            order: Ordre à annuler
        """
        order_id = order.order_id

        # Éviter les annulations multiples
        if order_id in self.cancelling_orders:
            self.logger.debug(f"🔍 [ORDER] Ordre {order_id} déjà en cours d'annulation")
            return

        self.cancelling_orders.add(order_id)

        # Log détaillé du timing
        now = datetime.now()
        time_since_placed = now - order.placed_at
        self.logger.warning(
            f"[ORDER] 🚫 Annulation de l'ordre expiré: {order.symbol} "
            f"{order.side} {order.qty} @ {order.price:.4f} (ID: {order_id}) - "
            f"Placé: {order.placed_at.strftime('%H:%M:%S')}, "
            f"Maintenant: {now.strftime('%H:%M:%S')}, "
            f"Durée: {time_since_placed.total_seconds():.1f}s, "
            f"Timeout: {order.timeout_minutes}min"
        )

        try:
            # Appeler l'API Bybit pour annuler l'ordre
            self.logger.debug("[ASYNC] Bybit REST call exécuté dans un thread : cancel_order()")
            response = await run_in_thread(
                self.bybit_client.cancel_order,
                symbol=order.symbol,
                order_id=order_id,
                category="linear"
            )

            # Vérifier si l'annulation a réussi
            if response and response.get('orderId') == order_id:
                self.logger.info(
                    f"[ORDER] ✅ Ordre annulé avec succès: {order.symbol} (ID: {order_id})"
                )

                # Appeler le callback de timeout si défini
                if self.on_order_timeout:
                    try:
                        await asyncio.to_thread(
                            self.on_order_timeout,
                            order_id,
                            order.symbol,
                            order.side,
                            order.qty,
                            order.price,
                        )
                    except Exception as e:
                        self.logger.error(f"[ORDER] ❌ Erreur callback timeout: {e}")
            else:
                self.logger.error(
                    f"[ORDER] ❌ Échec de l'annulation: {order.symbol} (ID: {order_id}) - Response: {response}"
                )

        except Exception as e:
            self.logger.error(
                f"[ORDER] ❌ Erreur lors de l'annulation de {order.symbol} "
                f"(ID: {order_id}): {e}"
            )
        finally:
            # Retirer l'ordre de la surveillance
            self.remove_order(order_id)

    def get_pending_orders_info(self) -> Dict[str, Any]:
        """
        Retourne des informations sur les ordres en attente.

        Returns:
            Dict contenant les statistiques des ordres en attente
        """
        if not self.pending_orders:
            return {
                "total_pending": 0,
                "expired_count": 0,
                "orders": []
            }

        expired_orders = [order for order in self.pending_orders.values() if order.is_expired]

        orders_info = []
        for order in self.pending_orders.values():
            orders_info.append({
                "order_id": order.order_id,
                "symbol": order.symbol,
                "side": order.side,
                "qty": order.qty,
                "price": order.price,
                "placed_at": order.placed_at.isoformat(),
                "remaining_minutes": round(order.remaining_minutes, 2),
                "is_expired": order.is_expired
            })

        return {
            "total_pending": len(self.pending_orders),
            "expired_count": len(expired_orders),
            "orders": orders_info
        }

    def _log_periodic_summary(self) -> None:
        """Émet un résumé synthétique au plus toutes les 60 secondes."""
        now = time.time()
        if now - self._last_summary_ts < self._summary_interval:
            return

        self._last_summary_ts = now
        expired_count = sum(1 for order in self.pending_orders.values() if order.is_expired)
        self.logger.info(
            f"[ORDER] Summary pending={len(self.pending_orders)} expirés={expired_count} annulations_en_cours={len(self.cancelling_orders)}"
        )

    def cleanup_expired_orders(self) -> None:
        """
        Nettoie les ordres expirés de la surveillance.

        Cette méthode peut être appelée pour forcer le nettoyage des ordres expirés.
        """
        expired_order_ids = [
            order_id for order_id, order in self.pending_orders.items()
            if order.is_expired
        ]

        for order_id in expired_order_ids:
            self.remove_order(order_id)

        if expired_order_ids:
            self.logger.info(
                f"[ORDER] 🧹 Nettoyage de {len(expired_order_ids)} ordre(s) expiré(s)"
            )
