"""
Root Handler for MetricForecastorAPI
Handles the root endpoint and provides server information
"""

import os
import sys
from datetime import datetime
from flask import Response, jsonify

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from commons import LoggerSetup
from config import ConfigManager


class RootHandler:
    """
    Handler for root endpoint that provides server information and available endpoints
    """
    
    def __init__(self, config_manager: ConfigManager, metrics_manager=None):
        self.logger = LoggerSetup.get_logger()
        self.config_manager = config_manager
        self.metrics_manager = metrics_manager
        self.logger.info("Initialized RootHandler")
    
    def handle_root(self) -> Response:
        """Handle root endpoint with server information"""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>MetricForecastorAPI Server</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }
                .container { background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
                .endpoint { margin: 15px 0; padding: 10px; background-color: #f8f9fa; border-left: 4px solid #007bff; }
                .endpoint a { color: #007bff; text-decoration: none; font-weight: bold; }
                .endpoint a:hover { text-decoration: underline; }
                .description { color: #666; margin-top: 5px; }
                .status { color: #28a745; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 MetricForecastorAPI Server</h1>
                <p class="status">✅ Server is running and ready to serve Grafana!</p>
                
                <h2>📊 Available Endpoints:</h2>
                
                <div class="endpoint">
                    <a href="/api/v1/query">/api/v1/query</a>
                    <div class="description">Instant queries (e.g., ?query=up)</div>
                </div>
                
                <div class="endpoint">
                    <a href="/api/v1/query_range">/api/v1/query_range</a>
                    <div class="description">Range queries for time series data</div>
                </div>
                
                <div class="endpoint">
                    <a href="/api/v1/labels">/api/v1/labels</a>
                    <div class="description">Get all available label names</div>
                </div>
                
                <div class="endpoint">
                    <a href="/api/v1/label/job/values">/api/v1/label/job/values</a>
                    <div class="description">Get label values (replace 'job' with any label)</div>
                </div>
                
                <div class="endpoint">
                    <a href="/api/v1/series">/api/v1/series</a>
                    <div class="description">Get series metadata</div>
                </div>
                
                <div class="endpoint">
                    <a href="/api/v1/metadata">/api/v1/metadata</a>
                    <div class="description">Get metric metadata</div>
                </div>
                
                <div class="endpoint">
                    <a href="/api/v1/admin/predict">/api/v1/admin/predict</a>
                    <div class="description">Generate predictions (GET with metric_name param)</div>
                </div>
                
                <div class="endpoint">
                    <a href="/api/v1/admin/train?metric_name=aerospike_namespace_master_objects">/api/v1/admin/train</a>
                    <div class="description">Train model for specific metric (GET with metric_name param)</div>
                </div>
                
                <div class="endpoint">
                    <a href="/health">/health</a>
                    <div class="description">Health check endpoint</div>
                </div>
                
                <h2>🔧 Grafana Configuration:</h2>
                <p><strong>URL:</strong> http://localhost:5050</p>
                <p><strong>Type:</strong> Prometheus</p>
                <p><strong>Access:</strong> Server (default)</p>
                
                <p style="margin-top: 30px; color: #666; font-size: 14px;">
                    Server started at: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """
                </p>
            </div>
        </body>
        </html>
        """
        return Response(html_content, mimetype='text/html')
