"""
Fallback Handler

Manages TTS fallback chain with retry logic.
Ensures audio is always generated, never returns silence.

Fallback chain:
1. Primary TTS Engine (Coqui XTTS v2)
2. Retry with modified parameters (once)
3. Secondary lightweight TTS (gTTS or similar)
4. System TTS (pyttsx3)
5. Structured failure (never empty)
"""

import logging
import time
from typing import Optional, Tuple
import numpy as np

from .tts_engine import TTSEngine
from .schemas import ProsodyProfile, FallbackInfo
from .waveform_validator import WaveformValidator
from .exceptions import (
    FallbackChainExhaustedError,
    AllEnginesUnavailableError,
    RetryLimitExceededError,
    TTSServiceError,
)


logger = logging.getLogger(__name__)


class FallbackHandler:
    """
    Manages TTS engine fallback chain.
    
    Strategy:
    1. Try primary engine (XTTS v2)
    2. If validation fails: retry once with modified params
    3. If still fails: try secondary engine (gTTS)
    4. If still fails: try system TTS (pyttsx3)
    5. Never return empty/silent audio
    
    Each fallback is tracked for monitoring.
    """
    
    def __init__(
        self,
        primary_engine: TTSEngine,
        validator: WaveformValidator,
        enable_retry: bool = True,
        enable_secondary: bool = True,
        enable_system_tts: bool = True,
        max_retries: int = 1,
    ):
        """
        Initialize fallback handler.
        
        Args:
            primary_engine: Primary TTS engine
            validator: Waveform validator
            enable_retry: Enable retry on primary engine
            enable_secondary: Enable secondary engine fallback
            enable_system_tts: Enable system TTS fallback
            max_retries: Maximum retry attempts on primary
        """
        self.primary_engine = primary_engine
        self.validator = validator
        self.enable_retry = enable_retry
        self.enable_secondary = enable_secondary
        self.enable_system_tts = enable_system_tts
        self.max_retries = max_retries
        
        # Statistics
        self.primary_success_count = 0
        self.retry_success_count = 0
        self.secondary_success_count = 0
        self.system_tts_success_count = 0
        self.total_attempts = 0
        
        logger.info(f"Fallback handler initialized: retry={enable_retry}, "
                   f"secondary={enable_secondary}, system_tts={enable_system_tts}")
    
    def synthesize_with_fallback(
        self,
        text: str,
        language: str,
        prosody_profile: Optional[ProsodyProfile] = None,
        speaker_id: Optional[str] = None,
        timeout_seconds: float = 10.0
    ) -> Tuple[np.ndarray, int, FallbackInfo]:
        """
        Synthesize with fallback chain.
        
        Args:
            text: Text to synthesize
            language: Language code
            prosody_profile: Prosody parameters
            speaker_id: Speaker ID
            timeout_seconds: Synthesis timeout
        
        Returns:
            Tuple of (audio_array, sample_rate, fallback_info)
        
        Raises:
            FallbackChainExhaustedError: If all fallback options fail
        """
        self.total_attempts += 1
        retry_count = 0
        primary_error = None
        
        # Attempt 1: Primary engine
        try:
            logger.info("Attempting primary TTS engine (XTTS v2)...")
            audio, sr = self.primary_engine.synthesize(
                text=text,
                language=language,
                prosody_profile=prosody_profile,
                speaker_id=speaker_id,
                timeout_seconds=timeout_seconds
            )
            
            # Validate audio
            metrics = self.validator.validate(audio, sr)
            
            if metrics.is_valid:
                self.primary_success_count += 1
                fallback_info = FallbackInfo(
                    fallback_used=False,
                    primary_engine_error=None,
                    engine_used="primary_xtts_v2",
                    retry_count=0
                )
                logger.info("Primary TTS engine succeeded")
                return audio, sr, fallback_info
            else:
                primary_error = f"Validation failed: {metrics.validation_errors}"
                logger.warning(f"Primary engine validation failed: {primary_error}")
        
        except Exception as e:
            primary_error = str(e)
            logger.warning(f"Primary TTS engine failed: {primary_error}")
        
        # Attempt 2: Retry with modified parameters (if enabled)
        if self.enable_retry and retry_count < self.max_retries:
            try:
                logger.info("Retrying primary engine with modified prosody...")
                retry_count += 1
                
                # Modify prosody for retry (reduce intensity)
                retry_prosody = self._adjust_prosody_for_retry(prosody_profile)
                
                audio, sr = self.primary_engine.synthesize(
                    text=text,
                    language=language,
                    prosody_profile=retry_prosody,
                    speaker_id=speaker_id,
                    timeout_seconds=timeout_seconds
                )
                
                # Validate
                metrics = self.validator.validate(audio, sr)
                
                if metrics.is_valid:
                    self.retry_success_count += 1
                    fallback_info = FallbackInfo(
                        fallback_used=True,
                        primary_engine_error=primary_error,
                        engine_used="primary_xtts_v2_retry",
                        retry_count=retry_count
                    )
                    logger.info("Primary TTS engine retry succeeded")
                    return audio, sr, fallback_info
                else:
                    logger.warning(f"Retry validation failed: {metrics.validation_errors}")
            
            except Exception as e:
                logger.warning(f"Primary engine retry failed: {e}")
        
        # Attempt 3: Secondary engine (gTTS)
        if self.enable_secondary:
            try:
                logger.info("Falling back to secondary engine (gTTS)...")
                audio, sr = self._synthesize_with_gtts(text, language)
                
                # Validate
                metrics = self.validator.validate(audio, sr)
                
                if metrics.is_valid:
                    self.secondary_success_count += 1
                    fallback_info = FallbackInfo(
                        fallback_used=True,
                        primary_engine_error=primary_error,
                        engine_used="secondary_gtts",
                        retry_count=retry_count
                    )
                    logger.info("Secondary TTS engine (gTTS) succeeded")
                    return audio, sr, fallback_info
                else:
                    logger.warning(f"gTTS validation failed: {metrics.validation_errors}")
            
            except Exception as e:
                logger.warning(f"Secondary engine (gTTS) failed: {e}")
        
        # Attempt 4: System TTS (pyttsx3)
        if self.enable_system_tts:
            try:
                logger.info("Falling back to system TTS (pyttsx3)...")
                audio, sr = self._synthesize_with_pyttsx3(text, language)
                
                # Validate (relaxed thresholds for system TTS)
                metrics = self.validator.validate(audio, sr)
                
                if metrics.is_valid or metrics.rms_amplitude > 0.001:  # More lenient
                    self.system_tts_success_count += 1
                    fallback_info = FallbackInfo(
                        fallback_used=True,
                        primary_engine_error=primary_error,
                        engine_used="system_pyttsx3",
                        retry_count=retry_count
                    )
                    logger.info("System TTS (pyttsx3) succeeded")
                    return audio, sr, fallback_info
                else:
                    logger.warning(f"System TTS validation failed: {metrics.validation_errors}")
            
            except Exception as e:
                logger.warning(f"System TTS (pyttsx3) failed: {e}")
        
        # All fallbacks exhausted
        logger.error(f"All TTS engines failed for text: '{text[:50]}...'")
        raise FallbackChainExhaustedError(
            "All TTS fallback engines failed",
            details={
                "primary_error": primary_error,
                "retry_count": retry_count,
                "text_length": len(text)
            }
        )
    
    def _adjust_prosody_for_retry(
        self,
        prosody_profile: Optional[ProsodyProfile]
    ) -> Optional[ProsodyProfile]:
        """
        Adjust prosody parameters for retry.
        
        Strategy: Reduce intensity towards neutral to avoid synthesis issues.
        
        Args:
            prosody_profile: Original prosody profile
        
        Returns:
            Modified prosody profile
        """
        if prosody_profile is None:
            return None
        
        # Reduce towards neutral
        return ProsodyProfile(
            rate_multiplier=(prosody_profile.rate_multiplier + 1.0) / 2,
            pitch_shift=prosody_profile.pitch_shift * 0.5,
            energy_scale=(prosody_profile.energy_scale + 1.0) / 2,
            pitch_variance=(prosody_profile.pitch_variance + 1.0) / 2,
            emotion_intensity=prosody_profile.emotion_intensity * 0.5
        )
    
    def _synthesize_with_gtts(self, text: str, language: str) -> Tuple[np.ndarray, int]:
        """
        Synthesize with gTTS (Google Text-to-Speech).
        
        Args:
            text: Text to synthesize
            language: Language code (ISO 639-1)
        
        Returns:
            Tuple of (audio_array, sample_rate)
        """
        try:
            from gtts import gTTS
            import tempfile
            import soundfile as sf
            from pathlib import Path
            
            # Map language codes (gTTS uses 2-letter codes)
            lang_map = {
                "en": "en", "es": "es", "fr": "fr", "de": "de",
                "it": "it", "pt": "pt", "ru": "ru", "zh": "zh",
                "ja": "ja", "ko": "ko", "hi": "hi", "ar": "ar"
            }
            gtts_lang = lang_map.get(language, "en")
            
            # Synthesize with gTTS
            tts = gTTS(text=text, lang=gtts_lang, slow=False)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_path = temp_file.name
            
            tts.save(temp_path)
            
            # Load audio
            audio, sr = sf.read(temp_path)
            
            # Clean up
            Path(temp_path).unlink()
            
            # Resample to 16kHz if needed
            if sr != 16000:
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
                sr = 16000
            
            # Convert to mono if stereo
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)
            
            return audio, sr
        
        except ImportError:
            logger.error("gTTS not installed. Install: pip install gtts")
            raise
        except Exception as e:
            logger.error(f"gTTS synthesis failed: {e}")
            raise
    
    def _synthesize_with_pyttsx3(self, text: str, language: str) -> Tuple[np.ndarray, int]:
        """
        Synthesize with pyttsx3 (system TTS).
        
        Args:
            text: Text to synthesize
            language: Language code
        
        Returns:
            Tuple of (audio_array, sample_rate)
        """
        try:
            import pyttsx3
            import tempfile
            import soundfile as sf
            from pathlib import Path
            
            # Initialize pyttsx3
            engine = pyttsx3.init()
            
            # Set rate and volume
            engine.setProperty('rate', 150)  # Normal speed
            engine.setProperty('volume', 0.9)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
            
            engine.save_to_file(text, temp_path)
            engine.runAndWait()
            
            # Load audio
            audio, sr = sf.read(temp_path)
            
            # Clean up
            Path(temp_path).unlink()
            
            # Resample to 16kHz if needed
            if sr != 16000:
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
                sr = 16000
            
            # Convert to mono if stereo
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)
            
            return audio, sr
        
        except ImportError:
            logger.error("pyttsx3 not installed. Install: pip install pyttsx3")
            raise
        except Exception as e:
            logger.error(f"pyttsx3 synthesis failed: {e}")
            raise
    
    def get_fallback_stats(self) -> dict:
        """Get fallback statistics"""
        return {
            "total_attempts": self.total_attempts,
            "primary_success_count": self.primary_success_count,
            "retry_success_count": self.retry_success_count,
            "secondary_success_count": self.secondary_success_count,
            "system_tts_success_count": self.system_tts_success_count,
            "fallback_rate": (
                (self.retry_success_count + self.secondary_success_count + self.system_tts_success_count)
                / max(self.total_attempts, 1)
            ),
            "primary_success_rate": self.primary_success_count / max(self.total_attempts, 1),
        }
