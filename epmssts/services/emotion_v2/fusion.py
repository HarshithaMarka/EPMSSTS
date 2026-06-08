"""
Adaptive Fusion Engine

Dynamic Bayesian fusion of audio and text emotion predictions.
NO fixed weights - adapts per request based on signal quality.
"""

import logging
import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from .exceptions import FusionError, EnsembleDisagreementError
from .schemas import FusionWeights


logger = logging.getLogger(__name__)


@dataclass
class FusionConfig:
    """Configuration for adaptive fusion"""
    
    # Weight computation parameters
    entropy_weight_factor: float = 0.3
    stt_confidence_weight_factor: float = 0.25
    quality_score_weight_factor: float = 0.2
    energy_band_weight_factor: float = 0.15
    
    # Disagreement thresholds
    max_kl_divergence: float = 1.5  # Alert if KL divergence exceeds this
    max_disagreement_score: float = 0.6  # Alert if disagreement exceeds this
    
    # Fusion method
    default_fusion_method: str = "bayesian"  # "bayesian", "weighted_average", "max_confidence"
    
    # Prior weights (starting point, will be adjusted dynamically)
    prior_audio_weight: float = 0.65
    prior_text_weight: float = 0.35


class AdaptiveFusionEngine:
    """
    Adaptive fusion of audio and text emotion predictions.
    
    Uses Bayesian-style dynamic weighting:
        P(final) ∝ P(audio)^α × P(text)^β
    
    Where α (audio_weight) and β (text_weight) are computed dynamically based on:
        - Audio entropy (low entropy → higher audio weight)
        - Text entropy (low entropy → higher text weight)
        - STT confidence (high confidence → higher text weight)
        - Audio quality score (high quality → higher audio weight)
        - Energy band (high energy → higher audio weight)
    
    NO FIXED WEIGHTS. Every request gets custom fusion weights.
    """
    
    def __init__(self, config: Optional[FusionConfig] = None):
        self.config = config or FusionConfig()
        
        # Track fusion statistics
        self.fusion_count = 0
        self.high_disagreement_count = 0
        self.audio_dominant_count = 0
        self.text_dominant_count = 0
        self.balanced_fusion_count = 0
    
    def fuse(
        self,
        audio_probs: Dict[str, float],
        text_probs: Dict[str, float],
        audio_entropy: float,
        text_entropy: float,
        stt_confidence: float,
        quality_score: float,
        energy_band: Optional[str] = None,
        audio_confidence: Optional[float] = None,
        text_confidence: Optional[float] = None,
    ) -> Tuple[Dict[str, float], FusionWeights]:
        """
        Fuse audio and text predictions with adaptive weighting.
        
        Args:
            audio_probs: Audio model probabilities
            text_probs: Text model probabilities
            audio_entropy: Entropy of audio prediction
            text_entropy: Entropy of text prediction
            stt_confidence: STT confidence score (0-1)
            quality_score: Audio quality score (0-1)
            energy_band: Energy band ("low", "medium", "high")
            audio_confidence: Optional audio model confidence
            text_confidence: Optional text model confidence
        
        Returns:
            Tuple of (fused_probabilities, fusion_weights)
        """
        try:
            # Step 1: Compute dynamic weights
            fusion_weights = self._compute_adaptive_weights(
                audio_entropy=audio_entropy,
                text_entropy=text_entropy,
                stt_confidence=stt_confidence,
                quality_score=quality_score,
                energy_band=energy_band,
                audio_confidence=audio_confidence,
                text_confidence=text_confidence,
            )
            
            # Step 2: Check disagreement
            disagreement_score = self._compute_disagreement(audio_probs, text_probs)
            kl_div = self._compute_kl_divergence(audio_probs, text_probs)
            
            if disagreement_score > self.config.max_disagreement_score:
                logger.warning(
                    f"High ensemble disagreement detected: {disagreement_score:.3f} "
                    f"(KL divergence: {kl_div:.3f})"
                )
                self.high_disagreement_count += 1
            
            # Step 3: Perform fusion
            if self.config.default_fusion_method == "bayesian":
                fused_probs = self._bayesian_fusion(
                    audio_probs,
                    text_probs,
                    fusion_weights.audio_weight,
                    fusion_weights.text_weight,
                )
            elif self.config.default_fusion_method == "weighted_average":
                fused_probs = self._weighted_average_fusion(
                    audio_probs,
                    text_probs,
                    fusion_weights.audio_weight,
                    fusion_weights.text_weight,
                )
            else:
                fused_probs = self._max_confidence_fusion(
                    audio_probs,
                    text_probs,
                    audio_confidence or 0.5,
                    text_confidence or 0.5,
                )
            
            # Step 4: Track statistics
            self.fusion_count += 1
            self._update_fusion_stats(fusion_weights)
            
            return fused_probs, fusion_weights
        
        except Exception as e:
            raise FusionError(
                f"Fusion failed: {e}",
                audio_probs=audio_probs,
                text_probs=text_probs,
            )
    
    def _compute_adaptive_weights(
        self,
        audio_entropy: float,
        text_entropy: float,
        stt_confidence: float,
        quality_score: float,
        energy_band: Optional[str],
        audio_confidence: Optional[float],
        text_confidence: Optional[float],
    ) -> FusionWeights:
        """
        Compute dynamic fusion weights based on signal quality indicators.
        
        Returns FusionWeights with α (audio_weight) and β (text_weight).
        """
        # Start with prior weights
        audio_weight = self.config.prior_audio_weight
        text_weight = self.config.prior_text_weight
        
        weight_factors = {}
        
        # Factor 1: Entropy-based adjustment
        # Lower entropy → higher weight (more confident prediction)
        entropy_factor_audio = np.exp(-audio_entropy)  # Low entropy → high factor
        entropy_factor_text = np.exp(-text_entropy)
        
        audio_weight += self.config.entropy_weight_factor * (entropy_factor_audio - 0.5)
        text_weight += self.config.entropy_weight_factor * (entropy_factor_text - 0.5)
        
        weight_factors["entropy_audio"] = float(entropy_factor_audio)
        weight_factors["entropy_text"] = float(entropy_factor_text)
        
        # Factor 2: STT confidence adjustment
        # High STT confidence → boost text weight (transcript is reliable)
        stt_factor = stt_confidence - 0.5  # Center around 0.5
        text_weight += self.config.stt_confidence_weight_factor * stt_factor
        audio_weight -= self.config.stt_confidence_weight_factor * stt_factor * 0.5
        
        weight_factors["stt_confidence"] = stt_confidence
        
        # Factor 3: Audio quality adjustment
        # High quality → boost audio weight
        quality_factor = quality_score - 0.5
        audio_weight += self.config.quality_score_weight_factor * quality_factor
        text_weight -= self.config.quality_score_weight_factor * quality_factor * 0.5
        
        weight_factors["quality_score"] = quality_score
        
        # Factor 4: Energy band adjustment
        # High energy → boost audio weight (more signal)
        if energy_band == "high":
            audio_weight += self.config.energy_band_weight_factor
            text_weight -= self.config.energy_band_weight_factor * 0.3
            weight_factors["energy_band_boost"] = 0.15
        elif energy_band == "low":
            audio_weight -= self.config.energy_band_weight_factor * 0.5
            text_weight += self.config.energy_band_weight_factor * 0.3
            weight_factors["energy_band_boost"] = -0.075
        else:
            weight_factors["energy_band_boost"] = 0.0
        
        # Factor 5: Model confidence adjustment (if available)
        if audio_confidence and text_confidence:
            conf_diff = audio_confidence - text_confidence
            audio_weight += 0.1 * conf_diff
            text_weight -= 0.1 * conf_diff
            
            weight_factors["audio_confidence"] = audio_confidence
            weight_factors["text_confidence"] = text_confidence
        
        # Normalize weights to sum to 1.0
        total = audio_weight + text_weight
        audio_weight /= total
        text_weight /= total
        
        # Clamp weights (never let one signal dominate too much)
        audio_weight = np.clip(audio_weight, 0.2, 0.8)
        text_weight = 1.0 - audio_weight
        
        return FusionWeights(
            audio_weight=float(audio_weight),
            text_weight=float(text_weight),
            fusion_method=self.config.default_fusion_method,
            weight_factors=weight_factors,
        )
    
    def _bayesian_fusion(
        self,
        audio_probs: Dict[str, float],
        text_probs: Dict[str, float],
        alpha: float,
        beta: float,
    ) -> Dict[str, float]:
        """
        Bayesian fusion: P(final) ∝ P(audio)^α × P(text)^β
        
        Args:
            audio_probs: Audio probabilities
            text_probs: Text probabilities
            alpha: Audio weight exponent
            beta: Text weight exponent
        """
        fused = {}
        
        # Get common labels
        all_labels = set(audio_probs.keys()) | set(text_probs.keys())
        
        for label in all_labels:
            p_audio = audio_probs.get(label, 1e-10)
            p_text = text_probs.get(label, 1e-10)
            
            # Bayesian product
            fused[label] = (p_audio ** alpha) * (p_text ** beta)
        
        # Normalize
        total = sum(fused.values())
        fused = {k: v / total for k, v in fused.items()}
        
        return fused
    
    def _weighted_average_fusion(
        self,
        audio_probs: Dict[str, float],
        text_probs: Dict[str, float],
        audio_weight: float,
        text_weight: float,
    ) -> Dict[str, float]:
        """Simple weighted average fusion"""
        fused = {}
        
        all_labels = set(audio_probs.keys()) | set(text_probs.keys())
        
        for label in all_labels:
            p_audio = audio_probs.get(label, 0.0)
            p_text = text_probs.get(label, 0.0)
            
            fused[label] = audio_weight * p_audio + text_weight * p_text
        
        # Normalize (should already sum to 1, but just in case)
        total = sum(fused.values())
        if total > 0:
            fused = {k: v / total for k, v in fused.items()}
        
        return fused
    
    def _max_confidence_fusion(
        self,
        audio_probs: Dict[str, float],
        text_probs: Dict[str, float],
        audio_confidence: float,
        text_confidence: float,
    ) -> Dict[str, float]:
        """Select prediction from model with higher confidence"""
        if audio_confidence >= text_confidence:
            return audio_probs
        else:
            return text_probs
    
    def _compute_disagreement(
        self,
        audio_probs: Dict[str, float],
        text_probs: Dict[str, float],
    ) -> float:
        """
        Compute disagreement score between audio and text predictions.
        
        Returns value in [0, 1] where 0 = perfect agreement, 1 = maximum disagreement.
        """
        # Get predicted labels
        audio_label = max(audio_probs, key=audio_probs.get)
        text_label = max(text_probs, key=text_probs.get)
        
        # If labels disagree, compute probability mass difference
        if audio_label != text_label:
            audio_conf = audio_probs[audio_label]
            text_conf = text_probs[text_label]
            
            # Disagreement = average of how confident each model is in different labels
            disagreement = (audio_conf + text_conf) / 2.0
        else:
            # Labels agree - compute distribution similarity
            # Even if labels match, distributions might differ
            disagreement = self._compute_distribution_distance(audio_probs, text_probs)
        
        return float(disagreement)
    
    def _compute_distribution_distance(
        self,
        probs1: Dict[str, float],
        probs2: Dict[str, float],
    ) -> float:
        """Compute L1 distance between probability distributions"""
        all_labels = set(probs1.keys()) | set(probs2.keys())
        
        distance = 0.0
        for label in all_labels:
            p1 = probs1.get(label, 0.0)
            p2 = probs2.get(label, 0.0)
            distance += abs(p1 - p2)
        
        # L1 distance ranges from 0 to 2, normalize to [0, 1]
        return distance / 2.0
    
    def _compute_kl_divergence(
        self,
        probs1: Dict[str, float],
        probs2: Dict[str, float],
    ) -> float:
        """Compute KL divergence between probability distributions"""
        all_labels = set(probs1.keys()) | set(probs2.keys())
        
        kl_div = 0.0
        for label in all_labels:
            p = probs1.get(label, 1e-10)
            q = probs2.get(label, 1e-10)
            
            kl_div += p * np.log(p / q)
        
        return float(kl_div)
    
    def _update_fusion_stats(self, weights: FusionWeights):
        """Update fusion statistics based on computed weights"""
        if weights.audio_weight > 0.6:
            self.audio_dominant_count += 1
        elif weights.text_weight > 0.6:
            self.text_dominant_count += 1
        else:
            self.balanced_fusion_count += 1
    
    def get_fusion_stats(self) -> Dict[str, any]:
        """Get fusion statistics"""
        return {
            "total_fusions": self.fusion_count,
            "high_disagreement_count": self.high_disagreement_count,
            "audio_dominant_count": self.audio_dominant_count,
            "text_dominant_count": self.text_dominant_count,
            "balanced_fusion_count": self.balanced_fusion_count,
            "audio_dominant_pct": (
                self.audio_dominant_count / self.fusion_count * 100
                if self.fusion_count > 0
                else 0.0
            ),
            "text_dominant_pct": (
                self.text_dominant_count / self.fusion_count * 100
                if self.fusion_count > 0
                else 0.0
            ),
        }
