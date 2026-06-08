"""
Prosody Mapper

Maps emotion labels to calibrated prosody parameters.
Controls speech rate, pitch, energy, and pitch variance.
"""

import logging
from typing import Dict, Optional
from dataclasses import dataclass

from .schemas import ProsodyProfile
from .exceptions import InvalidEmotionLabelError, InvalidProsodyParametersError


logger = logging.getLogger(__name__)


@dataclass
class EmotionProsodyMapping:
    """Calibrated prosody parameters for each emotion"""
    
    rate_multiplier: float  # Speech rate (1.0 = normal)
    pitch_shift: float  # Pitch shift in semitones
    energy_scale: float  # Energy/volume scale
    pitch_variance: float  # Pitch variance multiplier
    description: str


class ProsodyMapper:
    """
    Maps emotions to prosody parameters.
    
    Prosody dimensions:
    - Rate: Speech speed (0.8 = slower, 1.2 = faster)
    - Pitch: Baseline pitch shift in semitones (-2 to +3)
    - Energy: Volume/intensity scale (0.8 to 1.5)
    - Pitch Variance: Intonation expressiveness (0.8 to 1.3)
    
    Emotion mappings are calibrated to:
    - Preserve intelligibility
    - Avoid distortion
    - Sound natural
    - Match emotion perception
    """
    
    # Calibrated prosody mappings for each emotion
    EMOTION_MAPPINGS: Dict[str, EmotionProsodyMapping] = {
        "happy": EmotionProsodyMapping(
            rate_multiplier=1.08,  # 8% faster
            pitch_shift=1.5,  # Slight pitch lift
            energy_scale=1.15,  # Brighter, more energetic
            pitch_variance=1.2,  # More expressive intonation
            description="Upbeat, energetic, positive tone"
        ),
        
        "sad": EmotionProsodyMapping(
            rate_multiplier=0.90,  # 10% slower
            pitch_shift=-1.5,  # Lower pitch
            energy_scale=0.85,  # Softer, less intense
            pitch_variance=0.8,  # Flatter intonation
            description="Subdued, melancholic, lower energy"
        ),
        
        "angry": EmotionProsodyMapping(
            rate_multiplier=1.12,  # 12% faster (urgent)
            pitch_shift=0.5,  # Slightly higher pitch
            energy_scale=1.35,  # Louder, more forceful
            pitch_variance=1.25,  # More pitch variation (emphasis)
            description="Intense, forceful, emphatic"
        ),
        
        "neutral": EmotionProsodyMapping(
            rate_multiplier=1.0,  # Normal speed
            pitch_shift=0.0,  # No pitch shift
            energy_scale=1.0,  # Normal energy
            pitch_variance=1.0,  # Normal variance
            description="Natural, balanced, conversational"
        ),
        
        "excited": EmotionProsodyMapping(
            rate_multiplier=1.15,  # 15% faster (enthusiastic)
            pitch_shift=2.0,  # Higher pitch
            energy_scale=1.25,  # More energetic
            pitch_variance=1.3,  # Very expressive
            description="Enthusiastic, animated, high energy"
        ),
        
        "fear": EmotionProsodyMapping(
            rate_multiplier=1.10,  # Slightly faster (anxious)
            pitch_shift=1.0,  # Higher pitch (tension)
            energy_scale=0.95,  # Slightly reduced
            pitch_variance=1.15,  # More variation (nervousness)
            description="Anxious, tense, uncertain"
        ),
        
        "surprise": EmotionProsodyMapping(
            rate_multiplier=1.05,  # Slightly faster
            pitch_shift=2.5,  # Higher pitch (exclamation)
            energy_scale=1.15,  # More energetic
            pitch_variance=1.25,  # Expressive
            description="Unexpected, sudden, exclamatory"
        ),
        
        "disgust": EmotionProsodyMapping(
            rate_multiplier=0.95,  # Slightly slower
            pitch_shift=-0.5,  # Slightly lower
            energy_scale=0.90,  # Reduced energy
            pitch_variance=0.9,  # Less variance
            description="Aversive, repelled, negative"
        ),
    }
    
    # Boundary constraints for prosody parameters
    RATE_MIN = 0.7
    RATE_MAX = 1.3
    PITCH_SHIFT_MIN = -3.0
    PITCH_SHIFT_MAX = 3.5
    ENERGY_MIN = 0.7
    ENERGY_MAX = 1.5
    VARIANCE_MIN = 0.7
    VARIANCE_MAX = 1.4
    
    def __init__(self):
        """Initialize prosody mapper"""
        logger.info(f"Prosody mapper initialized with {len(self.EMOTION_MAPPINGS)} emotion mappings")
    
    def map_emotion_to_prosody(
        self,
        emotion_label: Optional[str],
        emotion_confidence: Optional[float] = None,
        intensity_multiplier: float = 1.0
    ) -> ProsodyProfile:
        """
        Map emotion label to prosody parameters.
        
        Args:
            emotion_label: Emotion label (happy, sad, angry, etc.)
            emotion_confidence: Confidence score (0-1). Lower confidence = less prosody intensity
            intensity_multiplier: Overall prosody intensity (0-2). User-controllable.
        
        Returns:
            ProsodyProfile with calibrated parameters
        
        Raises:
            InvalidEmotionLabelError: If emotion label not recognized
        """
        # Default to neutral if no emotion
        if not emotion_label:
            emotion_label = "neutral"
        
        emotion_label = emotion_label.lower()
        
        # Validate emotion
        if emotion_label not in self.EMOTION_MAPPINGS:
            raise InvalidEmotionLabelError(
                f"Emotion '{emotion_label}' not recognized. Valid emotions: {list(self.EMOTION_MAPPINGS.keys())}"
            )
        
        # Get base prosody mapping
        mapping = self.EMOTION_MAPPINGS[emotion_label]
        
        # Calculate effective intensity
        # If emotion_confidence is low, reduce prosody intensity
        confidence_factor = emotion_confidence if emotion_confidence is not None else 1.0
        effective_intensity = intensity_multiplier * confidence_factor
        
        # Apply intensity scaling
        # Neutral parameters remain neutral
        # Non-neutral parameters scale towards neutral at low intensity
        rate = self._scale_parameter(
            neutral=1.0,
            target=mapping.rate_multiplier,
            intensity=effective_intensity
        )
        
        pitch = self._scale_parameter(
            neutral=0.0,
            target=mapping.pitch_shift,
            intensity=effective_intensity
        )
        
        energy = self._scale_parameter(
            neutral=1.0,
            target=mapping.energy_scale,
            intensity=effective_intensity
        )
        
        variance = self._scale_parameter(
            neutral=1.0,
            target=mapping.pitch_variance,
            intensity=effective_intensity
        )
        
        # Enforce boundary constraints
        rate = self._clamp(rate, self.RATE_MIN, self.RATE_MAX)
        pitch = self._clamp(pitch, self.PITCH_SHIFT_MIN, self.PITCH_SHIFT_MAX)
        energy = self._clamp(energy, self.ENERGY_MIN, self.ENERGY_MAX)
        variance = self._clamp(variance, self.VARIANCE_MIN, self.VARIANCE_MAX)
        
        profile = ProsodyProfile(
            rate_multiplier=rate,
            pitch_shift=pitch,
            energy_scale=energy,
            pitch_variance=variance,
            emotion_intensity=effective_intensity
        )
        
        logger.debug(
            f"Mapped emotion '{emotion_label}' (confidence={confidence_factor:.2f}, "
            f"intensity={intensity_multiplier:.2f}) to prosody: "
            f"rate={rate:.2f}, pitch={pitch:.2f}, energy={energy:.2f}, variance={variance:.2f}"
        )
        
        return profile
    
    def _scale_parameter(self, neutral: float, target: float, intensity: float) -> float:
        """
        Scale parameter from neutral to target based on intensity.
        
        Args:
            neutral: Neutral value (no emotion)
            target: Target value (full emotion)
            intensity: Intensity factor (0-2)
        
        Returns:
            Scaled parameter value
        """
        # Linear interpolation from neutral to target
        # intensity=0 → neutral
        # intensity=1 → target
        # intensity>1 → beyond target (but clamped later)
        return neutral + (target - neutral) * intensity
    
    def _clamp(self, value: float, min_val: float, max_val: float) -> float:
        """Clamp value to range [min_val, max_val]"""
        return max(min_val, min(max_val, value))
    
    def get_emotion_description(self, emotion_label: str) -> str:
        """Get human-readable description of emotion prosody"""
        emotion_label = emotion_label.lower()
        if emotion_label in self.EMOTION_MAPPINGS:
            return self.EMOTION_MAPPINGS[emotion_label].description
        return "Unknown emotion"
    
    def get_supported_emotions(self) -> list:
        """Get list of supported emotion labels"""
        return list(self.EMOTION_MAPPINGS.keys())
    
    def validate_prosody_profile(self, profile: ProsodyProfile) -> bool:
        """
        Validate prosody profile parameters are within safe bounds.
        
        Args:
            profile: ProsodyProfile to validate
        
        Returns:
            True if valid, False otherwise
        
        Raises:
            InvalidProsodyParametersError: If parameters out of bounds
        """
        errors = []
        
        if not (self.RATE_MIN <= profile.rate_multiplier <= self.RATE_MAX):
            errors.append(f"Rate {profile.rate_multiplier} out of bounds [{self.RATE_MIN}, {self.RATE_MAX}]")
        
        if not (self.PITCH_SHIFT_MIN <= profile.pitch_shift <= self.PITCH_SHIFT_MAX):
            errors.append(f"Pitch shift {profile.pitch_shift} out of bounds [{self.PITCH_SHIFT_MIN}, {self.PITCH_SHIFT_MAX}]")
        
        if not (self.ENERGY_MIN <= profile.energy_scale <= self.ENERGY_MAX):
            errors.append(f"Energy {profile.energy_scale} out of bounds [{self.ENERGY_MIN}, {self.ENERGY_MAX}]")
        
        if not (self.VARIANCE_MIN <= profile.pitch_variance <= self.VARIANCE_MAX):
            errors.append(f"Variance {profile.pitch_variance} out of bounds [{self.VARIANCE_MIN}, {self.VARIANCE_MAX}]")
        
        if errors:
            raise InvalidProsodyParametersError(
                "Prosody parameters out of bounds",
                details={"errors": errors}
            )
        
        return True
    
    def get_prosody_stats(self) -> Dict:
        """Get statistics about prosody mappings"""
        return {
            "total_emotions": len(self.EMOTION_MAPPINGS),
            "supported_emotions": list(self.EMOTION_MAPPINGS.keys()),
            "rate_range": [self.RATE_MIN, self.RATE_MAX],
            "pitch_range": [self.PITCH_SHIFT_MIN, self.PITCH_SHIFT_MAX],
            "energy_range": [self.ENERGY_MIN, self.ENERGY_MAX],
            "variance_range": [self.VARIANCE_MIN, self.VARIANCE_MAX],
        }
