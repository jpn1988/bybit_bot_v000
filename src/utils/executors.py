#!/usr/bin/env python3
"""Exécuteur global partagé pour toutes les tâches concurrentes du bot."""

from concurrent.futures import ThreadPoolExecutor


# ✅ Instance unique : tous les modules doivent réutiliser ce même pool
GLOBAL_EXECUTOR = ThreadPoolExecutor(max_workers=8)

