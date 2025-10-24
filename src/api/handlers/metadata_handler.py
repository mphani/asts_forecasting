"""
Metadata Handler for MetricForecastorAPI
Handles metadata-related endpoints for Prometheus-compatible API
"""

import os
import sys
from flask import Response, jsonify

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from commons import LoggerSetup
from config import ConfigManager
from .metrics_manager import MetricsManager


class MetadataHandler:
    """
    Handler for metadata-related endpoints that provides metric metadata
    """
    
    def __init__(self, config_manager: ConfigManager, metrics_manager: MetricsManager):
        self.logger = LoggerSetup.get_logger()
        self.config_manager = config_manager
        self.metrics_manager = metrics_manager
        self.logger.info("Initialized MetadataHandler")
    
    def handle_metadata(self) -> Response:
        """Handle metadata queries - get metric metadata"""
        try:
            self.logger.info("Metadata query")
            result = self.metrics_manager.fetch_metrics_metadata()
            return jsonify(result)
        except Exception as e:
            self.logger.error(f"Error in metadata query: {e}")
            return jsonify({"status": "error", "error": str(e)}), 500
