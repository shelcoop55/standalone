import logging
import sys

def configure_logging():
    """
    Configures the root logger for the application.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger with the specified name.
    """
    return logging.getLogger(name)
