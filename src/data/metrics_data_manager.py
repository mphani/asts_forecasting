from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

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
from .prometheus_reader import PrometheusReader

class MetricsDataManager:
    DEFAULT_STORAGE_PATH = "./metadata"
    prometheus_url: str
    logger: Any
    config_manager: ConfigManager
    storage_path: str

    def __init__(
        self,
        config_manager: ConfigManager,
    ) -> None:
        self.logger = LoggerSetup.get_logger()
        self.logger.info(f"Initialized MetricsDataManager ")
        self.config_manager = config_manager
        self.prometheus_reader = PrometheusReader(
            config_manager=config_manager,
        )
    
    
    def get_metrics_for_days(self, metric_name: str, days_back: int) -> pd.DataFrame:
        """
        Get metrics data for specified number of days back from today
        
        Args:
            metric_name: Name of the metric
            days_back: Number of days back from today (0=today, 1=yesterday, 2=day before yesterday, etc.)
            
        Returns:
            Combined DataFrame with data from local files and Prometheus
        """
        try:
            # Get timezone from config for consistent timezone handling
            # Always read from Prometheus for today
            self.logger.info("days_back=0: Fetching today's data from Prometheus")
            metric_configurations = self.config_manager.get_metric_configuration(metric_name).copy()
            
            # Calculate hours from today 00:00:00 to now() (timezone aware)
            metric_timezone = pytz.timezone(metric_configurations["metric_timezone"])
            now = datetime.now(metric_timezone)
            hours_today = now.hour + 1
            
            metric_configurations["metric_history_hours"] = int(hours_today)
            self.logger.info(f"Calculated hours for today: {hours_today:.1f} hours")
            
            todays_data, _ = self.prometheus_reader.fetch_metric_data(metric_name, metric_configurations)
            
            # if only today data is required, we read it from Prometheus, so return the data
            if days_back == 0:
                self.logger.info(f"As days_back=0, Returning today's data for '{metric_name}'")
                return todays_data
            
            
            metric_config = self.config_manager.get_configuration("metrics")[metric_name]
            metric_timezone = pytz.timezone(metric_config["metric_timezone"])
            
            # Calculate cutoff time: 0=today, 1=yesterday, 2=day before yesterday
            now = datetime.now(metric_timezone)
            cutoff_time = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_back)
            
            self.logger.info(f"Getting data for '{metric_name}' from {cutoff_time} (days_back={days_back})")
            
            # Always read from local disk for historical data
            self.logger.info(f"days_back={days_back}: Reading historical data from local disk")
            local_data = self._read_local_data_since(metric_name, cutoff_time)
            
            # Combine today's data with historical data
            dataframes_to_combine = []
            
            if local_data is not None and not local_data.empty:
                dataframes_to_combine.append(local_data)
                self.logger.info(f"Found {len(local_data)} local records")
            
            if todays_data is not None and not todays_data.empty:
                dataframes_to_combine.append(todays_data)
                self.logger.info(f"Adding {len(todays_data)} today's records")
                
            # TODO: If there are not files for last few days like 2/3 days, then we need to fetch them dynamically from Prometheus
            
            if dataframes_to_combine:
                # Combine all data and remove duplicates
                combined_data = pd.concat(dataframes_to_combine, ignore_index=True)
                combined_data = combined_data.drop_duplicates(subset=['ds']).sort_values('ds')
                
                self.logger.info(f"Final combined data: {len(combined_data)} records")
                self.logger.debug(f"\t\t **** combined_data: {combined_data.head()}")
                
                return combined_data

            self.logger.warning("No data found (neither local nor today's data)")
            return None
                
        except Exception as e:
            self.logger.error(f"Error in smart data retrieval for '{metric_name}': {e}")
            return None
    
    
    def _read_local_data_since(self, metric_name: str, cutoff_time: datetime) -> Optional[pd.DataFrame]:
        """
        Read local data files since the cutoff time
        
        Args:
            metric_name: Name of the metric
            cutoff_time: Only include data after this time
            
        Returns:
            Combined DataFrame from local files or None if no data
        """
        try:
            storage_path = self.get_storage_path(metric_name)
            all_data = []
            
            # Get all files for this metric
            pattern = f"pd_*_{metric_name}.pkl"
            import glob
            files = glob.glob(os.path.join(storage_path, pattern))
            
            if not files:
                self.logger.info(f"filenames {files}")
                self.logger.debug(f"No local files found for {metric_name}")
                return None
            
            # Read and filter files
            for file_path in files:
                try:
                    df = self.load_metrics_from_file(file_path)
                    
                    if df is not None and 'ds' in df.columns:
                        # Ensure timezone compatibility for comparison
                        if cutoff_time.tzinfo is None and df['ds'].dt.tz is not None:
                            # If cutoff_time is naive but data has timezone, localize cutoff_time
                            cutoff_time_tz = cutoff_time.replace(tzinfo=df['ds'].dt.tz)
                        elif cutoff_time.tzinfo is not None and df['ds'].dt.tz is None:
                            # If cutoff_time has timezone but data is naive, convert data to cutoff_time timezone
                            df['ds'] = df['ds'].dt.tz_localize(cutoff_time.tzinfo)
                            cutoff_time_tz = cutoff_time
                        else:
                            cutoff_time_tz = cutoff_time
                        
                        # Filter data after cutoff time
                        df_filtered = df[df['ds'] >= cutoff_time_tz]
                        if not df_filtered.empty:
                            all_data.append(df_filtered)
                            self.logger.debug(f"Loaded {len(df_filtered)} records from {os.path.basename(file_path)}")
                    
                except Exception as e:
                    self.logger.warning(f"Error reading file {file_path}: {e}")
                    continue
            
            if all_data:
                combined = pd.concat(all_data, ignore_index=True)
                combined = combined.drop_duplicates(subset=['ds']).sort_values('ds')
                
                # Calculate days covered
                if not combined.empty:
                    earliest_time = combined['ds'].min()
                    latest_time = combined['ds'].max()
                    days_covered = (latest_time - earliest_time).total_seconds() / (24 * 3600)
                    
                    # Use timezone-aware now() for comparison
                    now_tz = datetime.now(earliest_time.tzinfo) if earliest_time.tzinfo else datetime.now()
                    days_since_cutoff = (now_tz - latest_time).total_seconds() / (24 * 3600)
                    
                    self.logger.info(f"Local Data - Time range: {earliest_time} to {latest_time}")
                    self.logger.info(f"Local Data - Days covered: {days_covered:.1f}")
                    self.logger.info(f"Local Data - Files read: {len(all_data)}")
                    self.logger.info(f"Local Data - Total Records: {len(combined)}")
                    
                self.logger.info(f"Loaded {len(combined)} total records from {len(all_data)} local files")
                return combined
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error reading local data: {e}")
            return None
    
    
    def fetch_and_store_metrics_by_date(self, metric_name: str) -> Dict[str, str]:
        """
        Fetch metrics from Prometheus and store them by date in separate files
        
        Args:
            metric_name: Name of the metric to fetch
            
        Returns:
            Dictionary mapping dates to filenames where data was stored
        """
        try:
            # Fetch data from Prometheus
            df, duration = self.prometheus_reader.fetch_metric_data(metric_name)
            
            if df is not None:
                
                # Store the DataFrame by date
                stored_files = self.store_metrics_by_date(metric_name, df)
                self.logger.info(f"Successfully fetched and stored {len(df)} records for metric '{metric_name}' across {len(stored_files)} dates")
                return stored_files
            else:
                self.logger.warning(f"No data fetched for metric '{metric_name}'")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error fetching and storing metrics by date for '{metric_name}': {e}")
            return {}
    
    
    def store_metrics_by_date(self, metric_name: str, metric_data: pd.DataFrame) -> Dict[str, str]:
        """
        Store DataFrame data by date, creating separate files for each date
        
        Args:
            metric_name: Name of the metric
            metric_data: DataFrame with 'ds' column containing dates
            
        Returns:
            Dictionary mapping dates to filenames where data was stored
        """
        if metric_data is None or metric_data.empty:
            self.logger.warning(f"No data to store for metric '{metric_name}'")
            return {}
        
        if 'ds' not in metric_data.columns:
            self.logger.error(f"DataFrame for '{metric_name}' missing 'ds' column")
            return {}
        
        stored_files = {}
        
        try:
            # Convert 'ds' column to date strings for grouping
            metric_data['date_str'] = metric_data['ds'].dt.strftime('%d%m%Y')

            # Group by date and store each group separately
            for date_str, group_df in metric_data.groupby('date_str'):
                # Create filename with date
                filename = self.get_filename_by_date(metric_name, date_str)
                
                # Calculate date-wise statistics
                ds_min = group_df['ds'].min()
                ds_max = group_df['ds'].max()
                record_count = len(group_df)
                
                # Store this date's data
                with open(filename, 'wb') as f:
                    pickle.dump(group_df.drop('date_str', axis=1), f)  # Remove temp column
                
                stored_files[date_str] = filename
                
                # Log detailed date-wise statistics
                self.logger.info(f"DATE: {date_str},{ds_min} to {ds_max}, {record_count},{os.path.basename(filename)}")
                
                self.logger.info(f"Stored {record_count} records for {metric_name} on {date_str}")
            
            return stored_files
            
        except Exception as e:
            self.logger.error(f"Error storing metrics by date for '{metric_name}': {e}")
            return {}
    
    
    def get_filename_by_date(self, metric_name: str, date_str: str) -> str:
        """
        Get filename for a specific metric and date
        
        Args:
            metric_name: Name of the metric
            date_str: Date string in DDMMYYYY format
            
        Returns:
            Full path to the file
        """
        storage_path = self.get_storage_path(metric_name)
        return os.path.join(storage_path, f"pd_{date_str}_{metric_name}.pkl")


    def load_metrics_from_file(self, file_path: str) -> pd.DataFrame:
        try:
            with open(file_path, 'rb') as f:
                df = pickle.load(f)
            
            if 'ds' in df.columns:
                self.logger.debug(f"Loaded {len(df)} records from {os.path.basename(file_path)}")
                return df
            
        except Exception as e:
            self.logger.warning(f"Error reading file {file_path}: {e}")
        
        return None

        
    def delete_metrics(self, metric_name: str) -> None:
        storage_path = self.get_storage_path(metric_name)
        pattern = f"pd_*_{metric_name}.pkl"
        import glob
        files = glob.glob(os.path.join(storage_path, pattern))
        
        for filename in files:
            try:
                os.remove(filename)
                self.logger.info(f"Deleted file: {filename}")
            except OSError as e:
                self.logger.error(f"Error deleting file {filename}: {e}")

        
    def get_filename(self, metric_name: str, date_str: Optional[str] = None) -> str:
        storage_path = self.get_storage_path(metric_name)
        if date_str:
            current_date = date_str
        else:
            # Get current date in DDMMYYYY format
            current_date = datetime.now().strftime("%d%m%Y")
        return os.path.join(storage_path, f"pd_{current_date}_{metric_name}.pkl")

        
    def get_storage_path(self, metric_name: str = None, hourly: bool = False) -> str:
        """
        Get the storage path for data with robust path resolution
        
        Args:
            metric_name: Name of the metric (optional)
            hourly: Whether to use hourly storage (unused, kept for compatibility)
            
        Returns:
            Path to the storage directory
        """
        # Get the absolute path to this file (metrics_data_manager.py)
        current_file_path = os.path.abspath(__file__)
        
        # Navigate to project root: src/datamanager/metrics_data_manager.py -> src/datamanager -> src -> project_root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
        
        # Build the data/metadata path relative to project root
        storage_path = os.path.join(project_root, "data", self.DEFAULT_STORAGE_PATH)
        
        if metric_name:
            storage_path = os.path.join(storage_path, metric_name)
            
        # Check if folder exists, create if it doesn't
        if not os.path.exists(storage_path):
            os.makedirs(storage_path, exist_ok=True)
            self.logger.info(f"Created storage directory: {storage_path}")
        
        return storage_path


if __name__ == "__main__":
    dm = MetricsDataManager(
        config_manager=ConfigManager("../../configs/config.yaml"),
    )

    # print("\t storage path: ",dm.get_storage_path())
    dm.fetch_and_store_metrics_by_date("aerospike_namespace_master_objects")
    
    # get - now - 3 days
    # dm.get_metrics_for_days("aerospike_namespace_master_objects", 7)
