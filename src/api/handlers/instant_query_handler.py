"""
Instant Query Handler for MetricForecastorAPI
Handles instant query endpoints for Prometheus-compatible API
"""

import os
import sys
from datetime import datetime
from flask import Response, jsonify, request

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from commons import LoggerSetup
from config import ConfigManager
from data import MetricsDataManager
from .metrics_manager import MetricsManager


class InstantQueryHandler:
    """
    Handler for instant query endpoints that provides current metric values
    """
    
    def __init__(self, config_manager: ConfigManager, data_manager: MetricsDataManager, metrics_manager: MetricsManager):
        self.logger = LoggerSetup.get_logger()
        self.config_manager = config_manager
        self.data_manager = data_manager
        self.metrics_manager = metrics_manager
        self.logger.info("Initialized InstantQueryHandler")
    
    def handle_query(self) -> Response:
        """Handle instant queries"""
        try:
            query = request.args.get('query', '')
            time_param = request.args.get('time')
            
            self.logger.info(f"Instant query: {query}")
            
            # Parse time parameter
            query_time = datetime.now()
            if time_param:
                try:
                    query_time = datetime.fromtimestamp(float(time_param))
                except ValueError:
                    self.logger.warning(f"Invalid time parameter: {time_param}")
            
            # Handle different query types
            if query == 'up':
                return self.handle_up(query_time)
            elif 'aerospike_namespace_master_objects' in query:
                return self.handle_metric_query(query, query_time)
            else:
                return self.handle_generic_query(query, query_time)
                
        except Exception as e:
            self.logger.error(f"Error in instant query: {e}")
            return jsonify({"status": "error", "error": str(e)}), 500
    
    def handle_up(self, query_time: datetime) -> Response:
        """Handle 'up' instant query"""
        # Get instance label from metrics_manager
        instance_label = self.metrics_manager.get_instance_label()
        
        return jsonify({
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {
                            "__name__": "up",
                            "job": "aerospike",
                            "instance": instance_label
                        },
                        "value": [int(query_time.timestamp()), "1"]
                    }
                ]
            }
        })
    
    def handle_metric_query(self, query: str, query_time: datetime) -> Response:
        """Handle metric instant query"""
        try:
            # Extract metric name from query
            metric_name = "aerospike_namespace_master_objects"
            
            # Get latest data point
            data = self.data_manager.get_metrics_for_days(metric_name, 0)  # Today's data
            
            if data is not None and not data.empty:
                latest_value = data['y'].iloc[-1]
                timestamp = int(data['ds'].iloc[-1].timestamp())
                
                # Get actual labels from configuration
                metric_labels = self.metrics_manager._get_metric_labels(metric_name)
                
                return jsonify({
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": [
                            {
                                "metric": {
                                    "__name__": metric_name,
                                    **metric_labels
                                },
                                "value": [timestamp, str(latest_value)]
                            }
                        ]
                    }
                })
            else:
                return jsonify({
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": []
                    }
                })
                
        except Exception as e:
            self.logger.error(f"Error in metric query: {e}")
            return jsonify({"status": "error", "error": str(e)}), 500
    
    def handle_generic_query(self, query: str, query_time: datetime) -> Response:
        """Handle generic instant query"""
        return jsonify({
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": []
            }
        })
