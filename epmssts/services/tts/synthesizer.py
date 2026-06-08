from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import logging
import os
import sys
import tempfile
import time
from typing import Dict, Literal, Optional

import numpy as np
import soundfile as sf
from scipy.signal import resample
import torch

logger = logging.getLogger(__name__)

try:
    from TTS.api import TTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    TTS = None

# pyttsx3 will be imported dynamically in __init__ to avoid module loading issues
PYTTSX3_AVAILABLE = True  # Assume available, check at runtime
SupportedTtsLang = Literal["en", "te", "hi"]
SupportedEmotion = Literal["neutral", "happy", "sad", "angry", "fearful"]


EMOTION_SPEED: Dict[SupportedEmotion, float] = {
    "happy": 1.05,
    "sad": 0.92,
    "angry": 1.10,
    "neutral": 1.00,
    "fearful": 0.95,
}


@dataclass
class TtsSynthesisRequest:
    text: str
    language: SupportedTtsLang
    emotion: SupportedEmotion


class TtsService:
    """
    Emotion-conditioned TTS using 3-tier fallback strategy:
    1. Coqui TTS (preferred, multilingual)
    2. pyttsx3 (Windows SAPI fallback)
    3. Synthetic tone generation (always works)

    - Supports English, Telugu, and Hindi text (voice availability depends on OS).
    - Emotion affects speaking speed only (safe, non-destructive).
    - Gracefully degrades to next tier if current engine fails.
    """

    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/your_tts",
        device: Optional[str] = None,
    ) -> None:
        self._engine_kind = "uninitialized"
        self._tts = None
        self._sample_rate = 22050
        self._pyttsx3 = None
        self._base_rate = 200

        engine_pref = os.environ.get("EPMSSTS_TTS_ENGINE", "auto").strip().lower()
        allow_coqui = engine_pref in {"auto", "coqui"}
        allow_pyttsx3 = engine_pref in {"auto", "pyttsx3"}
        allow_fallback = engine_pref in {"auto", "fallback"}

        # Coqui TTS is not reliable on Python 3.13; skip unless explicitly forced.
        if sys.version_info >= (3, 13) and engine_pref != "coqui":
            allow_coqui = False
            logger.info("Python 3.13+ detected: Coqui TTS disabled (requires build tools)")

        # pyttsx3 is now enabled for Python 3.13 - uses Windows SAPI directly
        # (Previous hang risk was resolved by properly handling engine initialization)

        # Tier 1: Try Coqui TTS
        if TTS_AVAILABLE and allow_coqui:
            if device is None:
                device = "cuda" if torch.cuda.is_available() else "cpu"

            use_gpu = device == "cuda"

            try:
                logger.info(f"Initializing Coqui TTS (device={device})...")
                # Initialize Coqui TTS model once.
                self._tts = TTS(model_name=model_name, gpu=use_gpu)

                # Try to read sample rate from underlying synthesizer, fall back to 22.05 kHz.
                default_sr = 22050
                synthesizer = getattr(self._tts, "synthesizer", None)
                sample_rate = getattr(synthesizer, "output_sample_rate", default_sr)
                self._sample_rate = int(sample_rate) if sample_rate else default_sr
                
                self._engine_kind = "coqui"
                logger.info(f"✓ Coqui TTS initialized (sample_rate={self._sample_rate})")
                return
            except Exception as exc:
                logger.warning(f"Coqui TTS initialization failed: {exc}")
                self._tts = None

        # Tier 2: Try pyttsx3
        if allow_pyttsx3:
            try:
                logger.info("Initializing pyttsx3...")
                import pyttsx3
                self._pyttsx3 = pyttsx3.init()
                
                try:
                    self._base_rate = int(self._pyttsx3.getProperty("rate") or 200)
                except Exception:
                    self._base_rate = 200
                
                self._engine_kind = "pyttsx3"
                logger.info(f"✓ pyttsx3 initialized (base_rate={self._base_rate})")
                return
            except (ImportError, Exception) as exc:
                logger.warning(f"pyttsx3 initialization failed: {exc}")
                self._pyttsx3 = None

        # Tier 3: Use synthetic fallback
        if allow_fallback:
            self._engine_kind = "fallback"
            logger.info("✓ Using synthetic tone fallback (always works)")
            return

        # No engines available
        raise RuntimeError(
            f"No TTS engine available. "
            f"Install Coqui TTS (Python <3.13) or pyttsx3. "
            f"Current Python: {sys.version_info.major}.{sys.version_info.minor}"
        )

    def _validate_request(self, request: TtsSynthesisRequest) -> None:
        if not request.text or not request.text.strip():
            raise ValueError("Text must be a non-empty string.")

        if request.language not in ("en", "te", "hi"):
            raise ValueError("Language must be one of: 'en', 'te', 'hi'.")

        if request.emotion not in EMOTION_SPEED:
            raise ValueError(
                "Emotion must be one of: 'neutral', 'happy', 'sad', 'angry', 'fearful'."
            )

    @staticmethod
    def _apply_speed(audio: np.ndarray, speed: float) -> np.ndarray:
        """
        Adjust speaking speed by resampling the waveform.

        Args:
            audio: Audio waveform (numpy array)
            speed: Speed multiplier (1.0 = normal, >1.0 = faster, <1.0 = slower)

        Returns:
            Resampled audio array
        """
        if speed == 1.0 or len(audio) == 0:
            return audio

        n_samples = max(1, int(len(audio) / speed))
        if n_samples == len(audio):
            return audio

        return resample(audio, n_samples).astype(np.float32)

    def _select_voice(self, language: SupportedTtsLang) -> None:
        """Select appropriate voice for target language (pyttsx3 only)."""
        if not self._pyttsx3:
            return

        tokens_by_lang = {
            "en": ["english", "en-", "en_"],
            "hi": ["hindi", "hi-", "hi_"],
            "te": ["telugu", "te-", "te_"],
        }
        tokens = tokens_by_lang.get(language, [])
        
        try:
            for voice in self._pyttsx3.getProperty("voices"):
                meta = f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')} {getattr(voice, 'languages', '')}".lower()
                if any(token in meta for token in tokens):
                    self._pyttsx3.setProperty("voice", voice.id)
                    logger.debug(f"Selected voice for {language}: {voice.id}")
                    return
        except Exception as exc:
            logger.debug(f"Could not select voice: {exc}")

    def synthesize(self, request: TtsSynthesisRequest) -> bytes:
        """
        Synthesize speech audio as WAV bytes.
        
        Uses 3-tier strategy: Coqui TTS → pyttsx3 → synthetic fallback
        
        Args:
            request: TtsSynthesisRequest with text, language, emotion
            
        Returns:
            WAV audio bytes
        """
        self._validate_request(request)
        
        logger.info(f"[TTS-Synth] Starting synthesis: engine={self._engine_kind}, text_len={len(request.text)}, lang={request.language}, emotion={request.emotion}")

        # Tier 1: Coqui TTS
        if self._engine_kind == "coqui" and self._tts is not None:
            logger.info(f"[TTS-Synth] Tier 1: Trying Coqui TTS...")
            try:
                wav = self._tts.tts(text=request.text)
                audio = np.asarray(wav, dtype=np.float32)

                speed = EMOTION_SPEED[request.emotion]
                audio = self._apply_speed(audio, speed)

                buf = BytesIO()
                sf.write(buf, audio, samplerate=self._sample_rate, format="WAV")
                result = buf.getvalue()
                logger.info(f"[TTS-Synth] Tier 1 SUCCESS: Coqui TTS generated {len(result)} bytes")
                return result
            except Exception as exc:
                logger.error(f"[TTS-Synth] Tier 1 FAILED: Coqui TTS: {exc}", exc_info=True)
                logger.info("Tier 1 failed, falling back to Tier 2...")

        # Tier 2: pyttsx3
        if self._engine_kind == "pyttsx3" and self._pyttsx3 is not None:
            logger.info(f"[TTS-Synth] Tier 2: Trying pyttsx3...")
            tmp_path = None
            try:
                self._select_voice(request.language)
                speed = EMOTION_SPEED[request.emotion]
                rate = max(80, int(self._base_rate * speed))
                logger.debug(f"[TTS-Synth] Setting pyttsx3 rate to {rate} (base={self._base_rate}, speed={speed})")
                
                try:
                    self._pyttsx3.setProperty("rate", rate)
                except Exception as exc:
                    logger.warning(f"[TTS-Synth] Could not set speech rate: {exc}")

                # Create temporary file for pyttsx3 output
                tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp_path = tmp_file.name
                tmp_file.close()
                logger.debug(f"[TTS-Synth] Temp file: {tmp_path}")

                logger.info(f"[TTS-Synth] Calling pyttsx3.save_to_file() with {len(request.text)} chars")
                logger.debug(f"[TTS-Synth] Text: {repr(request.text[:100])}")
                
                self._pyttsx3.save_to_file(request.text, tmp_path)
                logger.debug(f"[TTS-Synth] Calling pyttsx3.runAndWait()...")
                self._pyttsx3.runAndWait()
                logger.info(f"[TTS-Synth] pyttsx3.runAndWait() completed, waiting for file...")
                
                # Wait for file to be written with content
                wait_count = 0
                file_size = 0
                while wait_count < 20:  # Max 2 seconds
                    try:
                        file_size = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
                        logger.debug(f"[TTS-Synth] Temp file check {wait_count}/20: size={file_size} bytes")
                        if file_size > 44:  # WAV header minimum
                            logger.info(f"[TTS-Synth] File ready with {file_size} bytes")
                            break
                    except OSError as ose:
                        logger.debug(f"[TTS-Synth] Error checking file: {ose}")
                    time.sleep(0.1)
                    wait_count += 1
                
                if not os.path.exists(tmp_path):
                    logger.error(f"[TTS-Synth] pyttsx3 failed - file doesn't exist: {tmp_path}")
                    raise RuntimeError(f"pyttsx3 failed to create output file at {tmp_path}")
                
                file_size = os.path.getsize(tmp_path)
                logger.info(f"[TTS-Synth] Final pyttsx3 file size: {file_size} bytes")
                
                if file_size <= 44:
                    logger.error(f"[TTS-Synth] pyttsx3 generated invalid audio - too small: {file_size} bytes")
                    raise RuntimeError(f"pyttsx3 generated empty audio ({file_size} bytes)")
                
                # Read and return the generated audio
                with open(tmp_path, "rb") as handle:
                    audio_bytes = handle.read()
                    logger.info(f"[TTS-Synth] Read {len(audio_bytes)} bytes from temp file")
                    logger.debug(f"[TTS-Synth] First 50 bytes (hex): {audio_bytes[:50].hex()}")
                    return audio_bytes
                    
            except Exception as exc:
                logger.error(f"[TTS-Synth] Tier 2 FAILED: pyttsx3: {exc}", exc_info=True)
                logger.info("Tier 2 failed, falling back to Tier 3...")
            finally:
                # Clean up temporary file
                if tmp_path:
                    try:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                            logger.debug(f"[TTS-Synth] Cleaned up temp file: {tmp_path}")
                    except Exception as exc:
                        logger.debug(f"[TTS-Synth] Could not delete temp file: {exc}")

        # Tier 3: Synthetic fallback (always works)
        logger.warning(f"[TTS-Synth] Tier 3: Using synthetic fallback (no working TTS engine)")
        result = self._synthesize_fallback(request)
        logger.info(f"[TTS-Synth] Tier 3 generated {len(result)} bytes")
        return result

    def _synthesize_fallback(self, request: TtsSynthesisRequest) -> bytes:
        """
        Generate synthetic tone-based WAV as last-resort fallback.
        
        This tier always succeeds and guarantees audio output.
        Useful for testing and when TTS engines are unavailable.
        
        Args:
            request: TtsSynthesisRequest
            
        Returns:
            WAV audio bytes (always succeeds)
        """
        logger.info(f"[TTS-Fallback] Generating synthetic audio: text_len={len(request.text)}")
        try:
            # Duration based on text length (longer text = longer audio)
            word_count = max(1, len(request.text.split()))
            duration = max(0.6, min(3.0, 0.06 * word_count + 0.4))
            sr = int(self._sample_rate or 22050)
            
            logger.debug(f"[TTS-Fallback] Audio params: duration={duration:.2f}s, sr={sr}Hz, words={word_count}")
            
            # Generate time array
            t = np.linspace(0, duration, int(sr * duration), endpoint=False)
            
            # Base frequency depends on text (deterministic)
            base_freq = 220 + (abs(hash(request.text)) % 120)
            logger.debug(f"[TTS-Fallback] Generating sine wave: freq={base_freq}Hz")
            
            # Generate sine wave
            audio = 0.2 * np.sin(2 * np.pi * base_freq * t).astype(np.float32)

            # Apply emotion-based speed
            speed = EMOTION_SPEED[request.emotion]
            audio = self._apply_speed(audio, speed)
            logger.debug(f"[TTS-Fallback] Applied emotion speed: {speed}x")

            # Encode as WAV
            buf = BytesIO()
            sf.write(buf, audio, samplerate=sr, format="WAV")
            
            audio_bytes = buf.getvalue()
            logger.info(f"[TTS-Fallback] SUCCESS: Generated {len(audio_bytes)} bytes")
            return audio_bytes
            
        except Exception as exc:
            logger.error(f"[TTS-Fallback] FAILED (this should never happen): {exc}", exc_info=True)
            # Ultimate fallback: Generate empty silence to at least return valid WAV
            logger.warning("[TTS-Fallback] Returning silence as last resort")
            sr = 22050
            silence = np.zeros(sr, dtype=np.float32)  # 1 second of silence
            buf = BytesIO()
            sf.write(buf, silence, samplerate=sr, format="WAV")
            return buf.getvalue()


__all__ = ["TtsService", "TtsSynthesisRequest", "SupportedTtsLang", "SupportedEmotion"]

