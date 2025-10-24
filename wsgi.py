#!/usr/bin/env python3
"""
WSGI application entry point for MetricForecastorAPI
Used by Gunicorn to serve the Flask application
"""

import os
import sys

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import MetricForecastorAPI, ConfigManager

# Initialize configuration
config_manager = ConfigManager("configs/config.yaml")

# Create the Flask application
api_server = MetricForecastorAPI(config_manager)

# Export the Flask app for Gunicorn
application = api_server.app

if __name__ == "__main__":
    # This allows running the WSGI app directly for testing
    from werkzeug.serving import run_simple
    run_simple("0.0.0.0", 5050, application)
