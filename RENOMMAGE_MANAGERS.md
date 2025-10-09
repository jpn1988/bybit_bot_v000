# Plan de renommage des fichiers "manager"

## 🎯 Objectif

Simplifier les noms de fichiers en supprimant le préfixe "unified" qui n'apporte pas de valeur et crée de la confusion.

## 📋 Renommages proposés

| Ancien nom | Nouveau nom | Raison |
|------------|-------------|--------|
| `unified_data_manager.py` | `data_manager.py` | "unified" redondant - c'est LE gestionnaire de données |
| `config_unified.py` | `config_manager.py` | Convention cohérente avec les autres managers |
| `unified_monitoring_manager.py` | `monitoring_manager.py` | "unified" redondant - c'est LE gestionnaire de monitoring |

## 📊 Impact des changements

### 1. `unified_data_manager.py` → `data_manager.py`

**Fichiers à mettre à jour** (17 fichiers) :
```
src/bot.py
src/bot_initializer.py
src/bot_configurator.py
src/bot_starter.py
src/watchlist_manager.py
src/opportunity_manager.py
src/opportunity_detector.py
src/candidate_monitor.py
src/display_manager.py
src/ws_manager.py
src/callback_manager.py
src/unified_monitoring_manager.py
src/unified_data_manager_README.md
tests/test_unified_data_manager.py
tests/test_integration.py
tests/test_error_handling.py
JOURNAL.md
```

**Changements d'imports** :
```python
# Avant
from unified_data_manager import UnifiedDataManager

# Après
from data_manager import DataManager
```

### 2. `config_unified.py` → `config_manager.py`

**Fichiers à mettre à jour** (7 fichiers) :
```
src/bot.py
src/bot_initializer.py
src/watchlist_manager.py
src/funding_fetcher.py
src/logging_setup.py
tests/test_config.py
tests/test_data_fetcher.py
```

**Changements d'imports** :
```python
# Avant
from config_unified import UnifiedConfigManager, get_settings

# Après
from config_manager import ConfigManager, get_settings
```

**Note** : L'alias `ConfigManager = UnifiedConfigManager` existe déjà (ligne 537 de config_unified.py)

### 3. `unified_monitoring_manager.py` → `monitoring_manager.py`

**Fichiers à mettre à jour** (6 fichiers) :
```
src/bot_initializer.py
src/bot_starter.py
src/bot_health_monitor.py
src/callback_manager.py
tests/test_monitoring_components.py
tests/test_data_fetcher.py
```

**Changements d'imports** :
```python
# Avant
from unified_monitoring_manager import UnifiedMonitoringManager

# Après
from monitoring_manager import MonitoringManager
```

## 🔄 Stratégie de migration

### Option 1 : Migration immédiate (Recommandée)

1. **Renommer les fichiers** avec `git mv`
2. **Rechercher/Remplacer** dans tout le projet :
   - `unified_data_manager` → `data_manager`
   - `UnifiedDataManager` → `DataManager`
   - `config_unified` → `config_manager`
   - `UnifiedConfigManager` → `ConfigManager`
   - `unified_monitoring_manager` → `monitoring_manager`
   - `UnifiedMonitoringManager` → `MonitoringManager`
3. **Tester** que tout fonctionne
4. **Commit** avec un message clair

**Avantages** :
- ✅ Changement propre et immédiat
- ✅ Pas de code de compatibilité à maintenir
- ✅ Noms plus clairs dès maintenant

**Inconvénients** :
- ⚠️ Nécessite de mettre à jour ~30 fichiers
- ⚠️ Peut casser des branches en cours

### Option 2 : Migration progressive avec alias

1. **Garder les anciens fichiers** avec des imports d'alias :
   ```python
   # unified_data_manager.py (ancien fichier gardé temporairement)
   from data_manager import DataManager as UnifiedDataManager
   import warnings
   
   warnings.warn(
       "unified_data_manager est déprécié. Utilisez data_manager à la place.",
       DeprecationWarning,
       stacklevel=2
   )
   ```

