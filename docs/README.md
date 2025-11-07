# 📚 Documentation SmartOrderPlacer

## 🎯 Vue d'ensemble

Le **SmartOrderPlacer** est un système intelligent de placement d'ordres qui garantit des ordres **100% maker** avec des prix dynamiques optimisés. Il remplace les placements d'ordres directs par une logique sophistiquée qui maximise les chances d'exécution tout en minimisant les frais.

## 📋 Documentation disponible

### 📖 Guides principaux

| Document | Description | Public cible |
|----------|-------------|--------------|
| [**SMART_ORDER_PLACER.md**](./SMART_ORDER_PLACER.md) | Documentation technique complète | Développeurs |
| [**SMART_ORDER_FLOW.md**](./SMART_ORDER_FLOW.md) | Diagrammes de flux et processus | Développeurs, DevOps |
| [**CONFIGURATION_GUIDE.md**](./CONFIGURATION_GUIDE.md) | Guide de configuration et optimisation | Administrateurs |
| [**TROUBLESHOOTING_GUIDE.md**](./TROUBLESHOOTING_GUIDE.md) | Guide de dépannage et diagnostic | Support, Développeurs |

## 🚀 Démarrage rapide

### Installation

```python
# Le SmartOrderPlacer est déjà intégré dans le bot
from smart_order_placer import SmartOrderPlacer

# Initialisation
smart_placer = SmartOrderPlacer(bybit_client, logger)
```

### Utilisation basique

```python
# Placement d'ordre simple
result = smart_placer.place_order_with_refresh(
    symbol="BTCUSDT",
    side="Buy",
    qty="0.001",
    category="linear"
)

# Vérification du résultat
if result.success:
    print(f"✅ Ordre placé: {result.order_id}")
    print(f"💰 Prix: {result.price}")
    print(f"📊 Liquidité: {result.liquidity_level}")
else:
    print(f"❌ Échec: {result}")
```

## 🏗️ Architecture

```
SmartOrderPlacer
├── LiquidityClassifier     # Classification de la liquidité
├── DynamicPriceCalculator  # Calcul des prix dynamiques  
├── OrderResult            # Structure de résultat
└── SmartOrderPlacer       # Classe principale
```

## ✨ Fonctionnalités clés

- ✅ **100% Maker** : Tous les ordres utilisent `PostOnly`
- ✅ **Prix dynamiques** : Adaptation automatique à la liquidité
- ✅ **Refresh intelligent** : Annulation et remplacement automatiques
- ✅ **Respect des limites** : Minimum 5 USDT et précision Bybit
- ✅ **Cache optimisé** : Réduction des appels API
- ✅ **Logs détaillés** : Suivi complet du cycle de vie

## 🔄 Cycle de vie d'un ordre

1. **Récupération** : Order book avec cache (30s)
2. **Calcul** : Prix dynamique basé sur liquidité
3. **Vérification** : Minimum 5 USDT (ajustement auto)
4. **Placement** : Ordre PostOnly (100% maker)
5. **Surveillance** : Attente exécution (5s max)
6. **Refresh** : Retry avec prix ajusté si nécessaire

## 📊 Classification de liquidité

| Niveau | Critères | Offset | Usage |
|--------|----------|--------|-------|
| **High** | Spread < 0.1% + Volume > 1M | 0.02% | Marchés très liquides |
| **Medium** | Spread < 0.5% + Volume > 100K | 0.05% | Marchés normaux |
| **Low** | Autres cas | 0.10% | Marchés peu liquides |

## ⚙️ Configuration

### Paramètres essentiels

```python
ORDER_REFRESH_INTERVAL = 5  # secondes
MAX_RETRIES = 3             # tentatives max
MIN_ORDER_VALUE_USDT = 5.0  # minimum Bybit
```

### Offsets par liquidité

```python
MAKER_OFFSET_LEVELS = {
    "high_liquidity": 0.0002,    # 0.02%
    "medium_liquidity": 0.0005,  # 0.05%
    "low_liquidity": 0.0010      # 0.10%
}
```

## 🔧 Intégration

### Dans SchedulerManager

```python
# Ordres perp
result = self.smart_placer.place_order_with_refresh(
    symbol=symbol,
    side=side,
    qty=qty,
    category="linear"
)
```

### Dans SpotHedgeManager

```python
# Ordres spot
result = self.smart_placer.place_order_with_refresh(
    symbol=symbol,
    side=side,
    qty=spot_qty,
    category="spot"
)
```

## 📈 Monitoring

### Logs importants

```
[MAKER-OPEN] BTCUSDT Buy | price=45000.50 | offset=0.02% | retry=0
[MAKER-OPEN] Executed fully after 2.3s ✅
[MAKER-OPEN] Erreur placement ETHUSDT (retry 1): Order value too low
```

### Métriques clés

- **Taux de succès** : Pourcentage d'ordres exécutés
- **Temps d'exécution** : Durée moyenne d'exécution
- **Retries** : Nombre moyen de tentatives
- **Liquidité** : Distribution des niveaux

## 🐛 Dépannage

### Erreurs courantes

| Erreur | Cause | Solution |
|--------|-------|----------|
| `110094` | Valeur < 5 USDT | Ajustement auto quantité |
| `170134` | Trop de décimales | Formatage selon Bybit |
| `170140` | Limite inférieure | Vérification valeur finale |

### Diagnostic

```python
# Script de diagnostic
from smart_order_placer import diagnose_smart_order_placer
diagnose_smart_order_placer(smart_placer, "BTCUSDT")
```

## 📚 Ressources

### Documentation technique
- [Architecture détaillée](./SMART_ORDER_PLACER.md)
- [Diagrammes de flux](./SMART_ORDER_FLOW.md)
- [Configuration avancée](./CONFIGURATION_GUIDE.md)
- [Guide de dépannage](./TROUBLESHOOTING_GUIDE.md)

### Code source
- `src/smart_order_placer.py` - Module principal
- `src/scheduler_manager.py` - Intégration perp
- `src/spot_hedge_manager.py` - Intégration spot

### Tests
- Tests unitaires dans `tests/`
- Tests d'intégration avec testnet
- Scripts de diagnostic

## 🤝 Contribution

### Ajout de fonctionnalités
1. Créer une branche feature
2. Implémenter avec tests
3. Mettre à jour la documentation
4. Créer une pull request

### Signalement de bugs
1. Utiliser le guide de dépannage
2. Collecter les logs détaillés
3. Créer une issue avec reproduction
4. Fournir les informations de diagnostic

## 📞 Support

### Niveaux de support
1. **Auto-diagnostic** : Scripts et guides
2. **Configuration** : Ajustement paramètres
3. **Code** : Analyse et modification
4. **Infrastructure** : Support Bybit

### Contact
- Documentation : Consulter cette documentation
- Bugs : Créer une issue GitHub
- Questions : Contacter l'équipe de développement

---

## 📝 Changelog

### Version 1.0.0 (2025-10-30)
- ✅ Implémentation initiale
- ✅ Support ordres perp et spot
- ✅ Classification de liquidité
- ✅ Refresh automatique
- ✅ Cache optimisé
- ✅ Documentation complète

### Prochaines versions
- 🔄 Machine Learning pour prédiction liquidité
- 🔄 Support multi-exchange
- 🔄 Stratégies avancées (TWAP, iceberg)
- 🔄 Dashboard de performance

---

**Version** : 1.0.0  
**Dernière mise à jour** : 2025-10-30  
**Auteur** : Équipe de développement Bybit Bot
