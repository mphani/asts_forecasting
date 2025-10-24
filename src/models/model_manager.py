from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, Type
import threading

import numpy as np
import os
import pandas as pd
import pickle
import pytz
import requests
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commons import LoggerSetup, CommonsUtils
from config import ConfigManager
from data import MetricsDataManager
from .model_base import ModelInterface, ModelFactory, ModelRWLocker
from .prophet_modeller import ProphetModellerLogistic
from .model_storage import ModelStorageHandler


class ModelManager:
    DEFAULT_MODEL_NAME = "prophet_logistic_7"
    DEFAULT_PREDICT_FUTURE_HOURS = 2
    
    prometheus_url: str
    logger: Any
    config_manager: ConfigManager
    data_manager: MetricsDataManager
    
    # Read-Write Lock for efficient concurrent access
    _locker: ModelRWLocker
    
    # Storage handler for model persistence
    _storage_handler: ModelStorageHandler
    
    # Registry for trained models (in-memory cache)
    _trained_models_registry: Dict[str, Any]
    
    # Models dictionary
    # Registry of available models
    model_registry: Dict[str, Type[ModelInterface]] = {
        # "prophet": ProphetModeller,
        # Add more models here as they are implemented
        # "arima": ARIMAModeller,
        # "lstm": LSTMModeller,
        # "linear_regression": LinearRegressionModeller,
    }
    

    def __init__(
        self,
        config_manager: ConfigManager,
    ) -> None:
        self.logger = LoggerSetup.get_logger()
        self.logger.info(f"Initialized ModelManager ")
        self.config_manager = config_manager
        self.data_manager = MetricsDataManager(
            config_manager=config_manager,
        )
        
        # Initialize read-write locker
        self._locker = ModelRWLocker()
        
        # Initialize storage handler
        self._storage_handler = ModelStorageHandler(config_manager)
        
        # Initialize trained models registry
        self._trained_models_registry = {}
        
        # Register available models
        ModelFactory.register_model_by_name(ProphetModellerLogistic)
        
        # load the models into registry from config
        self.model_registry = self._read_models_info_from_config()
    
    
    def _read_models_info_from_config(self) -> Dict[str, ModelInterface]:
        models_info = self.config_manager.get_configuration("models")
        model_registry = {}
        
        self.logger.info(f"Total Number of models info read from config - {len(models_info.items())}")
        for model_name, model_info in models_info.items():
            self.logger.info(f"Loading model details for {model_name} - {model_info}")
            
            model_class_name = model_info["model_class"]
            
            # Create model instance from class name using ModelFactory
            # TODO: Remove ModelFactory and use model_registry directly
            model_instance = ModelFactory.create_model_instance(
                model_class_name, 
                self.config_manager, 
                self.data_manager
            )
            if model_instance:
                model_registry[model_name] = model_instance
                self.logger.info(f"Created {model_class_name} instance for {model_name}")
            
        return model_registry
    
    
    def train_model(self, model_name: str, metric_name: str, save_model: Optional[bool] = False) -> Optional[Dict[str, Any]]:
        """Train the specified model for all configured metrics"""
        self.logger.info(f"Training model {model_name}")
        
        # Acquire write lock for training (exclusive access)
        with self._locker.write_context():
            # Get model instance
            model_instance = self.model_registry.get(model_name)
            if not model_instance:
                self.logger.error(f"Model {model_name} not found in registry")
                return None
            
            metric_config = self.config_manager.get_metric_configuration(metric_name)
            if metric_config is None:
                self.logger.error(f"Metric {metric_name} not found in configuration")
                return None
            
            models_info = self.config_manager.get_configuration("models")
            
            # Process each metric
            try:
                self.logger.info(f"Training {model_name} for metric: {metric_name}")
                
                model_info = models_info.get(model_name, {})
                if model_info is None:
                    self.logger.error(f"Model {model_name} not found in configuration")
                    return None
                
                # Get training days from model config or use default
                days_to_train = model_info.get("days_to_train", ModelInterface.SEVEN_DAYS)
                
                # Get training data from data manager
                training_data = self.data_manager.get_metrics_for_days(metric_name, days_to_train)
                if training_data is None or training_data.empty:
                    self.logger.error(f"No training data available for {metric_name}")
                    return None
                
                # Train the model for this metric with the training data
                training_results = model_instance.train_model(metric_name, training_data)
                
                # Store complete training results in registry (not just the model)
                if training_results:
                    self._trained_models_registry[f"{model_name}-{metric_name}"] = training_results                
                    self.logger.info(f"Successfully trained {model_name} for {metric_name}")
                    self.logger.info(f"Training completed in {training_results['training_duration_seconds']:.2f} seconds")
                    self.logger.info(f"Model capacity: {training_results['capacity']}")
                    self.logger.info(f"Data points used: {training_results['data_points']}")
                    
                    # Save model if requested
                    if save_model:
                        save_success = self._storage_handler.save_model(model_name, metric_name, training_results)
                        training_results['save_success'] = save_success
                        if save_success:
                            self.logger.info(f"Successfully saved model for {metric_name}")
                        else:
                            self.logger.warning(f"Failed to save model for {metric_name}")
                else:
                    self.logger.error(f"Failed to train {model_name} for {metric_name}")
                
                return training_results
                
            except Exception as e:
                self.logger.error(f"Error training {model_name} for metric {metric_name}: {e}")
                return None
    
    
    def get_model(self, model_name: str, metric_name: str) -> Optional[Any]:
        """
        Get a specific model by name with read-write lock
        
        Args:
            model_name: Name of the model to retrieve
            
        Returns:
            Model instance or None if not found
        """
        with self._locker.read_context():
            self.logger.debug(f"Reading model: {model_name} for metric {metric_name}")
            model_instance = self._trained_models_registry.get(f"{model_name}-{metric_name}")
            
            if model_instance:
                self.logger.debug(f"Successfully retrieved model: {model_name}")
            else:
                self.logger.error(f"Model {model_name} not found in registry")
                model_data = self.load_single_model_from_disk(model_name, metric_name)
                # if model_data is None:
                #     self.logger.error(f"Model {model_name} not found in registry, and failed to load from disk")
                #     return None
                # self.logger.warning(f"Model {model_name} not found in registry")
            
            return model_instance
    
    
    def predict(self, model_name: str, metric_name: str, hours_ahead: int = 2) -> Optional[pd.DataFrame]:
        """
        Predict using the specified model
        """
        model_data = self.get_model(model_name, metric_name)
        model_instance = self.model_registry.get(model_name)

        if model_data is None:
            self.logger.error(f"Model {model_name} not found in registry")
            model_data = self.load_single_model_from_disk(model_name, metric_name)
            if model_data is None:
                self.logger.error(f"Model {model_name} not found in registry, and failed to load from disk")
                return None

        if not model_instance:
            self.logger.error(f"Model {model_name} not found in registry")
            return None
        
        
        params = {
            "hours_ahead": hours_ahead,
        }
        # Extract the actual Prophet model from the loaded data
        if isinstance(model_data, dict) and 'model' in model_data:
            prophet_model = model_data['model']
            # Log training parameters if available
            self.logger.info(f"\t *** Using model with capacity: {model_data['capacity']}")        
            params['capacity'] = model_data['capacity']
            params['min_value'] = model_data['min_value']
            params['max_value'] = model_data['max_value']
            params['trained_at'] = model_data['trained_at']        
        else:
            # If it's already a Prophet model (from training)
            prophet_model = model_data
                
        return model_instance.predict(metric_name, prophet_model, params)
    
    def get_model_training_params(self, model_name: str, metric_name: str) -> Optional[Dict[str, Any]]:
        """
        Get training parameters for a specific model from registry
        
        Args:
            model_name: Name of the model
            metric_name: Name of the metric
            
        Returns:
            Dictionary containing training parameters or None if not found
        """
        with self._locker.read_context():
            model_data = self._trained_models_registry.get(f"{model_name}-{metric_name}")
            if model_data and isinstance(model_data, dict):
                # Return training parameters (excluding the model object)
                return {
                    "capacity": model_data.get("capacity"),
                    "training_duration_seconds": model_data.get("training_duration_seconds"),
                    "data_points": model_data.get("data_points"),
                    "trained_at": model_data.get("trained_at"),
                    "model_type": model_data.get("model_type"),
                    "metric_name": model_data.get("metric_name")
                }
            return None
    
    def get_storage_handler(self) -> ModelStorageHandler:
        """
        Get the storage handler for direct storage operations
        
        Returns:
            The ModelStorageHandler instance
        """
        return self._storage_handler
    
    
    def load_single_model_from_disk(self, model_name: str, metric_name: str) -> Dict[str, ModelInterface]:
        """
        Load models from disk
        """
        model = self._storage_handler.load_model_with_params(model_name, metric_name)
        if model is None:
            self.logger.error(f"Model {model_name} for {metric_name} not found in registry, and could not be loaded from disk")
            return None
        
        self.logger.info(f"Loaded model {model_name} for {metric_name} from disk with params: {model}")
        self._trained_models_registry[f"{model_name}-{metric_name}"] = model
        
        return model
    


if __name__ == "__main__":
    # Example usage
    config_manager = ConfigManager("../../configs/config.yaml")
    pm = ModelManager(config_manager)
    
    # Test model training and saving
    results = pm.train_model("prophet_logistic_7", "aerospike_namespace_master_objects", save_model=True)
    # print(f"Training results: {results}")
    print(pm.get_model("prophet_logistic_7", "aerospike_namespace_master_objects"))
    
    # # Load models from disk
    # loaded_model_data = pm.load_single_model_from_disk("prophet_logistic_7", "aerospike_namespace_master_objects")
    # print(f"Loaded model data: {loaded_model_data is not None}")
