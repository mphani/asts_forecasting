from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

import numpy as np
import os
import pandas as pd
import pickle
from prophet import Prophet
import pytz
import requests
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commons import LoggerSetup, CommonsUtils
from config import ConfigManager
from data import MetricsDataManager
from .model_base import ModelInterface

class ProphetModellerLogistic(ModelInterface):
    """
    Prophet-based forecasting model implementation
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        data_manager: MetricsDataManager,
    ) -> None:
        super().__init__(config_manager, data_manager)
       
        self.MAX_CAPACITY_FACTOR = 1.1  # TODO: Check if we need to add this as a config parameter
    
    
    def train_model(self, metric_name: str, training_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Train Prophet model for the given metric using provided training data"""
        self.logger.info(f"Training Prophet model for {metric_name} with {len(training_data)} data points")
        
        try:
            if training_data is None or training_data.empty:
                self.logger.error(f"No training data provided for {metric_name}")
                return None
            
            # Validate required columns
            if 'ds' not in training_data.columns or 'y' not in training_data.columns:
                self.logger.error(f"Training data must have 'ds' and 'y' columns. Found: {list(training_data.columns)}")
                return None
            
            self.logger.info(f"Loaded {len(training_data)} rows for training")
            
            # Ensure datetime is in UTC timezone for Prophet compatibility
            training_data = training_data.copy()

            # Normalize the training data
            self.logger.debug(f"BEFORE - Training data before normalization: {training_data.head()}")
            training_data = self._normalize_training_data_ds(training_data)
            self.logger.debug(f"AFTER - Training data after normalization: {training_data.head()}")
                
            self.logger.info(f"Training data timezone: {training_data['ds'].dt.tz}")
            self.logger.info(f"Training data time range: {training_data['ds'].min()} to {training_data['ds'].max()}")
            
            # Create Prophet model with logistic growth
            model = Prophet(growth="logistic")
            self.logger.debug(f"{self.model_name} {ProphetModellerLogistic.__name__} Model created successfully")
            
            # Set capacity for logistic growth
            min_value = training_data["y"].min(skipna=True) 
            max_value = training_data["y"].max(skipna=True) 
            y_cap_value = max_value * self.MAX_CAPACITY_FACTOR
            
            training_data["cap"] = y_cap_value
            
            # Train the model and measure time
            self.logger.debug(f"Starting Prophet model training for {metric_name}...")
            start_time = time.time()
            
            model.fit(training_data)
            
            training_duration = time.time() - start_time
            self.logger.debug(f"Total time taken for Prophet model training for {metric_name} {training_duration:.2f} seconds")
            
            # Store the trained model and data
            trained_at_timestamp = datetime.now(pytz.UTC).timestamp()  # Store as UTC timestamp
            
            self.logger.info(f"Successfully trained Prophet model for {metric_name} in {training_duration:.2f} seconds")
            self.logger.debug(f"Capacity: {y_cap_value}, Min value: {min_value}, Max value: {max_value}")
            
            # Return training results
            training_results = {
                "model": model,
                "capacity": y_cap_value,
                "min_value": min_value,
                "max_value": max_value,
                "training_duration_seconds": training_duration,
                "data_points": len(training_data),
                "trained_at": trained_at_timestamp,  # Use the same UTC timestamp
                "model_type": "ProphetLogistic",
                "metric_name": metric_name
            }
            
            return training_results
            
        except Exception as e:
            self.logger.error(f"Error training Prophet model for {metric_name}: {e}")
            return None
    
        
    def predict(self, metric_name: str, model: Any, params: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """Make predictions using the trained Prophet model"""
        hours_ahead = params.get("hours_ahead", 2)
        y_cap = params.get("capacity", ModelInterface.CAPACITY_DEFAULT)
        
        self.logger.info(f"Starting predictions for {metric_name} {hours_ahead} hours ahead")
        
        try:            
            # Keep only predictions from current time to max_time (2 hours ahead)
            # DO NOT DELETE - future_df = future_df[(future_df['ds'] >= current_time_utc) & (future_df['ds'] <= max_time_utc)]
            
            future_df, max_time_utc = self._compute_future_dataframe(model, params)            
            future_df = future_df[ (future_df['ds'] <= max_time_utc)]
            self.logger.debug(f"Filtered future dataframe (current time to {hours_ahead}h ahead): {future_df['ds'].min()} to {future_df['ds'].max()}")
            
            start_time = time.time()
            predictions = model.predict(future_df)
            end_time = time.time()

            # Convert prediction timestamps back to UTC timezone-aware for API response
            predictions['ds'] = pd.to_datetime(predictions['ds'], utc=True)                        
            prediction_duration = end_time - start_time
            
            # Keep only the prediction columns
            prediction_columns = ['ds', 'yhat', 'yhat_lower', 'yhat_upper']
            predictions = predictions[prediction_columns]
            
            self.logger.info(f"Generated {len(predictions)} predictions for {metric_name} in {prediction_duration:.2f} seconds")
            return predictions
            
        except Exception as e:
            self.logger.error(f"Error making predictions for {metric_name}: {e}")
            return None

    
    def _compute_future_dataframe(self, model: Any, params: Dict[str, Any]) -> Tuple[pd.DataFrame, datetime]:
        """Compute the future dataframe for the given model and parameters"""
        hours_ahead = params.get("hours_ahead", 2)
        y_cap = params.get("capacity", ModelInterface.CAPACITY_DEFAULT)
        trained_at = params.get("trained_at")

        current_time = datetime.now()
        if trained_at:
            trained_datetime = datetime.fromtimestamp(trained_at)  # This gives GMT/local time
            current_time_plus_2h = current_time + timedelta(hours=hours_ahead)
            
            # Calculate hours between current_time_plus_2h and trained_at
            hours_between = (current_time_plus_2h - trained_datetime).total_seconds() / 3600
            end_time = current_time_plus_2h.replace(tzinfo=pytz.UTC)            
        else:
            current_time_plus_2h = current_time + timedelta(hours=hours_ahead)
            end_time = datetime.now(pytz.UTC) + timedelta(hours=hours_ahead)
            
        minutes_ahead_interval = 3  # 3 minutes
        
        # Use Prophet's make_future_dataframe to ensure continuity from training data
        self.logger.debug(f"Last training date: {model.history['ds'].max()}")
        
        # Calculate total periods needed from last training date to end_time
        # Ensure last_training_date is timezone-aware UTC for comparison
        # Convert to UTC but keep timezone-naive for Prophet compatibility
        time_diff = end_time - pd.to_datetime(model.history['ds'].max(), utc=True)
        total_periods = int(time_diff.total_seconds() / (minutes_ahead_interval * 60))
        
        future_df = model.make_future_dataframe(periods=total_periods, freq=f'{minutes_ahead_interval}min', include_history=False)
        future_df['ds'] = pd.to_datetime(future_df['ds'], utc=True).dt.tz_localize(None)
        future_df['cap'] = y_cap
        
        self.logger.debug(f"Creating future dataframe for {total_periods} periods (from last training to {end_time.strftime('%Y-%m-%d %H:%M:%S')})")
        self.logger.debug(f"Future dataframe time range: {future_df['ds'].min()} to {future_df['ds'].max()}")
        max_time_utc = datetime.now(pytz.UTC).replace(tzinfo=None) + timedelta(hours=hours_ahead)
        
        return future_df, max_time_utc
        

    def _normalize_training_data_ds(self, training_data: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure training_data['ds'] is timezone-naive UTC for Prophet.
        Rules:
        - numeric (int/float) -> parsed as epoch seconds (UTC)
        - strings -> parsed as UTC-aware datetimes
        - tz-aware -> converted to UTC
        - naive datetimes -> assumed to be UTC
        - final output -> tz info removed (naive UTC)
        Modifies training_data in-place and returns it.
        """
        col = 'ds'
        self.logger.info("Normalizing %s in training_data to naive UTC for Prophet", col)

        # 1) If numeric epoch seconds
        if pd.api.types.is_integer_dtype(training_data[col]) or pd.api.types.is_float_dtype(training_data[col]):
            self.logger.info("%s appears numeric -> parsing as epoch seconds (UTC)", col)
            training_data[col] = pd.to_datetime(training_data[col], unit='s', utc=True)

        # 2) If not datetime dtype (likely strings)
        elif not pd.api.types.is_datetime64_any_dtype(training_data[col]):
            self.logger.info("%s appears non-datetime -> parsing as UTC-aware", col)
            training_data[col] = pd.to_datetime(training_data[col], utc=True, errors='raise')

        # 3) Now either tz-aware or naive
        if training_data[col].dt.tz is None:
            self.logger.info("%s is naive -> localizing to UTC", col)
            training_data[col] = training_data[col].dt.tz_localize('UTC')
        else:
            self.logger.info("%s is tz-aware -> converting to UTC", col)
            training_data[col] = training_data[col].dt.tz_convert('UTC')

        # 4) Drop tz info for Prophet (naive UTC)
        training_data[col] = training_data[col].dt.tz_localize(None)
        self.logger.info("%s normalized: dtype=%s tz=%s", col, training_data[col].dtype, getattr(training_data[col].dt, 'tz', None))

        return training_data


if __name__ == "__main__":
    pm = ProphetModellerLogistic(
        config_manager=ConfigManager("../../configs/config.yaml"),
        data_manager=DataManager(ConfigManager("../../configs/config.yaml"))
    )
