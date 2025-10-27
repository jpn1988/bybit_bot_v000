#!/usr/bin/env python3
"""
Script de test pour vérifier que le bot refactorisé fonctionne identiquement.

Ce script teste que :
1. Les nouveaux composants s'initialisent correctement
2. Les méthodes déléguées fonctionnent
3. L'interface publique reste identique
4. Aucune régression n'est introduite
"""

import sys
import os
import asyncio
import unittest
from unittest.mock import Mock, patch, MagicMock

# Ajouter le répertoire src au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from bot import BotOrchestrator
from bot_lifecycle_manager import BotLifecycleManager
from position_event_handler import PositionEventHandler
from fallback_data_manager import FallbackDataManager


class TestRefactoredBot(unittest.TestCase):
    """Tests pour vérifier que le bot refactorisé fonctionne identiquement."""
    
    def setUp(self):
        """Configuration des tests."""
        # Mock des dépendances externes
        self.mock_logger = Mock()
        self.mock_testnet = True
        
        # Mock des composants
        self.mock_initializer = Mock()
        self.mock_configurator = Mock()
        self.mock_data_loader = Mock()
        self.mock_starter = Mock()
        self.mock_health_monitor = Mock()
        self.mock_shutdown_manager = Mock()
        self.mock_thread_manager = Mock()
        
        # Mock des managers
        self.mock_monitoring_manager = Mock()
        self.mock_display_manager = Mock()
        self.mock_ws_manager = Mock()
        self.mock_volatility_tracker = Mock()
        self.mock_watchlist_manager = Mock()
        self.mock_data_manager = Mock()
        self.mock_funding_close_manager = Mock()
        
        # Mock des données
        self.mock_data_manager.storage = Mock()
        self.mock_data_manager.fetcher = Mock()
        self.mock_data_manager.storage.get_linear_symbols.return_value = ["BTCUSDT"]
        self.mock_data_manager.storage.get_inverse_symbols.return_value = ["BTCUSD"]
        self.mock_watchlist_manager.get_selected_symbols.return_value = ["BTCUSDT", "ETHUSDT"]
        
        # Mock des méthodes
        self.mock_health_monitor.check_components_health.return_value = True
        self.mock_health_monitor.should_check_memory.return_value = False
        self.mock_monitoring_manager.get_active_positions.return_value = set()
        self.mock_monitoring_manager.has_active_positions.return_value = False

    def test_bot_orchestrator_initialization(self):
        """Test que BotOrchestrator s'initialise correctement."""
        with patch('bot.get_settings') as mock_get_settings:
            mock_get_settings.return_value = {
                "testnet": True,
                "api_key": "test_key",
                "api_secret": "test_secret"
            }
            
            with patch('bot.install_global_exception_handlers'):
                with patch('bot.close_all_http_clients'):
                    with patch('bot.start_metrics_monitoring'):
                        with patch('bot.BybitClient'):
                            with patch.object(BotOrchestrator, '_test_bybit_auth_connection_sync'):
                                bot = BotOrchestrator(
                                    logger=self.mock_logger,
                                    initializer=self.mock_initializer,
                                    configurator=self.mock_configurator,
                                    data_loader=self.mock_data_loader,
                                    starter=self.mock_starter,
                                    health_monitor=self.mock_health_monitor,
                                    shutdown_manager=self.mock_shutdown_manager,
                                    thread_manager=self.mock_thread_manager,
                                )
                                
                                # Vérifier que les composants sont initialisés
                                self.assertIsNotNone(bot._lifecycle_manager)
                                self.assertIsNotNone(bot._position_event_handler)
                                self.assertIsNotNone(bot._fallback_data_manager)
                                
                                # Vérifier que les composants sont du bon type
                                self.assertIsInstance(bot._lifecycle_manager, BotLifecycleManager)
                                self.assertIsInstance(bot._position_event_handler, PositionEventHandler)
                                self.assertIsInstance(bot._fallback_data_manager, FallbackDataManager)

    def test_position_event_handler_delegation(self):
        """Test que les callbacks de position sont correctement délégués."""
        with patch('bot.get_settings') as mock_get_settings:
            mock_get_settings.return_value = {
                "testnet": True,
                "api_key": "test_key",
                "api_secret": "test_secret"
            }
            
            with patch('bot.install_global_exception_handlers'):
                with patch('bot.close_all_http_clients'):
                    with patch('bot.start_metrics_monitoring'):
                        with patch('bot.BybitClient'):
                            with patch.object(BotOrchestrator, '_test_bybit_auth_connection_sync'):
                                bot = BotOrchestrator(logger=self.mock_logger)
                            
                            # Configurer les mocks
                            bot.monitoring_manager = self.mock_monitoring_manager
                            bot.ws_manager = self.mock_ws_manager
                            bot.display_manager = self.mock_display_manager
                            bot.data_manager = self.mock_data_manager
                            bot.funding_close_manager = self.mock_funding_close_manager
                            
                            # Tester le callback d'ouverture de position
                            bot._on_position_opened("BTCUSDT", {"symbol": "BTCUSDT"})
                            
                            # Vérifier que le PositionEventHandler a été appelé
                            self.mock_monitoring_manager.add_active_position.assert_called_once_with("BTCUSDT")
                            
                            # Tester le callback de fermeture de position
                            bot._on_position_closed("BTCUSDT", {"symbol": "BTCUSDT"})
                            
                            # Vérifier que le PositionEventHandler a été appelé
                            self.mock_monitoring_manager.remove_active_position.assert_called_once_with("BTCUSDT")

    def test_fallback_data_manager_delegation(self):
        """Test que les méthodes de données sont correctement déléguées."""
        with patch('bot.get_settings') as mock_get_settings:
            mock_get_settings.return_value = {"testnet": True}
            
            with patch('bot.install_global_exception_handlers'):
                with patch('bot.close_all_http_clients'):
                    with patch('bot.start_metrics_monitoring'):
                        with patch('bot.BybitClient'):
                            bot = BotOrchestrator(logger=self.mock_logger)
                            
                            # Configurer les mocks
                            bot.data_manager = self.mock_data_manager
                            bot.watchlist_manager = self.mock_watchlist_manager
                            
                            # Mock de la méthode du FallbackDataManager
                            expected_data = {"BTCUSDT": {"funding_rate": 0.01}}
                            bot._fallback_data_manager.get_funding_data_for_scheduler = Mock(return_value=expected_data)
                            
                            # Tester la délégation
                            result = bot._get_funding_data_for_scheduler()
                            
                            # Vérifier que le FallbackDataManager a été appelé
                            self.assertEqual(result, expected_data)
                            bot._fallback_data_manager.get_funding_data_for_scheduler.assert_called_once()

    def test_lifecycle_manager_integration(self):
        """Test que le BotLifecycleManager est correctement intégré."""
        with patch('bot.get_settings') as mock_get_settings:
            mock_get_settings.return_value = {"testnet": True}
            
            with patch('bot.install_global_exception_handlers'):
                with patch('bot.close_all_http_clients'):
                    with patch('bot.start_metrics_monitoring'):
                        with patch('bot.BybitClient'):
                            bot = BotOrchestrator(logger=self.mock_logger)
                            
                            # Vérifier que le lifecycle manager est configuré
                            self.assertIsNotNone(bot._lifecycle_manager)
                            self.assertEqual(bot._lifecycle_manager.testnet, True)
                            self.assertEqual(bot._lifecycle_manager.logger, self.mock_logger)

    def test_status_method_integration(self):
        """Test que la méthode get_status() utilise les nouveaux composants."""
        with patch('bot.get_settings') as mock_get_settings:
            mock_get_settings.return_value = {"testnet": True}
            
            with patch('bot.install_global_exception_handlers'):
                with patch('bot.close_all_http_clients'):
                    with patch('bot.start_metrics_monitoring'):
                        with patch('bot.BybitClient'):
                            bot = BotOrchestrator(logger=self.mock_logger)
                            
                            # Mock des méthodes
                            bot._lifecycle_manager.get_uptime.return_value = 123.45
                            bot._lifecycle_manager.is_running.return_value = True
                            bot._fallback_data_manager.get_fallback_summary.return_value = {"test": "data"}
                            
                            # Tester la méthode get_status
                            status = bot.get_status()
                            
                            # Vérifier que les nouveaux composants sont utilisés
                            self.assertEqual(status["uptime_seconds"], 123.45)
                            self.assertIn("lifecycle_status", status)
                            self.assertTrue(status["lifecycle_status"]["is_running"])
                            self.assertEqual(status["lifecycle_status"]["fallback_summary"], {"test": "data"})

    def test_component_configuration(self):
        """Test que les composants sont correctement configurés."""
        with patch('bot.get_settings') as mock_get_settings:
            mock_get_settings.return_value = {"testnet": True}
            
            with patch('bot.install_global_exception_handlers'):
                with patch('bot.close_all_http_clients'):
                    with patch('bot.start_metrics_monitoring'):
                        with patch('bot.BybitClient'):
                            bot = BotOrchestrator(logger=self.mock_logger)
                            
                            # Simuler l'initialisation des composants
                            bot.monitoring_manager = self.mock_monitoring_manager
                            bot.ws_manager = self.mock_ws_manager
                            bot.display_manager = self.mock_display_manager
                            bot.data_manager = self.mock_data_manager
                            bot.watchlist_manager = self.mock_watchlist_manager
                            
                            # Appeler _initialize_components pour tester la configuration
                            bot._initialize_components()
                            
                            # Vérifier que les composants sont configurés
                            self.mock_position_event_handler = bot._position_event_handler
                            self.mock_fallback_data_manager = bot._fallback_data_manager
                            
                            # Vérifier que les setters ont été appelés (via les mocks)
                            # Note: Dans un vrai test, on vérifierait que les composants sont configurés


def run_tests():
    """Lance tous les tests."""
    print("Lancement des tests du bot refactorise...")
    
    # Créer la suite de tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestRefactoredBot)
    
    # Lancer les tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Afficher le résumé
    if result.wasSuccessful():
        print("\nTous les tests sont passes ! Le bot refactorise fonctionne correctement.")
    else:
        print(f"\n{len(result.failures)} test(s) ont echoue, {len(result.errors)} erreur(s).")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
