from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Type
import pandas as pd
import threading
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import ConfigManager
from data import MetricsDataManager
from commons import LoggerSetup


class ModelInterface(ABC):
    """
    Abstract base class for all forecasting models
    """
    
    SEVEN_DAYS = 7
    FIFTEEN_DAYS = 15
    THIRTY_DAYS = 30
    FULL_YEAR_DAYS = 365
    
    CAPACITY_DEFAULT = 500000
    
    def __init__(
        self,
        config_manager: ConfigManager,
        data_manager: MetricsDataManager,
    ) -> None:
        self.logger = LoggerSetup.get_logger()
        self.config_manager = config_manager
        self.data_manager = data_manager
        self.model_name = self.__class__.__name__
        self.logger.info(f"Initialized {self.model_name}")
    
    @abstractmethod
    def train_model(self, metric_name: str, training_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Train the forecasting model
        
        Args:
            metric_name: Name of the metric to train on
            training_data: DataFrame with training data (must have 'ds' and 'y' columns)
            
        Returns:
            Dictionary containing training results:
            - model: The trained model object
            - capacity: Model capacity value
            - training_duration_seconds: Time taken to train
            - data_points: Number of training data points
            - trained_at: Timestamp when training completed
            - model_type: Type of model trained
            Returns None if training fails
        """
        pass
    
    @abstractmethod
    def predict(self, metric_name: str, model: Any, params: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        Make predictions using the trained model
        
        Args:
            metric_name: Name of the metric to predict
            model: The trained model object
            params: Dictionary containing prediction parameters
            
        Returns:
            DataFrame with predictions or None if prediction fails
        """
        pass
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the model
        
        Returns:
            Dictionary with model information
        """
        return {
            "model_name": self.model_name,
            "model_type": self.__class__.__name__,
            "config_manager": self.config_manager is not None,
            "data_manager": self.data_manager is not None
        }


class ModelFactory:
    """
    Factory class to create model instances based on configuration
    """
    
    MODEL_REGISTRY_CLASS: Dict[str, Type[ModelInterface]] = {}
    
    @classmethod
    def create_model_instance(
        cls,
        model_class_name: str,
        config_manager: ConfigManager,
        data_manager: MetricsDataManager
    ) -> Optional[ModelInterface]:
        """
        Create a model instance from class name string
        
        Args:
            model_class_name: String name of the model class
            config_manager: Configuration manager instance
            data_manager: Data manager instance
            
        Returns:
            Model instance or None if creation fails
        """
        try:
            # Method 1: Using ModelFactory registry
            if model_class_name in cls.MODEL_REGISTRY_CLASS:
                model_class = cls.MODEL_REGISTRY_CLASS[model_class_name]
                return model_class(config_manager, data_manager)
            
            # If not found in registry, log error
            available_models = list(cls.MODEL_REGISTRY_CLASS.keys())
            print(f"Model class '{model_class_name}' not found in registry.")
            print(f"Available models: {available_models}")
            return None
            
        except Exception as e:
            print(f"Error creating model instance for '{model_class_name}': {e}")
            return None
    
    @classmethod
    def get_available_models(cls) -> list:
        """Get list of available model types"""
        return list(cls.MODEL_REGISTRY_CLASS.keys())
    
    @classmethod
    def register_model(cls, model_type: str, model_class: Type[ModelInterface]):
        """
        Register a new model type
        
        Args:
            model_type: String identifier for the model
            model_class: Model class that implements ModelInterface
        """
        if not issubclass(model_class, ModelInterface):
            raise ValueError(f"Model class must implement ModelInterface")
        
        cls.MODEL_REGISTRY_CLASS[model_type] = model_class
        print(f"Registered model: {model_type} -> {model_class.__name__}")
    
    @classmethod
    def register_model_by_name(cls, model_class: Type[ModelInterface]):
        """
        Register a model using its class name as the key
        
        Args:
            model_class: Model class that implements ModelInterface
        """
        cls.register_model(model_class.__name__, model_class)


class ModelRWLocker:
    """
    Read-Write Lock implementation for ModelManager
    Allows multiple readers or exclusive writer access
    """
    
    def __init__(self):
        self.logger = LoggerSetup.get_logger()
        
        # Read-Write Lock components
        self._read_lock = threading.RLock()
        self._write_lock = threading.RLock()
        self._read_count = 0
        self._read_count_lock = threading.Lock()
    
    def acquire_read_lock(self):
        """Acquire read lock - allows multiple readers"""
        self._read_lock.acquire()
        with self._read_count_lock:
            self._read_count += 1
            if self._read_count == 1:
                # First reader blocks writers
                self._write_lock.acquire()
                self.logger.debug("First reader acquired write lock")
        self.logger.debug(f"Read lock acquired (readers: {self._read_count})")
    
    def release_read_lock(self):
        """Release read lock"""
        with self._read_count_lock:
            self._read_count -= 1
            if self._read_count == 0:
                # Last reader releases write lock
                self._write_lock.release()
                self.logger.debug("Last reader released write lock")
        self._read_lock.release()
        self.logger.debug(f"Read lock released (readers: {self._read_count})")
    
    def acquire_write_lock(self):
        """Acquire write lock - exclusive access"""
        self.logger.debug("Waiting for write lock")
        self._write_lock.acquire()
        self.logger.debug("Write lock acquired")
    
    def release_write_lock(self):
        """Release write lock"""
        self._write_lock.release()
        self.logger.debug("Write lock released")
    
    def read_context(self):
        """
        Context manager for read operations
        
        Usage:
            with locker.read_context():
                # Read operations here
                pass
        """
        return ReadLockContext(self)
    
    def write_context(self):
        """
        Context manager for write operations
        
        Usage:
            with locker.write_context():
                # Write operations here
                pass
        """
        return WriteLockContext(self)


class ReadLockContext:
    """Context manager for read lock operations"""
    
    def __init__(self, locker: ModelRWLocker):
        self.locker = locker
    
    def __enter__(self):
        self.locker.acquire_read_lock()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.locker.release_read_lock()


class WriteLockContext:
    """Context manager for write lock operations"""
    
    def __init__(self, locker: ModelRWLocker):
        self.locker = locker
    
    def __enter__(self):
        self.locker.acquire_write_lock()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.locker.release_write_lock()
