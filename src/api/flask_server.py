"""
Flask API Server for Prometheus-compatible datasource
Provides endpoints compatible with Grafana Prometheus datasource
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from commons import LoggerSetup
from config import ConfigManager
from data import MetricsDataManager
from models import ModelManager
from .handlers.metrics_manager import MetricsManager
from .handlers.admin_api_handlers import ApiHandler
from .handlers.root_handler import RootHandler
from .handlers.label_handler import LabelHandler
from .handlers.metadata_handler import MetadataHandler
from .handlers.series_handler import SeriesHandler
from .handlers.instant_query_handler import InstantQueryHandler
from .handlers.range_query_handler import RangeQueryHandler


class MetricForecastorAPI:
    """
    Flask API server that provides forecasting endpoints following Prometheus HTTP API standards
    """
    
    def __init__(self, config_manager: ConfigManager):
        self.logger = LoggerSetup.get_logger()
        self.config_manager = config_manager
        self.data_manager = MetricsDataManager(config_manager)
        self.model_manager = ModelManager(config_manager)
        self.metrics_manager = MetricsManager(config_manager)
        self.api_handler = ApiHandler(config_manager, self.metrics_manager)
        self.root_handler = RootHandler(self.config_manager, self.metrics_manager)
        self.label_handler = LabelHandler(self.config_manager, self.metrics_manager)
        self.metadata_handler = MetadataHandler(self.config_manager, self.metrics_manager)
        self.series_handler = SeriesHandler(self.config_manager, self.metrics_manager)
        self.instant_query_handler = InstantQueryHandler(self.config_manager, self.data_manager, self.metrics_manager)
        self.range_query_handler = RangeQueryHandler(self.config_manager, self.data_manager, self.api_handler, self.metrics_manager)
        
        # Initialize Flask app
        self.app = Flask(__name__)
        CORS(self.app)  # Enable CORS for Grafana
        
        # Register routes
        self._register_routes()
                
        self.logger.info("Initialized MetricForecastorAPI")
    
    def _register_routes(self):
        """Register all API routes"""
        
        @self.app.route('/api/v1/query', methods=['GET'])
        def query():
            """Handle instant queries - /api/v1/query?query=up"""
            return self.instant_query_handler.handle_query()
        
        @self.app.route('/api/v1/admin/predict', methods=['GET'])
        def predict():
            """Handle instant queries - /api/v1/admin/predict"""
            return self.api_handler.handle_predict()
        
        @self.app.route('/api/v1/query_range', methods=['GET'])
        def query_range():
            """Handle range queries - /api/v1/query_range"""
            return self.range_query_handler.handle_query_range()
        
        @self.app.route('/api/v1/label/<label_name>/values', methods=['GET'])
        def label_values(label_name):
            """Handle label values - /api/v1/label/job/values"""
            return self.label_handler.handle_label_values(label_name)
        
        @self.app.route('/api/v1/labels', methods=['GET'])
        def labels():
            """Handle labels - /api/v1/labels"""
            return self.label_handler.handle_labels()
        
        @self.app.route('/api/v1/metadata', methods=['GET'])
        def metadata():
            """Handle metadata - /api/v1/metadata"""
            return self.metadata_handler.handle_metadata()
        
        @self.app.route('/api/v1/series', methods=['GET'])
        def series():
            """Handle series - /api/v1/series"""
            return self.series_handler.handle_series()
        
        @self.app.route('/health', methods=['GET'])
        def health():
            """Health check endpoint"""
            return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})
        
        @self.app.route('/', methods=['GET'])
        def root():
            """Root endpoint with server information"""
            return self.root_handler.handle_root()
    
    def run(self, host: str = "0.0.0.0", port: int = 5050, debug: bool = False):
        """Run the Flask server"""
        self.logger.info(f"Starting Flask server on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug)