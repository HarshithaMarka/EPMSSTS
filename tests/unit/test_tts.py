"""
Unit tests for TTS service.
"""

import numpy as np
import pytest

from epmssts.services.tts.synthesizer import TtsService, TtsSynthesisRequest, EMOTION_SPEED


class TestTtsService:
    """Tests for TtsService."""
    
    def test_service_initializes(self):
        """Test that service initializes successfully."""
        service = TtsService()
        assert service is not None
    
    def test_synthesize_rejects_empty_text(self):
        """Test that empty text raises an error."""
        service = TtsService()
        request = TtsSynthesisRequest(text="", language="en", emotion="neutral")
        
        with pytest.raises(ValueError, match="non-empty"):
            service.synthesize(request)
    
    def test_synthesize_rejects_invalid_language(self):
        """Test that invalid language raises an error."""
        service = TtsService()
        request = TtsSynthesisRequest(text="Hello", language="fr", emotion="neutral")  # type: ignore
        
        with pytest.raises(ValueError, match="Language"):
            service.synthesize(request)
    
    def test_synthesize_rejects_invalid_emotion(self):
        """Test that invalid emotion raises an error."""
        service = TtsService()
        request = TtsSynthesisRequest(text="Hello", language="en", emotion="excited")  # type: ignore
        
        with pytest.raises(ValueError, match="Emotion"):
            service.synthesize(request)
    
    def test_synthesize_returns_wav_bytes(self):
        """Test that synthesis returns WAV bytes."""
        service = TtsService()
        request = TtsSynthesisRequest(text="Hello", language="en", emotion="neutral")
        
        wav_bytes = service.synthesize(request)
        
        assert isinstance(wav_bytes, bytes)
        assert len(wav_bytes) > 0
        # WAV files start with "RIFF"
        assert wav_bytes[:4] == b"RIFF"
    
    def test_synthesize_all_emotions(self):
        """Test synthesis with all supported emotions."""
        service = TtsService()
        text = "Hello"
        
        for emotion in EMOTION_SPEED.keys():
            request = TtsSynthesisRequest(text=text, language="en", emotion=emotion)  # type: ignore
            wav_bytes = service.synthesize(request)
            
            assert isinstance(wav_bytes, bytes)
            assert len(wav_bytes) > 0
    
    def test_synthesize_all_languages(self):
        """Test synthesis with all supported languages."""
        service = TtsService()
        text = "Hello"
        
        for language in ["en", "te", "hi"]:
            request = TtsSynthesisRequest(text=text, language=language, emotion="neutral")  # type: ignore
            wav_bytes = service.synthesize(request)
            
            assert isinstance(wav_bytes, bytes)
            assert len(wav_bytes) > 0
    
    def test_apply_speed_neutral_unchanged(self):
        """Test that neutral emotion (speed=1.0) doesn't change audio."""
        audio = np.random.randn(16000).astype(np.float32)
        result = TtsService._apply_speed(audio, speed=1.0)
        
        np.testing.assert_array_equal(audio, result)
    
    def test_apply_speed_faster(self):
        """Test that speed > 1.0 shortens audio."""
        audio = np.random.randn(16000).astype(np.float32)
        result = TtsService._apply_speed(audio, speed=1.5)
        
        assert len(result) < len(audio)
    
    def test_apply_speed_slower(self):
        """Test that speed < 1.0 lengthens audio."""
        audio = np.random.randn(16000).astype(np.float32)
        result = TtsService._apply_speed(audio, speed=0.8)
        
        assert len(result) > len(audio)
