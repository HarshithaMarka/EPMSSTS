"""
Signal processing pipeline for audio preprocessing.

Implements the exact processing order for audio cleaning and standardization.
"""

from dataclasses import dataclass
from typing import Tuple
import numpy as np
from scipy import signal
import librosa
from scipy.io import wavfile

from .schemas import EnergyBand
from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for signal processing pipeline."""
    
    # Resampling
    target_sample_rate: int = 16000
    
    # Filtering
    highpass_freq: float = 40.0  # Hz
    highpass_order: int = 5
    
    # VAD
    vad_threshold_db: float = -40.0
    vad_frame_ms: float = 20.0
    vad_min_duration_frames: int = 2
    
    # Normalization
    target_rms_by_band: dict = None
    max_gain_by_band: dict = None
    
    # Limiter
    limiter_threshold: float = -1.0  # dBFS
    limiter_release_ms: float = 100.0
    
    # Mel-spectrogram
    n_fft: int = 2048
    hop_length: int = 512
    n_mels: int = 128
    fmin: float = 40.0
    fmax: float = 8000.0
    
    def __post_init__(self):
        """Set defaults for band-based normalization."""
        if self.target_rms_by_band is None:
            self.target_rms_by_band = {
                EnergyBand.VERY_LOW: -24.0,
                EnergyBand.LOW: -22.0,
                EnergyBand.NORMAL: -20.0,
                EnergyBand.HIGH: -18.0,
            }
        
        if self.max_gain_by_band is None:
            self.max_gain_by_band = {
                EnergyBand.VERY_LOW: 6.0,
                EnergyBand.LOW: 10.0,
                EnergyBand.NORMAL: 12.0,
                EnergyBand.HIGH: 12.0,
            }


class SignalProcessingPipeline:
    """Implements signal processing pipeline in exact order."""
    
    def __init__(self, config: PipelineConfig = None):
        """Initialize pipeline with configuration."""
        self.config = config or PipelineConfig()
    
    def process(
        self,
        file_path: str,
    ) -> Tuple[np.ndarray, np.ndarray, EnergyBand, float]:
        """
        Process audio through complete pipeline.
        
        Pipeline order (critical):
        1. Decode to PCM float32
        2. Convert to mono
        3. Resample to 16kHz
        4. DC offset removal
        5. High-pass filter (40Hz)
        6. Silence trimming via VAD
        7. Compute metrics BEFORE normalization
        8. Classify energy band
        9. Adaptive RMS normalization
        10. Soft limiter
        11. Log-mel spectrogram extraction
        12. Feature standardization
        
        Args:
            file_path: Path to audio file (WAV, MP3, FLAC, M4A)
        
        Returns:
            Tuple[waveform, mel_spectrogram, energy_band, silence_ratio]
        """
        try:
            # 1. Decode to PCM float32 and mono
            waveform, sr = self._decode_and_mono(file_path)
            logger.debug("Decoded audio", shape=waveform.shape, sr=sr)
            
            # 2. Resample to target rate if needed
            if sr != self.config.target_sample_rate:
                waveform = librosa.resample(
                    waveform,
                    orig_sr=sr,
                    target_sr=self.config.target_sample_rate
                )
                sr = self.config.target_sample_rate
            logger.debug("Resampled", target_sr=sr)
            
            # 3. DC offset removal
            waveform = self._remove_dc_offset(waveform)
            
            # 4. High-pass filter
            waveform = self._apply_highpass_filter(waveform, sr)
            
            # 5. Silence trimming via VAD
            waveform, silence_ratio = self._trim_silence_vad(waveform, sr)
            logger.debug("Trimmed silence", ratio=silence_ratio)
            
            # 6. Classify energy band (BEFORE normalization!)
            rms_db = self._compute_rms_dbfs(waveform)
            energy_band = self._classify_energy_band(rms_db)
            logger.debug("Energy band", band=energy_band.value, rms_db=rms_db)
            
            # 7. Adaptive RMS normalization
            waveform = self._normalize_adaptive(waveform, energy_band)
            
            # 8. Soft limiter (prevent clipping)
            waveform = self._apply_limiter(waveform)
            
            # 9. Log-mel spectrogram extraction
            mel_spec = self._compute_mel_spectrogram(waveform, sr)
            logger.debug("Computed mel-spec", shape=mel_spec.shape)
            
            # 10. Feature standardization
            mel_spec = self._standardize_features(mel_spec)
            
            logger.info(
                "Pipeline processing complete",
                waveform_shape=waveform.shape,
                mel_spec_shape=mel_spec.shape,
                energy_band=energy_band.value,
                silence_ratio=silence_ratio,
            )
            
            return waveform, mel_spec, energy_band, silence_ratio
        
        except Exception as e:
            logger.error("Pipeline processing failed", exc=e)
            raise
    
    def _decode_and_mono(self, file_path: str) -> Tuple[np.ndarray, int]:
        """Decode audio file to PCM float32 mono."""
        try:
            waveform, sr = librosa.load(file_path, sr=None, mono=True, dtype=np.float32)
            return waveform, sr
        except Exception as e:
            logger.error("Decode failed", file_path=file_path, exc=e)
            raise
    
    def _remove_dc_offset(self, waveform: np.ndarray) -> np.ndarray:
        """Remove DC offset from waveform."""
        return waveform - np.mean(waveform)
    
    def _apply_highpass_filter(self, waveform: np.ndarray, sr: int) -> np.ndarray:
        """Apply high-pass filter (cut < 40Hz)."""
        try:
            # Butterworth HP filter
            sos = signal.butter(
                self.config.highpass_order,
                self.config.highpass_freq,
                btype='high',
                fs=sr,
                output='sos'
            )
            return signal.sosfilt(sos, waveform).astype(np.float32)
        except Exception as e:
            logger.warning("Highpass filter failed, returning original", exc=e)
            return waveform
    
    def _trim_silence_vad(
        self,
        waveform: np.ndarray,
        sr: int
    ) -> Tuple[np.ndarray, float]:
        """Trim silence using Voice Activity Detection."""
        try:
            # Compute spectrogram
            S = librosa.stft(waveform)
            S_db = librosa.power_to_db(np.abs(S) ** 2, ref=np.max)
            
            # VAD: frames above threshold are voice
            threshold_db = self.config.vad_threshold_db
            voice_frames = np.mean(S_db, axis=0) > threshold_db
            
            # Morphological opening to remove noise
            voice_frames = signal.medfilt(voice_frames.astype(int), kernel_size=5) == 1
            
            # Find first and last voice frames
            voice_indices = np.where(voice_frames)[0]
            
            if len(voice_indices) == 0:
                # No voice detected, return original with high silence ratio
                return waveform, 1.0
            
            first_frame = voice_indices[0]
            last_frame = voice_indices[-1]
            
            # Convert frame indices to sample indices
            start_sample = max(0, librosa.frames_to_samples(first_frame, hop_length=self.config.hop_length))
            end_sample = min(len(waveform), librosa.frames_to_samples(last_frame + 1, hop_length=self.config.hop_length))
            
            # Trim
            trimmed = waveform[start_sample:end_sample]
            
            # Calculate silence ratio
            n_voice_frames = np.sum(voice_frames)
            silence_ratio = 1.0 - (n_voice_frames / len(voice_frames))
            
            return trimmed, float(np.clip(silence_ratio, 0.0, 1.0))
        
        except Exception as e:
            logger.warning("VAD failed, using energy-based trimming", exc=e)
            return self._trim_silence_energy(waveform, sr)
    
    def _trim_silence_energy(
        self,
        waveform: np.ndarray,
        sr: int
    ) -> Tuple[np.ndarray, float]:
        """Fallback: energy-based silence trimming."""
        try:
            trimmed, _ = librosa.effects.trim(
                waveform,
                top_db=40,
                ref=np.max
            )
            silence_ratio = 1.0 - (len(trimmed) / len(waveform))
            return trimmed, float(np.clip(silence_ratio, 0.0, 1.0))
        except Exception:
            return waveform, 0.0
    
    def _compute_rms_dbfs(self, waveform: np.ndarray) -> float:
        """Compute RMS in dBFS."""
        rms = np.sqrt(np.mean(waveform ** 2))
        if rms < 1e-10:
            return -120.0
        return np.clip(20 * np.log10(rms), -120.0, 0.0)
    
    def _classify_energy_band(self, rms_dbfs: float) -> EnergyBand:
        """Classify energy band based on RMS level."""
        if rms_dbfs < -35.0:
            return EnergyBand.VERY_LOW
        elif rms_dbfs < -25.0:
            return EnergyBand.LOW
        elif rms_dbfs < -15.0:
            return EnergyBand.NORMAL
        else:
            return EnergyBand.HIGH
    
    def _normalize_adaptive(
        self,
        waveform: np.ndarray,
        energy_band: EnergyBand
    ) -> np.ndarray:
        """Adaptive RMS normalization based on energy band."""
        try:
            target_rms_dbfs = self.config.target_rms_by_band[energy_band]
            max_gain_db = self.config.max_gain_by_band[energy_band]
            
            # Current RMS
            current_rms = np.sqrt(np.mean(waveform ** 2))
            if current_rms < 1e-10:
                return waveform
            
            # Calculate needed gain
            current_rms_dbfs = 20 * np.log10(current_rms)
            gain_db = target_rms_dbfs - current_rms_dbfs
            
            # Cap gain to band-specific maximum
            gain_db = np.clip(gain_db, 0, max_gain_db)
            
            # Apply gain
            gain_linear = 10 ** (gain_db / 20)
            normalized = waveform * gain_linear
            
            logger.debug(
                "Applied adaptive normalization",
                band=energy_band.value,
                gain_db=gain_db,
                target_rms=target_rms_dbfs
            )
            
            return normalized.astype(np.float32)
        
        except Exception as e:
            logger.warning("Normalization failed, returning original", exc=e)
            return waveform
    
    def _apply_limiter(self, waveform: np.ndarray) -> np.ndarray:
        """Apply soft limiter to prevent clipping."""
        try:
            threshold_linear = 10 ** (self.config.limiter_threshold / 20)
            
            # Soft knee compression above threshold
            mask = np.abs(waveform) > threshold_linear
            if np.any(mask):
                # Compress peaks using soft knee
                excess = np.abs(waveform[mask]) - threshold_linear
                compression = threshold_linear + excess / 2
                sign = np.sign(waveform[mask])
                waveform[mask] = sign * compression
            
            return waveform.astype(np.float32)
        except Exception as e:
            logger.warning("Limiter failed, returning original", exc=e)
            return waveform
    
    def _compute_mel_spectrogram(self, waveform: np.ndarray, sr: int) -> np.ndarray:
        """Compute log-mel spectrogram."""
        try:
            mel_spec = librosa.feature.melspectrogram(
                y=waveform,
                sr=sr,
                n_fft=self.config.n_fft,
                hop_length=self.config.hop_length,
                n_mels=self.config.n_mels,
                fmin=self.config.fmin,
                fmax=self.config.fmax,
                power=2.0
            )
            
            # Convert to log scale
            log_mel = librosa.power_to_db(mel_spec, ref=np.max)
            return log_mel.astype(np.float32)
        except Exception as e:
            logger.error("Mel-spectrogram computation failed", exc=e)
            raise
    
    def _standardize_features(self, mel_spec: np.ndarray) -> np.ndarray:
        """Standardize features per sample (z-score normalization)."""
        try:
            mean = np.mean(mel_spec)
            std = np.std(mel_spec)
            
            if std < 1e-10:
                return mel_spec
            
            standardized = (mel_spec - mean) / std
            return standardized.astype(np.float32)
        except Exception as e:
            logger.warning("Feature standardization failed", exc=e)
            return mel_spec
