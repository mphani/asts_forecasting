import json
import os
import sys
import pytz

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Any, Optional
import yaml
from commons import LoggerSetup 
from datetime import timezone

class ConfigManager:
    """Class to store metric processing state supporting JSON and YAML configs."""

    filePath: str
    fileName: str
    fullPath: str
    file_ext: str
    config: dict[str, Any]
    logger: Any

    def __init__(self, full_path: str) -> None:
        self.logger = LoggerSetup.get_logger()
        self.fullPath = full_path
        self.file_ext = self._get_file_ext()
        self.logger.info(f"Initializing ConfigManager for {self.fullPath} (ext: {self.file_ext})")
        if self.file_ext not in ("json", "yml", "yaml"):
            self.logger.error(f"Invalid file type: {self.file_ext}")
            raise ValueError("Invalid file type: only .json, .yml, or .yaml supported")
        if self.file_ext in ("yml", "yaml") and yaml is None:
            raise ImportError("PyYAML is required for YAML support. Please install pyyaml.")
        self.config = self.load_configuration()
        if not self.config:
            self.logger.error("Error loading configuration")
            raise ValueError("Error loading configuration")
        self.logger.info("Configuration loaded successfully")

    def _get_file_ext(self) -> str:
        ext = self.fullPath.split(".")[-1].lower()
        self.logger.debug(f"Detected file extension: {ext}")
        return ext

    def save_configuration(self) -> None:
        """Save metric configuration to file (JSON or YAML)"""
        os.makedirs(self.filePath, exist_ok=True)
        self.logger.info(f"Saving configuration to {self.fullPath} as {self.file_ext}")
        try:
            if self.file_ext == "json":
                with open(self.fullPath, "w") as f:
                    json.dump(self.config, f, indent=4)
            elif self.file_ext in ("yml", "yaml"):
                with open(self.fullPath, "w") as f:
                    yaml.safe_dump(self.config, f, default_flow_style=False)
            else:
                self.logger.error(f"Invalid file type: {self.file_ext}")
                raise ValueError("Invalid file type: only .json, .yml, or .yaml supported")
            self.logger.info(f"Configuration saved to {self.fullPath}")
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            raise

    def override_configuration(self, config: dict[str, Any]) -> None:
        """Write configuration to file"""
        self.logger.info("Overriding configuration in memory and saving to disk")
        self.config = config
        self.save_configuration()
        self.reload_configuration()

    def load_configuration(self) -> Optional[dict[str, Any]]:
        """Load metric configuration from file (JSON or YAML)"""
        if os.path.exists(self.fullPath):
            self.logger.info(f"Loading configuration from {self.fullPath}")
            try:
                with open(self.fullPath, "r") as f:
                    if self.file_ext == "json":
                        config = json.load(f)
                    elif self.file_ext in ("yml", "yaml"):
                        config = yaml.safe_load(f)
                    else:
                        self.logger.error(f"Invalid file type: {self.file_ext}")
                        raise ValueError("Invalid file type: only .json, .yml, or .yaml supported")
                self.logger.info(f"Configuration loaded from {self.fullPath}")
                return config
            except (json.JSONDecodeError, yaml.YAMLError, ValueError) as e:
                self.logger.error(f"Failed to load configuration: {e}")
                return None
        self.logger.warning(f"Configuration file {self.fullPath} does not exist")
        return None

    def get_configuration(self, config: str, default: Any = None) -> Any:
        """Get configuration value"""
        self.logger.debug(f"Getting configuration value for key: {config}")
        if config in os.environ:
            self.logger.info(f"Found {config} in environment variables")
            return os.environ[config]
        value = self.config[config] if config in self.config else default
        if value is default:
            self.logger.debug(f"Key {config} not found, returning default: {default}")
        return value

    def get_metric_configuration(self, metric_name: str) -> Any:
        """Get metric configuration value"""
        self.logger.debug(f"Getting metric configuration for key: {metric_name}")
        
        metrics = self.config["metrics"]         
        if metric_name in metrics:
            return metrics[metric_name] 
        else:
            self.logger.error(f"Metric {metric_name} not found in configuration")
                            
        return None

    def get_metric_config_value(self, metric_name: str, metric_key: str, default: Any = None) -> Any:
        """Get metric configuration value"""
        self.logger.debug(f"Getting metric configuration value for key: {metric_name}")
        
        metrics = self.config["metrics"]         
        if metric_name in metrics:
            if metric_key in metrics[metric_name]:
                return metrics[metric_name][metric_key]
            else:
                if metric_key in metrics:
                    self.logger.error(f"Metric {metric_key} not found for metric {metric_name}, using metrics.config[{metric_key}]")
                    return metrics[metric_key] 
                else:                
                    self.logger.error(f"Metric {metric_key} not found in configuration for metric {metric_name}")
                    return default
        else:
            self.logger.error(f"Metric {metric_name} not found in configuration")
                            
        return None

    def reload_configuration(self) -> Optional[dict[str, Any]]:
        """Reload configuration from file"""
        self.logger.info("Reloading configuration from file")
        self.config = self.load_configuration()
        return self.config

    def add_metric_config(self, config: dict[str, Any]) -> None:
        """Add a metric config to the metrics array and save the configuration."""
        self.logger.info(f"Adding metric config: {config.get('metric_name', '<unknown>')}")
        if "metrics" not in self.config or not isinstance(self.config["metrics"], list):
            self.logger.debug("No metrics array found, initializing new list")
            self.config["metrics"] = []
        self.config["metrics"].append(config)
        self.save_configuration()

    def remove_metric_config(self, metric_name: str) -> None:
        """Remove a metric config by name from the metrics array and save the configuration."""
        self.logger.info(f"Removing metric config: {metric_name}")
        metrics_list = self.config.get("metrics", [])
        new_metrics_list = [
            m for m in metrics_list if m.get("metric_name") != metric_name
        ]
        self.config["metrics"] = new_metrics_list
        self.save_configuration()

    def get_timezone(self, metric_timezone: str = "UTC") -> timezone:
        """Get the timezone from the configuration"""
        return pytz.timezone(metric_timezone)

if __name__ == "__main__":
    config_manager = ConfigManager("../../configs/config.yaml")
    # print("\n",config_manager.get_configuration("metrics"))
    # print("\n",config_manager.get_configuration("metrics")["aerospike_namespace_master_objects"])    
    
    print("\n\n",config_manager.get_metric_configuration("aerospike_namespace_master_objects"))        
    # print("\n\n",config_manager.get_metric_configuration("aerospike_namespace_master_objects2"))            
    # print("\n\n",config_manager.get_metric_config_value("aerospike_namespace_master_objects", "metric_timezone"))            
    # print("\n\n",config_manager.get_metric_config_value("aerospike_namespace_master_objects", "metric_timezone2","GMT"))            
