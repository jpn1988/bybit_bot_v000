"""Tests pour le système de métriques."""

import pytest
from unittest.mock import patch, Mock
from metrics import MetricsCollector, record_api_call, record_filter_result, record_ws_connection, record_ws_error, get_metrics_summary, reset_metrics
from metrics_monitor import MetricsMonitor


class TestMetricsCollector:
    """Tests pour MetricsCollector."""
    
    def test_init(self):
        """Test d'initialisation."""
        collector = MetricsCollector()
        
        assert collector._data.api_calls_total == 0
        assert collector._data.api_errors_total == 0
        assert collector._data.pairs_kept_total == 0
        assert collector._data.pairs_rejected_total == 0
        assert len(collector._data.api_latencies) == 0
        assert collector._data.ws_connections == 0
        assert collector._data.ws_reconnects == 0
        assert collector._data.ws_errors == 0
    
    def test_record_api_call_success(self):
        """Test d'enregistrement d'un appel API réussi."""
        collector = MetricsCollector()
        
        collector.record_api_call(0.5, success=True)
        
        assert collector._data.api_calls_total == 1
        assert collector._data.api_errors_total == 0
        assert len(collector._data.api_latencies) == 1
        assert collector._data.api_latencies[0] == 0.5
    
    def test_record_api_call_error(self):
        """Test d'enregistrement d'un appel API en erreur."""
        collector = MetricsCollector()
        
        collector.record_api_call(1.0, success=False)
        
        assert collector._data.api_calls_total == 1
        assert collector._data.api_errors_total == 1
        assert len(collector._data.api_latencies) == 1
        assert collector._data.api_latencies[0] == 1.0
    
    def test_record_filter_result(self):
        """Test d'enregistrement des résultats de filtre."""
        collector = MetricsCollector()
        
        collector.record_filter_result("funding", 10, 5)
        collector.record_filter_result("spread", 8, 2)
        
        assert collector._data.pairs_kept_total == 18
        assert collector._data.pairs_rejected_total == 7
        assert collector._data.filter_stats["funding"]["kept"] == 10
        assert collector._data.filter_stats["funding"]["rejected"] == 5
        assert collector._data.filter_stats["spread"]["kept"] == 8
        assert collector._data.filter_stats["spread"]["rejected"] == 2
    
    def test_record_ws_connection(self):
        """Test d'enregistrement des connexions WebSocket."""
        collector = MetricsCollector()
        
        collector.record_ws_connection(connected=True)
        collector.record_ws_connection(connected=True)
        collector.record_ws_connection(connected=False)
        
        assert collector._data.ws_connections == 2
        assert collector._data.ws_reconnects == 1
    
    def test_record_ws_error(self):
        """Test d'enregistrement des erreurs WebSocket."""
        collector = MetricsCollector()
        
        collector.record_ws_error()
        collector.record_ws_error()
        
        assert collector._data.ws_errors == 2
    
    def test_get_metrics_summary(self):
        """Test de récupération du résumé des métriques."""
        collector = MetricsCollector()
        
        # Ajouter quelques métriques
        collector.record_api_call(0.5, success=True)
        collector.record_api_call(1.0, success=False)
        collector.record_filter_result("funding", 10, 5)
        collector.record_ws_connection(connected=True)
        collector.record_ws_error()
        
        summary = collector.get_metrics_summary()
        
        assert summary["api_calls_total"] == 2
        assert summary["api_errors_total"] == 1
        assert summary["api_error_rate_percent"] == 50.0
        assert summary["api_avg_latency_ms"] == 750.0  # (0.5 + 1.0) / 2 * 1000
        assert summary["pairs_kept_total"] == 10
        assert summary["pairs_rejected_total"] == 5
        assert summary["filter_success_rate_percent"] == 66.67  # 10/15 * 100
        assert summary["ws_connections"] == 1
        assert summary["ws_errors"] == 1
        assert "uptime_seconds" in summary
        assert "filter_stats" in summary
    
    def test_reset(self):
        """Test de remise à zéro."""
        collector = MetricsCollector()
        
        # Ajouter quelques métriques
        collector.record_api_call(0.5, success=True)
        collector.record_filter_result("funding", 10, 5)
        
        # Vérifier qu'elles sont là
        assert collector._data.api_calls_total == 1
        assert collector._data.pairs_kept_total == 10
        
        # Remettre à zéro
        collector.reset()
        
        # Vérifier qu'elles sont remises à zéro
        assert collector._data.api_calls_total == 0
        assert collector._data.pairs_kept_total == 0
        assert len(collector._data.api_latencies) == 0


class TestMetricsFunctions:
    """Tests pour les fonctions globales de métriques."""
    
    def test_record_api_call_global(self):
        """Test de la fonction globale record_api_call."""
        reset_metrics()
        
        record_api_call(0.3, success=True)
        record_api_call(0.7, success=False)
        
        summary = get_metrics_summary()
        assert summary["api_calls_total"] == 2
        assert summary["api_errors_total"] == 1
        assert summary["api_error_rate_percent"] == 50.0
    
    def test_record_filter_result_global(self):
        """Test de la fonction globale record_filter_result."""
        reset_metrics()
        
        record_filter_result("test_filter", 5, 3)
        
        summary = get_metrics_summary()
        assert summary["pairs_kept_total"] == 5
        assert summary["pairs_rejected_total"] == 3
        assert summary["filter_stats"]["test_filter"]["kept"] == 5
        assert summary["filter_stats"]["test_filter"]["rejected"] == 3
    
    def test_record_ws_connection_global(self):
        """Test de la fonction globale record_ws_connection."""
        reset_metrics()
        
        record_ws_connection(connected=True)
        record_ws_connection(connected=False)
        
        summary = get_metrics_summary()
        assert summary["ws_connections"] == 1
        assert summary["ws_reconnects"] == 1
    
    def test_record_ws_error_global(self):
        """Test de la fonction globale record_ws_error."""
        reset_metrics()
        
        record_ws_error()
        record_ws_error()
        
        summary = get_metrics_summary()
        assert summary["ws_errors"] == 2


class TestMetricsMonitor:
    """Tests pour MetricsMonitor."""
    
    def test_init(self):
        """Test d'initialisation."""
        monitor = MetricsMonitor(interval_minutes=2)
        
        assert monitor.interval_seconds == 120
        assert monitor.running is False
        assert monitor.monitor_thread is None
    
    @patch('metrics_monitor.setup_logging')
    def test_start_stop(self, mock_setup_logging):
        """Test de démarrage et arrêt du monitoring."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        monitor = MetricsMonitor(interval_minutes=1)
        
        # Démarrer
        monitor.start()
        assert monitor.running is True
        assert monitor.monitor_thread is not None
        assert monitor.monitor_thread.is_alive()
        
        # Arrêter
        monitor.stop()
        assert monitor.running is False
    
    @patch('metrics_monitor.setup_logging')
    def test_log_metrics_now(self, mock_setup_logging):
        """Test d'affichage immédiat des métriques."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        monitor = MetricsMonitor()
        
        # Ajouter quelques métriques
        record_api_call(0.5, success=True)
        record_filter_result("test", 5, 3)
        
        # Forcer l'affichage
        monitor.log_metrics_now()
        
        # Vérifier que le logger a été appelé
        assert mock_logger.info.called
