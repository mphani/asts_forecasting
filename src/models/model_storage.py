import os
import pickle
import sys
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commons import LoggerSetup


class ModelStorageHandler:
    """
    Handles model storage and retrieval operations
    Manages file paths, serialization, and persistence
    """
    
    DEFAULT_STORAGE_PATH = "./models_info"
    
    # File type constants
    MODEL_FILE_TYPE = "MODEL"
    PARAMS_FILE_TYPE = "PARAMS"
    
    
    def __init__(self, config_manager):
        self.logger = LoggerSetup.get_logger()
        self.config_manager = config_manager
        self.logger.info("Initialized ModelStorageHandler")
    
    
    def get_storage_path(self, model_name: str = None, date_str: str = None) -> str:
        """
        Get the storage path for models with flat file organization
        
        Args:
            model_name: Name of the model type (optional, kept for compatibility)
            date_str: Date string in DDMMYYYY format (optional, kept for compatibility)
            
        Returns:
            Path to the storage directory
        """
        # Get the absolute path to this file (model_storage.py)
        current_file_path = os.path.abspath(__file__)
        
        # Navigate to project root: src/models/model_storage.py -> src/models -> src -> project_root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
        
        # Build the models/models_info path relative to project root (flat structure)
        storage_path = os.path.join(project_root, "models", "models_info")
        
        self.logger.debug(f"Storage path: {storage_path}")
            
        # Check if folder exists, create if it doesn't
        if not os.path.exists(storage_path):
            os.makedirs(storage_path, exist_ok=True)
            self.logger.info(f"Created model storage directory: {storage_path}")
        
        return storage_path
   
    
    def get_model_filename(self, model_name: str, metric_name: str, date_str: Optional[str] = None, file_type: str = MODEL_FILE_TYPE) -> Tuple[str, str]:
        """
        Get the filename for a saved model with date-based naming
        
        Args:
            model_name: Name of the model type
            metric_name: Name of the metric
            date_str: Date string in DDMMYYYY format (optional, defaults to current date)
            file_type: Type of file (MODEL_FILE_TYPE or PARAMS_FILE_TYPE)
            
        Returns:
            Full path to the model file
        """
        # Use current date if not provided
        current_date = date_str if date_str is not None else datetime.now().strftime("%d%m%Y")

        storage_path = self.get_storage_path(model_name, current_date)
        
        # Create filename with pattern: ddmmyyyy_<metric-name>.MODEL.pkl or ddmmyyyy_<metric-name>.PARAMS.pkl
        filename = f"{current_date}_{metric_name}.{file_type}.pkl"
        latest_filename = f"latest_{metric_name}.{file_type}.pkl"
        
        return os.path.join(storage_path, filename), os.path.join(storage_path, latest_filename)
    
    
    def save_model(self, model_name: str, metric_name: str, training_results: Any) -> bool:
        """
        Save a trained model to disk
        
        Args:
            model_name: Name of the model type
            metric_name: Name of the metric
            training_results: Dictionary containing training results
            
        Returns:
            True if successful, False otherwise
        """
        try:
            model = training_results['model']
            
            # Get the filename for saving the model
            date_model_filename, latest_model_filename = self.get_model_filename(model_name, metric_name, file_type=self.MODEL_FILE_TYPE)
            
            # Save the model using pickle
            with open(date_model_filename, 'wb') as f:
                pickle.dump(model, f)
            
            with open(latest_model_filename, 'wb') as f:
                pickle.dump(params_data, f)
            
            # Create params data without the model and DataFrame to avoid duplication
            params_data = {
                "capacity": training_results.get("capacity"),
                "training_duration_seconds": training_results.get("training_duration_seconds"),
                "data_points": training_results.get("data_points"),
                "trained_at": training_results.get("trained_at"),
                "model_type": training_results.get("model_type"),
                "metric_name": training_results.get("metric_name"),
                "model_filename": model_filename  # Reference to the saved model file
            }
            
            # Save training params (without model and DataFrame)
            date_params_filename, latest_params_filename = self.get_model_filename(model_name, metric_name, file_type=self.PARAMS_FILE_TYPE)
            with open(date_params_filename, 'wb') as f:
                pickle.dump(params_data, f)

            # save this model as the latest model for this metric as well.                
            with open(latest_params_filename, 'wb') as f:
                pickle.dump(params_data, f)
                
            
            self.logger.info(f"Successfully saved model {model_name} for {metric_name} to {date_model_filename}")
            self.logger.info(f"Successfully saved training params to {date_params_filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving model {model_name} for {metric_name}: {e}")
            return False
    
    
    def load_model(self, model_name: str, metric_name: str, date_str: Optional[str] = None) -> Optional[Any]:
        """
        Load a trained model from disk
        
        Args:
            model_name: Name of the model type
            metric_name: Name of the metric
            date_str: Date string in DDMMYYYY format (optional, defaults to current date)
            
        Returns:
            The loaded model object or None if loading fails
        """
        try:
            # Get the filename for loading the model
            print("\t\t ***** step 1")
            filename, latest_model_filename = self.get_model_filename(model_name, metric_name, date_str, file_type=self.MODEL_FILE_TYPE)
            print("\t\t ***** step 2")
            
            # Check if file exists, else load the last model generated
            if not os.path.exists(filename):
                self.logger.warning(f"Model file not found: {filename}")
                
                if not os.path.exists(latest_model_filename):
                    return None
                
                self.logger.warning(f"Loading latest model for {metric_name} from {latest_model_filename}")                
                with open(latest_model_filename, 'rb') as f:
                    model = pickle.load(f)                
            else:            
                # Load the model using pickle
                with open(filename, 'rb') as f:
                    model = pickle.load(f)
            
            self.logger.info(f"Successfully loaded model {model_name} for {metric_name} from {filename}")
            return model
            
        except Exception as e:
            self.logger.error(f"Error loading model {model_name} for {metric_name}: {e}")
            return None
    
    
    def load_training_params(self, model_name: str, metric_name: str, date_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Load training parameters from disk
        
        Args:
            model_name: Name of the model type
            metric_name: Name of the metric
            date_str: Date string in DDMMYYYY format (optional, defaults to current date)
            
        Returns:
            Dictionary containing training parameters or None if loading fails
        """
        try:
            # Get the filename for loading the params
            params_filename, latest_params_filename = self.get_model_filename(model_name, metric_name, date_str, file_type=self.PARAMS_FILE_TYPE)
            
            # Check if file exists, else load the last training params generated
            if not os.path.exists(params_filename):
                self.logger.warning(f"Training params file not found: {params_filename}")
                
                if not os.path.exists(latest_params_filename):
                    return None
                
                self.logger.warning(f"Loading latest training params for {metric_name} from {latest_params_filename}")
                with open(latest_params_filename, 'rb') as f:
                    params = pickle.load(f)
            else:
                # Load the params using pickle
                with open(params_filename, 'rb') as f:
                    params = pickle.load(f)
                        
            self.logger.info(f"Successfully loaded training params for {model_name} - {metric_name} from {params_filename}")
            return params
            
        except Exception as e:
            self.logger.error(f"Error loading training params for {model_name} - {metric_name}: {e}")
            return None
    
    
    def load_model_with_params(self, model_name: str, metric_name: str, date_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Load both model and training parameters from disk
        
        Args:
            model_name: Name of the model type
            metric_name: Name of the metric
            date_str: Date string in DDMMYYYY format (optional, defaults to current date)
            
        Returns:
            Dictionary containing both model and parameters, or None if loading fails
        """
        try:
            # Load the model
            model = self.load_model(model_name, metric_name, date_str)
            if model is None:
                return None
            
            # Load the training parameters
            params = self.load_training_params(model_name, metric_name, date_str)
            if params is None:
                return None
            
            # Combine model and parameters
            model_with_params = {
                "model": model,
                "capacity": params.get("capacity"),
                "training_duration_seconds": params.get("training_duration_seconds"),
                "data_points": params.get("data_points"),
                "trained_at": params.get("trained_at"),
                "model_type": params.get("model_type"),
                "metric_name": params.get("metric_name"),
                "capacity": params.get("capacity"),
                "max_value": params.get("max_value"),
                "min_value": params.get("min_value"),
                "model_filename": params.get("model_filename")
            }
            
            self.logger.info(f"Successfully loaded model and parameters for {model_name} - {metric_name}")
            return model_with_params
            
        except Exception as e:
            self.logger.error(f"Error loading model and parameters for {model_name} - {metric_name}: {e}")
            return None
    
    
    def list_saved_models(self, model_name: str = None) -> Dict[str, list]:
        """
        List all saved models in the storage directory
        
        Args:
            model_name: Optional model name to filter by
            
        Returns:
            Dictionary with model names as keys and lists of saved dates as values
        """
        try:
            saved_models = {}
            base_path = self.get_storage_path()
            
            if not os.path.exists(base_path):
                return saved_models
            
            # Get all .pkl files in the flat directory
            import glob
            pattern = os.path.join(base_path, "*.pkl")
            files = glob.glob(pattern)
            
            for file_path in files:
                filename = os.path.basename(file_path)
                # Parse filename: ddmmyyyy_<metric-name>.MODEL.pkl or ddmmyyyy_<metric-name>.PARAMS.pkl
                if "_" in filename and "." in filename:
                    parts = filename.split("_", 1)
                    if len(parts) == 2:
                        date_str = parts[0]
                        metric_and_type = parts[1]
                        
                        # Extract metric name and file type
                        if ".MODEL.pkl" in metric_and_type:
                            metric_name = metric_and_type.replace(".MODEL.pkl", "")
                            file_type = "MODEL"
                        elif ".PARAMS.pkl" in metric_and_type:
                            metric_name = metric_and_type.replace(".PARAMS.pkl", "")
                            file_type = "PARAMS"
                        else:
                            continue
                        
                        # Group by metric name and collect dates
                        if metric_name not in saved_models:
                            saved_models[metric_name] = []
                        if date_str not in saved_models[metric_name]:
                            saved_models[metric_name].append(date_str)
            
            # Sort dates for each metric
            for metric_name in saved_models:
                saved_models[metric_name] = sorted(saved_models[metric_name])
            
            return saved_models
            
        except Exception as e:
            self.logger.error(f"Error listing saved models: {e}")
            return {}
    
    
    def delete_model(self, model_name: str, metric_name: str, date_str: Optional[str] = None) -> bool:
        """
        Delete a saved model and its results
        
        Args:
            model_name: Name of the model type
            metric_name: Name of the metric
            date_str: Date string in DDMMYYYY format (optional, defaults to current date)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            model_filename, latest_model_filename = self.get_model_filename(model_name, metric_name, date_str, file_type=self.MODEL_FILE_TYPE)
            params_filename, latest_params_filename = self.get_model_filename(model_name, metric_name, date_str, file_type=self.PARAMS_FILE_TYPE)
            
            deleted_files = []
            
            # Delete model file
            if os.path.exists(model_filename):
                os.remove(model_filename)
                deleted_files.append(model_filename)
            
            # Delete params file
            if os.path.exists(params_filename):
                os.remove(params_filename)
                deleted_files.append(params_filename)
            
            if deleted_files:
                self.logger.info(f"Successfully deleted files: {deleted_files}")
                return True
            else:
                self.logger.warning(f"No files found to delete for {model_name} - {metric_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error deleting model {model_name} for {metric_name}: {e}")
            return False
