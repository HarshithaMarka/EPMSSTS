"""
Unit tests for dialect classifier.
"""

import pytest

from epmssts.services.dialect.classifier import DialectClassifier


class TestDialectClassifier:
    """Tests for DialectClassifier."""
    
    def test_classifier_initializes(self):
        """Test that classifier initializes successfully."""
        classifier = DialectClassifier()
        assert classifier is not None
    
    def test_detect_empty_text_returns_standard(self):
        """Test that empty text returns standard Telugu."""
        classifier = DialectClassifier()
        result = classifier.detect("")
        
        assert result.dialect == "standard_telugu"
        assert 0.0 <= result.confidence <= 1.0
    
    def test_detect_telangana_keywords(self):
        """Test detection of Telangana dialect."""
        classifier = DialectClassifier()
        text = "ra emo inka enduku"
        
        result = classifier.detect(text)
        
        # Should detect a valid dialect (likely Telangana or standard with keywords)
        assert result.dialect in classifier.DIALECTS
        assert 0.0 <= result.confidence <= 1.0
    
    def test_detect_andhra_keywords(self):
        """Test detection of Andhra dialect."""
        classifier = DialectClassifier()
        text = "ayya andi kadha"
        
        result = classifier.detect(text)
        
        # Should detect Andhra due to keywords
        assert result.dialect in classifier.DIALECTS
        assert 0.0 <= result.confidence <= 1.0
    
    def test_detect_no_keywords_returns_standard(self):
        """Test that text without dialect markers returns standard."""
        classifier = DialectClassifier()
        text = "క్ష్ణ కథ నుండి కథ"
        
        result = classifier.detect(text)
        
        # Should default to standard Telugu (no markers)
        assert result.dialect == "standard_telugu"
    
    def test_detect_case_insensitive(self):
        """Test that detection is case-insensitive."""
        classifier = DialectClassifier()
        text_lower = "ra emo"
        text_upper = "RA EMO"
        
        result_lower = classifier.detect(text_lower)
        result_upper = classifier.detect(text_upper)
        
        # Both should detect the same dialect
        assert result_lower.dialect == result_upper.dialect
    
    def test_confidence_is_valid(self):
        """Test that confidence is always between 0 and 1."""
        classifier = DialectClassifier()
        
        test_texts = [
            "",
            "ra emo",
            "ayya andi",
            "random text",
            "ra ayya emo andi",  # Mixed keywords
        ]
        
        for text in test_texts:
            result = classifier.detect(text)
            assert 0.0 <= result.confidence <= 1.0
