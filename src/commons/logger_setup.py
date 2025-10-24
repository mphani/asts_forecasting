import logging
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class LoggerSetup:
    """
    A utility class to set up and manage logging across the application.
    Implements the singleton pattern to ensure only one logger instance exists.
    """

    _instance = None
    _logger = None
    _log_level = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggerSetup, cls).__new__(cls)
            cls._setup_logger()
        return cls._instance

    @classmethod
    def _setup_logger(cls):
        """Set up the logger with both file and console handlers."""
        cls._logger = logging.getLogger("time_seer")
        if cls._log_level is None:
            cls._log_level = logging.DEBUG
        cls._logger.setLevel(cls._log_level)

        # Prevent adding handlers multiple times
        if not cls._logger.handlers:
            # --- Example: file handler setup (uncomment and use if needed) ---
            # from pathlib import Path
            # log_dir = Path('logs')
            # log_dir.mkdir(exist_ok=True)
            # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # file_handler = logging.FileHandler(f'logs/app_{timestamp}.log', encoding='utf-8')
            # file_handler.setLevel(cls._log_level)
            # file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
            # file_handler.setFormatter(file_formatter)
            # cls._logger.addHandler(file_handler)
            # --- End example ---

            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(cls._log_level)
            console_formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
            )
            console_handler.setFormatter(console_formatter)
            cls._logger.addHandler(console_handler)
        cls._initialized = True

    @classmethod
    def get_logger(cls):
        """Get the shared logger instance."""
        if cls._logger is None or not cls._initialized:
            cls._setup_logger()
        return cls._logger

    @classmethod
    def set_log_level(cls, level: str):
        """Dynamically update the log level at runtime."""
        cls._log_level = getattr(logging, level.upper(), logging.DEBUG)
        if cls._logger is not None:
            cls._logger.setLevel(cls._log_level)
            for handler in cls._logger.handlers:
                handler.setLevel(cls._log_level)
        else:
            cls._setup_logger()

    @classmethod
    def initialize(cls, level: str = None):
        """Explicitly initialize the logger with a given log level."""
        if level is not None:
            cls.set_log_level(level)
        else:
            cls._setup_logger()
