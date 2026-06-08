"""
Input validators for Audio Preprocessing Service.

Comprehensive validation before audio processing begins.
"""

import os
from pathlib import Path
from typing import Tuple, Optional
import soundfile as sf

from .exceptions import (
    UnsupportedFormatError,
    FileSizeError,
    CorruptFileError,
    DurationError,
)
from .logging_config import get_logger

logger = get_logger(__name__)

# Configuration
SUPPORTED_FORMATS = {".wav", ".mp3", ".flac", ".m4a"}
MAX_FILE_SIZE_BYTES = 10_000_000  # 10MB
MIN_DURATION_SECONDS = 1.5
MAX_DURATION_SECONDS = 60.0


class AudioValidator:
    """Validates audio files before processing."""
    
    def __init__(
        self,
        max_file_size: int = MAX_FILE_SIZE_BYTES,
        min_duration: float = MIN_DURATION_SECONDS,
        max_duration: float = MAX_DURATION_SECONDS,
    ):
        """Initialize audio validator with thresholds."""
        self.max_file_size = max_file_size
        self.min_duration = min_duration
        self.max_duration = max_duration
    
    def validate(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate audio file comprehensively.
        
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            # Check file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Check format
            self._validate_format(file_path)
            
            # Check file size
            self._validate_file_size(file_path)
            
            # Check file is not empty
            self._validate_file_not_empty(file_path)
            
            # Check duration
            self._validate_duration(file_path)
            
            logger.info("Validation passed", file_path=file_path)
            return True, None
        
        except Exception as e:
            error_msg = str(e)
            logger.warning("Validation failed", file_path=file_path, error=error_msg)
            return False, error_msg
    
    def _validate_format(self, file_path: str):
        """Validate file format is supported."""
        ext = Path(file_path).suffix.lower()
        
        if ext not in SUPPORTED_FORMATS:
            raise UnsupportedFormatError(
                ext,
                details={"supported": list(SUPPORTED_FORMATS)}
            )
    
    def _validate_file_size(self, file_path: str):
        """Validate file size is within limits."""
        size_bytes = os.path.getsize(file_path)
        
        if size_bytes == 0:
            raise FileSizeError(0, self.max_file_size)
        
        if size_bytes > self.max_file_size:
            raise FileSizeError(size_bytes, self.max_file_size)
    
    def _validate_file_not_empty(self, file_path: str):
        """Quick check that file has audio content."""
        try:
            data, sr = sf.read(file_path, dtype='float32', frames=1024)
            if len(data) == 0:
                raise CorruptFileError(
                    "File contains no audio frames",
                    details={"file_path": file_path}
                )
        except Exception as e:
            if isinstance(e, CorruptFileError):
                raise
            raise CorruptFileError(
                f"Cannot read audio file: {str(e)}",
                details={"file_path": file_path}
            )
    
    def _validate_duration(self, file_path: str):
        """Validate audio duration is within limits."""
        try:
            # Use soundfile to get duration
            with sf.SoundFile(file_path) as f:
                frames = f.frames
                sample_rate = f.samplerate
                duration = frames / sample_rate
            
            if duration < self.min_duration:
                raise DurationError(duration, self.min_duration, self.max_duration)
            
            if duration > self.max_duration:
                raise DurationError(duration, self.min_duration, self.max_duration)
        
        except Exception as e:
            if hasattr(e, 'reason_code'):
                raise
            raise CorruptFileError(
                f"Cannot determine duration: {str(e)}",
                details={"file_path": file_path}
            )

