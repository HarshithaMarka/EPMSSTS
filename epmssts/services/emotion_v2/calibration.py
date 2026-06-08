"""
Calibration Layer

Temperature scaling and per-class threshold adjustments for emotion probabilities.
Prevents overconfidence, neutral collapse, and volume bias.
"""

import logging
import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from .exceptions import CalibrationError, ConfidenceCollapseError
from .schemas import CalibrationInfo


logger = logging.getLogger(__name__)


@dataclass
class CalibrationConfig:
    """Configuration for calibration layer"""
    
    # Temperature scaling (T > 1 = more conservative, T < 1 = sharper)
    temperature_audio: float = 1.5
    temperature_text: float = 1.3
    
    # Per-class threshold adjustments (add to probability before selecting)
    class_adjustments: Dict[str, float] = None
    
    # Neutral collapse prevention
    neutral_penalty: float = 0.1  # Reduce neutral probability by this amount
    max_neutral_prob: float = 0.7  # Cap neutral at this value
    
    # Volume bias correction
    volume_bias_threshold: float = 0.3  # Low volume detection threshold
    sad_boost_on_low_volume: float = 0.15  # Boost sad on low volume (whisper detection)
    
    # Confidence floor
    min_confidence_floor: float = 0.25  # Minimum probability for winning class
    
    def __post_init__(self):
        if self.class_adjustments is None:
            # Default adjustments to balance classes
            self.class_adjustments = {
                "angry": 0.0,
                "happy": 0.0,
                "neutral": -0.1,  # Penalize neutral (avoid collapse)
                "sad": 0.05,       # Slight boost to sad (often underrepresented)
            }


