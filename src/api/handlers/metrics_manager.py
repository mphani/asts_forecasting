"""
MetricsManager for handling metrics and predictions in the Flask API
"""

import os
import sys
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from flask import request

# Add src to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from commons import LoggerSetup
from config import ConfigManager
from data import MetricsDataManager
from models import ModelManager


class MetricsManager:
    """
    Manages metrics and predictions for the Flask API
    Handles data retrieval, model loading, and prediction generation
    """
    
    def __init__(self, config_manager: ConfigManager):
        self.logger = LoggerSetup.get_logger()
        self.config_manager = config_manager
        self.data_manager = MetricsDataManager(config_manager)
        self.model_manager = ModelManager(config_manager)
        
        # Cache for loaded models
        self._loaded_models = {}
        
        # Global set for unique labels across all metrics
        self._global_labels = set()
        
        # Global dict for label names and their unique values
        self._global_label_values = {}
        
        self.logger.info("Initialized MetricsManager")
    
    def get_instance_label(self) -> str:
        """Get the instance label with real IP and port from Flask request"""
        import socket
        
        # Try multiple methods to get the real IP address
        real_ip = None
        
        # Method 1: Check X-Forwarded-For header (for proxies/load balancers)
        forwarded_for = request.environ.get('HTTP_X_FORWARDED_FOR')
        if forwarded_for:
            real_ip = forwarded_for.split(',')[0].strip()
            self.logger.debug(f"Using X-Forwarded-For IP: {real_ip}")
        
        # Method 2: Check X-Real-IP header (for nginx proxies)
        if not real_ip:
            real_ip = request.environ.get('HTTP_X_REAL_IP')
            if real_ip:
                self.logger.debug(f"Using X-Real-IP: {real_ip}")
        
        # Method 3: Use REMOTE_ADDR (direct connection)
        if not real_ip:
            real_ip = request.environ.get('REMOTE_ADDR', 'localhost')
            self.logger.debug(f"Using REMOTE_ADDR: {real_ip}")
        
        # Method 4: If we got localhost/127.0.0.1, try to get the actual server IP
        if real_ip in ['127.0.0.1', 'localhost', '::1']:
            try:
                # Get the actual server IP by connecting to a remote address
                # This doesn't actually send data, just determines the local IP
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    server_ip = s.getsockname()[0]
                    if server_ip and server_ip != '127.0.0.1':
                        real_ip = server_ip
                        self.logger.debug(f"Using detected server IP: {real_ip}")
            except Exception as e:
                self.logger.debug(f"Could not detect server IP: {e}")
        
        # Method 5: Fallback to hostname resolution
        if real_ip in ['127.0.0.1', 'localhost', '::1']:
            try:
                hostname = socket.gethostname()
                server_ip = socket.gethostbyname(hostname)
                if server_ip and server_ip != '127.0.0.1':
                    real_ip = server_ip
                    self.logger.debug(f"Using hostname resolution IP: {real_ip}")
            except Exception as e:
                self.logger.debug(f"Could not resolve hostname: {e}")
        
        # Clean up the IP address
        if ',' in real_ip:
            real_ip = real_ip.split(',')[0].strip()
        
        # Get the actual port from the request
        server_port = request.environ.get('SERVER_PORT', '5050')
        
        # Log the final result for debugging
        self.logger.debug(f"Final instance label: {real_ip}:{server_port}")
        
        return f"{real_ip}:{server_port}"
    
    def fetch_metrics_metadata(self):
        """
        Fetch metrics metadata
        """
        metrics = self.config_manager.get_configuration("metrics")
        
        metadata_response = {
            "status": "success",
            "data": {}
        }
        
        for metric_name, metric_config in metrics.items():
            self.logger.info(f"Processing metric: {metric_name}")
            
            # we have actual metrics as-well as global cofigs also, ignore configs
            if "metric_" in metric_name or not isinstance(metric_config, dict):
                continue
            
            # Extract metadata from config
            metric_type = metric_config.get("metric_type", "gauge")
            metric_unit = metric_config.get("metric_unit", "")
            metric_help = metric_config.get("description", f"{metric_name} metric")
            
            # Add to response
            metadata_response["data"][metric_name] = [
                {
                    "type": metric_type,
                    "unit": metric_unit,
                    "help": metric_help
                }
            ]
        
        return metadata_response


    def fetch_labels(self):
        """
        Fetch labels from all metrics and return unique label names
        """
        metrics = self.config_manager.get_configuration("metrics")
        
        # Clear and rebuild global labels set
        self._global_labels.clear()
        
        for metric_name, metric_config in metrics.items():
            # Skip non-dictionary configs
            if "metric_" in metric_name or not isinstance(metric_config, dict):
                continue
            
            # Add metric labels to global set
            metric_labels = metric_config.get("metric_labels", {})
            for label_name in metric_labels.keys():
                self._global_labels.add(label_name)
        
        # Add common Prometheus labels
        self._global_labels.update(["__name__", "job", "instance"])
        
        return {
            "status": "success",
            "data": sorted(list(self._global_labels))
        }


    def fetch_label_values(self, label_name: str):
        """
        Fetch unique values for the given label_name
        """
        # Get unique values for the label, return empty list if not found
        values = self._global_label_values.get(label_name, set())
        metrics = self.config_manager.get_configuration("metrics")
        
        values.clear()
        for metric_name, metric_config in metrics.items():
            # Skip non-dictionary configs
            if "metric_" in metric_name or not isinstance(metric_config, dict):
                continue
            
            if label_name in metric_config.get("metric_labels", {}):
                values.add(metric_config.get("metric_labels", {})[label_name])
                    
        return {
            "status": "success",
            "data": sorted(list(values))
        }


    def fetch_metrics_series(self):
        """
        Fetch all prediction metrics for the series endpoint
        Returns a list of metric entries with their labels
        """
        series_data = []
        
        # Get all configured metrics
        metrics_config = self.config_manager.get_configuration('metrics')
        
        # Add base metrics and prediction metrics for each configured metric
        for metric_name, metric_config in metrics_config.items():
            if metric_name == 'model_to_use' or "metric_" in metric_name :
                continue  # Skip non-metric entries
            
            # Get metric labels
            metric_labels = metric_config.get('metric_labels', {})
            
            # Add the base metric first
            base_metric_entry = {
                "__name__": metric_name,
                **metric_labels
            }
            series_data.append(base_metric_entry)
            self.logger.debug(f"Added base metric: {metric_name}")
            
            # Add three prediction metrics for each base metric
            prediction_types = ['yhat', 'yhat_upper', 'yhat_lower']
            
            for prediction_type in prediction_types:
                prediction_metric_name = f"{metric_name}_{prediction_type}"
                
                # Create metric entry
                metric_entry = {
                    "__name__": prediction_metric_name,
                    **metric_labels
                }
                
                series_data.append(metric_entry)
                self.logger.debug(f"Added prediction metric: {prediction_metric_name}")
        
        self.logger.info(f"Generated {len(series_data)} metrics (base + predictions) for series endpoint")
        
        return {
            "status": "success",
            "data": series_data
        }

    def _get_metric_labels(self, metric_name: str):
        """
        Get metric labels from the configuration
        """
        metric_config = self.config_manager.get_configuration("metrics")[metric_name]
        return metric_config.get("metric_labels", {})

if __name__ == "__main__":
    mm = MetricsManager(ConfigManager("configs/config.yaml"))
    result = mm.fetch_metrics_metadata()
    print("Metadata:", result)
    
    labels_result = mm.fetch_labels()
    print("Labels:", labels_result)
            