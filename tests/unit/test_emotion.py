"""
Unit tests for emotion detection service.
"""

import numpy as np
import pytest

from epmssts.services.emotion.audio_emotion import AudioEmotionService, EMOTIONS


class TestAudioEmotionService:
    """Tests for AudioEmotionService."""
    
    def test_service_initializes(self):
        """Test that service initializes successfully."""
        service = AudioEmotionService()
        assert service is not None
    
    def test_is_silent_detects_zero_audio(self):
        """Test silence detection on zero audio."""
        service = AudioEmotionService()
        audio = np.zeros(16000, dtype=np.float32)
        assert service.is_silent(audio)
    
    def test_predict_on_silence_returns_neutral(self):
        """Test that silence returns neutral emotion."""
        service = AudioEmotionService()
        audio = np.zeros(16000, dtype=np.float32)
        
        result = service.predict(audio, sample_rate=16000)
        
        assert result.label == "neutral"
        assert result.confidence == 1.0
        assert result.scores["neutral"] == 1.0
    
    def test_predict_rejects_wrong_sample_rate(self):
        """Test that predict rejects non-16kHz audio."""
        service = AudioEmotionService()
        audio = np.random.randn(8000).astype(np.float32)
        
        with pytest.raises(ValueError, match="16kHz"):
            service.predict(audio, sample_rate=8000)
    
    def test_predict_rejects_stereo_audio(self):
        """Test that predict rejects stereo audio."""
        service = AudioEmotionService()
        audio = np.random.randn(16000, 2).astype(np.float32)
        
        with pytest.raises(ValueError, match="mono"):
            service.predict(audio, sample_rate=16000)
    
    def test_predict_returns_valid_emotion(self):
        """Test that predict returns a valid emotion label."""
        service = AudioEmotionService()
        # Generate random audio (not silent)
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        
        result = service.predict(audio, sample_rate=16000)
        
        assert result.label in EMOTIONS
        assert 0.0 <= result.confidence <= 1.0
    
    def test_predict_scores_sum_to_one(self):
        """Test that emotion scores sum to approximately 1.0."""
        service = AudioEmotionService()
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        
        result = service.predict(audio, sample_rate=16000)
        
        total = sum(result.scores.values())
        assert abs(total - 1.0) < 1e-5
    
    def test_predict_all_emotions_present(self):
        """Test that all expected emotions are in scores."""
        service = AudioEmotionService()
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        
        result = service.predict(audio, sample_rate=16000)
        
        for emotion in EMOTIONS:
            assert emotion in result.scores
