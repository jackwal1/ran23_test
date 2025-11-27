# File path: logging_control.py

from utils import constants as CONST
import logging

# Default log level if not set or invalid
default_log_level = logging.INFO
log_level_str = CONST.LOG_LEVEL
print(f'LOG_LEVEL set to --> {log_level_str}')

# Mapping of string log levels to logging module levels
log_levels = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
log_level = log_levels.get(log_level_str, default_log_level)

# Define formats for each log level
log_formats = {
    logging.DEBUG: '%(asctime)s - %(levelname)s - RAN - %(filename)s - %(funcName)s - %(message)s',
    logging.INFO: '%(asctime)s - %(levelname)s - RAN - %(filename)s - %(funcName)s - %(message)s',
    logging.WARNING: '%(levelname)s - RAN - %(message)s',
    logging.ERROR: '%(asctime)s - %(levelname)s - RAN - %(filename)s - %(funcName)s - %(message)s',
    logging.CRITICAL: '%(asctime)s - %(levelname)s - RAN - %(filename)s - %(funcName)s - %(message)s',
}

# Select format based on the log level
log_format = log_formats.get(log_level, log_formats[default_log_level])

# Configure the logging module
logging.basicConfig(level=log_level, format=log_format)

# Optional: Create a logger instance
logger = logging.getLogger()


