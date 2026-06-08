"""
Waveform Validator

Validates synthesized audio quality to ensure:
- Audio is not silent
- Audio has reasonable duration
- Audio is not corrupted
- Audio does not contain pure tones
- Audio is not clipped
"""

import logging
import numpy as np
from typing import Tuple, List
from pathlib import Path

from .schemas import WaveformQualityMetrics
from .exceptions import (
    AudioDurationTooShortError,
    AudioFileSizeTooSmallError,
    SilentAudioDetectedError,
    AudioClippingDetectedError,
    PureToneDetectedError,
    CorruptedWaveformError,
)


logger = logging.getLogger(__name__)


class WaveformValidator:
    """
    Validates synthesized audio waveforms.
    
    Checks:
    1. Duration: > 0.1s (not too short)
    2. RMS amplitude: > threshold (not silent)
    3. Peak amplitude: < 0.99 (not clipped)
    4. Spectral flatness: In normal range (not pure tone, not noise)
    5. File size: > minimum kb (not corrupted)
    
    Usage:
        validator = WaveformValidator()
        metrics = validator.validate(audio_array, sample_rate)
        if not metrics.is_valid:
            # Handle invalid audio
    """
    
    def __init__(
        self,
        min_duration_seconds: float = 0.1,
        min_rms_amplitude: float = 0.01,
        max_peak_amplitude: float = 0.99,
        min_spectral_flatness: float = 0.05,
        max_spectral_flatness: float = 0.6,
        min_file_size_kb: float = 5.0,
    ):
        """
        Initialize waveform validator.
        
        Args:
            min_duration_seconds: Minimum acceptable duration
            min_rms_amplitude: Minimum RMS (below = likely silent)
            max_peak_amplitude: Max peak (above = clipping)
            min_spectral_flatness: Min flatness (below = pure tone)
            max_spectral_flatness: Max flatness (above = noise)
            min_file_size_kb: Minimum file size
        """
        self.min_duration_seconds = min_duration_seconds
        self.min_rms_amplitude = min_rms_amplitude
        self.max_peak_amplitude = max_peak_amplitude
        self.min_spectral_flatness = min_spectral_flatness
        self.max_spectral_flatness = max_spectral_flatness
        self.min_file_size_kb = min_file_size_kb
        
        logger.info(f"Waveform validator initialized with thresholds: "
                   f"min_duration={min_duration_seconds}s, "
                   f"min_rms={min_rms_amplitude}, "
                   f"max_peak={max_peak_amplitude}")
    
    def validate(
        self,
        audio_array: np.ndarray,
        sample_rate: int,
        file_path: Path = None
    ) -> WaveformQualityMetrics:
        """
        Validate audio waveform quality.
        
        Args:
            audio_array: Audio samples (numpy array)
            sample_rate: Sample rate (Hz)
            file_path: Optional file path for size check
        
        Returns:
            WaveformQualityMetrics with validation results
        """
        errors: List[str] = []
        
        # Check 1: Duration
        duration_seconds = len(audio_array) / sample_rate
        if duration_seconds < self.min_duration_seconds:
            errors.append(f"Duration {duration_seconds:.3f}s < {self.min_duration_seconds}s")
        
        # Check 2: RMS amplitude (silence detection)
        rms_amplitude = self._calculate_rms(audio_array)
        if rms_amplitude < self.min_rms_amplitude:
            errors.append(f"RMS {rms_amplitude:.4f} < {self.min_rms_amplitude} (likely silent)")
        
        # Check 3: Peak amplitude (clipping detection)
        peak_amplitude = np.max(np.abs(audio_array))
        is_clipping = peak_amplitude > self.max_peak_amplitude
        if is_clipping:
            errors.append(f"Peak amplitude {peak_amplitude:.3f} > {self.max_peak_amplitude} (clipping)")
        
        # Check 4: Spectral flatness (pure tone / noise detection)
        spectral_flatness = self._calculate_spectral_flatness(audio_array)
        if spectral_flatness < self.min_spectral_flatness:
            errors.append(f"Spectral flatness {spectral_flatness:.3f} < {self.min_spectral_flatness} (pure tone)")
        elif spectral_flatness > self.max_spectral_flatness:
            errors.append(f"Spectral flatness {spectral_flatness:.3f} > {self.max_spectral_flatness} (noise)")
        
        # Check 5: File size (if file path provided)
        file_size_kb = 0.0
        if file_path and file_path.exists():
            file_size_kb = file_path.stat().st_size / 1024
            if file_size_kb < self.min_file_size_kb:
                errors.append(f"File size {file_size_kb:.1f}KB < {self.min_file_size_kb}KB")
        
        # Determine overall validity
        is_valid = len(errors) == 0
        
        metrics = WaveformQualityMetrics(
            duration_seconds=duration_seconds,
            file_size_kb=file_size_kb,
            rms_amplitude=rms_amplitude,
            peak_amplitude=peak_amplitude,
            is_clipping=is_clipping,
            spectral_flatness=spectral_flatness,
            is_valid=is_valid,
            validation_errors=errors
        )
        
        if not is_valid:
            logger.warning(f"Waveform validation failed: {errors}")
        else:
            logger.debug(f"Waveform validation passed: duration={duration_seconds:.2f}s, "
                        f"rms={rms_amplitude:.4f}, peak={peak_amplitude:.3f}, "
                        f"flatness={spectral_flatness:.3f}")
        
        return metrics
    
    def validate_and_raise(
        self,
        audio_array: np.ndarray,
        sample_rate: int,
        file_path: Path = None
    ) -> WaveformQualityMetrics:
        """
        Validate audio and raise exception if invalid.
        
        Args:
            audio_array: Audio samples
            sample_rate: Sample rate
            file_path: Optional file path
        
        Returns:
            WaveformQualityMetrics if valid
        
        Raises:
            AudioDurationTooShortError: If duration too short
            SilentAudioDetectedError: If audio is silent
            AudioClippingDetectedError: If clipping detected
            PureToneDetectedError: If pure tone detected
            AudioFileSizeTooSmallError: If file size too small
            CorruptedWaveformError: If other validation failure
        """
        metrics = self.validate(audio_array, sample_rate, file_path)
        
        if not metrics.is_valid:
            # Determine specific error type
            if metrics.duration_seconds < self.min_duration_seconds:
                raise AudioDurationTooShortError(
                    f"Audio duration {metrics.duration_seconds:.2f}s too short",
                    details={"duration": metrics.duration_seconds, "min_duration": self.min_duration_seconds}
                )
            
            if metrics.rms_amplitude < self.min_rms_amplitude:
                raise SilentAudioDetectedError(
                    f"Audio RMS {metrics.rms_amplitude:.4f} below threshold (likely silent)",
                    details={"rms": metrics.rms_amplitude, "threshold": self.min_rms_amplitude}
                )
            
            if metrics.is_clipping:
                raise AudioClippingDetectedError(
                    f"Audio clipping detected (peak={metrics.peak_amplitude:.3f})",
                    details={"peak": metrics.peak_amplitude, "threshold": self.max_peak_amplitude}
                )
            
            if metrics.spectral_flatness < self.min_spectral_flatness:
                raise PureToneDetectedError(
                    f"Pure tone detected (spectral_flatness={metrics.spectral_flatness:.3f})",
                    details={"flatness": metrics.spectral_flatness, "min_flatness": self.min_spectral_flatness}
                )
            
            if metrics.file_size_kb > 0 and metrics.file_size_kb < self.min_file_size_kb:
                raise AudioFileSizeTooSmallError(
                    f"Audio file size {metrics.file_size_kb:.1f}KB too small",
                    details={"file_size_kb": metrics.file_size_kb, "min_size_kb": self.min_file_size_kb}
                )
            
            # Generic corruption error
            raise CorruptedWaveformError(
                f"Waveform validation failed: {metrics.validation_errors}",
                details={"errors": metrics.validation_errors}
            )
        
        return metrics
    
    def _calculate_rms(self, audio_array: np.ndarray) -> float:
        """
        Calculate RMS (Root Mean Square) amplitude.
        
        RMS is a measure of average signal energy.
        Low RMS indicates silence or very quiet audio.
        
        Args:
            audio_array: Audio samples
        
        Returns:
            RMS amplitude (0-1)
        """
        if len(audio_array) == 0:
            return 0.0
        return float(np.sqrt(np.mean(audio_array ** 2)))
    
    def _calculate_spectral_flatness(self, audio_array: np.ndarray) -> float:
        """
        Calculate spectral flatness (Wiener entropy).
        
        Spectral flatness measures how noise-like vs tone-like a signal is:
        - 0.0: Pure tone (single frequency)
        - 1.0: White noise (all frequencies equally)
        - 0.1-0.4: Typical speech range
        
        Args:
            audio_array: Audio samples
        
        Returns:
            Spectral flatness (0-1)
        """
        try:
            # Compute FFT magnitude spectrum
            fft = np.fft.rfft(audio_array)
            magnitude = np.abs(fft)
            
            # Avoid log(0) issues
            magnitude = magnitude + 1e-10
            
            # Geometric mean
            geometric_mean = np.exp(np.mean(np.log(magnitude)))
            
            # Arithmetic mean
            arithmetic_mean = np.mean(magnitude)
            
            # Spectral flatness = geometric mean / arithmetic mean
            flatness = geometric_mean / (arithmetic_mean + 1e-10)
            
            return float(flatness)
        
        except Exception as e:
            logger.warning(f"Spectral flatness calculation failed: {e}")
            return 0.5  # Default to middle value
    
    def get_validation_stats(self) -> dict:
        """Get validation statistics"""
        return {
            "min_duration_seconds": self.min_duration_seconds,
            "min_rms_amplitude": self.min_rms_amplitude,
            "max_peak_amplitude": self.max_peak_amplitude,
            "min_spectral_flatness": self.min_spectral_flatness,
            "max_spectral_flatness": self.max_spectral_flatness,
            "min_file_size_kb": self.min_file_size_kb,
        }
