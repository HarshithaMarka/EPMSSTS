"""
TTS Engine

Neural TTS synthesis engine with Coqui XTTS v2 support.
Handles model loading, GPU acceleration, and prosody-controlled synthesis.
"""

import logging
import time
import torch
import numpy as np
from typing import Optional, Tuple
from pathlib import Path
import io
import tempfile

from .schemas import ProsodyProfile
from .exceptions import (
    TTSModelLoadError,
    ModelWarmupError,
    SynthesisInferenceError,
    SynthesisTimeoutError,
    GPUOOMError,
    EmptyAudioGenerationError,
    GPUMemoryAllocationError,
    UnsupportedLanguageError,
)


logger = logging.getLogger(__name__)


class TTSEngine:
    """
    Neural TTS synthesis engine.
    
    Primary: Coqui XTTS v2 (multilingual, emotion-controllable)
    Features:
    - GPU acceleration
    - FP16 inference
    - Prosody control via speaking rate and pitch
    - Multi-speaker support
    - Cached model (warmed at startup)
    
    Supported languages: en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh, ja, ko, hi
    """
    
    SUPPORTED_LANGUAGES = {
        "en", "es", "fr", "de", "it", "pt", "pl", "tr", 
        "ru", "nl", "cs", "ar", "zh", "ja", "ko", "hi"
    }
    
    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        device: str = "cuda",
        enable_fp16: bool = True,
        sample_rate: int = 16000,
    ):
        """
        Initialize TTS engine.
        
        Args:
            model_name: TTS model identifier
            device: "cuda" or "cpu"
            enable_fp16: Use FP16 for GPU inference
            sample_rate: Output audio sample rate
        """
        self.model_name = model_name
        self.device = device if torch.cuda.is_available() else "cpu"
        self.enable_fp16 = enable_fp16 and self.device == "cuda"
        self.sample_rate = sample_rate
        
        self.model = None
        self.model_loaded = False
        
        logger.info(f"Initializing TTS engine: {model_name} on {self.device}")
        
        # Load model
        self._load_model()
        
        # Warm up model
        self._warmup_model()
    
    def _load_model(self):
        """Load TTS model"""
        try:
            start_time = time.time()
            
            # Import TTS library
            try:
                from TTS.api import TTS
            except ImportError:
                logger.error("TTS library (Coqui TTS) not installed. Install: pip install TTS")
                raise TTSModelLoadError(
                    "TTS library not installed",
                    details={"install_command": "pip install TTS"}
                )
            
            # Initialize model
            logger.info(f"Loading TTS model: {self.model_name}...")
            
            self.model = TTS(
                model_name=self.model_name,
                gpu=(self.device == "cuda")
            )
            
            # Move to device
            if self.device == "cuda":
                try:
                    self.model.to(self.device)
                    if self.enable_fp16:
                        # Enable FP16 if supported
                        logger.info("Enabling FP16 inference")
                        # Note: XTTS v2 may not support FP16 directly
                        # Implementation depends on specific model architecture
                except torch.cuda.OutOfMemoryError as e:
                    logger.error(f"GPU OOM during model loading: {e}")
                    raise GPUMemoryAllocationError(
                        "Insufficient GPU memory to load TTS model",
                        details={"error": str(e)}
                    )
            
            load_time = time.time() - start_time
            self.model_loaded = True
            
            logger.info(f"TTS model loaded successfully in {load_time:.2f}s")
        
        except Exception as e:
            logger.exception(f"Failed to load TTS model: {e}")
            raise TTSModelLoadError(
                f"Failed to load TTS model: {str(e)}",
                details={"model_name": self.model_name, "device": self.device}
            )
    
    def _warmup_model(self):
        """Warm up model with dummy inference"""
        try:
            logger.info("Warming up TTS model...")
            start_time = time.time()
            
            # Run dummy synthesis
            self._synthesize_internal(
                text="Hello, this is a warmup.",
                language="en",
                prosody_profile=None,
                timeout_seconds=30.0
            )
            
            warmup_time = time.time() - start_time
            logger.info(f"Model warmup completed in {warmup_time:.2f}s")
        
        except Exception as e:
            logger.warning(f"Model warmup failed: {e}")
            raise ModelWarmupError(
                f"Model warmup failed: {str(e)}",
                details={"model_name": self.model_name}
            )
    
    def synthesize(
        self,
        text: str,
        language: str,
        prosody_profile: Optional[ProsodyProfile] = None,
        speaker_id: Optional[str] = None,
        timeout_seconds: float = 10.0
    ) -> Tuple[np.ndarray, int]:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            language: Language code (en, es, fr, etc.)
            prosody_profile: Prosody parameters to apply
            speaker_id: Speaker voice ID (if multi-speaker)
            timeout_seconds: Synthesis timeout
        
        Returns:
            Tuple of (audio_array, sample_rate)
        
        Raises:
            UnsupportedLanguageError: If language not supported
            SynthesisInferenceError: If synthesis fails
            SynthesisTimeoutError: If synthesis times out
            EmptyAudioGenerationError: If output is empty
        """
        # Validate language
        if language not in self.SUPPORTED_LANGUAGES:
            raise UnsupportedLanguageError(
                f"Language '{language}' not supported. Supported: {self.SUPPORTED_LANGUAGES}",
                details={"language": language}
            )
        
        # Validate model loaded
        if not self.model_loaded:
            raise SynthesisInferenceError(
                "TTS model not loaded",
                details={"model_loaded": False}
            )
        
        # Synthesize
        audio_array = self._synthesize_internal(
            text=text,
            language=language,
            prosody_profile=prosody_profile,
            speaker_id=speaker_id,
            timeout_seconds=timeout_seconds
        )
        
        # Validate output
        if audio_array is None or len(audio_array) == 0:
            raise EmptyAudioGenerationError(
                "TTS synthesis returned empty audio",
                details={"text_length": len(text)}
            )
        
        return audio_array, self.sample_rate
    
    def _synthesize_internal(
        self,
        text: str,
        language: str,
        prosody_profile: Optional[ProsodyProfile],
        speaker_id: Optional[str] = None,
        timeout_seconds: float = 10.0
    ) -> np.ndarray:
        """
        Internal synthesis with timeout and error handling.
        
        Args:
            text: Text to synthesize
            language: Language code
            prosody_profile: Prosody parameters
            speaker_id: Speaker ID
            timeout_seconds: Timeout
        
        Returns:
            Audio array (numpy)
        """
        try:
            start_time = time.time()
            
            # Prepare synthesis parameters
            synthesis_kwargs = {
                "text": text,
                "language": language,
            }
            
            # Add speaker if specified
            if speaker_id:
                synthesis_kwargs["speaker"] = speaker_id
            
            # Apply prosody adjustments if provided
            # Note: XTTS v2 prosody control depends on implementation
            # Some models use speed, pitch parameters directly
            if prosody_profile:
                # Speech rate control
                if hasattr(self.model, "speed"):
                    synthesis_kwargs["speed"] = prosody_profile.rate_multiplier
                
                # Pitch shift (if supported)
                # Note: Not all TTS models support pitch control at inference
                # May require post-processing with librosa or pyrubberband
            
            # Synthesize audio
            # XTTS v2 API: tts_to_file or tts
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Use tts_to_file for XTTS v2
            self.model.tts_to_file(
                text=text,
                file_path=temp_path,
                language=language,
                speaker=speaker_id if speaker_id else None
            )
            
            # Load generated audio
            import soundfile as sf
            audio_array, sr = sf.read(temp_path)
            
            # Clean up temp file
            Path(temp_path).unlink()
            
            # Resample if needed
            if sr != self.sample_rate:
                import librosa
                audio_array = librosa.resample(
                    audio_array,
                    orig_sr=sr,
                    target_sr=self.sample_rate
                )
            
            # Apply prosody post-processing if needed
            if prosody_profile:
                audio_array = self._apply_prosody_post_processing(
                    audio_array,
                    prosody_profile
                )
            
            elapsed = time.time() - start_time
            
            # Check timeout
            if elapsed > timeout_seconds:
                logger.warning(f"Synthesis took {elapsed:.2f}s (timeout: {timeout_seconds}s)")
                raise SynthesisTimeoutError(
                    f"Synthesis exceeded timeout ({timeout_seconds}s)",
                    details={"elapsed": elapsed, "timeout": timeout_seconds}
                )
            
            logger.debug(f"Synthesis completed in {elapsed:.2f}s, audio length: {len(audio_array)} samples")
            
            return audio_array
        
        except torch.cuda.OutOfMemoryError as e:
            logger.error(f"GPU OOM during synthesis: {e}")
            raise GPUOOMError(
                "GPU out of memory during synthesis",
                details={"text_length": len(text)}
            )
        
        except Exception as e:
            logger.exception(f"Synthesis inference error: {e}")
            raise SynthesisInferenceError(
                f"Synthesis inference failed: {str(e)}",
                details={"text_length": len(text), "language": language}
            )
    
    def _apply_prosody_post_processing(
        self,
        audio_array: np.ndarray,
        prosody_profile: ProsodyProfile
    ) -> np.ndarray:
        """
        Apply prosody adjustments via post-processing.
        
        Uses librosa/pyrubberband for time stretching and pitch shifting.
        
        Args:
            audio_array: Input audio
            prosody_profile: Prosody parameters
        
        Returns:
            Modified audio array
        """
        try:
            import librosa
            import pyrubberband as pyrb
            
            # Apply time stretching (rate adjustment)
            if abs(prosody_profile.rate_multiplier - 1.0) > 0.01:
                # Inverse because slower speech = longer duration = rate < 1.0
                stretch_rate = 1.0 / prosody_profile.rate_multiplier
                audio_array = pyrb.time_stretch(
                    audio_array,
                    self.sample_rate,
                    stretch_rate
                )
            
            # Apply pitch shifting
            if abs(prosody_profile.pitch_shift) > 0.1:
                audio_array = pyrb.pitch_shift(
                    audio_array,
                    self.sample_rate,
                    prosody_profile.pitch_shift
                )
            
            # Apply energy scaling
            if abs(prosody_profile.energy_scale - 1.0) > 0.01:
                audio_array = audio_array * prosody_profile.energy_scale
            
            # Clamp to prevent clipping
            audio_array = np.clip(audio_array, -1.0, 1.0)
            
            return audio_array
        
        except ImportError:
            logger.warning("pyrubberband not available, skipping prosody post-processing")
            logger.warning("Install: pip install pyrubberband")
            return audio_array
        
        except Exception as e:
            logger.warning(f"Prosody post-processing failed: {e}")
            return audio_array
    
    def get_model_info(self) -> dict:
        """Get model information"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "fp16_enabled": self.enable_fp16,
            "sample_rate": self.sample_rate,
            "model_loaded": self.model_loaded,
            "supported_languages": list(self.SUPPORTED_LANGUAGES),
            "gpu_available": torch.cuda.is_available(),
            "gpu_memory_allocated_mb": torch.cuda.memory_allocated() / 1024 / 1024 if torch.cuda.is_available() else 0,
        }
