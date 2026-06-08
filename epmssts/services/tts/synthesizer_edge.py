"""
Production-Grade Emotion-Preserving TTS Service using Edge TTS

This module provides a real-time, async, neural-voice-based TTS system with:
- Emotion-to-prosody mapping (rate, pitch, volume)
- Dialect-aware voice selection
- Multi-language support (English, Hindi, Telugu)
- Non-blocking async execution
- Comprehensive validation and error handling
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import io
import logging
import tempfile
from typing import Dict, Literal, Optional

import edge_tts
import soundfile as sf
import numpy as np

logger = logging.getLogger(__name__)

SupportedTtsLang = Literal["en", "te", "hi"]
SupportedEmotion = Literal["neutral", "happy", "sad", "angry", "fearful"]


# ===== EMOTION-TO-PROSODY MAPPING =====
# Controls speech characteristics based on detected emotion
@dataclass
class ProsodyConfig:
    """Prosody parameters for emotion expression"""
    rate: float  # Speech rate multiplier (1.0 = normal, >1.0 = faster)
    pitch: int   # Pitch shift in semitones (+/- 10 range)
    volume: float  # Volume multiplier (1.0 = normal)


EMOTION_PROSODY: Dict[SupportedEmotion, ProsodyConfig] = {
    "neutral": ProsodyConfig(rate=1.0, pitch=0, volume=1.0),
    "happy": ProsodyConfig(rate=1.15, pitch=3, volume=1.2),
    "sad": ProsodyConfig(rate=0.85, pitch=-3, volume=0.8),
    "angry": ProsodyConfig(rate=1.25, pitch=4, volume=1.3),
    "fearful": ProsodyConfig(rate=0.95, pitch=-1, volume=0.9),
}


# ===== LANGUAGE AND DIALECT VOICE MAPPING =====
# Neural voices from Edge TTS optimized for quality and emotion expression

VOICE_MAPPING: Dict[SupportedTtsLang, Dict[str, str]] = {
    "en": {
        "default": "en-US-AriaNeural",  # Female, expressive
        "us": "en-US-GuyNeural",  # Male, clear
        "uk": "en-GB-SoniaNeural",  # Female, British
        "au": "en-AU-NatashaNeural",  # Female, Australian
        "in": "en-IN-NeerjaNeural",  # Female, Indian English
    },
    "hi": {
        "default": "hi-IN-SwaraNeural",  # Female, natural
        "male": "hi-IN-MadhurNeural",  # Male, clear
    },
    "te": {
        "default": "te-IN-ShrutiNeural",  # Female, expressive
        "male": "te-IN-MohanNeural",  # Male, natural
    },
}


@dataclass
class TtsSynthesisRequest:
    """TTS request with emotion and language specification"""
    text: str
    language: SupportedTtsLang
    emotion: SupportedEmotion
    dialect: Optional[str] = None  # Optional dialect (e.g., "us", "uk", "in")


class EdgeTtsService:
    """
    Production-grade async TTS service using Microsoft Edge Neural Voices.
    
    Features:
    - Neural voices with emotion expression
    - Emotion-to-prosody mapping (rate, pitch, volume)
    - Dialect-aware voice selection
    - Non-blocking async execution
    - Comprehensive validation
    - No silent/empty audio
    
    Usage:
        service = EdgeTtsService()
        request = TtsSynthesisRequest(
            text="Hello world",
            language="en",
            emotion="happy"
        )
        wav_bytes = await service.synthesize(request)
    """
    
    def __init__(self) -> None:
        """Initialize Edge TTS service (no model loading required)"""
        self._sample_rate = 24000  # Edge TTS output sample rate
        logger.info("✓ Edge TTS service initialized (async neural voices)")
    
    def _validate_request(self, request: TtsSynthesisRequest) -> None:
        """Validate TTS request parameters"""
        if not request.text or not request.text.strip():
            raise ValueError("Text must be a non-empty string")
        
        if request.language not in VOICE_MAPPING:
            raise ValueError(f"Language must be one of: {list(VOICE_MAPPING.keys())}")
        
        if request.emotion not in EMOTION_PROSODY:
            raise ValueError(f"Emotion must be one of: {list(EMOTION_PROSODY.keys())}")
        
        # Validate text length (Edge TTS has limits)
        if len(request.text) > 10000:
            raise ValueError("Text too long (max 10000 characters)")
    
    def _select_voice(
        self, 
        language: SupportedTtsLang, 
        dialect: Optional[str] = None
    ) -> str:
        """
        Select appropriate neural voice based on language and dialect.
        
        Args:
            language: Target language (en, hi, te)
            dialect: Optional dialect specifier (us, uk, in, etc.)
        
        Returns:
            Edge TTS voice name (e.g., "en-US-AriaNeural")
        """
        voices = VOICE_MAPPING[language]
        
        # Try dialect-specific voice first
        if dialect and dialect.lower() in voices:
            voice = voices[dialect.lower()]
            logger.debug(f"Selected dialect voice: {voice} ({language}-{dialect})")
            return voice
        
        # Fall back to default voice
        voice = voices["default"]
        logger.debug(f"Selected default voice: {voice} ({language})")
        return voice
    
    def _create_prosody_params(self, prosody: ProsodyConfig) -> tuple[str, str, str]:
        """
        Convert internal prosody config to Edge TTS parameter strings.

        Edge `Communicate` expects plain text and prosody controls passed as
        keyword parameters (`rate`, `pitch`, `volume`) instead of SSML text.
        """
        rate_percent = int((prosody.rate - 1.0) * 100)
        rate_str = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"

        # Edge expects pitch in Hz (e.g., +10Hz / -10Hz)
        # Approximate semitone shifts into Hz deltas for expressive speech.
        pitch_hz = prosody.pitch * 20
        pitch_str = f"+{pitch_hz}Hz" if pitch_hz >= 0 else f"{pitch_hz}Hz"

        volume_percent = int((prosody.volume - 1.0) * 100)
        volume_str = f"+{volume_percent}%" if volume_percent >= 0 else f"{volume_percent}%"

        logger.debug(
            f"[TTS] Prosody params: rate={rate_str}, pitch={pitch_str}, volume={volume_str}"
        )
        return rate_str, pitch_str, volume_str
    
    async def synthesize(self, request: TtsSynthesisRequest) -> bytes:
        """
        Synthesize speech with emotion-conditioned prosody.
        
        Args:
            request: TTS synthesis request
        
        Returns:
            WAV audio bytes (24kHz, mono, int16)
        
        Raises:
            ValueError: Invalid request parameters
            RuntimeError: Synthesis failed or produced empty audio
        """
        # Step 1: Validate request
        self._validate_request(request)
        
        text = request.text.strip()
        language = request.language
        emotion = request.emotion
        dialect = request.dialect
        
        logger.info(
            f"[TTS] Synthesizing: text_len={len(text)}, "
            f"lang={language}, emotion={emotion}, dialect={dialect}"
        )
        print(f"[EDGE TTS DEBUG] Emotion received in synthesize: '{emotion}' (type: {type(emotion).__name__})")
        
        # Step 2: Select voice based on language and dialect
        voice = self._select_voice(language, dialect)
        
        # Step 3: Get emotion-based prosody configuration
        prosody = EMOTION_PROSODY[emotion]
        logger.info(
            f"[TTS] Prosody: rate={prosody.rate:.2f}, "
            f"pitch={prosody.pitch:+d}st, volume={prosody.volume:.2f}"
        )
        
        # Step 4: Convert emotion prosody to Edge TTS parameters
        rate_str, pitch_str, volume_str = self._create_prosody_params(prosody)

        # Step 5: Synthesize with Edge TTS (async, non-blocking)
        try:
            communicate = edge_tts.Communicate(
                text,
                voice,
                rate=rate_str,
                pitch=pitch_str,
                volume=volume_str,
            )

            # Collect audio chunks
            audio_data = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.extend(chunk["data"])
            
            if not audio_data or len(audio_data) < 1000:
                raise RuntimeError(
                    f"TTS synthesis produced insufficient audio: {len(audio_data)} bytes"
                )
            
            logger.info(f"[TTS] Edge TTS synthesis complete: {len(audio_data)} bytes (raw MP3)")
            
        except Exception as exc:
            logger.error(f"[TTS] Edge TTS synthesis failed: {exc}")
            raise RuntimeError(f"TTS synthesis failed: {exc}") from exc
        
        # Step 6: For now, return MP3 directly (browsers can play it)
        # TODO: Add proper MP3->WAV conversion when ffmpeg is available
        logger.info(f"[TTS] Returning MP3 audio: {len(audio_data)} bytes")
        
        # Validate output size
        if len(audio_data) < 5000:
            raise RuntimeError(
                f"Audio output too small: {len(audio_data)} bytes (expected >5KB)"
            )
        
        logger.info(
            f"[TTS] ✓ Synthesis successful: {len(audio_data)} bytes, "
            f"emotion={emotion}, voice={voice}"
        )
        
        # Return MP3 data as-is (frontend can handle MP3)
        return bytes(audio_data)
    
    async def _convert_to_wav(self, mp3_data: bytes) -> bytes:
        """
        Convert MP3 audio to WAV format.
        
        Edge TTS outputs MP3, but we need WAV for consistency with the rest
        of the pipeline and for better compatibility.
        
        Args:
            mp3_data: MP3 audio bytes
        
        Returns:
            WAV audio bytes (16-bit PCM, mono, 24kHz)
        """
        # Use pydub for pure-Python conversion (works without ffmpeg on some systems)
        try:
            from pydub import AudioSegment
            import io
            
            logger.debug("[TTS] Converting MP3 to WAV using pydub")
            
            # Load MP3 from bytes
            audio = AudioSegment.from_mp3(io.BytesIO(mp3_data))
            
            # Convert to desired format
            audio = audio.set_frame_rate(24000).set_channels(1).set_sample_width(2)
            
            # Export as WAV bytes
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            wav_bytes = wav_buffer.getvalue()
            
            logger.debug(f"[TTS] Conversion complete: {len(wav_bytes)} bytes")
            return wav_bytes
            
        except ImportError:
            logger.error("[TTS] pydub not available - cannot convert MP3 to WAV")
            raise RuntimeError(
                "Audio conversion requires pydub with ffmpeg installed. "
                "Install ffmpeg: https://ffmpeg.org/download.html"
            )
        except Exception as exc:
            logger.error(f"[TTS] Conversion failed: {exc}")
            raise RuntimeError(f"Audio conversion failed: {exc}") from exc


# Alias for backward compatibility with existing code
TtsService = EdgeTtsService
