import os
import sys
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
import pytz
from flask import Response, jsonify, request

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from commons import LoggerSetup
from config import ConfigManager
from data import MetricsDataManager
from models import ModelManager
from .metrics_manager import MetricsManager


class ApiHandler:
    """
    API Handler for forecasting predictions
    Provides REST API endpoints for model predictions
    """
    
    def __init__(self, config_manager: ConfigManager, metrics_manager: MetricsManager):
        self.logger = LoggerSetup.get_logger()
        self.config_manager = config_manager
        self.data_manager = MetricsDataManager(config_manager)
        self.model_manager = ModelManager(config_manager)
        self.metrics_manager = metrics_manager
        self.logger.info("Initialized ApiHandler for predictions")
    
    
    def predict(self, metric_name: str, predict_future_hours: int = ModelManager.DEFAULT_PREDICT_FUTURE_HOURS) -> Dict[str, Any]:
        """
        Make predictions using a trained model
        
        Args:
            model_name: Name of the model to use
            metric_name: Name of the metric to predict
            hours_ahead: Number of hours to predict ahead
            
        Returns:
            Dictionary containing predictions
        """
        try:
            metric_config = self.config_manager.get_metric_configuration(metric_name)
            if metric_config is None:
                self.logger.error(f"API: Metric {metric_name} not found in configuration")
                self.logger.error(metric_name)
                return {
                    "success": False,
                    "error": f"Metric {metric_name} not found in configuration"
                }
            
            # model_name = metric_config["model_to_use"]
            # hours_ahead = metric_config["predict_future_hours"]
            model_name = self.config_manager.get_metric_config_value(metric_name, "model_to_use", ModelManager.DEFAULT_MODEL_NAME)
            # hours_ahead = self.config_manager.get_metric_config_value(metric_name, "predict_future_hours", ModelManager.DEFAULT_PREDICT_FUTURE_HOURS)
            hours_ahead = predict_future_hours

            self.logger.info(f"API: Making predictions for {metric_name} using {model_name} for {hours_ahead} hours")
            
            # response = { "success": False, "model_name": model_name, "metric_name": metric_name} 
            
            predictions = self.model_manager.predict(model_name, metric_name, hours_ahead)
            
            if predictions is not None and not predictions.empty:
                # Transform predictions to Grafana-compatible format
                grafana_response = self._transform_predictions_to_grafana_format(
                    predictions, metric_name, metric_config
                )
                self.logger.info(f"API: Successfully generated {len(predictions)} predictions")
                return grafana_response
            else:
                response = {
                    "success": False,
                    "error": f"No predictions generated for {metric_name} using {model_name}",
                    "model_name": model_name,
                    "metric_name": metric_name,
                    "hours_ahead": hours_ahead
                }
                self.logger.warning(f"API: No predictions generated for {metric_name}")
            
            return response
            
        except Exception as e:
            self.logger.error(f"API: Error making predictions for {metric_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                # "model_name": model_name if model_name is not None else "Not found",
                "metric_name": metric_name,
                # "hours_ahead": hours_ahead
            }
    

    def train_model(self, metric_name: str) -> Dict[str, Any]:
        """
        Train a model for a specific metric
        
        Args:
            metric_name: Name of the metric to train on
            
        Returns:
            Dictionary containing training results
        """
        try:
            self.logger.info(f"API: Training model for metric {metric_name}")
            
            # Get metric configuration using config manager
            metric_config = self.config_manager.get_metric_configuration(metric_name)
            
            # Validate metric config
            if metric_config is None:
                self.logger.error(f"API: Metric configuration not found for {metric_name}")
                return {
                    "success": False,
                    "error": f"Metric configuration not found for {metric_name}",
                    "metric_name": metric_name
                }
            
            # Get the model_to_use parameter from metric config
            model_name = self.config_manager.get_metric_config_value(metric_name, "model_to_use", ModelManager.DEFAULT_MODEL_NAME)
            self.logger.info(f"API: Training model {model_name} for metric {metric_name}")
            
            # Train the model and get the training results
            training_results = self.model_manager.train_model(model_name, metric_name, save_model=True)
            
            if training_results is not None:
                return {
                    "success": True,
                    "message": f"Model training completed successfully for {metric_name}",
                    "model_name": model_name,
                    "metric_name": metric_name,
                    "training_results": training_results
                }
            else:
                return {
                    "success": False,
                    "error": f"Model training failed for {metric_name}",
                    "model_name": model_name,
                    "metric_name": metric_name
                }
                
        except Exception as e:
            self.logger.error(f"API: Error training model for {metric_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "metric_name": metric_name
            }
    
    
    def _transform_predictions_to_grafana_format(self, predictions, metric_name, metric_config):
        """
        Transform predictions DataFrame to Grafana-compatible JSON format
        Creates separate metrics for yhat, yhat_upper, and yhat_lower
        
        Args:
            predictions: DataFrame with columns ['ds', 'yhat', 'yhat_lower', 'yhat_upper']
            metric_name: Name of the metric
            metric_config: Metric configuration dictionary
            
        Returns:
            Dictionary in Grafana-compatible format
        """
        import pandas as pd
        from datetime import datetime
        
        try:
            # Get metric labels from configuration
            metric_labels = metric_config.get("metric_labels", {})
            
            # Add instance label from metrics_manager
            instance_label = self.metrics_manager.get_instance_label()
            
            # Create base metric dictionary with labels
            base_metric_dict = {
                **metric_labels,
                "instance": instance_label
            }
            
            # Transform predictions to Grafana format with aggregation
            result_list = []
            
            # Group predictions by metric type and aggregate values
            metric_types = ['yhat', 'yhat_upper', 'yhat_lower']
            
            for metric_type in metric_types:
                # Create metric name with suffix
                full_metric_name = f"{metric_name}_{metric_type}"
                
                # Create metric dictionary for this specific metric type
                metric_dict = {
                    "__name__": full_metric_name,
                    **base_metric_dict
                }
                
                # Aggregate all values for this metric type
                values = []
                for _, row in predictions.iterrows():
                    # Ensure we're working with UTC timezone-aware datetime
                    ds_utc = row['ds']
                    if ds_utc.tz is None:
                        # If timezone-naive, assume it's UTC and localize
                        ds_utc = ds_utc.tz_localize('UTC')
                    elif ds_utc.tz != pytz.UTC:
                        # Convert to UTC if not already UTC
                        ds_utc = ds_utc.tz_convert('UTC')
                    
                    # Convert to Unix timestamp (seconds since epoch in UTC)
                    timestamp = int(ds_utc.timestamp())
                    value = str(row[metric_type])
                    
                    values.append([timestamp, value])
                
                # Create Grafana-compatible result entry with aggregated values
                result_entry = {
                    "metric": metric_dict,
                    "values": values  # Use "values" for multiple data points
                }
                
                result_list.append(result_entry)
            
            # Return Grafana-compatible response
            return {
                "status": "success",
                "data": {
                    "resultType": "matrix",  # Changed to matrix for multiple data points
                    "result": result_list,
                    "prediction_counter": len(predictions)  # Testing counter
                }
            }
            
        except Exception as e:
            self.logger.error(f"API: Error transforming predictions to Grafana format: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def handle_predict(self) -> Response:
        """Handle predict endpoint"""
        try:
            metric_name = request.args.get('metric_name')
            start = request.args.get('start')
            end = request.args.get('end')
            
            self.logger.info(f"Predict query: {metric_name}, start: {start}, end: {end}")
            
            # Parse time parameters
            start_time = datetime.fromtimestamp(float(start)) if start else datetime.now() - timedelta(hours=1)
            end_time = datetime.fromtimestamp(float(end)) if end else datetime.now()
            
            # Calculate total hours
            total_hours = (end_time - start_time).total_seconds() / 3600
            self.logger.info(f"Total hours to predict: {total_hours:.2f}")
            
            prediction_response = self.predict(metric_name)
            
            # The predict method now returns Grafana-compatible format directly
            return jsonify(prediction_response)
                        
        except Exception as e:
            self.logger.error(f"Error in predict query: {e}")
            return jsonify({"status": "error", "error": str(e)}), 500
        

if __name__ == "__main__":
    # Example usage
    config_manager = ConfigManager("../../configs/config.yaml")
    api_handler = ApiHandler(config_manager)
    
    # Load the model from disk to memory
    # api_handler.model_manager.load_single_model_from_disk("prophet_logistic_7", "aerospike_namespace_master_objects")
    # print(api_handler.predict("aerospike_namespace_master_objects"))
    
    api_handler.train_model("aerospike_namespace_master_objects")
    
    # api_handler.train_model("aerospike_namespace_master_objects")