2. **Migrer progressivement** les imports au fil du temps

**Avantages** :
- ✅ Migration douce sans casser le code existant
- ✅ Avertissements pour guider la migration

**Inconvénients** :
- ⚠️ Maintenance de code de compatibilité
- ⚠️ Confusion temporaire (2 façons de faire la même chose)
- ⚠️ Migration qui peut traîner

## ✅ Recommandation finale

**Option 1 : Migration immédiate**

**Raisons** :
1. Le projet est en développement actif (pas de version stable déployée)
2. Pas de code externe qui dépend de ces noms
3. Meilleur moment pour faire un changement propre
4. Noms plus clairs = meilleure lisibilité immédiate

## 📝 Script de migration automatique

```bash
#!/bin/bash
# migration_managers.sh

echo "🔄 Migration des noms de managers..."

# 1. Renommer les fichiers
echo "📁 Renommage des fichiers..."
git mv src/unified_data_manager.py src/data_manager.py
git mv src/config_unified.py src/config_manager.py
git mv src/unified_monitoring_manager.py src/monitoring_manager.py
git mv src/unified_data_manager_README.md src/data_manager_README.md
git mv tests/test_unified_data_manager.py tests/test_data_manager.py

# 2. Mettre à jour les imports (Linux/Mac avec sed)
echo "🔧 Mise à jour des imports..."
find . -type f -name "*.py" -exec sed -i 's/from unified_data_manager import/from data_manager import/g' {} +
find . -type f -name "*.py" -exec sed -i 's/import unified_data_manager/import data_manager/g' {} +
find . -type f -name "*.py" -exec sed -i 's/UnifiedDataManager/DataManager/g' {} +

find . -type f -name "*.py" -exec sed -i 's/from config_unified import/from config_manager import/g' {} +
find . -type f -name "*.py" -exec sed -i 's/import config_unified/import config_manager/g' {} +
find . -type f -name "*.py" -exec sed -i 's/UnifiedConfigManager/ConfigManager/g' {} +

find . -type f -name "*.py" -exec sed -i 's/from unified_monitoring_manager import/from monitoring_manager import/g' {} +
find . -type f -name "*.py" -exec sed -i 's/import unified_monitoring_manager/import monitoring_manager/g' {} +
find . -type f -name "*.py" -exec sed -i 's/UnifiedMonitoringManager/MonitoringManager/g' {} +

# 3. Mettre à jour les fichiers markdown
echo "📄 Mise à jour de la documentation..."
find . -type f -name "*.md" -exec sed -i 's/unified_data_manager/data_manager/g' {} +
find . -type f -name "*.md" -exec sed -i 's/UnifiedDataManager/DataManager/g' {} +
find . -type f -name "*.md" -exec sed -i 's/config_unified/config_manager/g' {} +
find . -type f -name "*.md" -exec sed -i 's/UnifiedConfigManager/ConfigManager/g' {} +
find . -type f -name "*.md" -exec sed -i 's/unified_monitoring_manager/monitoring_manager/g' {} +
find . -type f -name "*.md" -exec sed -i 's/UnifiedMonitoringManager/MonitoringManager/g' {} +

echo "✅ Migration terminée !"
echo "🧪 Testez le bot avec : python src/bot.py"
```

