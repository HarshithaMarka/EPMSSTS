"""
Unit tests for STT service.
"""

import numpy as np
import pytest

from epmssts.services.stt.transcriber import SpeechToTextService
from epmssts.services.stt.audio_handler import preprocess_audio_bytes, TARGET_SAMPLE_RATE


class TestSpeechToTextService:
    """Tests for SpeechToTextService."""
    
    def test_service_initializes(self):
        """Test that service initializes successfully."""
        service = SpeechToTextService()
        assert service is not None
    
    def test_model_enforcement(self):
        """Test that only large-v3 model is allowed."""
        with pytest.raises(ValueError, match="large-v3"):
            SpeechToTextService(model_size="base")
    
    def test_is_silent_detects_zero_audio(self):
        """Test silence detection on zero audio."""
        service = SpeechToTextService()
        audio = np.zeros(16000, dtype=np.float32)
        assert service.is_silent(audio)
    
    def test_is_silent_detects_quiet_audio(self):
        """Test silence detection on very quiet audio."""
        service = SpeechToTextService()
        audio = np.random.randn(16000).astype(np.float32) * 1e-5
        assert service.is_silent(audio)
    
    def test_is_silent_rejects_normal_audio(self):
        """Test that normal audio is not detected as silent."""
        service = SpeechToTextService()
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        assert not service.is_silent(audio)
    
    def test_transcribe_rejects_wrong_sample_rate(self):
        """Test that transcribe rejects non-16kHz audio."""
        service = SpeechToTextService()
        audio = np.random.randn(8000).astype(np.float32)
        
        with pytest.raises(ValueError, match="16kHz"):
            service.transcribe(audio, sample_rate=8000)
    
    def test_transcribe_rejects_stereo_audio(self):
        """Test that transcribe rejects stereo audio."""
        service = SpeechToTextService()
        audio = np.random.randn(16000, 2).astype(np.float32)
        
        with pytest.raises(ValueError, match="mono"):
            service.transcribe(audio, sample_rate=16000)


class TestAudioHandler:
    """Tests for audio preprocessing."""
    
    def test_preprocess_empty_bytes(self):
        """Test that empty bytes raise an error."""
        with pytest.raises(ValueError):
            preprocess_audio_bytes(b"")
    
    def test_preprocess_invalid_audio(self):
        """Test that invalid audio bytes raise an error."""
        with pytest.raises(ValueError, match="Invalid"):
            preprocess_audio_bytes(b"not an audio file")
    
    def test_preprocess_returns_correct_sample_rate(self):
        """Test that preprocessing returns 16kHz."""
        # Create a simple WAV file in memory
        import io
        import soundfile as sf
        
        # Generate 1 second of random audio at 44.1kHz
        audio_44k = np.random.randn(44100).astype(np.float32)
        buf = io.BytesIO()
        sf.write(buf, audio_44k, 44100, format='WAV')
        wav_bytes = buf.getvalue()
        
        # Preprocess
        audio_16k, sr = preprocess_audio_bytes(wav_bytes)
        
        assert sr == TARGET_SAMPLE_RATE
        assert audio_16k.dtype == np.float32
        assert audio_16k.ndim == 1
    
    def test_preprocess_converts_stereo_to_mono(self):
        """Test that stereo audio is converted to mono."""
        import io
        import soundfile as sf
        
        # Generate 1 second of stereo audio
        audio_stereo = np.random.randn(16000, 2).astype(np.float32)
        buf = io.BytesIO()
        sf.write(buf, audio_stereo, 16000, format='WAV')
        wav_bytes = buf.getvalue()
        
        # Preprocess
        audio_mono, sr = preprocess_audio_bytes(wav_bytes)
        
        assert audio_mono.ndim == 1
        assert len(audio_mono) == 16000
