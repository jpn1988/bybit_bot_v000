#!/usr/bin/env python3
"""Script pour analyser les imports, fonctions et classes inutilisés dans le repo."""

import ast
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, List, Tuple

class CodeAnalyzer(ast.NodeVisitor):
    """Analyse un fichier Python pour extraire définitions et utilisations."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.imports = []  # Liste des imports: (module, name, alias)
        self.definitions = []  # Liste des définitions: (type, name, line)
        self.usages = set()  # Ensemble des noms utilisés
        
    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.imports.append(('import', alias.name, name, node.lineno))
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        module = node.module or ''
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.imports.append(('from', module, name, node.lineno))
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node):
        # Ne pas compter les méthodes privées ou spéciales comme inutilisées
        if not node.name.startswith('_'):
            self.definitions.append(('function', node.name, node.lineno))
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node):
        if not node.name.startswith('_'):
            self.definitions.append(('async_function', node.name, node.lineno))
        self.generic_visit(node)
    
    def visit_ClassDef(self, node):
        if not node.name.startswith('_'):
            self.definitions.append(('class', node.name, node.lineno))
        self.generic_visit(node)
    
    def visit_Name(self, node):
        # Enregistrer les noms utilisés
        if isinstance(node.ctx, (ast.Load, ast.Del)):
            self.usages.add(node.id)
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        # Pour les attributs comme module.fonction
        self.usages.add(node.attr)
        self.generic_visit(node)

def analyze_file(filepath: Path) -> CodeAnalyzer:
    """Analyse un fichier Python et retourne l'analyseur."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filepath)
        analyzer = CodeAnalyzer(str(filepath))
        analyzer.visit(tree)
        return analyzer
    except Exception as e:
        print(f"Erreur lors de l'analyse de {filepath}: {e}")
        return None

def find_python_files(root_dir: Path) -> List[Path]:
    """Trouve tous les fichiers Python dans le répertoire."""
    python_files = []
    for path in root_dir.rglob('*.py'):
        # Ignorer les fichiers de cache
        if '__pycache__' not in str(path) and 'htmlcov' not in str(path):
            python_files.append(path)
    return python_files

def main():
    root_dir = Path('.')
    src_dir = root_dir / 'src'
    tests_dir = root_dir / 'tests'
    
    # Trouver tous les fichiers Python
    all_files = find_python_files(src_dir) + find_python_files(tests_dir)
    all_files += list(root_dir.glob('*.py'))
    
    # Analyser chaque fichier
    file_analyses = {}
    all_usages = set()
    all_definitions = {}  # {name: [(filepath, type, line)]}
    all_imports = {}  # {name: [(filepath, module, line)]}
    
    print("📊 Analyse du codebase en cours...\n")
    
    for filepath in all_files:
        analyzer = analyze_file(filepath)
        if analyzer:
            file_analyses[str(filepath)] = analyzer
            all_usages.update(analyzer.usages)
            
            # Enregistrer toutes les définitions
            for def_type, name, line in analyzer.definitions:
                if name not in all_definitions:
                    all_definitions[name] = []
                all_definitions[name].append((str(filepath), def_type, line))
            
            # Enregistrer tous les imports
            for imp_type, module, name, line in analyzer.imports:
                if name not in all_imports:
                    all_imports[name] = []
                all_imports[name].append((str(filepath), module, line))
    
    # Identifier les éléments inutilisés
    unused_definitions = []
    unused_imports = []
    
    # Vérifier les définitions
    for name, locations in all_definitions.items():
        if name not in all_usages:
            # Vérifier si c'est dans __init__.py (peut être exporté)
            is_in_init = any('__init__.py' in loc[0] for loc in locations)
            # Vérifier si c'est main (point d'entrée)
            is_main = name == 'main'
            # Vérifier si c'est un test
            is_test = name.startswith('test_') or any('test_' in loc[0] for loc in locations)
            
            if not (is_in_init or is_main or is_test):
                for filepath, def_type, line in locations:
                    unused_definitions.append((filepath, def_type, name, line))
    
    # Vérifier les imports
    for name, locations in all_imports.items():
        if name not in all_usages:
            for filepath, module, line in locations:
                unused_imports.append((filepath, module, name, line))
    
    # Afficher les résultats
    print("=" * 80)
    print("🔍 RAPPORT D'ANALYSE - ÉLÉMENTS INUTILISÉS")
    print("=" * 80)
    print()
    
    if unused_imports:
        print("📦 IMPORTS INUTILISÉS:")
        print("-" * 80)
        unused_imports.sort(key=lambda x: (x[0], x[3]))
        current_file = None
        for filepath, module, name, line in unused_imports:
            if filepath != current_file:
                print(f"\n📄 {filepath}")
                current_file = filepath
            if module:
                print(f"   Ligne {line:4d}: from {module} import {name}")
            else:
                print(f"   Ligne {line:4d}: import {name}")
        print()
    else:
        print("✅ Aucun import inutilisé trouvé!\n")
    
    print("=" * 80)
    
    if unused_definitions:
        print("\n🏗️  DÉFINITIONS INUTILISÉES (fonctions/classes):")
        print("-" * 80)
        unused_definitions.sort(key=lambda x: (x[0], x[3]))
        current_file = None
        for filepath, def_type, name, line in unused_definitions:
            if filepath != current_file:
                print(f"\n📄 {filepath}")
                current_file = filepath
            icon = "🔧" if 'function' in def_type else "📦"
            print(f"   {icon} Ligne {line:4d}: {def_type} '{name}'")
        print()
    else:
        print("\n✅ Aucune définition inutilisée trouvée!\n")
    
    print("=" * 80)
    print("\n📈 STATISTIQUES:")
    print(f"   • Fichiers analysés: {len(file_analyses)}")
    print(f"   • Imports inutilisés: {len(unused_imports)}")
    print(f"   • Définitions inutilisées: {len(unused_definitions)}")
    print()
    print("=" * 80)

if __name__ == '__main__':
    main()

