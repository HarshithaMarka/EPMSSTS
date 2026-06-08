"""
Logging configuration for STT service

Structured JSON logging for production observability
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict


class StructuredJsonFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs.
    
    Includes all relevant context for observability:
    - Request ID
    - Service name
    - Error details
    - Performance metrics
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        
        log_dict = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Include exception info if present
        if record.exc_info:
            log_dict["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }
        
        # Include custom attributes from LogRecord
        if hasattr(record, 'request_id'):
            log_dict["request_id"] = record.request_id
        
        if hasattr(record, 'service'):
            log_dict["service"] = record.service
        
        if hasattr(record, 'metrics'):
            log_dict["metrics"] = record.metrics
        
        if hasattr(record, 'device'):
            log_dict["device"] = record.device
        
        if hasattr(record, 'model'):
            log_dict["model"] = record.model
        
        # Include all other extra fields
        for key, value in record.__dict__.items():
            if key not in [
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'message', 'pathname', 'process', 'processName',
                'relativeCreated', 'thread', 'threadName', 'exc_info',
                'exc_text', 'stack_info', 'taskName',
                'request_id', 'service', 'metrics', 'device', 'model',
            ]:
                if not key.startswith('_'):
                    log_dict[key] = self._serialize_value(value)
        
        return json.dumps(log_dict)
    
    def _serialize_value(self, value: Any) -> Any:
        """Serialize value to JSON-safe format"""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]
        return str(value)


def configure_logging(
    service_name: str = "stt",
    log_level: str = "INFO",
    log_file: str = None,
) -> logging.Logger:
    """
    Configure logging for STT service.
    
    Args:
        service_name: Name of service for logs
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for file logging
        
    Returns:
        Configured logger
    """
    
    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = StructuredJsonFormatter()
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Suppress noisy internal loggers
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    logging.getLogger("torch").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    
    return logger


class StructuredLogger:
    """
    Helper class for structured logging with context.
    
    Usage:
        slog = StructuredLogger(logger, request_id="xyz")
        slog.info("Message", device="cuda", latency_ms=123.4)
    """
    
    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
    
    def _log(self, level: int, message: str, **extras):
        """Log with context"""
        record = self.logger.makeRecord(
            name=self.logger.name,
            level=level,
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        
        # Add context
        for key, value in self.context.items():
            setattr(record, key, value)
        
        # Add extras
        for key, value in extras.items():
            setattr(record, key, value)
        
        self.logger.handle(record)
    
    def debug(self, message: str, **extras):
        self._log(logging.DEBUG, message, **extras)
    
    def info(self, message: str, **extras):
        self._log(logging.INFO, message, **extras)
    
    def warning(self, message: str, **extras):
        self._log(logging.WARNING, message, **extras)
    
    def error(self, message: str, **extras):
        self._log(logging.ERROR, message, **extras)
    
    def critical(self, message: str, **extras):
        self._log(logging.CRITICAL, message, **extras)
