"""
Audio Emotion Models Ensemble

Implements Wav2Vec2 + HuBERT ensemble for robust audio-based emotion recognition.
Production-grade inference with uncertainty quantification.
"""

import logging
import torch
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime
from transformers import (
    Wav2Vec2ForSequenceClassification,
    Wav2Vec2Processor,
    HubertForSequenceClassification,
    Wav2Vec2FeatureExtractor,
)

from .exceptions import AudioModelLoadError, ModelInferenceError
from .schemas import ModelPrediction


logger = logging.getLogger(__name__)


class AudioEmotionModel:
    """
    Base class for audio emotion classification models.
    
    Provides common interface for Wav2Vec2, HuBERT, and other audio models.
    """
    
    def __init__(self, model_name: str, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.model = None
        self.processor = None
        self.is_loaded = False
        self.inference_count = 0
        self.total_inference_time_ms = 0.0
        
        # Emotion label mapping (model-specific, to be set by subclass)
        self.label_map = {}
    
    def load(self):
        """Load model and processor - implemented by subclasses"""
        raise NotImplementedError
    
    def preprocess(self, audio: np.ndarray, sample_rate: int) -> torch.Tensor:
        """Preprocess audio for model - implemented by subclasses"""
        raise NotImplementedError
    
    def predict(self, audio: np.ndarray, sample_rate: int) -> ModelPrediction:
        """Run inference and return structured prediction"""
        raise NotImplementedError
    
    def _compute_entropy(self, probs: np.ndarray) -> float:
        """Compute Shannon entropy of probability distribution"""
        # Avoid log(0)
        probs_safe = np.clip(probs, 1e-10, 1.0)
        entropy = -np.sum(probs_safe * np.log(probs_safe))
        return float(entropy)
    
    def _compute_confidence(self, probs: np.ndarray) -> float:
        """Compute model confidence as max probability"""
        return float(np.max(probs))


class Wav2Vec2EmotionModel(AudioEmotionModel):
    """
    Wav2Vec2-based emotion recognition model.
    
    Uses pre-trained Wav2Vec2 fine-tuned on emotion datasets.
    """
    
    def __init__(
        self,
        model_name: str = "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
        device: str = "cpu",
    ):
        super().__init__(model_name=model_name, device=device)
        
        # Standard emotion label mapping for this model
        self.label_map = {
            0: "angry",
            1: "happy",
            2: "neutral",
            3: "sad",
            4: "excited",  # May map to 'happy' in some models
        }
    
    def load(self):
        """Load Wav2Vec2 model and processor"""
        try:
            logger.info(f"Loading Wav2Vec2 model: {self.model_name}")
            
            self.processor = Wav2Vec2Processor.from_pretrained(self.model_name)
            self.model = Wav2Vec2ForSequenceClassification.from_pretrained(
                self.model_name
            )
            self.model.to(self.device)
            self.model.eval()
            
            self.is_loaded = True
            logger.info(f"Wav2Vec2 model loaded successfully on {self.device}")
            
        except Exception as e:
            raise AudioModelLoadError(
                f"Failed to load Wav2Vec2 model: {e}",
                model_name=self.model_name,
            )
    
    def preprocess(self, audio: np.ndarray, sample_rate: int) -> torch.Tensor:
        """Preprocess audio for Wav2Vec2"""
        # Ensure audio is 1D
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)
        
        # Resample to 16kHz if needed (Wav2Vec2 expects 16kHz)
        target_sr = 16000
        if sample_rate != target_sr:
            import librosa
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=target_sr)
        
        # Process audio
        inputs = self.processor(
            audio,
            sampling_rate=target_sr,
            return_tensors="pt",
            padding=True,
        )
        
        return inputs.input_values.to(self.device)
    
    def predict(self, audio: np.ndarray, sample_rate: int) -> ModelPrediction:
        """Run Wav2Vec2 inference"""
        if not self.is_loaded:
            raise ModelInferenceError(
                "Model not loaded",
                model_name=self.model_name,
            )
        
        start_time = datetime.now()
        
        try:
            # Preprocess
            input_values = self.preprocess(audio, sample_rate)
            
            # Inference
            with torch.no_grad():
                logits = self.model(input_values).logits
            
            # Softmax to get probabilities
            probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]
            
            # Map to emotion labels
            probabilities = {}
            for idx, prob in enumerate(probs):
                label = self.label_map.get(idx, f"class_{idx}")
                probabilities[label] = float(prob)
            
            # Compute entropy and confidence
            entropy = self._compute_entropy(probs)
            confidence = self._compute_confidence(probs)
            
            # Timing
            inference_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.inference_count += 1
            self.total_inference_time_ms += inference_time_ms
            
            return ModelPrediction(
                probabilities=probabilities,
                entropy=entropy,
                model_confidence=confidence,
                model_name="wav2vec2",
                inference_time_ms=inference_time_ms,
            )
        
        except Exception as e:
            raise ModelInferenceError(
                f"Wav2Vec2 inference failed: {e}",
                model_name=self.model_name,
                original_error=e,
            )


