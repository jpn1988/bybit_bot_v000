#!/usr/bin/env python3
"""
Tests pour BotOrchestrator - Orchestrateur principal du bot Bybit.

Ce module teste :
- L'initialisation de BotOrchestrator
- Le démarrage et l'arrêt du bot
- La gestion des composants
- La surveillance de santé
- La gestion des erreurs
"""

import pytest
import asyncio
import time
import signal
import sys
from unittest.mock import Mock, patch, AsyncMock
from bot import BotOrchestrator, AsyncBotRunner, main_async


class TestBotOrchestrator:
    """Tests pour la classe BotOrchestrator."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock des dépendances externes."""
        with patch('bot.setup_logging') as mock_logging, \
             patch('bot.get_settings') as mock_settings, \
            patch('bot.close_all_http_clients') as mock_close, \
            patch('bot.start_metrics_monitoring') as mock_metrics, \
            patch('bot.BotInitializer') as mock_initializer, \
            patch('bot.BotConfigurator') as mock_configurator, \
            patch('bot.DataManager') as mock_data_manager, \
            patch('bot.BotStarter') as mock_starter, \
            patch('bot.BotHealthMonitor') as mock_health, \
            patch('bot.ShutdownManager') as mock_shutdown, \
            patch('bot.ThreadManager') as mock_thread:
            
            # Configuration des mocks
            mock_logging.return_value = Mock()
            mock_settings.return_value = {"testnet": True}
            
            # Mock des managers
            mock_init_instance = Mock()
            mock_config_instance = Mock()
            mock_data_instance = Mock()
            mock_starter_instance = Mock()
            mock_health_instance = Mock()
            mock_shutdown_instance = Mock()
            mock_thread_instance = Mock()
            
            mock_initializer.return_value = mock_init_instance
            mock_configurator.return_value = mock_config_instance
            mock_data_manager.return_value = mock_data_instance
            mock_starter.return_value = mock_starter_instance
            mock_health.return_value = mock_health_instance
            mock_shutdown.return_value = mock_shutdown_instance
            mock_thread.return_value = mock_thread_instance
            
            # Mock des managers retournés par l'initializer
            mock_managers = {
                "data_manager": Mock(),
                "display_manager": Mock(),
                "monitoring_manager": Mock(),
                "ws_manager": Mock(),
                "volatility_tracker": Mock(),
                "watchlist_manager": Mock(),
                "callback_manager": Mock(),
                "opportunity_manager": Mock(),
            }
            mock_init_instance.get_managers.return_value = mock_managers
            
            # Mock du metrics_monitor (importé dynamiquement)
            with patch('metrics_monitor.metrics_monitor', Mock()):
                yield {
                    'mock_logging': mock_logging,
                    'mock_settings': mock_settings,
                    'mock_close': mock_close,
                    'mock_metrics': mock_metrics,
                    'mock_initializer': mock_initializer,
                    'mock_configurator': mock_configurator,
                    'mock_data_manager': mock_data_manager,
                    'mock_starter': mock_starter,
                    'mock_health': mock_health,
                    'mock_shutdown': mock_shutdown,
                    'mock_thread': mock_thread,
                    'mock_init_instance': mock_init_instance,
                    'mock_config_instance': mock_config_instance,
                    'mock_data_instance': mock_data_instance,
                    'mock_starter_instance': mock_starter_instance,
                    'mock_health_instance': mock_health_instance,
                    'mock_shutdown_instance': mock_shutdown_instance,
                    'mock_thread_instance': mock_thread_instance,
                    'mock_managers': mock_managers,
                }

    def test_bot_orchestrator_initialization(self, mock_dependencies):
        """Test de l'initialisation de BotOrchestrator."""
        orchestrator = BotOrchestrator()
        
        # Vérifier que les composants sont initialisés
        assert orchestrator.running is True
        assert orchestrator.testnet is True
        assert orchestrator.start_time is not None
        
        # Vérifier que les managers sont initialisés
        assert hasattr(orchestrator, '_initializer')
        assert hasattr(orchestrator, '_configurator')
        assert hasattr(orchestrator, '_data_loader')
        assert hasattr(orchestrator, '_starter')
        assert hasattr(orchestrator, '_health_monitor')
        assert hasattr(orchestrator, '_shutdown_manager')
        assert hasattr(orchestrator, '_thread_manager')
        
        # Vérifier que les managers sont récupérés
        assert hasattr(orchestrator, 'data_manager')
        assert hasattr(orchestrator, 'display_manager')
        assert hasattr(orchestrator, 'monitoring_manager')
        assert hasattr(orchestrator, 'ws_manager')
        assert hasattr(orchestrator, 'volatility_tracker')
        assert hasattr(orchestrator, 'watchlist_manager')
        assert hasattr(orchestrator, 'callback_manager')
        assert hasattr(orchestrator, 'opportunity_manager')
        
        # Vérifier que les méthodes d'initialisation sont appelées
        mock_dependencies['mock_init_instance'].initialize_managers.assert_called_once()
        mock_dependencies['mock_init_instance'].initialize_specialized_managers.assert_called_once()
        mock_dependencies['mock_init_instance'].setup_manager_callbacks.assert_called_once()
        mock_dependencies['mock_shutdown_instance'].setup_signal_handler.assert_called_once_with(orchestrator)

    def test_initialize_components(self, mock_dependencies):
        """Test de l'initialisation des composants."""
        orchestrator = BotOrchestrator()
        
        # Vérifier que les managers sont correctement assignés
        assert orchestrator.data_manager == mock_dependencies['mock_managers']['data_manager']
        assert orchestrator.display_manager == mock_dependencies['mock_managers']['display_manager']
        assert orchestrator.monitoring_manager == mock_dependencies['mock_managers']['monitoring_manager']
        assert orchestrator.ws_manager == mock_dependencies['mock_managers']['ws_manager']
        assert orchestrator.volatility_tracker == mock_dependencies['mock_managers']['volatility_tracker']
        assert orchestrator.watchlist_manager == mock_dependencies['mock_managers']['watchlist_manager']
        assert orchestrator.callback_manager == mock_dependencies['mock_managers']['callback_manager']
        assert orchestrator.opportunity_manager == mock_dependencies['mock_managers']['opportunity_manager']

    @pytest.mark.asyncio
    async def test_start_success(self, mock_dependencies):
        """Test du démarrage réussi du bot."""
        orchestrator = BotOrchestrator()
        
        # Mock des méthodes de configuration
        mock_config = {"test": "config"}
        mock_dependencies['mock_config_instance'].load_and_validate_config.return_value = mock_config
        mock_dependencies['mock_config_instance'].get_market_data.return_value = ("http://test", {"test": "data"})
        mock_dependencies['mock_data_instance'].load_watchlist_data.return_value = True
        
        # Mock de la méthode asynchrone start_bot_components
        mock_dependencies['mock_starter_instance'].start_bot_components = AsyncMock()
        
        # Mock de la boucle d'attente
        with patch.object(orchestrator, '_keep_bot_alive', new_callable=AsyncMock) as mock_keep_alive:
            await orchestrator.start()
            
            # Vérifier que les méthodes sont appelées dans le bon ordre
            mock_dependencies['mock_config_instance'].load_and_validate_config.assert_called_once()
            mock_dependencies['mock_config_instance'].get_market_data.assert_called_once()
            mock_dependencies['mock_config_instance'].configure_managers.assert_called_once()
            mock_dependencies['mock_data_instance'].load_watchlist_data.assert_called_once()
            mock_dependencies['mock_starter_instance'].display_startup_summary.assert_called_once()
            mock_dependencies['mock_starter_instance'].start_bot_components.assert_called_once()
            mock_keep_alive.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_config_validation_error(self, mock_dependencies):
        """Test du démarrage avec erreur de validation de configuration."""
        orchestrator = BotOrchestrator()
        
        # Mock d'une erreur de validation
        mock_dependencies['mock_config_instance'].load_and_validate_config.side_effect = ValueError("Config error")
        
        # Le démarrage doit se terminer proprement sans exception
        await orchestrator.start()
        
        # Vérifier que les étapes suivantes ne sont pas exécutées
        mock_dependencies['mock_config_instance'].get_market_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_market_data_error(self, mock_dependencies):
        """Test du démarrage avec erreur de récupération des données de marché."""
        orchestrator = BotOrchestrator()
        
        # Mock de la configuration réussie mais échec des données de marché
        mock_config = {"test": "config"}
        mock_dependencies['mock_config_instance'].load_and_validate_config.return_value = mock_config
        mock_dependencies['mock_config_instance'].get_market_data.side_effect = Exception("Market data error")
        
        # Le démarrage doit se terminer proprement
        await orchestrator.start()
        
        # Vérifier que les étapes suivantes ne sont pas exécutées
        mock_dependencies['mock_config_instance'].configure_managers.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_watchlist_load_error(self, mock_dependencies):
        """Test du démarrage avec erreur de chargement de la watchlist."""
        orchestrator = BotOrchestrator()
        
        # Mock de la configuration et données de marché réussies mais échec de la watchlist
        mock_config = {"test": "config"}
        mock_dependencies['mock_config_instance'].load_and_validate_config.return_value = mock_config
        mock_dependencies['mock_config_instance'].get_market_data.return_value = ("http://test", {"test": "data"})
        mock_dependencies['mock_data_instance'].load_watchlist_data.return_value = False
        
        # Le démarrage doit se terminer proprement
        await orchestrator.start()
        
        # Vérifier que les étapes suivantes ne sont pas exécutées
        mock_dependencies['mock_starter_instance'].display_startup_summary.assert_not_called()

    @pytest.mark.asyncio
    async def test_keep_bot_alive_normal_operation(self, mock_dependencies):
        """Test de la boucle de maintien du bot en vie."""
        orchestrator = BotOrchestrator()
        
        # Mock des vérifications de santé
        mock_dependencies['mock_health_instance'].check_components_health.return_value = True
        mock_dependencies['mock_health_instance'].should_check_memory.return_value = False
        
        # Mock de asyncio.sleep pour éviter l'attente réelle
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Simuler l'arrêt après 2 itérations
            call_count = 0
            def side_effect():
                nonlocal call_count
                call_count += 1
                if call_count >= 2:
                    orchestrator.running = False
            
            mock_sleep.side_effect = side_effect
            
            await orchestrator._keep_bot_alive()
            
            # Vérifier que les vérifications de santé sont effectuées
            assert mock_dependencies['mock_health_instance'].check_components_health.call_count >= 1

    @pytest.mark.asyncio
    async def test_keep_bot_alive_component_failure(self, mock_dependencies):
        """Test de la boucle avec échec d'un composant."""
        orchestrator = BotOrchestrator()
        
        # Mock d'un échec de composant
        mock_dependencies['mock_health_instance'].check_components_health.return_value = False
        mock_dependencies['mock_health_instance'].should_check_memory.return_value = False
        
        # Mock de asyncio.sleep pour éviter l'attente réelle
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Simuler l'arrêt après 1 itération
            def side_effect():
                orchestrator.running = False
            
            mock_sleep.side_effect = side_effect
            
            await orchestrator._keep_bot_alive()
            
            # Vérifier que la vérification de santé est effectuée
            mock_dependencies['mock_health_instance'].check_components_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_keep_bot_alive_memory_monitoring(self, mock_dependencies):
        """Test de la surveillance mémoire."""
        orchestrator = BotOrchestrator()
        
        # Mock des vérifications de santé et mémoire
        mock_dependencies['mock_health_instance'].check_components_health.return_value = True
        mock_dependencies['mock_health_instance'].should_check_memory.return_value = True
        
        # Mock de asyncio.sleep pour éviter l'attente réelle
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Simuler l'arrêt après 1 itération
            def side_effect():
                orchestrator.running = False
            
            mock_sleep.side_effect = side_effect
            
            await orchestrator._keep_bot_alive()
            
            # Vérifier que la surveillance mémoire est effectuée
            mock_dependencies['mock_health_instance'].monitor_memory_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_keep_bot_alive_cancelled_error(self, mock_dependencies):
        """Test de la gestion de CancelledError."""
        orchestrator = BotOrchestrator()
        
        # Mock de asyncio.sleep pour lever CancelledError
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = asyncio.CancelledError()
            
            await orchestrator._keep_bot_alive()
            
            # Vérifier que running est mis à False
            assert orchestrator.running is False

    @pytest.mark.asyncio
    async def test_keep_bot_alive_exception(self, mock_dependencies):
        """Test de la gestion d'exception dans la boucle."""
        orchestrator = BotOrchestrator()
        
        # Mock de asyncio.sleep pour lever une exception
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = Exception("Test error")
            
            await orchestrator._keep_bot_alive()
            
            # Vérifier que running est mis à False
            assert orchestrator.running is False

    def test_get_status(self, mock_dependencies):
        """Test de la récupération du statut."""
        orchestrator = BotOrchestrator()
        
        # Mock des méthodes de statut
        mock_dependencies['mock_health_instance'].get_health_status.return_value = {"health": "ok"}
        mock_dependencies['mock_starter_instance'].get_startup_stats.return_value = {"stats": "ok"}
        
        status = orchestrator.get_status()
        
        # Vérifier la structure du statut
        assert "running" in status
        assert "uptime_seconds" in status
        assert "testnet" in status
        assert "health_status" in status
        assert "startup_stats" in status
        
        assert status["running"] is True
        assert status["testnet"] is True
        assert status["uptime_seconds"] >= 0
        assert status["health_status"] == {"health": "ok"}
        assert status["startup_stats"] == {"stats": "ok"}

    @pytest.mark.asyncio
    async def test_stop_success(self, mock_dependencies):
        """Test de l'arrêt réussi du bot."""
        orchestrator = BotOrchestrator()
        
        # Mock de l'arrêt asynchrone
        mock_dependencies['mock_shutdown_instance'].stop_all_managers_async = AsyncMock()
        
        await orchestrator.stop()
        
        # Vérifier que running est mis à False
        assert orchestrator.running is False
        
        # Vérifier que l'arrêt asynchrone est appelé
        mock_dependencies['mock_shutdown_instance'].stop_all_managers_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_with_exception(self, mock_dependencies):
        """Test de l'arrêt avec exception."""
        orchestrator = BotOrchestrator()
        
        # Mock d'une exception lors de l'arrêt
        mock_dependencies['mock_shutdown_instance'].stop_all_managers_async.side_effect = Exception("Stop error")
        
        # L'arrêt ne doit pas lever d'exception
        await orchestrator.stop()
        
        # Vérifier que running est mis à False malgré l'erreur
        assert orchestrator.running is False


