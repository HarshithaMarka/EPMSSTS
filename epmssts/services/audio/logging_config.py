"""
Structured logging configuration for Audio Preprocessing Service.

JSON-formatted logs with request context for observability.
"""

import json
import logging
from typing import Optional, Any, Dict
from datetime import datetime
import traceback


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add request context if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "latency_ms"):
            log_data["latency_ms"] = record.latency_ms
        if hasattr(record, "reason_code"):
            log_data["reason_code"] = record.reason_code
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        return json.dumps(log_data, default=str)


class StructuredLogger:
    """Structured logger with request context management."""
    
    def __init__(self, name: str = __name__):
        """Initialize structured logger."""
        self.logger = logging.getLogger(name)
        self.context: Dict[str, Any] = {}
        
        # Configure handler if not already configured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(StructuredFormatter())
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def set_context(self, request_id: str, **kwargs):
        """Set logging context for a request."""
        self.context = {
            "request_id": request_id,
            **kwargs
        }
    
    def clear_context(self):
        """Clear logging context."""
        self.context = {}
    
    def _add_context(self, record: Dict[str, Any]):
        """Add context to log record."""
        for key, value in self.context.items():
            if key not in record:
                record[key] = value
    
    def info(self, message: str, **kwargs):
        """Log info level message with context."""
        record = {**kwargs}
        self._add_context(record)
        extra = {"extra": record} if record else {}
        self.logger.info(message, extra=extra)
    
    def warning(self, message: str, **kwargs):
        """Log warning level message with context."""
        record = {**kwargs}
        self._add_context(record)
        extra = {"extra": record} if record else {}
        self.logger.warning(message, extra=extra)
    
    def error(self, message: str, exc: Optional[Exception] = None, **kwargs):
        """Log error level message with context."""
        record = {**kwargs}
        self._add_context(record)
        extra = {"extra": record} if record else {}
        
        if exc:
            self.logger.error(
                message,
                exc_info=exc,
                extra=extra
            )
        else:
            self.logger.error(message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        """Log debug level message with context."""
        record = {**kwargs}
        self._add_context(record)
        extra = {"extra": record} if record else {}
        self.logger.debug(message, extra=extra)


def get_logger(name: str) -> StructuredLogger:
    """Factory function to get structured logger instance."""
    return StructuredLogger(name)