class HubertEmotionModel(AudioEmotionModel):
    """
    HuBERT-based emotion recognition model (secondary/ensemble model).
    
    Provides additional signal for ensemble robustness.
    """
    
    def __init__(
        self,
        model_name: str = "superb/hubert-base-superb-er",
        device: str = "cpu",
    ):
        super().__init__(model_name=model_name, device=device)
        
        # Standard emotion label mapping
        self.label_map = {
            0: "neutral",
            1: "happy",
            2: "sad",
            3: "angry",
        }
    
    def load(self):
        """Load HuBERT model"""
        try:
            logger.info(f"Loading HuBERT model: {self.model_name}")
            
            self.processor = Wav2Vec2FeatureExtractor.from_pretrained(self.model_name)
            self.model = HubertForSequenceClassification.from_pretrained(
                self.model_name
            )
            self.model.to(self.device)
            self.model.eval()
            
            self.is_loaded = True
            logger.info(f"HuBERT model loaded successfully on {self.device}")
            
        except Exception as e:
            # HuBERT is secondary - log warning but don't fail hard
            logger.warning(f"Failed to load HuBERT model: {e}")
            raise AudioModelLoadError(
                f"Failed to load HuBERT model: {e}",
                model_name=self.model_name,
            )
    
    def preprocess(self, audio: np.ndarray, sample_rate: int) -> torch.Tensor:
        """Preprocess audio for HuBERT"""
        # Ensure audio is 1D
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)
        
        # Resample to 16kHz
        target_sr = 16000
        if sample_rate != target_sr:
            import librosa
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=target_sr)
        
        # Process audio
        inputs = self.processor(
            audio,
            sampling_rate=target_sr,
            return_tensors="pt",
            padding=True,
        )
        
        return inputs.input_values.to(self.device)
    
    def predict(self, audio: np.ndarray, sample_rate: int) -> ModelPrediction:
        """Run HuBERT inference"""
        if not self.is_loaded:
            raise ModelInferenceError(
                "Model not loaded",
                model_name=self.model_name,
            )
        
        start_time = datetime.now()
        
        try:
            # Preprocess
            input_values = self.preprocess(audio, sample_rate)
            
            # Inference
            with torch.no_grad():
                logits = self.model(input_values).logits
            
            # Softmax
            probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]
            
            # Map to labels
            probabilities = {}
            for idx, prob in enumerate(probs):
                label = self.label_map.get(idx, f"class_{idx}")
                probabilities[label] = float(prob)
            
            # Compute metrics
            entropy = self._compute_entropy(probs)
            confidence = self._compute_confidence(probs)
            
            # Timing
            inference_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.inference_count += 1
            self.total_inference_time_ms += inference_time_ms
            
            return ModelPrediction(
                probabilities=probabilities,
                entropy=entropy,
                model_confidence=confidence,
                model_name="hubert",
                inference_time_ms=inference_time_ms,
            )
        
        except Exception as e:
            raise ModelInferenceError(
                f"HuBERT inference failed: {e}",
                model_name=self.model_name,
                original_error=e,
            )


class AudioEnsemble:
    """
    Ensemble of audio emotion models for robust prediction.
    
    Combines Wav2Vec2 (primary) and HuBERT (secondary) for improved reliability.
    """
    
    def __init__(self, device: str = "cpu", use_secondary: bool = True):
        self.device = device
        self.use_secondary = use_secondary
        
        # Primary model (always used)
        self.primary_model = Wav2Vec2EmotionModel(device=device)
        
        # Secondary model (optional, for ensemble robustness)
        self.secondary_model = None
        if use_secondary:
            try:
                self.secondary_model = HubertEmotionModel(device=device)
            except Exception as e:
                logger.warning(f"Secondary model unavailable: {e}")
                self.use_secondary = False
        
        self.is_initialized = False
    
    def load_models(self):
        """Load all ensemble models"""
        logger.info("Loading audio ensemble models...")
        
        # Load primary
        self.primary_model.load()
        
        # Load secondary if enabled
        if self.use_secondary and self.secondary_model:
            try:
                self.secondary_model.load()
            except Exception as e:
                logger.warning(f"Secondary model load failed, continuing with primary only: {e}")
                self.use_secondary = False
        
        self.is_initialized = True
        logger.info(f"Audio ensemble initialized (primary + {1 if self.use_secondary else 0} secondary)")
    
    def predict(self, audio: np.ndarray, sample_rate: int) -> Tuple[ModelPrediction, Optional[ModelPrediction]]:
        """
        Run ensemble prediction.
        
        Returns:
            Tuple of (primary_prediction, secondary_prediction)
            secondary_prediction is None if not available
        """
        if not self.is_initialized:
            raise ModelInferenceError("Ensemble not initialized")
        
        # Primary prediction (always)
        primary_pred = self.primary_model.predict(audio, sample_rate)
        
        # Secondary prediction (if available)
        secondary_pred = None
        if self.use_secondary and self.secondary_model and self.secondary_model.is_loaded:
            try:
                secondary_pred = self.secondary_model.predict(audio, sample_rate)
            except Exception as e:
                logger.warning(f"Secondary model prediction failed: {e}")
        
        return primary_pred, secondary_pred
    
    def get_model_status(self) -> Dict[str, bool]:
        """Get status of all models in ensemble"""
        return {
            "primary_loaded": self.primary_model.is_loaded,
            "secondary_loaded": (
                self.secondary_model.is_loaded
                if self.secondary_model
                else False
            ),
            "ensemble_ready": self.is_initialized,
        }
