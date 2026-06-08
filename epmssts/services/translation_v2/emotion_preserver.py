"""
Emotion Preservation Module

Ensures emotional tone is preserved across translation.
Compares sentiment polarity and intensity before/after translation.
"""

import logging
import re
from typing import Optional, Dict, Tuple

from .schemas import EmotionPreservationMetrics
from .exceptions import EmotionPreservationError


logger = logging.getLogger(__name__)


class EmotionPreserver:
    """
    Emotion preservation scorer and validator.
    
    Ensures emotional tone is maintained during translation:
    - Polarity matching (positive/negative)
    - Intensity preservation
    - Emotion markers (!?, capitalization, emoji)
    """
    
    def __init__(
        self,
        min_preservation_score: float = 0.6,
    ):
        self.min_preservation_score = min_preservation_score
        
        # Emotion keywords by language (extensible)
        self.emotion_keywords = {
            "en": {
                "positive": [
                    "happy", "great", "wonderful", "excellent", "amazing", 
                    "love", "joy", "excited", "fantastic", "delighted"
                ],
                "negative": [
                    "sad", "angry", "terrible", "awful", "hate", 
                    "furious", "disappointed", "upset", "horrible", "bad"
                ],
            },
            "es": {
                "positive": [
                    "feliz", "genial", "maravilloso", "excelente", "increíble",
                    "amor", "alegría", "emocionado", "fantástico"
                ],
                "negative": [
                    "triste", "enojado", "terrible", "horrible", "odio",
                    "furioso", "decepcionado", "molesto"
                ],
            },
            # Add more languages as needed
        }
        
        # Statistics
        self.preservation_count = 0
        self.failed_preservation_count = 0
    
    def evaluate_preservation(
        self,
        original_text: str,
        translated_text: str,
        original_emotion: Optional[str] = None,
        original_emotion_confidence: Optional[float] = None,
        source_lang: str = "en",
        target_lang: str = "es",
    ) -> EmotionPreservationMetrics:
        """
        Evaluate emotion preservation between original and translated text.
        
        Args:
            original_text: Source text
            translated_text: Translated text
            original_emotion: Original emotion label (if available)
            original_emotion_confidence: Original emotion confidence
            source_lang: Source language code
            target_lang: Target language code
        
        Returns:
            EmotionPreservationMetrics with detailed scores
        """
        # Extract emotion signals from both texts
        original_signals = self._extract_emotion_signals(original_text, source_lang)
        translated_signals = self._extract_emotion_signals(translated_text, target_lang)
        
        # Compute polarity match
        polarity_match = self._check_polarity_match(
            original_signals, translated_signals
        )
        
        # Compute intensity preservation
        intensity_preserved = self._check_intensity_preservation(
            original_signals, translated_signals
        )
        
        # Check emotion markers preservation
        markers_preserved = self._check_markers_preservation(
            original_text, translated_text
        )
        
        # Estimate translated emotion (simple heuristic)
        translated_emotion_estimate = self._estimate_emotion(
            translated_signals, original_emotion
        )
        
        # Compute overall preservation score
        preservation_score = self._compute_preservation_score(
            polarity_match=polarity_match,
            intensity_preserved=intensity_preserved,
            markers_preserved=markers_preserved,
            original_emotion_confidence=original_emotion_confidence,
        )
        
        # Update statistics
        self.preservation_count += 1
        if preservation_score < self.min_preservation_score:
            self.failed_preservation_count += 1
        
        return EmotionPreservationMetrics(
            preservation_score=preservation_score,
            original_emotion=original_emotion,
            translated_emotion_estimate=translated_emotion_estimate,
            polarity_match=polarity_match,
            intensity_preserved=intensity_preserved,
            markers_preserved=markers_preserved,
        )
    
    def _extract_emotion_signals(
        self,
        text: str,
        language: str,
    ) -> Dict:
        """Extract emotion signals from text"""
        signals = {
            "polarity": "neutral",
            "intensity": 0.0,
            "exclamation_count": 0,
            "question_count": 0,
            "caps_ratio": 0.0,
            "positive_keywords": 0,
            "negative_keywords": 0,
        }
        
        # Count exclamation and question marks
        signals["exclamation_count"] = text.count("!")
        signals["question_count"] = text.count("?")
        
        # Compute capitalization ratio
        if text:
            caps_count = sum(1 for c in text if c.isupper())
            signals["caps_ratio"] = caps_count / len(text)
        
        # Count emotion keywords
        text_lower = text.lower()
        keywords = self.emotion_keywords.get(language, self.emotion_keywords.get("en", {}))
        
        if keywords:
            signals["positive_keywords"] = sum(
                1 for keyword in keywords.get("positive", [])
                if keyword in text_lower
            )
            signals["negative_keywords"] = sum(
                1 for keyword in keywords.get("negative", [])
                if keyword in text_lower
            )
        
        # Determine polarity
        if signals["positive_keywords"] > signals["negative_keywords"]:
            signals["polarity"] = "positive"
        elif signals["negative_keywords"] > signals["positive_keywords"]:
            signals["polarity"] = "negative"
        else:
            signals["polarity"] = "neutral"
        
        # Compute intensity
        signals["intensity"] = (
            signals["exclamation_count"]
            + signals["positive_keywords"]
            + signals["negative_keywords"]
            + signals["caps_ratio"] * 5
        ) / 10.0
        
        return signals
    
    def _check_polarity_match(
        self,
        original_signals: Dict,
        translated_signals: Dict,
    ) -> bool:
        """Check if polarity matches between original and translated"""
        return original_signals["polarity"] == translated_signals["polarity"]
    
    def _check_intensity_preservation(
        self,
        original_signals: Dict,
        translated_signals: Dict,
    ) -> bool:
        """Check if emotional intensity is preserved"""
        original_intensity = original_signals["intensity"]
        translated_intensity = translated_signals["intensity"]
        
        # Allow 30% variation
        intensity_diff = abs(original_intensity - translated_intensity)
        max_allowed_diff = original_intensity * 0.3
        
        return intensity_diff <= max_allowed_diff
    
    def _check_markers_preservation(
        self,
        original_text: str,
        translated_text: str,
    ) -> bool:
        """Check if emotion markers are preserved"""
        # Check exclamation marks
        original_exclamations = original_text.count("!")
        translated_exclamations = translated_text.count("!")
        
        # Allow some variation but should be similar
        if original_exclamations > 0:
            if translated_exclamations == 0:
                return False
        
        # Check capitalization (for emphasis)
        original_has_caps = any(c.isupper() for c in original_text)
        translated_has_caps = any(c.isupper() for c in translated_text)
        
        if original_has_caps and not translated_has_caps:
            return False
        
        return True
    
    def _estimate_emotion(
        self,
        signals: Dict,
        original_emotion: Optional[str],
    ) -> Optional[str]:
        """Estimate emotion from signals"""
        polarity = signals["polarity"]
        intensity = signals["intensity"]
        
        if polarity == "positive":
            if intensity > 0.5:
                return "happy" if original_emotion != "excited" else "excited"
            else:
                return "neutral"
        elif polarity == "negative":
            if intensity > 0.5:
                return "angry" if signals["exclamation_count"] > 0 else "sad"
            else:
                return "sad"
        else:
            return "neutral"
    
    def _compute_preservation_score(
        self,
        polarity_match: bool,
        intensity_preserved: bool,
        markers_preserved: bool,
        original_emotion_confidence: Optional[float],
    ) -> float:
        """Compute overall emotion preservation score"""
        score = 0.0
        
        # Polarity match (40% weight)
        if polarity_match:
            score += 0.4
        
        # Intensity preservation (30% weight)
        if intensity_preserved:
            score += 0.3
        
        # Markers preservation (30% weight)
        if markers_preserved:
            score += 0.3
        
        # Adjust by original emotion confidence
        if original_emotion_confidence:
            score = score * (0.5 + 0.5 * original_emotion_confidence)
        
        return min(1.0, max(0.0, score))
    
    def get_preservation_stats(self) -> Dict:
        """Get emotion preservation statistics"""
        return {
            "preservation_count": self.preservation_count,
            "failed_preservation_count": self.failed_preservation_count,
            "failed_preservation_rate": (
                self.failed_preservation_count / self.preservation_count
                if self.preservation_count > 0
                else 0.0
            ),
        }
