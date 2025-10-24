from typing import Any, List, Tuple
import datetime
from datetime import timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commons.logger_setup import LoggerSetup
from config.config_manager import ConfigManager

class CommonsUtils:
    logger: Any
    config_manager: ConfigManager

    def __init__(
        self,
        config_manager: ConfigManager,
    ) -> None:
        self.logger = LoggerSetup.get_logger()
        self.logger.info(f"Initialized CommonsUtils ")
        self.config_manager = config_manager
        
    def chunk_time_slices(self,
        start: datetime.datetime, end: datetime.datetime, window_size: timedelta
    ) -> List[Tuple[datetime.datetime, datetime.datetime]]:
        """
        Break a datetime interval into chunks of specified window size.

        Args:
            start (datetime): Start of the interval
            end (datetime): End of the interval
            window_size (timedelta): Size of each chunk

        Returns:
            List[Tuple[datetime, datetime]]: List of (chunk_start, chunk_end) tuples

        Example:
            >>> from datetime import datetime, timedelta
            >>> start = datetime(2024, 1, 1, 0, 0)
            >>> end = datetime(2024, 1, 1, 4, 30)
            >>> chunks = chunk_datetime_interval(start, end, timedelta(hours=1))
            >>> for chunk_start, chunk_end in chunks:
            ...     print(f"{chunk_start} - {chunk_end}")
        """
        self.logger.debug(f"Chunking time slices from {start} to {end} with window {window_size}")
        if end <= start:
            self.logger.error("End datetime must be after start datetime")
            raise ValueError("End datetime must be after start datetime")

        if window_size <= timedelta(0):
            self.logger.error("Window size must be positive")
            raise ValueError("Window size must be positive")

        chunks = []
        chunk_start = start

        while chunk_start < end:
            # Calculate the end of this chunk
            chunk_end = min(chunk_start + window_size, end)
            chunks.append((chunk_start, chunk_end))
            chunk_start = chunk_end

        self.logger.debug(f"Created {len(chunks)} time chunks.")
        return chunks


if __name__ == "__main__":
    cu = CommonsUtils(ConfigManager("../../configs/config.yaml"))
    cu.chunk_time_slices(datetime.datetime(2024, 1, 1, 0, 0), datetime.datetime(2025, 1, 1, 4, 30), timedelta(hours=1))
