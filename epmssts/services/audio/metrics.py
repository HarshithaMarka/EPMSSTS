"""
Signal metrics extraction for audio preprocessing.

Computes RMS, peak, SNR, spectral features, and pitch metrics.
"""

import numpy as np
from typing import Tuple, NamedTuple
from scipy import signal
from scipy.fftpack import fft
import librosa

from .schemas import SignalMetrics
from .logging_config import get_logger

logger = get_logger(__name__)


class MetricsExtractionParams(NamedTuple):
    """Parameters for metrics extraction."""
    n_fft: int = 2048
    hop_length: int = 512
    n_mels: int = 128
    fmin: float = 40.0
    fmax: float = 8000.0
    f0_min: float = 50.0
    f0_max: float = 500.0


class SignalMetricsExtractor:
    """Extracts signal metrics from audio waveform."""
    
    def __init__(self, params: MetricsExtractionParams = MetricsExtractionParams()):
        """Initialize metrics extractor."""
        self.params = params
    
    def extract(
        self,
        waveform: np.ndarray,
        sample_rate: int,
    ) -> SignalMetrics:
        """
        Extract all signal metrics from waveform.
        
        BEFORE normalization to capture true signal properties.
        
        Args:
            waveform: Audio waveform (float32, 1D)
            sample_rate: Sample rate in Hz
        
        Returns:
            SignalMetrics: Extracted metrics
        """
        try:
            # Compute RMS and peak
            rms_dbfs = self._compute_rms_dbfs(waveform)
            peak_dbfs = self._compute_peak_dbfs(waveform)
            
            # Estimate SNR
            snr_estimate = self._estimate_snr(waveform, sample_rate)
            
            # Spectral features
            spectral_centroid = self._compute_spectral_centroid(waveform, sample_rate)
            zero_crossing_rate = self._compute_zero_crossing_rate(waveform)
            energy_variance = self._compute_energy_variance(waveform, sample_rate)
            
            # Pitch features (using limited range for speech)
            pitch_mean, pitch_variance = self._compute_pitch_features(waveform, sample_rate)
            
            metrics = SignalMetrics(
                rms_dbfs=float(rms_dbfs),
                peak_dbfs=float(peak_dbfs),
                snr_estimate=float(snr_estimate),
                spectral_centroid=float(spectral_centroid),
                zero_crossing_rate=float(zero_crossing_rate),
                energy_variance=float(energy_variance),
                pitch_mean=float(pitch_mean),
                pitch_variance=float(pitch_variance),
            )
            
            logger.debug(
                "Metrics extraction successful",
                rms_dbfs=rms_dbfs,
                snr_estimate=snr_estimate,
                spectral_centroid=spectral_centroid
            )
            
            return metrics
        
        except Exception as e:
            logger.error("Metrics extraction failed", exc=e)
            raise
    
    def _compute_rms_dbfs(self, waveform: np.ndarray) -> float:
        """
        Compute RMS level in dBFS.
        
        dBFS = 20 * log10(RMS / 1.0)
        Reference level is 1.0 for float32 audio.
        """
        rms = np.sqrt(np.mean(waveform ** 2))
        
        # Prevent log(0)
        if rms < 1e-10:
            return -120.0
        
        dbfs = 20 * np.log10(rms)
        return np.clip(dbfs, -120.0, 0.0)
    
    def _compute_peak_dbfs(self, waveform: np.ndarray) -> float:
        """
        Compute peak level in dBFS.
        
        Peak dBFS = 20 * log10(max(abs(waveform)))
        """
        peak = np.max(np.abs(waveform))
        
        if peak < 1e-10:
            return -120.0
        
        dbfs = 20 * np.log10(peak)
        return np.clip(dbfs, -120.0, 1.0)  # Allow slight headroom
    
    def _estimate_snr(self, waveform: np.ndarray, sample_rate: int) -> float:
        """
        Estimate Signal-to-Noise Ratio.
        
        Uses spectral analysis to detect noise floor.
        SNR = 10 * log10(signal_power / noise_power)
        """
        try:
            # Compute spectrogram
            freqs, times, spectrogram = signal.spectrogram(
                waveform,
                fs=sample_rate,
                nperseg=self.params.n_fft,
                noverlap=self.params.n_fft // 2
            )
            
            # Power in dB
            power_db = 10 * np.log10(spectrogram + 1e-10)
            
            # Estimate noise as the minimum power across time
            noise_power = np.percentile(power_db, 5)
            signal_power = np.percentile(power_db, 95)
            
            snr = signal_power - noise_power
            return np.clip(snr, 0.0, 100.0)
        
        except Exception as e:
            logger.warning("SNR estimation failed, returning default", error=str(e))
            return 0.0
    
    def _compute_spectral_centroid(self, waveform: np.ndarray, sample_rate: int) -> float:
        """
        Compute spectral centroid in Hz.
        
        Centroid = sum(f * magnitude) / sum(magnitude)
        """
        try:
            centroid = librosa.feature.spectral_centroid(y=waveform, sr=sample_rate)[0]
            mean_centroid = np.mean(centroid)
            return np.clip(mean_centroid, 0.0, sample_rate / 2)
        except Exception as e:
            logger.warning("Spectral centroid computation failed", error=str(e))
            return 1000.0
    
    def _compute_zero_crossing_rate(self, waveform: np.ndarray) -> float:
        """
        Compute zero crossing rate (0-1).
        
        ZCR = number of zero crossings / total samples
        """
        try:
            zcr = librosa.feature.zero_crossing_rate(waveform)[0]
            mean_zcr = np.mean(zcr)
            return np.clip(mean_zcr, 0.0, 1.0)
        except Exception as e:
            logger.warning("ZCR computation failed", error=str(e))
            return 0.1
    
    def _compute_energy_variance(self, waveform: np.ndarray, sample_rate: int) -> float:
        """
        Compute energy variance across frames.
        
        Indicates consistency of energy levels (low for steady tone, high for varied speech).
        """
        try:
            # Frame-based energy
            frame_length = int(0.02 * sample_rate)  # 20ms frames
            hop_length = frame_length // 2
            
            frames = librosa.util.frame(waveform, frame_length, hop_length)
            energy = np.sum(frames ** 2, axis=0)
            
            # Variance of log energy
            log_energy = np.log10(energy + 1e-10)
            variance = np.var(log_energy)
            
            return float(variance)
        except Exception as e:
            logger.warning("Energy variance computation failed", error=str(e))
            return 0.5
    
    def _compute_pitch_features(
        self,
        waveform: np.ndarray,
        sample_rate: int
    ) -> Tuple[float, float]:
        """
        Compute pitch mean and variance.
        
        Uses piptrack for pitch detection in speech frequency range.
        Returns pitch in Hz (0 if unvoiced).
        """
        try:
            # Compute pitch using piptrack
            f0 = librosa.yin(
                waveform,
                fmin=self.params.f0_min,
                fmax=self.params.f0_max,
                sr=sample_rate
            )
            
            # Remove frames with no pitch (f0=0 or nan)
            voiced = f0[f0 > 0]
            
            if len(voiced) == 0:
                return 0.0, 0.0
            
            pitch_mean = np.mean(voiced)
            pitch_variance = np.var(voiced)
            
            return float(pitch_mean), float(pitch_variance)
        
        except Exception as e:
            logger.warning("Pitch estimation failed", error=str(e))
            return 0.0, 0.0
