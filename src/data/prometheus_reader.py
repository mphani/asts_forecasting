from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

import numpy as np
import os
import pandas as pd
import pytz
import requests
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from commons import LoggerSetup, CommonsUtils
from config import ConfigManager


class PrometheusReader:
    prometheus_url: str
    logger: Any
    config_manager: ConfigManager

    def __init__(
        self,
        config_manager: ConfigManager,
    ) -> None:
        self.logger = LoggerSetup.get_logger()
        self.logger.info(f"Initialized PrometheusReader ")
        self.config_manager = config_manager
        self.prometheus_url = self.config_manager.get_configuration("metric_prometheus_url")
        self.commons_utils = CommonsUtils(config_manager)

    def fetch_metric_data(self,        
                          metric_name: str,
                          metric_configurations: Optional[dict] = None,
                          ) -> Tuple[Optional[pd.DataFrame], Optional[timedelta]]:
        
        metric_config = metric_configurations
        
        if metric_config is None:
            if metric_name in self.config_manager.get_configuration("metrics"):
                metric_config = self.config_manager.get_configuration("metrics")[metric_name]
                if metric_config is None:
                    self.logger.error(f"Metric {metric_name} not found in configuration")
                    return None, None
            else:
                self.logger.error(f"Metric {metric_name} not found in configuration")
                return None, None
        
        metric_timezone = pytz.timezone(
            metric_config["metric_timezone"]
        )
        
        compute_start_time = datetime.now( metric_timezone)
        
        # Ensure compute_start_time is timezone-aware
        if compute_start_time.tzinfo is None:
            compute_start_time = compute_start_time.replace(tzinfo=metric_timezone)
            
        # Determine the time window for fetching data
        fetch_start_time = compute_start_time - timedelta(
            hours=metric_config["metric_history_hours"]
        )
        # TODO: get the delta from config
        fetch_end_time = compute_start_time - timedelta(minutes=10)

        return self.fetch_metric_data_with_time(metric_name, compute_start_time, fetch_start_time, fetch_end_time, metric_config)


    def fetch_metric_data_with_time(self,        
                          metric_name: str, compute_start_time: datetime, 
                          fetch_start_time: datetime, fetch_end_time: datetime,
                          metric_configurations: Optional[dict] = None,
                          ) -> Tuple[Optional[pd.DataFrame], Optional[timedelta]]:
        
        """Fetch historical data for this metric from Prometheus"""
        
        metric_config = metric_configurations
        
        # if given metric_configurations is None, then get the metric_config from the config_manager
        if metric_config is None:
            if metric_name in self.config_manager.get_configuration("metrics"):
                metric_config = self.config_manager.get_configuration("metrics")[metric_name]
                if metric_config is None:
                    self.logger.error(f"Metric {metric_name} not found in configuration")
                    return None, None
            else:
                self.logger.error(f"Metric {metric_name} not found in configuration")
                return None, None
                        
        metric_query = metric_config["metric_query"]
        if "metric_placeholders" in metric_config:
           metric_placeholders = metric_config["metric_placeholders"]
        else:
           metric_placeholders = self.config_manager.get_configuration("metrics")["metric_placeholders"]
           
        print(f"\n\n\t\t **** metric_query: {metric_query}")
                   
        # Only process placeholders if they exist and are not None
        if metric_placeholders:
            for placeholder, value in metric_placeholders.items():
                metric_query = metric_query.replace(placeholder, value)
        
        try:
            metric_timezone = pytz.timezone(
                metric_config["metric_timezone"]
            )
            
            self.logger.info(
                f"Fetching data from {fetch_start_time} to {fetch_end_time} for {metric_name}"
            )
            
            chunked = self.commons_utils.chunk_time_slices(
                start=fetch_start_time,
                end=fetch_end_time,
                window_size=timedelta(hours= metric_config["metric_chunk_hours"] ),
            )
            
            fetchedPDs = pd.DataFrame()
            for start_time, end_time in chunked:
                df = self._query_prom( metric_name, metric_query, start_time, end_time)
                if df is not None:
                    if len(df) == 0:
                        self.logger.debug(
                            f"No data fetched for {start_time} - {end_time} for {metric_name}"
                        )
                        continue
                    self.logger.debug(
                        f"Fetched {len(df)} data points from Prometheus for {metric_name}"
                    )
                    fetchedPDs = pd.concat([fetchedPDs, df], ignore_index=True)
                else:
                    self.logger.error(
                        f"Error fetching data from Prometheus for {metric_name}"
                    )
                    return None, None
                
            self.logger.debug(f"Total fetched data points: {len(fetchedPDs)} for {metric_name}")      
            return fetchedPDs, datetime.now(metric_timezone) - compute_start_time

        except Exception as e:
            self.logger.error(f"Error fetching data: {str(e)}")
            raise e


    def _query_prom(self, metric_name: str, metric_query: str,
                   start_time: datetime = None, end_time: datetime = None
                   ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data from Prometheus with proper timezone handling
        """
        self.logger.debug(f"Querying Prometheus for {metric_name} from {start_time} to {end_time}")
        
        metric_config = self.config_manager.get_metric_configuration(metric_name)
        if metric_config is None:
            self.logger.error(f"Metric {metric_name} not found in configuration")
            return
        
        try:
            metric_timezone = pytz.timezone(
                metric_config["metric_timezone"]
            )
            
            
            # Convert to UTC for Prometheus
            if start_time.tzinfo is None:
                start_time = metric_timezone.localize(start_time)
            if end_time.tzinfo is None:
                end_time = metric_timezone.localize(end_time)

            # Convert to UTC for Prometheus query
            start_time_utc = start_time.astimezone(pytz.UTC)
            end_time_utc = end_time.astimezone(pytz.UTC)

            # Format in UTC
            start_time_str = start_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_time_str = end_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

            params = {
                "query": metric_query,
                "start": start_time_str,
                "end": end_time_str,
                "step": metric_config["metric_step"],
            }
            
            self.logger.debug(f"Querying Prometheus {self.prometheus_url}/api/v1/query_range with params: {params}")

            response = requests.get(
                f"{self.prometheus_url}/api/v1/query_range", params=params, verify=False
            )

            if response.status_code == 200:
                results = response.json()["data"]["result"]

                # Process the results into a DataFrame with proper timezone handling
                data = []
                seen_timestamps = set()
                for result in results:
                    for value in result["values"]:
                        # Convert timestamp to datetime in UTC
                        timestamp_utc = datetime.fromtimestamp(
                            float(value[0]), tz=pytz.UTC
                        )
                        # Convert to desired timezone
                        timestamp_local = timestamp_utc.astimezone(metric_timezone)

                        if timestamp_local not in seen_timestamps:
                            seen_timestamps.add(timestamp_local)
                            metric_value = float(value[1])
                            data.append({"ds": timestamp_local, "y": metric_value})

                self.logger.debug(f"Fetched {len(data)} data points from Prometheus for {metric_name}")
                return pd.DataFrame(data)
            else:
                self.logger.error(
                    f"Error fetching data from Prometheus: {response.status_code} {response.json()}"
                )
                return None

        except Exception as e:
            self.logger.error(f"Error fetching data: {str(e)}")
            return None


if __name__ == "__main__":
    cm = ConfigManager("../../configs/config.yaml")
    pm = PrometheusReader(
        config_manager = cm,
    )
    # print(pm.fetch_metric_data("aerospike_namespace_master_objects"))
    
    # read only today with configuration
    metric_configurations = cm.get_metric_configuration("aerospike_namespace_master_objects").copy()
    
    # Calculate hours from today 00:00:00 to now()
    metric_timezone = pytz.timezone(metric_configurations["metric_timezone"])
    now = datetime.now(metric_timezone)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hours_today = (now - today_start).total_seconds() / 3600
    
    metric_configurations["metric_history_hours"] = int(hours_today)
    print(pm.fetch_metric_data("aerospike_namespace_master_objects", metric_configurations))
    
    print(f"\n\n \t\t *********** hours_today == {hours_today}")
    print("\n\n \t\t ***********metric_history_hours is in MAIN ***********", metric_configurations["metric_history_hours"])

