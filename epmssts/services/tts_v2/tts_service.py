"""
TTS Service

Production-grade Text-to-Speech service with emotion preservation.

Pipeline:
1. Input validation
2. Prosody mapping (emotion → parameters)
3. Neural synthesis (Coqui XTTS v2)
4. Waveform validation
5. Fallback chain (if needed)
6. Output delivery

Never returns silent or corrupted audio.
"""

import logging
import time
import numpy as np
from typing import Optional, Dict
from pathlib import Path
import uuid
import io
import base64
import soundfile as sf
from collections import deque

from .schemas import (
    TTSRequest,
    TTSResponse,
    ProsodyProfile,
    WaveformQualityMetrics,
    FallbackInfo,
    TTSHealthResponse,
    TTSMetricsSnapshot,
)
from .exceptions import (
    EmptyInputTextError,
    TextTooLongError,
    TranslationConfidenceTooLowError,
    UnsupportedLanguageError,
    TTSServiceError,
)
from .prosody_mapper import ProsodyMapper
from .tts_engine import TTSEngine
from .waveform_validator import WaveformValidator
from .fallback_handler import FallbackHandler


logger = logging.getLogger(__name__)


class TTSService:
    """
    Main TTS service orchestrator.
    
    Features:
    - Emotion-aware prosody control
    - Neural TTS synthesis (Coqui XTTS v2)
    - Waveform quality validation
    - Intelligent fallback chain
    - Latency monitoring
    - Never returns silent audio
    
    Performance targets:
    - p95 latency < 1.5s (short text)
    - p95 latency < 3s (moderate text)
    """
    
    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        device: str = "cuda",
        enable_fp16: bool = True,
        sample_rate: int = 16000,
        output_dir: str = "./tts_outputs",
        max_text_length: int = 5000,
        min_translation_confidence: float = 0.5,
    ):
        """
        Initialize TTS service.
        
        Args:
            model_name: TTS model identifier
            device: "cuda" or "cpu"
            enable_fp16: Use FP16 for GPU
            sample_rate: Output sample rate
            output_dir: Directory for audio outputs
            max_text_length: Maximum text length
            min_translation_confidence: Minimum translation confidence threshold
        """
        self.model_name = model_name
        self.device = device
        self.sample_rate = sample_rate
        self.output_dir = Path(output_dir)
        self.max_text_length = max_text_length
        self.min_translation_confidence = min_translation_confidence
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        logger.info("Initializing TTS service components...")
        
        self.prosody_mapper = ProsodyMapper()
        
        self.tts_engine = TTSEngine(
            model_name=model_name,
            device=device,
            enable_fp16=enable_fp16,
            sample_rate=sample_rate
        )
        
        self.waveform_validator = WaveformValidator()
        
        self.fallback_handler = FallbackHandler(
            primary_engine=self.tts_engine,
            validator=self.waveform_validator
        )
        
        # Metrics tracking
        self.request_count = 0
        self.success_count = 0
        self.partial_count = 0
        self.failed_count = 0
        self.emotion_distribution = {}
        self.language_distribution = {}
        self.latency_history = deque(maxlen=1000)
        self.error_history = deque(maxlen=100)
        
        # Service metadata
        self.service_start_time = time.time()
        
        logger.info("TTS service initialized successfully")
    
    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """
        Synthesize speech from text.
        
        Pipeline:
        1. Validate input
        2. Map emotion to prosody
        3. Synthesize with TTS engine
        4. Validate waveform quality
        5. Fallback if needed
        6. Save audio file
        7. Return response
        
        Args:
            request: TTS request
        
        Returns:
            TTS response with audio path and metrics
        """
        start_time = time.time()
        latency_breakdown: Dict[str, float] = {}
        
        try:
            self.request_count += 1
            
            # Step 1: Validate input
            validation_start = time.time()
            self._validate_request(request)
            latency_breakdown["validation_ms"] = (time.time() - validation_start) * 1000
            
            # Step 2: Map emotion to prosody
            prosody_start = time.time()
            prosody_profile = self.prosody_mapper.map_emotion_to_prosody(
                emotion_label=request.emotion_label,
                emotion_confidence=request.emotion_confidence,
                intensity_multiplier=request.prosody_intensity or 1.0
            )
            latency_breakdown["prosody_mapping_ms"] = (time.time() - prosody_start) * 1000
            
            # Step 3: Synthesize with fallback
            synthesis_start = time.time()
            audio_array, sr, fallback_info = self.fallback_handler.synthesize_with_fallback(
                text=request.translated_text,
                language=self._map_language_code(request.target_language),
                prosody_profile=prosody_profile,
                speaker_id=request.speaker_id,
                timeout_seconds=10.0
            )
            latency_breakdown["synthesis_ms"] = (time.time() - synthesis_start) * 1000
            
            # Step 4: Validate waveform
            validation_start = time.time()
            waveform_quality = self.waveform_validator.validate(audio_array, sr)
            latency_breakdown["waveform_validation_ms"] = (time.time() - validation_start) * 1000
            
            # Step 5: Save audio file
            save_start = time.time()
            audio_path = self._save_audio(audio_array, sr, request.request_id)
            latency_breakdown["save_audio_ms"] = (time.time() - save_start) * 1000
            
            # Step 6: Determine status
            status = "success" if waveform_quality.is_valid and not fallback_info.fallback_used else "partial"
            
            if status == "success":
                self.success_count += 1
            else:
                self.partial_count += 1
            
            # Update statistics
            if request.emotion_label:
                self.emotion_distribution[request.emotion_label] = \
                    self.emotion_distribution.get(request.emotion_label, 0) + 1
            
            self.language_distribution[request.target_language] = \
                self.language_distribution.get(request.target_language, 0) + 1
            
            # Calculate total latency
            total_latency_ms = (time.time() - start_time) * 1000
            self.latency_history.append(total_latency_ms)
            
            # Build response
            response = TTSResponse(
                status=status,
                audio_path=str(audio_path),
                audio_base64=None,  # Optional: encode if requested
                prosody_profile=prosody_profile,
                waveform_quality=waveform_quality,
                fallback_info=fallback_info,
                latency_ms=total_latency_ms,
                latency_breakdown=latency_breakdown,
                model_version=self.model_name,
                request_id=request.request_id,
                error_message=None
            )
            
            logger.info(f"TTS synthesis completed: status={status}, latency={total_latency_ms:.1f}ms, "
                       f"fallback={fallback_info.fallback_used}")
            
            return response
        
        except TTSServiceError as e:
            logger.error(f"TTS service error: {e}")
            self.failed_count += 1
            self.error_history.append(e.error_code.name)
            
            return self._build_error_response(
                request=request,
                error_message=str(e),
                latency_ms=(time.time() - start_time) * 1000,
                latency_breakdown=latency_breakdown
            )
        
        except Exception as e:
            logger.exception(f"Unexpected TTS error: {e}")
            self.failed_count += 1
            self.error_history.append("UNEXPECTED_ERROR")
            
            return self._build_error_response(
                request=request,
                error_message=f"Unexpected error: {str(e)}",
                latency_ms=(time.time() - start_time) * 1000,
                latency_breakdown=latency_breakdown
            )
    
    def _validate_request(self, request: TTSRequest):
        """Validate TTS request"""
        # Check text length
        if not request.translated_text or len(request.translated_text.strip()) == 0:
            raise EmptyInputTextError("Translated text is empty")
        
        if len(request.translated_text) > self.max_text_length:
            raise TextTooLongError(
                f"Text length {len(request.translated_text)} exceeds maximum {self.max_text_length}",
                details={"length": len(request.translated_text), "max_length": self.max_text_length}
            )
        
        # Check translation confidence
        if request.translation_confidence is not None:
            if request.translation_confidence < self.min_translation_confidence:
                raise TranslationConfidenceTooLowError(
                    f"Translation confidence {request.translation_confidence:.2f} below threshold {self.min_translation_confidence:.2f}",
                    details={"confidence": request.translation_confidence, "threshold": self.min_translation_confidence}
                )
        
        # Check language support
        lang_code = self._map_language_code(request.target_language)
        if lang_code not in self.tts_engine.SUPPORTED_LANGUAGES:
            raise UnsupportedLanguageError(
                f"Language '{request.target_language}' not supported",
                details={"language": request.target_language, "supported": list(self.tts_engine.SUPPORTED_LANGUAGES)}
            )
    
    def _map_language_code(self, language: str) -> str:
        """
        Map language code to TTS engine format.
        
        Input: 'en', 'en-US', 'eng_Latn', etc.
        Output: 'en'
        """
        # Extract first 2 characters
        return language.lower()[:2]
    
    def _save_audio(self, audio_array: np.ndarray, sample_rate: int, request_id: Optional[str] = None) -> Path:
        """Save audio to file"""
        # Generate filename
        if request_id:
            filename = f"tts_{request_id}.wav"
        else:
            filename = f"tts_{uuid.uuid4()}.wav"
        
        audio_path = self.output_dir / filename
        
        # Save as WAV (16kHz, mono, PCM 16-bit)
        sf.write(audio_path, audio_array, sample_rate, subtype='PCM_16')
        
        logger.debug(f"Audio saved to {audio_path}")
        
        return audio_path
    
    def _build_error_response(
        self,
        request: TTSRequest,
        error_message: str,
        latency_ms: float,
        latency_breakdown: Dict[str, float]
    ) -> TTSResponse:
        """Build error response"""
        return TTSResponse(
            status="failed",
            audio_path=None,
            audio_base64=None,
            prosody_profile=ProsodyProfile(
                rate_multiplier=1.0,
                pitch_shift=0.0,
                energy_scale=1.0,
                pitch_variance=1.0,
                emotion_intensity=0.0
            ),
            waveform_quality=None,
            fallback_info=FallbackInfo(
                fallback_used=False,
                primary_engine_error=error_message,
                engine_used="none",
                retry_count=0
            ),
            latency_ms=latency_ms,
            latency_breakdown=latency_breakdown,
            model_version=self.model_name,
            request_id=request.request_id,
            error_message=error_message
        )
    
    def get_health(self) -> TTSHealthResponse:
        """Get service health status"""
        import torch
        
        return TTSHealthResponse(
            status="healthy" if self.tts_engine.model_loaded else "unhealthy",
            models_loaded={
                "primary_tts": self.tts_engine.model_loaded,
            },
            gpu_available=torch.cuda.is_available(),
            gpu_memory_used_mb=torch.cuda.memory_allocated() / 1024 / 1024 if torch.cuda.is_available() else None,
            error_rate=self.failed_count / max(self.request_count, 1),
            fallback_rate=self.fallback_handler.get_fallback_stats()["fallback_rate"],
            average_latency_ms=np.mean(self.latency_history) if self.latency_history else 0.0,
            uptime_seconds=time.time() - self.service_start_time
        )
    
    def get_metrics(self) -> TTSMetricsSnapshot:
        """Get detailed metrics snapshot"""
        latency_array = np.array(self.latency_history) if self.latency_history else np.array([0])
        
        return TTSMetricsSnapshot(
            total_requests=self.request_count,
            success_count=self.success_count,
            partial_count=self.partial_count,
            failed_count=self.failed_count,
            fallback_count=self.fallback_handler.retry_success_count + 
                          self.fallback_handler.secondary_success_count + 
                          self.fallback_handler.system_tts_success_count,
            average_latency_ms=float(np.mean(latency_array)),
            latency_p50_ms=float(np.percentile(latency_array, 50)),
            latency_p95_ms=float(np.percentile(latency_array, 95)),
            latency_p99_ms=float(np.percentile(latency_array, 99)),
            emotion_distribution=dict(self.emotion_distribution),
            language_distribution=dict(self.language_distribution),
            error_distribution=dict(self.error_history) if self.error_history else {},
            average_audio_duration_seconds=0.0,  # TODO: Track
            average_audio_size_kb=0.0,  # TODO: Track
            waveform_validation_failures=0  # TODO: Track
        )
