"""
Test Fixtures for STT Service

Provides synthetic audio samples and fixtures for testing.
"""

import numpy as np
import soundfile as sf
import io
import base64
from typing import Tuple, NamedTuple
from dataclasses import dataclass


class AudioSample(NamedTuple):
    """Audio sample with metadata"""
    audio_array: np.ndarray
    sample_rate: int
    duration_seconds: float
    description: str


@dataclass
class MockWhisperSegment:
    """Mock Whisper segment for testing"""
    text: str
    start: float
    end: float
    avg_logprob: float = -0.5
    no_speech_prob: float = 0.1


@dataclass
class MockWhisperInfo:
    """Mock Whisper info object for testing"""
    language: str = "en"
    language_prob: float = 0.95
    avg_logprob: float = -0.5
    no_speech_prob: float = 0.1


class SttAudioFixtures:
    """Factory for generating synthetic audio fixtures"""
    
    @staticmethod
    def _generate_base_audio(
        duration_seconds: float,
        sample_rate: int = 16000,
        frequency: float = 440.0,
    ) -> np.ndarray:
        """Generate clean sine wave"""
        t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds))
        audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)
        return audio
    
    @staticmethod
    def _add_noise(audio: np.ndarray, snr_db: float = 20.0) -> np.ndarray:
        """Add Gaussian noise to audio"""
        signal_power = np.mean(audio ** 2)
        noise_power = signal_power / (10 ** (snr_db / 10))
        noise = np.random.normal(0, np.sqrt(noise_power), audio.shape)
        return audio + noise
    
    @staticmethod
    def _to_wav_bytes(audio: np.ndarray, sample_rate: int = 16000) -> bytes:
        """Convert audio array to WAV bytes"""
        buffer = io.BytesIO()
        sf.write(buffer, audio, sample_rate, format='WAV')
        buffer.seek(0)
        return buffer.read()
    
    @staticmethod
    def _to_base64(audio_bytes: bytes) -> str:
        """Encode audio bytes to base64"""
        return base64.b64encode(audio_bytes).decode('utf-8')
    
    @classmethod
    def clean_speech(cls, duration_seconds: float = 5.0) -> Tuple[str, AudioSample]:
        """
        Generate clean speech-like audio (high frequency).
        
        Returns:
            Tuple of (base64_encoded_audio, AudioSample metadata)
        """
        # Simulate speech with multiple frequencies
        sample_rate = 16000
        t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds))
        
        # Mix of frequencies that sound like speech
        f1, f2, f3 = 200, 700, 2200  # Formant-like frequencies
        audio = (
            0.5 * np.sin(2 * np.pi * f1 * t) +
            0.3 * np.sin(2 * np.pi * f2 * t) +
            0.2 * np.sin(2 * np.pi * f3 * t)
        ).astype(np.float32)
        
        # Slight amplitude modulation (speech-like)
        envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 2 * t)
        audio = audio * envelope
        
        # Normalize
        audio = audio / (np.abs(audio).max() + 1e-6)
        
        wav_bytes = cls._to_wav_bytes(audio, sample_rate)
        b64_audio = cls._to_base64(wav_bytes)
        
        return b64_audio, AudioSample(
            audio_array=audio,
            sample_rate=sample_rate,
            duration_seconds=duration_seconds,
            description="Clean speech-like audio",
        )
    
    @classmethod
    def noisy_speech(cls, duration_seconds: float = 5.0, snr_db: float = 10.0) -> Tuple[str, AudioSample]:
        """Generate speech with background noise"""
        audio, _ = cls.clean_speech(duration_seconds)
        # This is already base64, decode first
        wav_bytes = base64.b64decode(audio)
        audio_array, sr = sf.read(io.BytesIO(wav_bytes))
        
        noisy = cls._add_noise(audio_array, snr_db=snr_db)
        noisy = (noisy / (np.abs(noisy).max() + 1e-6)).astype(np.float32)
        
        wav_bytes = cls._to_wav_bytes(noisy, sr)
        b64_audio = cls._to_base64(wav_bytes)
        
        return b64_audio, AudioSample(
            audio_array=noisy,
            sample_rate=sr,
            duration_seconds=duration_seconds,
            description=f"Speech with noise (SNR={snr_db}dB)",
        )
    
    @classmethod
    def whisper_audio(cls, duration_seconds: float = 5.0) -> Tuple[str, AudioSample]:
        """Generate whisper-like audio (low amplitude, high frequency)"""
        sample_rate = 16000
        t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds))
        
        # High frequency, low amplitude (whisper-like)
        audio = (0.1 * np.sin(2 * np.pi * 3000 * t)).astype(np.float32)
        
        # Add fricative-like noise quality
        noise = np.random.normal(0, 0.05, audio.shape)
        audio = audio + noise
        
        # Normalize
        audio = audio / (np.abs(audio).max() + 1e-6)
        
        wav_bytes = cls._to_wav_bytes(audio, sample_rate)
        b64_audio = cls._to_base64(wav_bytes)
        
        return b64_audio, AudioSample(
            audio_array=audio,
            sample_rate=sample_rate,
            duration_seconds=duration_seconds,
            description="Whisper-like low-amplitude audio",
        )
    
    @classmethod
    def loud_speech(cls, duration_seconds: float = 5.0) -> Tuple[str, AudioSample]:
        """Generate clipped/loud speech"""
        audio, sample_info = cls.clean_speech(duration_seconds)
        
        wav_bytes = base64.b64decode(audio)
        audio_array, sr = sf.read(io.BytesIO(wav_bytes))
        
        # Amplify and clip
        loud = audio_array * 3.0
        loud = np.clip(loud, -1.0, 1.0).astype(np.float32)
        
        wav_bytes = cls._to_wav_bytes(loud, sr)
        b64_audio = cls._to_base64(wav_bytes)
        
        return b64_audio, AudioSample(
            audio_array=loud,
            sample_rate=sr,
            duration_seconds=duration_seconds,
            description="Clipped/loud speech",
        )
    
    @classmethod
    def silence(cls, duration_seconds: float = 5.0) -> Tuple[str, AudioSample]:
        """Generate silence (should be rejected)"""
        sample_rate = 16000
        audio = np.zeros(int(sample_rate * duration_seconds), dtype=np.float32)
        
        # Add tiny noise floor
        audio = audio + np.random.normal(0, 0.001, audio.shape)
        
        wav_bytes = cls._to_wav_bytes(audio, sample_rate)
        b64_audio = cls._to_base64(wav_bytes)
        
        return b64_audio, AudioSample(
            audio_array=audio,
            sample_rate=sample_rate,
            duration_seconds=duration_seconds,
            description="Silent audio (should be rejected)",
        )
    
    @classmethod
    def very_short_audio(cls) -> Tuple[str, AudioSample]:
        """Generate audio that's too short"""
        return cls.clean_speech(duration_seconds=0.2)
    
    @classmethod
    def very_long_audio(cls) -> Tuple[str, AudioSample]:
        """Generate audio that's too long"""
        return cls.clean_speech(duration_seconds=700.0)  # > 10 minutes
    
    @staticmethod
    def generate_mock_segments(
        text: str,
        duration: float,
        num_segments: int = 3,
    ) -> list:
        """Generate mock Whisper segments"""
        segment_duration = duration / num_segments
        segments = []
        
        words = text.split()
        words_per_segment = max(1, len(words) // num_segments)
        
        for i in range(num_segments):
            start_idx = i * words_per_segment
            end_idx = min(start_idx + words_per_segment, len(words))
            
            if end_idx <= start_idx:
                continue
            
            segment_text = " ".join(words[start_idx:end_idx])
            segments.append(MockWhisperSegment(
                text=segment_text,
                start=i * segment_duration,
                end=(i + 1) * segment_duration,
                avg_logprob=-0.5 + np.random.normal(0, 0.1),
                no_speech_prob=0.05 + np.random.normal(0, 0.02),
            ))
        
        return segments
