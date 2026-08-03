import logging
import sys
from pathlib import Path

# Create logs directory if it doesn't exist
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Configure logging format
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def setup_logging():
    """Setup logging configuration for all bots"""
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=[
            # Console handler
            logging.StreamHandler(sys.stdout),
            # File handler for all logs
            logging.FileHandler(log_dir / "bot.log", encoding='utf-8')
        ]
    )
    
    # Add separate error file handler
    error_handler = logging.FileHandler(log_dir / "errors.log", encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    logging.getLogger().addHandler(error_handler)
    
    # Set specific logger levels
    logging.getLogger('aiogram').setLevel(logging.INFO)
    logging.getLogger('aiogram.event').setLevel(logging.INFO)
    
    return logging.getLogger(__name__)

def get_logger(name: str):
    """Get a specific logger with proper configuration"""
    return logging.getLogger(name)

# Initialize logging when module is imported
main_logger = setup_logging()