class CalibrationLayer:
    """
    Calibrates emotion probabilities using temperature scaling and thresholding.
    
    Addresses:
    - Overconfidence (temperature scaling)
    - Neutral collapse (penalize neutral)
    - Volume bias (boost sad on low volume)
    - Class imbalance (per-class adjustments)
    """
    
    def __init__(self, config: Optional[CalibrationConfig] = None):
        self.config = config or CalibrationConfig()
        
        # Track calibration statistics
        self.calibration_count = 0
        self.neutral_collapses_prevented = 0
        self.volume_bias_corrections = 0
    
    def calibrate_audio_probs(
        self,
        probs: Dict[str, float],
        volume_level: Optional[float] = None,
        energy_band: Optional[str] = None,
    ) -> Tuple[Dict[str, float], CalibrationInfo]:
        """
        Calibrate audio model probabilities.
        
        Args:
            probs: Raw probabilities from audio model
            volume_level: Optional volume level (0-1 scale)
            energy_band: Optional energy band ("low", "medium", "high")
        
        Returns:
            Tuple of (calibrated_probs, calibration_info)
        """
        try:
            # Step 1: Temperature scaling
            scaled_probs = self._apply_temperature(
                probs,
                temperature=self.config.temperature_audio,
            )
            
            # Step 2: Volume bias correction (whisper sadness detection)
            if volume_level is not None and volume_level < self.config.volume_bias_threshold:
                scaled_probs = self._correct_volume_bias(scaled_probs, volume_level)
                self.volume_bias_corrections += 1
            elif energy_band == "low":
                # Also apply if energy band is explicitly low
                scaled_probs = self._correct_volume_bias(scaled_probs, 0.2)
                self.volume_bias_corrections += 1
            
            # Step 3: Neutral collapse prevention
            scaled_probs, neutral_capped = self._prevent_neutral_collapse(scaled_probs)
            if neutral_capped:
                self.neutral_collapses_prevented += 1
            
            # Step 4: Per-class adjustments
            adjusted_probs = self._apply_class_adjustments(scaled_probs)
            
            # Step 5: Renormalize
            final_probs = self._normalize(adjusted_probs)
            
            # Step 6: Confidence floor enforcement
            final_probs = self._apply_confidence_floor(final_probs)
            
            self.calibration_count += 1
            
            # Build calibration info
            info = CalibrationInfo(
                temperature=self.config.temperature_audio,
                class_adjustments=self.config.class_adjustments,
                neutral_penalty_applied=neutral_capped,
                volume_bias_corrected=(
                    volume_level is not None
                    and volume_level < self.config.volume_bias_threshold
                ),
            )
            
            return final_probs, info
        
        except Exception as e:
            raise CalibrationError(
                f"Audio calibration failed: {e}",
                original_probabilities=probs,
            )
    
    def calibrate_text_probs(
        self,
        probs: Dict[str, float],
    ) -> Tuple[Dict[str, float], CalibrationInfo]:
        """
        Calibrate text model probabilities.
        
        Args:
            probs: Raw probabilities from text model
        
        Returns:
            Tuple of (calibrated_probs, calibration_info)
        """
        try:
            # Step 1: Temperature scaling
            scaled_probs = self._apply_temperature(
                probs,
                temperature=self.config.temperature_text,
            )
            
            # Step 2: Neutral collapse prevention
            scaled_probs, neutral_capped = self._prevent_neutral_collapse(scaled_probs)
            
            # Step 3: Per-class adjustments
            adjusted_probs = self._apply_class_adjustments(scaled_probs)
            
            # Step 4: Renormalize
            final_probs = self._normalize(adjusted_probs)
            
            # Step 5: Confidence floor
            final_probs = self._apply_confidence_floor(final_probs)
            
            info = CalibrationInfo(
                temperature=self.config.temperature_text,
                class_adjustments=self.config.class_adjustments,
                neutral_penalty_applied=neutral_capped,
                volume_bias_corrected=False,
            )
            
            return final_probs, info
        
        except Exception as e:
            raise CalibrationError(
                f"Text calibration failed: {e}",
                original_probabilities=probs,
            )
    
    def _apply_temperature(
        self,
        probs: Dict[str, float],
        temperature: float,
    ) -> Dict[str, float]:
        """Apply temperature scaling to probabilities"""
        # Convert to logits (inverse softmax)
        logits = {}
        for label, prob in probs.items():
            # Prevent log(0)
            prob_safe = max(prob, 1e-10)
            logits[label] = np.log(prob_safe)
        
        # Scale by temperature
        scaled_logits = {k: v / temperature for k, v in logits.items()}
        
        # Apply softmax
        exp_logits = {k: np.exp(v) for k, v in scaled_logits.items()}
        total = sum(exp_logits.values())
        scaled_probs = {k: v / total for k, v in exp_logits.items()}
        
        return scaled_probs
    
    def _prevent_neutral_collapse(
        self,
        probs: Dict[str, float],
    ) -> Tuple[Dict[str, float], bool]:
        """
        Prevent neutral class from dominating.
        
        Returns:
            Tuple of (adjusted_probs, neutral_was_capped)
        """
        neutral_prob = probs.get("neutral", 0.0)
        neutral_capped = False
        
        # Check if neutral is too high
        if neutral_prob > self.config.max_neutral_prob:
            # Cap neutral
            probs["neutral"] = self.config.max_neutral_prob
            neutral_capped = True
            
            # Redistribute excess probability to other classes
            excess = neutral_prob - self.config.max_neutral_prob
            other_labels = [k for k in probs.keys() if k != "neutral"]
            
            if other_labels:
                boost_per_label = excess / len(other_labels)
                for label in other_labels:
                    probs[label] += boost_per_label
        
        return probs, neutral_capped
    
    def _correct_volume_bias(
        self,
        probs: Dict[str, float],
        volume_level: float,
    ) -> Dict[str, float]:
        """
        Correct for volume bias (whisper sadness detection).
        
        Low volume audio often misclassified as neutral - boost sad probability.
        """
        # Compute volume correction factor (stronger correction for lower volume)
        correction_factor = 1.0 - volume_level  # 0-1 scale
        sad_boost = self.config.sad_boost_on_low_volume * correction_factor
        
        # Boost sad, reduce neutral
        probs["sad"] = probs.get("sad", 0.0) + sad_boost
        probs["neutral"] = max(0.0, probs.get("neutral", 0.0) - sad_boost * 0.5)
        
        return probs
    
    def _apply_class_adjustments(
        self,
        probs: Dict[str, float],
    ) -> Dict[str, float]:
        """Apply per-class threshold adjustments"""
        adjusted = {}
        for label, prob in probs.items():
            adjustment = self.config.class_adjustments.get(label, 0.0)
            adjusted[label] = max(0.0, prob + adjustment)
        
        return adjusted
    
    def _normalize(self, probs: Dict[str, float]) -> Dict[str, float]:
        """Renormalize probabilities to sum to 1.0"""
        total = sum(probs.values())
        if total > 0:
            return {k: v / total for k, v in probs.items()}
        else:
            # Fallback to uniform distribution
            n = len(probs)
            return {k: 1.0 / n for k in probs.keys()}
    
    def _apply_confidence_floor(
        self,
        probs: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Ensure winning class has minimum confidence.
        
        If max probability < floor, fall back to neutral.
        """
        max_prob = max(probs.values())
        
        if max_prob < self.config.min_confidence_floor:
            logger.warning(
                f"Confidence below floor ({max_prob:.3f} < {self.config.min_confidence_floor}), "
                "falling back to neutral"
            )
            # Fall back to neutral-dominant distribution
            return {
                "angry": 0.1,
                "happy": 0.1,
                "neutral": 0.6,
                "sad": 0.2,
            }
        
        return probs
    
    def get_calibration_stats(self) -> Dict[str, int]:
        """Get calibration statistics"""
        return {
            "total_calibrations": self.calibration_count,
            "neutral_collapses_prevented": self.neutral_collapses_prevented,
            "volume_bias_corrections": self.volume_bias_corrections,
        }