class TestAsyncBotRunner:
    """Tests pour la classe AsyncBotRunner."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock des dépendances externes."""
        with patch('bot.setup_logging') as mock_logging, \
             patch('bot.BotOrchestrator') as mock_orchestrator:
            
            mock_logging.return_value = Mock()
            mock_orchestrator_instance = Mock()
            mock_orchestrator.return_value = mock_orchestrator_instance
            
            yield {
                'mock_logging': mock_logging,
                'mock_orchestrator': mock_orchestrator,
                'mock_orchestrator_instance': mock_orchestrator_instance,
            }

    def test_async_bot_runner_initialization(self, mock_dependencies):
        """Test de l'initialisation d'AsyncBotRunner."""
        runner = AsyncBotRunner()
        
        assert runner.running is True
        assert hasattr(runner, 'orchestrator')
        assert hasattr(runner, 'logger')
        
        # Vérifier que BotOrchestrator est créé
        mock_dependencies['mock_orchestrator'].assert_called_once()

    @pytest.mark.asyncio
    async def test_start_success(self, mock_dependencies):
        """Test du démarrage réussi d'AsyncBotRunner."""
        runner = AsyncBotRunner()
        
        # Mock du démarrage de l'orchestrateur
        mock_dependencies['mock_orchestrator_instance'].start = AsyncMock()
        
        # Mock des signal handlers
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_loop_instance = Mock()
            mock_loop.return_value = mock_loop_instance
            
            await runner.start()
            
            # Vérifier que l'orchestrateur est démarré
            mock_dependencies['mock_orchestrator_instance'].start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_with_signal_handlers_not_supported(self, mock_dependencies):
        """Test du démarrage sans support des signal handlers."""
        runner = AsyncBotRunner()
        
        # Mock du démarrage de l'orchestrateur
        mock_dependencies['mock_orchestrator_instance'].start = AsyncMock()
        
        # Mock de l'absence de support des signal handlers
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_loop_instance = Mock()
            mock_loop_instance.add_signal_handler.side_effect = NotImplementedError()
            mock_loop.return_value = mock_loop_instance
            
            await runner.start()
            
            # Vérifier que l'orchestrateur est démarré malgré l'erreur
            mock_dependencies['mock_orchestrator_instance'].start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_cancelled_error(self, mock_dependencies):
        """Test du démarrage avec CancelledError."""
        runner = AsyncBotRunner()
        
        # Mock d'une CancelledError
        mock_dependencies['mock_orchestrator_instance'].start = AsyncMock(side_effect=asyncio.CancelledError())
        
        # Mock des signal handlers
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_loop_instance = Mock()
            mock_loop.return_value = mock_loop_instance
            
            await runner.start()
            
            # Vérifier que l'orchestrateur est démarré
            mock_dependencies['mock_orchestrator_instance'].start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_exception(self, mock_dependencies):
        """Test du démarrage avec exception."""
        runner = AsyncBotRunner()
        
        # Mock d'une exception
        mock_dependencies['mock_orchestrator_instance'].start = AsyncMock(side_effect=Exception("Test error"))
        
        # Mock des signal handlers
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_loop_instance = Mock()
            mock_loop.return_value = mock_loop_instance
            
            await runner.start()
            
            # Vérifier que l'orchestrateur est démarré
            mock_dependencies['mock_orchestrator_instance'].start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_success(self, mock_dependencies):
        """Test de l'arrêt réussi d'AsyncBotRunner."""
        runner = AsyncBotRunner()
        
        # Mock de l'arrêt de l'orchestrateur (maintenant asynchrone)
        mock_dependencies['mock_orchestrator_instance'].stop = AsyncMock()
        
        # Mock des tâches asynchrones
        with patch('asyncio.all_tasks') as mock_tasks, \
             patch('asyncio.current_task') as mock_current_task, \
             patch('asyncio.gather', new_callable=AsyncMock) as mock_gather, \
             patch('sys.exit') as mock_exit:
            
            mock_task1 = Mock()
            mock_task2 = Mock()
            mock_tasks.return_value = [mock_task1, mock_task2]
            mock_current_task.return_value = mock_task1
            mock_gather.return_value = []
            
            await runner.stop()
            
            # Vérifier que l'orchestrateur est arrêté
            mock_dependencies['mock_orchestrator_instance'].stop.assert_called_once()
            
            # Vérifier que les tâches sont annulées
            mock_task2.cancel.assert_called_once()
            mock_gather.assert_called_once()
            mock_exit.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, mock_dependencies):
        """Test de l'arrêt quand le runner n'est pas en cours d'exécution."""
        runner = AsyncBotRunner()
        runner.running = False
        
        # Mock de l'arrêt de l'orchestrateur (maintenant asynchrone)
        mock_dependencies['mock_orchestrator_instance'].stop = AsyncMock()
        
        await runner.stop()
        
        # Vérifier que l'orchestrateur n'est pas arrêté
        mock_dependencies['mock_orchestrator_instance'].stop.assert_not_called()


