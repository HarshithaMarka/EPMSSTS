"""
Test fixtures and utilities for audio preprocessing service tests.

Generates synthetic audio for testing various scenarios.
"""

import numpy as np
import soundfile as sf
import tempfile
from pathlib import Path
from typing import Tuple


class AudioTestFixtures:
    """Factory for generating test audio files."""
    
    SAMPLE_RATE = 16000
    
    @staticmethod
    def create_clean_speech(
        duration_seconds: float = 3.0,
        frequency: float = 200.0,
        sample_rate: int = 16000,
    ) -> np.ndarray:
        """
        Create clean speech-like test audio (sine wave).
        
        Args:
            duration_seconds: Duration in seconds
            frequency: Base frequency in Hz (speech range)
            sample_rate: Sample rate in Hz
        
        Returns:
            Audio waveform
        """
        samples = int(duration_seconds * sample_rate)
        t = np.linspace(0, duration_seconds, samples, dtype=np.float32)
        
        # Sine wave with amplitude variation (speech-like)
        audio = 0.1 * np.sin(2 * np.pi * frequency * t)
        
        # Add amplitude modulation
        modulation = 0.5 + 0.5 * np.sin(2 * np.pi * 2 * t)  # 2Hz modulation
        audio = audio * modulation
        
        return audio.astype(np.float32)
    
    @staticmethod
    def create_noisy_audio(
        clean_signal: np.ndarray,
        snr_db: float = 10.0,
    ) -> np.ndarray:
        """
        Add noise to clean signal with specified SNR.
        
        Args:
            clean_signal: Clean audio waveform
            snr_db: Signal-to-noise ratio in dB
        
        Returns:
            Noisy waveform
        """
        signal_power = np.mean(clean_signal ** 2)
        target_noise_power = signal_power / (10 ** (snr_db / 10))
        
        noise = np.random.normal(0, np.sqrt(target_noise_power), len(clean_signal))
        noisy = clean_signal + noise
        
        return noisy.astype(np.float32)
    
    @staticmethod
    def create_clipped_audio(
        audio: np.ndarray,
        clip_percentage: float = 0.1,
    ) -> np.ndarray:
        """
        Create clipped audio by limiting peaks.
        
        Args:
            audio: Original waveform
            clip_percentage: Percentage of samples to clip
        
        Returns:
            Clipped waveform
        """
        clipped = audio.copy()
        threshold = np.percentile(np.abs(clipped), 100 - clip_percentage)
        clipped = np.clip(clipped, -threshold, threshold)
        
        return clipped.astype(np.float32)
    
    @staticmethod
    def create_silence(
        duration_seconds: float = 1.0,
        sample_rate: int = 16000,
    ) -> np.ndarray:
        """Create silence."""
        samples = int(duration_seconds * sample_rate)
        return np.zeros(samples, dtype=np.float32)
    
    @staticmethod
    def create_mostly_silent(
        total_duration: float = 3.0,
        silence_ratio: float = 0.9,
        sample_rate: int = 16000,
    ) -> np.ndarray:
        """Create audio that is mostly silent with brief speech."""
        samples = int(total_duration * sample_rate)
        audio = np.zeros(samples, dtype=np.float32)
        
        # Add brief speech segment
        speech_samples = int(samples * (1 - silence_ratio))
        speech = AudioTestFixtures.create_clean_speech(
            duration_seconds=speech_samples / sample_rate,
            frequency=200.0,
            sample_rate=sample_rate
        )
        
        # Place in middle
        start = (samples - len(speech)) // 2
        audio[start:start + len(speech)] = speech
        
        return audio
    
    @staticmethod
    def create_whisper(
        duration_seconds: float = 3.0,
        sample_rate: int = 16000,
    ) -> np.ndarray:
        """
        Create very low energy audio (whisper-like).
        Target RMS: -38dBFS
        """
        audio = AudioTestFixtures.create_clean_speech(
            duration_seconds=duration_seconds,
            frequency=150.0,
            sample_rate=sample_rate
        )
        
        # Scale to -38dBFS
        target_dbfs = -38.0
        current_rms = np.sqrt(np.mean(audio ** 2))
        if current_rms > 0:
            current_dbfs = 20 * np.log10(current_rms)
            gain_db = target_dbfs - current_dbfs
            gain_linear = 10 ** (gain_db / 20)
            audio = audio * gain_linear
        
        return audio.astype(np.float32)
    
    @staticmethod
    def create_loud_speech(
        duration_seconds: float = 3.0,
        sample_rate: int = 16000,
    ) -> np.ndarray:
        """
        Create very high energy audio (loud speech-like).
        Target RMS: -10dBFS
        """
        audio = AudioTestFixtures.create_clean_speech(
            duration_seconds=duration_seconds,
            frequency=200.0,
            sample_rate=sample_rate
        )
        
        # Scale to -10dBFS
        target_dbfs = -10.0
        current_rms = np.sqrt(np.mean(audio ** 2))
        if current_rms > 0:
            current_dbfs = 20 * np.log10(current_rms)
            gain_db = target_dbfs - current_dbfs
            gain_linear = 10 ** (gain_db / 20)
            audio = audio * gain_linear
        
        # Cap to prevent clipping
        audio = np.clip(audio, -0.99, 0.99)
        
        return audio.astype(np.float32)
    
    @staticmethod
    def save_wav_file(
        audio: np.ndarray,
        sample_rate: int = 16000,
        temp_dir: str = None,
    ) -> str:
        """
        Save audio to temporary WAV file.
        
        Args:
            audio: Audio waveform
            sample_rate: Sample rate in Hz
            temp_dir: Directory for temp file (uses system temp if None)
        
        Returns:
            Path to saved file
        """
        suffix = ".wav"
        if temp_dir:
            tmp = tempfile.NamedTemporaryFile(
                dir=temp_dir,
                delete=False,
                suffix=suffix
            )
        else:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        
        sf.write(tmp.name, audio, sample_rate)
        tmp.close()
        
        return tmp.name
    
    @staticmethod
    def save_corrupt_file(temp_dir: str = None) -> str:
        """
        Save corrupted file (invalid audio data).
        
        Returns:
            Path to corrupt file
        """
        if temp_dir:
            tmp = tempfile.NamedTemporaryFile(
                dir=temp_dir,
                delete=False,
                suffix=".wav"
            )
        else:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        
        # Write invalid data
        tmp.write(b"This is not valid WAV data")
        tmp.close()
        
        return tmp.name
