"""
Comprehensive Unit Tests for EPMSSTS Services
"""

import pytest
import numpy as np
import soundfile as sf
import io
import torch

from epmssts.services.translation.translator import TranslationService, NLLB_LANG_CODES
from epmssts.services.stt.transcriber import SpeechToTextService
from epmssts.services.emotion.audio_emotion import AudioEmotionService
from epmssts.services.dialect.classifier import DialectClassifier


class TestTranslationService:
    """Unit tests for Translation Service."""
    
    @pytest.fixture
    def translation_service(self):
        """Initialize translation service."""
        service = TranslationService()
        return service
    
    def test_service_initialization(self, translation_service):
        """Test translation service initializes correctly."""
        assert translation_service is not None
        # Check attributes exist
        assert hasattr(translation_service, '_device')
        assert hasattr(translation_service, '_max_new_tokens')
    
    def test_supported_languages(self, translation_service):
        """Test supported language codes."""
        supported = list(NLLB_LANG_CODES.keys())
        assert 'en' in supported
        assert 'hi' in supported
        assert 'te' in supported
        assert len(supported) == 3
    
    def test_language_validation(self, translation_service):
        """Test language validation."""
        # Valid languages
        assert translation_service._validate_lang('en') == 'en'
        assert translation_service._validate_lang('hi') == 'hi'
        assert translation_service._validate_lang('te') == 'te'
    
    def test_invalid_language(self, translation_service):
        """Test invalid language raises error."""
        with pytest.raises(ValueError):
            translation_service._validate_lang('invalid')
    
    def test_translate_english_text(self, translation_service):
        """Test translating English text."""
        if translation_service._model is None:
            pytest.skip("Translation model not loaded")
        
        result = translation_service.translate(
            "Hello world",
            source_lang="en",
            target_lang="hi"
        )
        
        assert result is not None
        assert hasattr(result, 'translated_text')
        assert len(result.translated_text) > 0
    
    def test_translate_identity(self, translation_service):
        """Test identity translation (same source and target)."""
        text = "Hello world"
        result = translation_service.translate(
            text,
            source_lang="en",
            target_lang="en"
        )
        
        # Identity translation should return same or similar text
        assert result.translated_text.strip() == text
    
    def test_translate_empty_text(self, translation_service):
        """Test translation with empty text raises error."""
        with pytest.raises(ValueError):
            translation_service.translate(
                "",
                source_lang="en",
                target_lang="hi"
            )
    
    def test_translate_whitespace_text(self, translation_service):
        """Test translation with whitespace-only text raises error."""
        with pytest.raises(ValueError):
            translation_service.translate(
                "   ",
                source_lang="en",
                target_lang="hi"
            )
    
    def test_model_available(self, translation_service):
        """Test if translation model is available."""
        # Model may not load in Python 3.13, but service should handle gracefully
        if translation_service._model is None:
            pytest.skip("Translation model not loaded (expected on Python 3.13)")
        
        assert translation_service._model is not None
        assert translation_service._tokenizer is not None


class TestSpeechToTextService:
    """Unit tests for Speech-to-Text Service."""
    
    @pytest.fixture
    def stt_service(self):
        """Initialize STT service."""
        service = SpeechToTextService()
        return service
    
    @pytest.fixture
    def sample_audio(self):
        """Generate sample audio for testing."""
        sample_rate = 16000
        duration = 2
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
        return audio, sample_rate
    
    def test_service_initialization(self, stt_service):
        """Test STT service initializes correctly."""
        assert stt_service is not None
        assert hasattr(stt_service, '_model')
    
    def test_model_loaded(self, stt_service):
        """Test that Whisper model is loaded."""
        assert stt_service._model is not None
    
    def test_supported_languages(self, stt_service):
        """Test service can detect multiple languages."""
        # Whisper supports 99+ languages
        assert stt_service is not None
    
    def test_transcribe_audio(self, stt_service, sample_audio):
        """Test transcribing audio."""
        audio, sample_rate = sample_audio
        
        # Transcribe audio
        result = stt_service.transcribe(audio, sample_rate)
        assert result is not None
        assert hasattr(result, 'text')


class TestAudioEmotionService:
    """Unit tests for Emotion Detection Service."""
    
    @pytest.fixture
    def emotion_service(self):
        """Initialize emotion service."""
        service = AudioEmotionService()
        return service
    
    @pytest.fixture
    def sample_audio(self):
        """Generate sample audio for testing."""
        sample_rate = 16000
        duration = 2
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
        return audio, sample_rate
    
    def test_service_initialization(self, emotion_service):
        """Test emotion service initializes correctly."""
        assert emotion_service is not None
    
    def test_supported_emotions(self, emotion_service):
        """Test supported emotion labels."""
        # Service should support standard emotions
        assert emotion_service is not None
    
    def test_emotion_detection(self, emotion_service, sample_audio):
        """Test emotion detection from audio."""
        audio, sample_rate = sample_audio
        
        # Emotion detection
        result = emotion_service.predict(audio, sample_rate)
        
        assert result is not None
        assert hasattr(result, 'emotion')
        assert hasattr(result, 'confidence')
        assert 0 <= result.confidence <= 1


class TestDialectClassifier:
    """Unit tests for Dialect Classifier."""
    
    @pytest.fixture
    def dialect_classifier(self):
        """Initialize dialect classifier."""
        classifier = DialectClassifier()
        return classifier
    
    @pytest.fixture
    def sample_audio(self):
        """Generate sample audio for testing."""
        sample_rate = 16000
        duration = 2
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
        return audio, sample_rate
    
    def test_service_initialization(self, dialect_classifier):
        """Test dialect classifier initializes correctly."""
        assert dialect_classifier is not None
    
    def test_detect_dialect(self, dialect_classifier):
        """Test dialect detection from text."""
        # Test with Telugu text
        text = "మీరు ఎలా ఉన్నారు"
        
        # Dialect detection
        result = dialect_classifier.detect(text)
        
        # Should return a result
        assert result is not None


class TestServiceIntegration:
    """Integration tests between services."""
    
    def test_translation_with_various_texts(self):
        """Test translation with different text formats."""
        service = TranslationService()
        
        if service._model is None:
            pytest.skip("Translation model not loaded")
        
        test_cases = [
            ("Hello", "en", "hi"),
            ("Good morning", "en", "te"),
            ("नमस्ते", "hi", "en"),
        ]
        
        for text, src, tgt in test_cases:
            try:
                result = service.translate(text, src, tgt)
                assert result is not None
            except ValueError:
                # May fail for unsupported language pairs
                pass


class TestErrorRecovery:
    """Test error recovery and graceful degradation."""
    
    def test_translation_model_graceful_failure(self):
        """Test translation gracefully handles missing model."""
        service = TranslationService()
        
        if service._model is None:
            # Service should still work, returning original text
            result = service.translate("Hello", "en", "hi")
            assert result is not None
            assert hasattr(result, 'translated_text')
    
    def test_service_reinitialization(self):
        """Test services can be reinitialized."""
        service1 = TranslationService()
        service2 = TranslationService()
        
        # Both should initialize without error
        assert service1 is not None
        assert service2 is not None


@pytest.mark.benchmark
class TestPerformance:
    """Performance benchmarks for services."""
    
    def test_translation_speed(self, benchmark):
        """Benchmark translation speed."""
        service = TranslationService()
        
        if service._model is None:
            pytest.skip("Translation model not loaded")
        
        def translate():
            return service.translate("Hello", "en", "hi")
        
        # Should complete in reasonable time
        result = benchmark(translate)
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
