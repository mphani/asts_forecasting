"""
Series Handler for MetricForecastorAPI
Handles series-related endpoints for Prometheus-compatible API
"""

import os
import sys
from datetime import datetime, timedelta
from flask import Response, jsonify, request

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from commons import LoggerSetup
from config import ConfigManager
from .metrics_manager import MetricsManager


class SeriesHandler:
    """
    Handler for series-related endpoints that provides series metadata
    """
    
    def __init__(self, config_manager: ConfigManager, metrics_manager: MetricsManager):
        self.logger = LoggerSetup.get_logger()
        self.config_manager = config_manager
        self.metrics_manager = metrics_manager
        self.logger.info("Initialized SeriesHandler")
    
    def handle_series(self) -> Response:
        """Handle series queries - get series metadata"""
        try:
            match = request.args.get('match[]', '')
            start = request.args.get('start')
            end = request.args.get('end')
            
            self.logger.info(f"Series query: {match}")
            
            # Parse time parameters
            start_time = datetime.fromtimestamp(float(start)) if start else datetime.now() - timedelta(hours=1)
            end_time = datetime.fromtimestamp(float(end)) if end else datetime.now()
            
            # Use MetricsManager to get series data
            series_response = self.metrics_manager.fetch_metrics_series()
            
            return jsonify(series_response)
                
        except Exception as e:
            self.logger.error(f"Error in series query: {e}")
            return jsonify({"status": "error", "error": str(e)}), 500
