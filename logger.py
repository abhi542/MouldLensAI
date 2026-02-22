import logging
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger
import os

def setup_logger(name="mouldlens"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Don't add multiple handlers if already set up
    if not logger.handlers:
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        # StreamHandler (Console)
        stream_handler = logging.StreamHandler()
        
        # RotatingFileHandler (Max 5MB per file, keep 3 backups)
        file_handler = RotatingFileHandler(
            "logs/mouldlens.log", maxBytes=5*1024*1024, backupCount=3
        )
        
        # JSON Formatter
        format_str = '%(asctime)s %(levelname)s %(name)s %(message)s'
        formatter = jsonlogger.JsonFormatter(format_str)
        
        stream_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        logger.addHandler(stream_handler)
        logger.addHandler(file_handler)
        
    return logger

logger = setup_logger()