**Pour Windows (PowerShell)** :
```powershell
# migration_managers.ps1

Write-Host "🔄 Migration des noms de managers..." -ForegroundColor Cyan

# 1. Renommer les fichiers
Write-Host "📁 Renommage des fichiers..." -ForegroundColor Yellow
git mv src/unified_data_manager.py src/data_manager.py
git mv src/config_unified.py src/config_manager.py
git mv src/unified_monitoring_manager.py src/monitoring_manager.py
git mv src/unified_data_manager_README.md src/data_manager_README.md
git mv tests/test_unified_data_manager.py tests/test_data_manager.py

# 2. Mettre à jour les imports
Write-Host "🔧 Mise à jour des imports..." -ForegroundColor Yellow

# Fonction pour remplacer dans tous les fichiers Python
function Replace-InFiles {
    param([string]$pattern, [string]$replacement)
    Get-ChildItem -Recurse -Include *.py | ForEach-Object {
        (Get-Content $_.FullName) -replace $pattern, $replacement | Set-Content $_.FullName
    }
}

Replace-InFiles "from unified_data_manager import" "from data_manager import"
Replace-InFiles "import unified_data_manager" "import data_manager"
Replace-InFiles "UnifiedDataManager" "DataManager"

Replace-InFiles "from config_unified import" "from config_manager import"
Replace-InFiles "import config_unified" "import config_manager"
Replace-InFiles "UnifiedConfigManager" "ConfigManager"

Replace-InFiles "from unified_monitoring_manager import" "from monitoring_manager import"
Replace-InFiles "import unified_monitoring_manager" "import monitoring_manager"
Replace-InFiles "UnifiedMonitoringManager" "MonitoringManager"

# 3. Mettre à jour les fichiers markdown
Write-Host "📄 Mise à jour de la documentation..." -ForegroundColor Yellow
Get-ChildItem -Recurse -Include *.md | ForEach-Object {
    $content = Get-Content $_.FullName
    $content = $content -replace "unified_data_manager", "data_manager"
    $content = $content -replace "UnifiedDataManager", "DataManager"
    $content = $content -replace "config_unified", "config_manager"
    $content = $content -replace "UnifiedConfigManager", "ConfigManager"
    $content = $content -replace "unified_monitoring_manager", "monitoring_manager"
    $content = $content -replace "UnifiedMonitoringManager", "MonitoringManager"
    $content | Set-Content $_.FullName
}

Write-Host "✅ Migration terminée !" -ForegroundColor Green
Write-Host "🧪 Testez le bot avec : python src/bot.py" -ForegroundColor Cyan
```

## 🧪 Tests après migration

```bash
# 1. Vérifier les imports
cd src
python -c "from data_manager import DataManager; print('✅ DataManager OK')"
python -c "from config_manager import ConfigManager; print('✅ ConfigManager OK')"
python -c "from monitoring_manager import MonitoringManager; print('✅ MonitoringManager OK')"

# 2. Tester le bot
python -c "from bot import AsyncBotRunner; print('✅ Bot OK')"

# 3. Lancer les tests unitaires
cd ..
python -m pytest tests/ -v

# 4. Vérifier qu'aucun ancien import ne reste
grep -r "unified_data_manager" src/ tests/
grep -r "config_unified" src/ tests/
grep -r "unified_monitoring_manager" src/ tests/
# Si aucun résultat → ✅ Migration complète
```

## 📚 Mise à jour de la documentation

Après la migration, mettre à jour :
- ✅ `ARCHITECTURE.md` (déjà fait avec les nouveaux noms)
- ⏳ `README.md` : Ajouter référence vers ARCHITECTURE.md
- ⏳ `JOURNAL.md` : Ajouter une entrée pour documenter le changement
- ⏳ `data_manager_README.md` : Mettre à jour les références

## 🎯 Bénéfices attendus

| Avant | Après | Gain |
|-------|-------|------|
| `unified_data_manager.py` (28 caractères) | `data_manager.py` (16 caractères) | **-43% plus court** |
| `config_unified.py` (18 caractères) | `config_manager.py` (18 caractères) | **Cohérence** |
| `unified_monitoring_manager.py` (32 caractères) | `monitoring_manager.py` (22 caractères) | **-31% plus court** |
| Confusion : "Pourquoi 'unified' ?" | Clarté : Noms descriptifs | **Compréhension** |

---

**Note** : Ce document est un plan. La migration sera effectuée dans un commit séparé pour faciliter le suivi et le rollback si nécessaire.

**Dernière mise à jour** : 9 octobre 2025

