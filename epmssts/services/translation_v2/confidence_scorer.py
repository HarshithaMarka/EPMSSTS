"""
Translation Confidence Scorer

Multi-factor confidence scoring for translation quality assessment.
"""

import logging
import re
from typing import Optional, Dict
from collections import Counter

from .schemas import TranslationConfidenceMetrics


logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """
    Comprehensive translation confidence scoring.
    
    Factors:
    1. Model log probability
    2. Length consistency (source-target ratio)
    3. Repetition detection
    4. Language consistency
    5. Named entity preservation
    """
    
    def __init__(self):
        # Statistics
        self.scoring_count = 0
        self.low_confidence_count = 0
    
    def compute_confidence(
        self,
        original_text: str,
        translated_text: str,
        model_log_prob: Optional[float] = None,
        source_lang: str = "en",
        target_lang: str = "es",
    ) -> TranslationConfidenceMetrics:
        """
        Compute comprehensive translation confidence.
        
        Args:
            original_text: Source text
            translated_text: Translated text
            model_log_prob: Optional model log probability
            source_lang: Source language code
            target_lang: Target language code
        
        Returns:
            TranslationConfidenceMetrics with detailed scores
        """
        # Factor 1: Length consistency
        length_consistency = self._compute_length_consistency(
            original_text, translated_text, source_lang, target_lang
        )
        
        # Factor 2: Repetition score
        repetition_score = self._compute_repetition_score(translated_text)
        
        # Factor 3: Language consistency
        language_consistency = self._compute_language_consistency(
            translated_text, target_lang
        )
        
        # Factor 4: Named entity preservation (basic)
        entity_preservation = self._check_entity_preservation(
            original_text, translated_text
        )
        
        # Factor 5: Model log probability (if available)
        model_confidence = self._normalize_log_prob(model_log_prob) if model_log_prob else 0.7
        
        # Compute overall confidence
        overall_confidence = self._compute_overall_confidence(
            length_consistency=length_consistency,
            repetition_score=repetition_score,
            language_consistency=language_consistency,
            entity_preservation=entity_preservation,
            model_confidence=model_confidence,
        )
        
        # Update statistics
        self.scoring_count += 1
        if overall_confidence < 0.6:
            self.low_confidence_count += 1
        
        return TranslationConfidenceMetrics(
            overall_confidence=overall_confidence,
            model_log_probability=model_log_prob,
            length_consistency_score=length_consistency,
            repetition_score=repetition_score,
            language_consistency_score=language_consistency,
        )
    
    def _compute_length_consistency(
        self,
        original_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
    ) -> float:
        """
        Compute length consistency between source and target.
        
        Different language pairs have different typical length ratios.
        """
        original_len = len(original_text.split())
        translated_len = len(translated_text.split())
        
        if original_len == 0:
            return 0.0
        
        ratio = translated_len / original_len
        
        # Expected ratio ranges by language pair (heuristic)
        expected_ratios = {
            ("en", "es"): (0.9, 1.3),   # English to Spanish
            ("en", "te"): (0.8, 1.5),   # English to Telugu
            ("en", "hi"): (0.8, 1.5),   # English to Hindi
            ("en", "fr"): (0.9, 1.3),   # English to French
            ("en", "de"): (0.8, 1.2),   # English to German
            ("en", "zh"): (0.5, 0.9),   # English to Chinese
        }
        
        # Get expected range or use default
        lang_pair = (source_lang, target_lang)
        min_ratio, max_ratio = expected_ratios.get(lang_pair, (0.7, 1.5))
        
        # Score based on how close to expected range
        if min_ratio <= ratio <= max_ratio:
            return 1.0
        elif ratio < min_ratio:
            # Too short
            diff = min_ratio - ratio
            return max(0.0, 1.0 - diff)
        else:
            # Too long
            diff = ratio - max_ratio
            return max(0.0, 1.0 - diff * 0.5)
    
    def _compute_repetition_score(self, text: str) -> float:
        """
        Detect repetitive loops in translation.
        
        Returns 1.0 if no repetition, lower if repetition detected.
        """
        if not text or len(text) < 10:
            return 1.0
        
        # Check for exact phrase repetition
        words = text.lower().split()
        
        # Check for repeated n-grams (3-grams)
        ngram_size = 3
        if len(words) < ngram_size:
            return 1.0
        
        ngrams = []
        for i in range(len(words) - ngram_size + 1):
            ngram = tuple(words[i:i+ngram_size])
            ngrams.append(ngram)
        
        # Count ngram frequencies
        ngram_counts = Counter(ngrams)
        
        # Check for high-frequency ngrams
        if ngrams:
            max_count = max(ngram_counts.values())
            total_ngrams = len(ngrams)
            
            # If any ngram appears more than 20% of the time, penalize
            repetition_ratio = max_count / total_ngrams
            
            if repetition_ratio > 0.2:
                return max(0.0, 1.0 - repetition_ratio)
        
        # Check for character-level repetition (e.g., "aaaa")
        char_repetition = bool(re.search(r'(.)\1{4,}', text))
        if char_repetition:
            return 0.3
        
        return 1.0
    
    def _compute_language_consistency(
        self,
        text: str,
        target_lang: str,
    ) -> float:
        """
        Check if translated text is in target language.
        
        Simple heuristic - in production, use proper language detector.
        """
        # Check for script consistency
        if target_lang == "te":
            # Telugu script
            telugu_chars = len(re.findall(r'[\u0C00-\u0C7F]', text))
            total_chars = len(text.replace(" ", ""))
            if total_chars > 0:
                return telugu_chars / total_chars
        
        elif target_lang == "hi":
            # Devanagari script
            devanagari_chars = len(re.findall(r'[\u0900-\u097F]', text))
            total_chars = len(text.replace(" ", ""))
            if total_chars > 0:
                return devanagari_chars / total_chars
        
        elif target_lang in ["en", "es", "fr", "de", "it", "pt"]:
            # Latin script
            latin_chars = len(re.findall(r'[A-Za-z]', text))
            total_chars = len(text.replace(" ", ""))
            if total_chars > 0:
                return latin_chars / total_chars
        
        # Default: assume consistent
        return 0.9
    
    def _check_entity_preservation(
        self,
        original_text: str,
        translated_text: str,
    ) -> float:
        """
        Check if named entities are preserved.
        
        Named entities (proper nouns, numbers) should typically be preserved.
        """
        # Extract capitalized words (likely proper nouns)
        original_entities = set(
            word for word in original_text.split()
            if word and word[0].isupper() and len(word) > 1
        )
        
        if not original_entities:
            return 1.0  # No entities to preserve
        
        # Check if entities appear in translation
        translated_lower = translated_text.lower()
        preserved_count = sum(
            1 for entity in original_entities
            if entity.lower() in translated_lower
        )
        
        preservation_ratio = preserved_count / len(original_entities)
        return preservation_ratio
    
    def _normalize_log_prob(self, log_prob: float) -> float:
        """Normalize log probability to [0, 1] range"""
        # Log probs are typically negative
        # Map to confidence: -10 to 0 → 0 to 1
        if log_prob >= 0:
            return 1.0
        
        # Clamp and normalize
        normalized = 1.0 + (log_prob / 10.0)
        return max(0.0, min(1.0, normalized))
    
    def _compute_overall_confidence(
        self,
        length_consistency: float,
        repetition_score: float,
        language_consistency: float,
        entity_preservation: float,
        model_confidence: float,
    ) -> float:
        """
        Compute weighted overall confidence.
        
        Weights:
        - Model confidence: 30%
        - Length consistency: 20%
        - Repetition score: 25%
        - Language consistency: 15%
        - Entity preservation: 10%
        """
        confidence = (
            model_confidence * 0.30
            + length_consistency * 0.20
            + repetition_score * 0.25
            + language_consistency * 0.15
            + entity_preservation * 0.10
        )
        
        return min(1.0, max(0.0, confidence))
    
    def get_scoring_stats(self) -> Dict:
        """Get confidence scoring statistics"""
        return {
            "scoring_count": self.scoring_count,
            "low_confidence_count": self.low_confidence_count,
            "low_confidence_rate": (
                self.low_confidence_count / self.scoring_count
                if self.scoring_count > 0
                else 0.0
            ),
        }
