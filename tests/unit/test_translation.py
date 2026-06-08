"""
Unit tests for translation service.
"""

import pytest

from epmssts.services.translation.translator import TranslationService, NLLB_MODEL_ID


class TestTranslationService:
    """Tests for TranslationService."""
    
    def test_service_initializes(self):
        """Test that service initializes successfully."""
        service = TranslationService()
        assert service is not None
    
    def test_model_enforcement(self):
        """Test that only NLLB-200 model is allowed."""
        with pytest.raises(ValueError, match="nllb-200"):
            TranslationService(model_id="facebook/some-other-model")
    
    def test_translate_rejects_empty_text(self):
        """Test that empty text raises an error."""
        service = TranslationService()
        
        with pytest.raises(ValueError, match="non-empty"):
            service.translate("", source_lang="en", target_lang="hi")
    
    def test_translate_rejects_invalid_source_lang(self):
        """Test that invalid source language raises an error."""
        service = TranslationService()
        
        with pytest.raises(ValueError, match="Unsupported"):
            service.translate("Hello", source_lang="fr", target_lang="en")
    
    def test_translate_rejects_invalid_target_lang(self):
        """Test that invalid target language raises an error."""
        service = TranslationService()
        
        with pytest.raises(ValueError, match="Unsupported"):
            service.translate("Hello", source_lang="en", target_lang="fr")
    
    def test_translate_identity_returns_same_text(self):
        """Test that translating to same language returns input."""
        service = TranslationService()
        text = "Hello world"
        
        result = service.translate(text, source_lang="en", target_lang="en")
        
        assert result.translated_text == text
        assert result.model == NLLB_MODEL_ID
    
    def test_translate_returns_non_empty_text(self):
        """Test that translation returns non-empty text."""
        service = TranslationService()
        text = "Hello world"
        
        result = service.translate(text, source_lang="en", target_lang="hi")
        
        assert result.translated_text
        assert isinstance(result.translated_text, str)
        assert len(result.translated_text) > 0
    
    def test_translate_all_language_pairs(self):
        """Test translation for all supported language pairs."""
        service = TranslationService()
        text = "Hello"
        languages = ["en", "hi", "te"]
        
        for src in languages:
            for tgt in languages:
                if src != tgt:
                    result = service.translate(text, source_lang=src, target_lang=tgt)
                    assert result.translated_text
                    assert isinstance(result.translated_text, str)
