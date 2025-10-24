"""
Label Handler for MetricForecastorAPI
Handles label-related endpoints for Prometheus-compatible API
"""

import os
import sys
from flask import Response, jsonify

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from commons import LoggerSetup
from config import ConfigManager
from .metrics_manager import MetricsManager


class LabelHandler:
    """
    Handler for label-related endpoints that provides label names and values
    """
    
    def __init__(self, config_manager: ConfigManager, metrics_manager: MetricsManager):
        self.logger = LoggerSetup.get_logger()
        self.config_manager = config_manager
        self.metrics_manager = metrics_manager
        self.logger.info("Initialized LabelHandler")
    
    def handle_labels(self) -> Response:
        """Handle labels queries - get all available label names"""
        try:
            result = self.metrics_manager.fetch_labels()
            return jsonify(result)
        except Exception as e:
            self.logger.error(f"Error in labels query: {e}")
            return jsonify({"status": "error", "error": str(e)}), 500
    
    def handle_label_values(self, label_name: str) -> Response:
        """Handle label values queries - get values for a specific label"""
        try:
            self.logger.info(f"Label values query for: {label_name}")
            
            # Use MetricsManager to get label values
            result = self.metrics_manager.fetch_label_values(label_name)
            return jsonify(result)
                
        except Exception as e:
            self.logger.error(f"Error in label values query: {e}")
            return jsonify({"status": "error", "error": str(e)}), 500
