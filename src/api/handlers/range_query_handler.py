"""
Range Query Handler for MetricForecastorAPI
Handles range query endpoints for Prometheus-compatible API
"""

import os
import sys
from datetime import datetime, timedelta
from flask import Response, jsonify, request

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from commons import LoggerSetup
from config import ConfigManager
from data import MetricsDataManager
from .admin_api_handlers import ApiHandler
from .metrics_manager import MetricsManager

import pytz


class RangeQueryHandler:
    """
    Handler for range query endpoints that provides time series data over a range
    """
    
    def __init__(self, config_manager: ConfigManager, data_manager: MetricsDataManager, api_handler: ApiHandler, metrics_manager: MetricsManager):
        self.logger = LoggerSetup.get_logger()
        self.config_manager = config_manager
        self.data_manager = data_manager
        self.api_handler = api_handler
        self.metrics_manager = metrics_manager
        self.logger.info("Initialized RangeQueryHandler")
    
    def handle_query_range(self) -> Response:
        """Handle range queries"""
        try:
            query = request.args.get('query', '')
            start = request.args.get('start')
            end = request.args.get('end')
            step = request.args.get('step', '60')
            
            self.logger.info(f"Range query: {query}, start: {start}, end: {end}, step: {step}")
            
            # Parse time parameters
            start_time = datetime.fromtimestamp(float(start)) if start else datetime.now() - timedelta(hours=1)
            end_time = datetime.fromtimestamp(float(end)) if end else datetime.now()
            step_seconds = int(step)
            
            # Handle different query types
            if query == 'up':
                return self._handle_up_range_query(start_time, end_time, step_seconds)
            elif '_yhat' in query:
                # Check if it's a prediction metric (has _yhat, _yhat_upper, or _yhat_lower)
                return self._handle_prediction_range_query(query, start_time, end_time, step_seconds)
            else:
                # Handle base metrics or other queries
                return self._handle_metric_range_query(query, start_time, end_time, step_seconds)
                
        except Exception as e:
            self.logger.error(f"Error in range query: {e}")
            return jsonify({"status": "error", "error": str(e)}), 500
    
    def _handle_up_range_query(self, start_time: datetime, end_time: datetime, step_seconds: int) -> Response:
        """Handle 'up' range query"""
        # Generate time series data
        current_time = start_time
        values = []
        
        while current_time <= end_time:
            values.append([int(current_time.timestamp()), "1"])
            current_time += timedelta(seconds=step_seconds)
            
        # Get real IP and port from Flask request
        instance_value = self.metrics_manager.get_instance_label()
        
        return jsonify({
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {
                            "__name__": "up",
                            "instance": instance_value
                        },
                        "values": values
                    }
                ]
            }
        })
    
    def _handle_metric_range_query(self, query: str, start_time: datetime, end_time: datetime, step_seconds: int) -> Response:
        """Handle metric range query"""
        try:
            # Extract metric name from query - handle both simple names and queries with labels
            if '{' in query:
                # Query has labels like "metric_name{label1=value1, label2=value2}"
                metric_name = query.split('{')[0]
            else:
                metric_name = query
            
            self.logger.info(f"Metric range query: {metric_name}")
            
            # Get data for the time range
            data = self.data_manager.get_metrics_for_days(metric_name, 0)  # Today's data
            
            if data is not None and not data.empty:
                # Convert start_time and end_time to timezone-aware UTC for comparison
                start_time_utc = start_time.replace(tzinfo=pytz.UTC) if start_time.tzinfo is None else start_time.astimezone(pytz.UTC)
                end_time_utc = end_time.replace(tzinfo=pytz.UTC) if end_time.tzinfo is None else end_time.astimezone(pytz.UTC)
                
                # Filter data to the requested time range
                filtered_data = data[(data['ds'] >= start_time_utc) & (data['ds'] <= end_time_utc)]
                
                if not filtered_data.empty:
                    values = []
                    for _, row in filtered_data.iterrows():
                        timestamp = int(row['ds'].timestamp())
                        value = str(row['y'])
                        values.append([timestamp, value])
                    
                    metric_labels = self.metrics_manager._get_metric_labels(metric_name)
                    
                    # Add instance label with real IP and port
                    metric_labels['instance'] = self.metrics_manager.get_instance_label()
                    
                    return jsonify({
                        "status": "success",
                        "data": {
                            "resultType": "matrix",
                            "result": [
                                {
                                    "metric": {
                                        "__name__": metric_name,
                                        **metric_labels
                                    },
                                    "values": values
                                }
                            ]
                        }
                    })
            
            # Return empty result if no data
            return jsonify({
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": []
                }
            })
                
        except Exception as e:
            self.logger.error(f"Error in metric range query: {e}")
            return jsonify({"status": "error", "error": str(e)}), 500
    
    def _handle_prediction_range_query(self, query: str, start_time: datetime, end_time: datetime, step_seconds: int) -> Response:
        """Handle prediction metric range query"""
        try:
            # Extract base metric name and prediction type
            # Split at _yhat: before_yhat = base_metric_name, after_yhat = prediction_suffix
            requested_metric_name = query
            parts = query.split('_yhat', 1)
            base_metric_name = parts[0]
            
            self.logger.debug(f"Prediction range query: {base_metric_name}")
            self.logger.debug(f"Grafana time range: {start_time} to {end_time}")
            self.logger.debug(f"Will generate FUTURE predictions starting from {end_time}")
            
            # Get predictions using ApiHandler
            prediction_response = self.api_handler.predict(base_metric_name)
            self.logger.debug(f"Prediction response status: {prediction_response.get('status')}")
            
            # Filter the response to only include the specific prediction type requested
            if prediction_response.get('status') == 'success' and 'data' in prediction_response:
                filtered_result = []
                # requested_metric_name = f"{base_metric_name}_{prediction_type}"
                
                for result in prediction_response['data']['result']:
                    if result['metric']['__name__'] == requested_metric_name:
                        filtered_result.append(result)
                
                # Update the response with filtered results
                prediction_response['data']['result'] = filtered_result
                self.logger.debug(f"Filtered prediction response to only include {requested_metric_name}: {len(filtered_result)} results")
            
            # Return the filtered Grafana-compatible format
            return jsonify(prediction_response)
                
        except Exception as e:
            self.logger.error(f"Error in prediction range query: {e}")
            return jsonify({"status": "error", "error": str(e)}), 500
    
    def handle_generic_range_query(self, query: str, start_time: datetime, end_time: datetime, step_seconds: int) -> Response:
        """Handle generic range query"""
        return jsonify({
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": []
            }
        })
