"""
Text Emotion Model

DistilRoBERTa-based emotion classification from transcribed text.
Language-aware with multi-lingual support.
"""

import logging
import torch
from typing import Dict, Optional
from datetime import datetime
from transformers import pipeline, AutoModelForSequenceClassification, AutoTokenizer

from .exceptions import TextModelLoadError, ModelInferenceError
from .schemas import ModelPrediction


logger = logging.getLogger(__name__)


class TextEmotionModel:
    """
    Text-based emotion classifier using DistilRoBERTa.
    
    Provides emotion prediction from transcript text with language detection.
    """
    
    def __init__(
        self,
        model_name: str = "j-hartmann/emotion-english-distilroberta-base",
        device: str = "cpu",
    ):
        self.model_name = model_name
        self.device = device
        self.model = None
        self.tokenizer = None
        self.pipeline = None
        self.is_loaded = False
        
        self.inference_count = 0
        self.total_inference_time_ms = 0.0
        
        # Emotion label mapping (model outputs these directly)
        self.supported_emotions = [
            "anger",
            "disgust",
            "fear",
            "joy",
            "neutral",
            "sadness",
            "surprise",
        ]
        
        # Map to our standard labels
        self.label_mapping = {
            "anger": "angry",
            "joy": "happy",
            "sadness": "sad",
            "neutral": "neutral",
            "disgust": "angry",  # Map disgust to angry
            "fear": "sad",       # Map fear to sad
            "surprise": "happy", # Map surprise to happy
        }
    
    def load(self):
        """Load text emotion model"""
        try:
            logger.info(f"Loading text emotion model: {self.model_name}")
            
            # Load tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name
            )
            self.model.to(self.device)
            self.model.eval()
            
            # Create pipeline for convenience
            self.pipeline = pipeline(
                "text-classification",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if self.device == "cuda" else -1,
                return_all_scores=True,
            )
            
            self.is_loaded = True
            logger.info(f"Text emotion model loaded successfully on {self.device}")
            
        except Exception as e:
            raise TextModelLoadError(
                f"Failed to load text emotion model: {e}",
                model_name=self.model_name,
            )
    
    def predict(
        self,
        text: str,
        language: Optional[str] = None,
        min_confidence: float = 0.1,
    ) -> ModelPrediction:
        """
        Predict emotion from text.
        
        Args:
            text: Input transcript
            language: Optional language code (e.g., "en", "es")
            min_confidence: Minimum confidence threshold
        
        Returns:
            ModelPrediction with probabilities mapped to standard labels
        """
        if not self.is_loaded:
            raise ModelInferenceError(
                "Model not loaded",
                model_name=self.model_name,
            )
        
        # Language check (currently supports English primarily)
        if language and language not in ["en", "eng", "english", None]:
            logger.warning(f"Language '{language}' may not be optimal for this model")
        
        # Handle empty/short text
        if not text or len(text.strip()) < 3:
            logger.warning("Text too short for reliable emotion prediction")
            return self._default_prediction()
        
        start_time = datetime.now()
        
        try:
            # Run inference
            results = self.pipeline(text[:512])[0]  # Limit to 512 tokens
            
            # Convert to probabilities dict
            raw_probs = {}
            for item in results:
                label = item["label"].lower()
                score = item["score"]
                raw_probs[label] = score
            
            # Map to standard emotion labels
            mapped_probs = self._map_to_standard_labels(raw_probs)
            
            # Compute entropy and confidence
            import numpy as np
            probs_array = np.array(list(mapped_probs.values()))
            entropy = self._compute_entropy(probs_array)
            confidence = float(np.max(probs_array))
            
            # Timing
            inference_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.inference_count += 1
            self.total_inference_time_ms += inference_time_ms
            
            return ModelPrediction(
                probabilities=mapped_probs,
                entropy=entropy,
                model_confidence=confidence,
                model_name="distilroberta",
                inference_time_ms=inference_time_ms,
            )
        
        except Exception as e:
            raise ModelInferenceError(
                f"Text model inference failed: {e}",
                model_name=self.model_name,
                original_error=e,
            )
    
    def _map_to_standard_labels(self, raw_probs: Dict[str, float]) -> Dict[str, float]:
        """
        Map model-specific labels to standard emotion labels.
        
        Aggregates probabilities for mapped labels (e.g., disgust + anger → angry).
        """
        mapped = {
            "angry": 0.0,
            "happy": 0.0,
            "neutral": 0.0,
            "sad": 0.0,
        }
        
        for raw_label, prob in raw_probs.items():
            standard_label = self.label_mapping.get(raw_label, "neutral")
            mapped[standard_label] += prob
        
        # Renormalize if needed
        total = sum(mapped.values())
        if total > 0:
            mapped = {k: v / total for k, v in mapped.items()}
        
        return mapped
    
    def _default_prediction(self) -> ModelPrediction:
        """Return default neutral prediction for empty/invalid text"""
        return ModelPrediction(
            probabilities={
                "angry": 0.0,
                "happy": 0.0,
                "neutral": 1.0,
                "sad": 0.0,
            },
            entropy=0.0,
            model_confidence=1.0,
            model_name="distilroberta",
            inference_time_ms=0.0,
        )
    
    def _compute_entropy(self, probs) -> float:
        """Compute Shannon entropy"""
        import numpy as np
        probs_safe = np.clip(probs, 1e-10, 1.0)
        entropy = -np.sum(probs_safe * np.log(probs_safe))
        return float(entropy)
    
    def detect_language(self, text: str) -> Optional[str]:
        """
        Detect language of input text (basic implementation).
        
        For production, integrate with langdetect or fastText.
        """
        # Placeholder - in production, use proper language detection
        # For now, assume English if text contains common English words
        common_english = ["the", "is", "are", "you", "and", "to", "a", "of"]
        text_lower = text.lower()
        
        english_word_count = sum(1 for word in common_english if word in text_lower)
        
        if english_word_count >= 2:
            return "en"
        
        return None  # Unknown language
