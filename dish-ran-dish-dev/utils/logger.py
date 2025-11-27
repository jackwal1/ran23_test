import logging
from datetime import datetime
import pytz

ist_timezone = pytz.timezone("Asia/Kolkata")
timestamp_ist = datetime.now(pytz.UTC).astimezone(ist_timezone)

class SimpleLogger:
    def __init__(self):
        # Use a specific logger instance
        self.logger = logging.getLogger("SimpleLogger")
        
        # Avoid adding handlers if they already exist
        if not self.logger.handlers:
            self.logger.setLevel(logging.DEBUG)  # Capture all log levels

            # Create a console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)  # Set handler level to capture all logs

            # Set log format
            formatter = logging.Formatter(
                fmt="%(asctime)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            console_handler.setFormatter(formatter)

            # Add the handler to the logger
            self.logger.addHandler(console_handler)

    def log(self, message: str):
        # Handle log levels based on keywords in the message
        if "error" in message.lower():
            self.logger.error(message)
        elif "warn" in message.lower():
            self.logger.warning(message)
        elif "info" in message.lower():
            self.logger.info(message)
        elif "debug" in message.lower():
            self.logger.debug(message)
        else:
            self.logger.info(message)  # Default to INFO level for unmatched cases

# Example usage
logger = SimpleLogger()