class TestMainAsync:
    """Tests pour la fonction main_async."""

    @pytest.mark.asyncio
    async def test_main_async(self):
        """Test de la fonction main_async."""
        with patch('bot.AsyncBotRunner') as mock_runner_class:
            mock_runner = Mock()
            mock_runner.start = AsyncMock()
            mock_runner_class.return_value = mock_runner
            
            await main_async()
            
            # Vérifier que AsyncBotRunner est créé et démarré
            mock_runner_class.assert_called_once()
            mock_runner.start.assert_called_once()


class TestBotIntegration:
    """Tests d'intégration pour le module bot."""

    @pytest.mark.asyncio
    async def test_full_bot_lifecycle(self):
        """Test du cycle de vie complet du bot."""
        with patch('bot.setup_logging') as mock_logging, \
            patch('bot.get_settings') as mock_settings, \
            patch('bot.close_all_http_clients') as mock_close, \
            patch('bot.start_metrics_monitoring') as mock_metrics, \
            patch('bot.BotInitializer') as mock_initializer, \
            patch('bot.BotConfigurator') as mock_configurator, \
            patch('bot.DataManager') as mock_data_manager, \
            patch('bot.BotStarter') as mock_starter, \
            patch('bot.BotHealthMonitor') as mock_health, \
            patch('bot.ShutdownManager') as mock_shutdown, \
            patch('bot.ThreadManager') as mock_thread, \
            patch('metrics_monitor.metrics_monitor', Mock()):
            
            # Configuration des mocks
            mock_logging.return_value = Mock()
            mock_settings.return_value = {"testnet": True}
            
            # Mock des instances
            mock_init_instance = Mock()
            mock_config_instance = Mock()
            mock_data_instance = Mock()
            mock_starter_instance = Mock()
            mock_health_instance = Mock()
            mock_shutdown_instance = Mock()
            mock_thread_instance = Mock()
            
            mock_initializer.return_value = mock_init_instance
            mock_configurator.return_value = mock_config_instance
            mock_data_manager.return_value = mock_data_instance
            mock_starter.return_value = mock_starter_instance
            mock_health.return_value = mock_health_instance
            mock_shutdown.return_value = mock_shutdown_instance
            mock_thread.return_value = mock_thread_instance
            
            # Mock des managers
            mock_managers = {
                "data_manager": Mock(),
                "display_manager": Mock(),
                "monitoring_manager": Mock(),
                "ws_manager": Mock(),
                "volatility_tracker": Mock(),
                "watchlist_manager": Mock(),
                "callback_manager": Mock(),
                "opportunity_manager": Mock(),
            }
            mock_init_instance.get_managers.return_value = mock_managers
            
            # Mock des méthodes de démarrage
            mock_config = {"test": "config"}
            mock_config_instance.load_and_validate_config.return_value = mock_config
            mock_config_instance.get_market_data.return_value = ("http://test", {"test": "data"})
            mock_data_instance.load_watchlist_data.return_value = True
            
            # Mock de la méthode asynchrone start_bot_components
            mock_starter_instance.start_bot_components = AsyncMock()
            
            # Créer et tester l'orchestrateur
            orchestrator = BotOrchestrator()
            
            # Vérifier l'initialisation
            assert orchestrator.running is True
            assert orchestrator.testnet is True
            
            # Tester le démarrage
            with patch.object(orchestrator, '_keep_bot_alive', new_callable=AsyncMock) as mock_keep_alive:
                await orchestrator.start()
                
                # Vérifier que toutes les étapes sont exécutées
                mock_config_instance.load_and_validate_config.assert_called_once()
                mock_config_instance.get_market_data.assert_called_once()
                mock_config_instance.configure_managers.assert_called_once()
                mock_data_instance.load_watchlist_data.assert_called_once()
                mock_starter_instance.display_startup_summary.assert_called_once()
                mock_starter_instance.start_bot_components.assert_called_once()
                mock_keep_alive.assert_called_once()
            
            # Tester l'arrêt
            mock_shutdown_instance.stop_all_managers_async = AsyncMock()
            await orchestrator.stop()
            
            assert orchestrator.running is False
            mock_shutdown_instance.stop_all_managers_async.assert_called_once()
