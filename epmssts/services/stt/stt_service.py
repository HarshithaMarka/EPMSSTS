"""
Speech-to-Text (STT) Service

Production-grade STT service combining Whisper model, confidence scoring, 
device management, and concurrency control.
"""

import logging
import base64
import asyncio
import io
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
import json


# Import service components
from .device_manager import DeviceManager
from .model_manager import ModelManager
from .confidence_scorer import TranscriptionConfidenceScorer
from .schemas import SttRequest, SttResponse, TranscriptionSegment
from .exceptions import (
    SttServiceException,
    ModelNotInitializedError,
    InferenceTimeoutError,
    InferenceError,
    NoSpeechDetectedError,
    AudioTooShortError,
    AudioTooLongError,
    InvalidAudioFormatError,
    EmptyTranscriptError,
    HallucinationDetectedError,
    ConfidenceTooLowError,
    InferenceQueueFullError,
)


logger = logging.getLogger(__name__)


@dataclass
class InferenceMetrics:
    """Metrics for a single inference"""
    total_time_ms: float
    preprocess_time_ms: float
    inference_time_ms: float
    postprocess_time_ms: float
    audio_duration_seconds: float
    device_used: str
    model_used: str
    confidence_score: float
    processing_speed_x: float  # audio_duration / total_time


class SpeechToTextService:
    """
    Enterprise-grade Speech-to-Text service.
    
    Responsibilities:
    - Accept audio and produce transcription
    - Enforce quality thresholds
    - Manage GPU/CPU device fallback
    - Control concurrency and prevent GPU OOM
    - Track observability metrics
    - Handle errors gracefully
    """
    
    def __init__(
        self,
        model_size: str = "base",
        device_prefer_gpu: bool = True,
        max_concurrent_inferences: int = 4,
        queue_timeout_seconds: float = 30.0,
        inference_timeout_seconds: float = 60.0,
    ):
        """
        Initialize STT service.
        
        Args:
            model_size: Size of Whisper model (tiny, base, small, medium, large, large-v3)
            device_prefer_gpu: Try GPU first if available
            max_concurrent_inferences: Max concurrent inference requests
            queue_timeout_seconds: Time to wait for queue slot
            inference_timeout_seconds: Time to wait for inference to complete
        """
        self.model_size = model_size
        self.device_prefer_gpu = device_prefer_gpu
        self.max_concurrent_inferences = max_concurrent_inferences
        self.queue_timeout_seconds = queue_timeout_seconds
        self.inference_timeout_seconds = inference_timeout_seconds
        
        # Components
        self.device_manager = None
        self.model_manager = ModelManager()
        self.confidence_scorer = TranscriptionConfidenceScorer()
        
        # Concurrency control
        self.semaphore = None
        self.queue_size = 0
        
        # Metrics
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_inference_time_ms': 0.0,
            'total_audio_duration_seconds': 0.0,
            'language_distribution': {},
            'error_distribution': {},
            'confidence_scores': [],
            'no_speech_rejections': 0,
            'confidence_rejections': 0,
            'hallucination_detections': 0,
            'gpu_used_count': 0,
            'cpu_used_count': 0,
        }
        
        self.is_initialized = False
        self.initialization_error = None
        self.last_inference_time = None
    
    async def initialize(self):
        """
        Initialize service: set up device and load model.
        
        Raises:
            Various exceptions if initialization fails
        """
        try:
            logger.info(f"Initializing STT service with {self.model_size} model")
            
            # Initialize device manager
            self.device_manager = DeviceManager(prefer_gpu=self.device_prefer_gpu)
            device_config = self.device_manager.initialize()
            logger.info(f"Device initialized: {device_config.device_type}")
            
            # Initialize model manager
            self.model_manager.initialize(
                device_manager=self.device_manager,
                model_size=self.model_size,
                quantization=device_config.quantization_method,
            )
            logger.info("Model loaded successfully")
            
            # Initialize concurrency semaphore
            self.semaphore = asyncio.Semaphore(self.max_concurrent_inferences)
            
            self.is_initialized = True
            logger.info("STT service initialization complete")
        
        except Exception as e:
            self.initialization_error = str(e)
            self.is_initialized = False
            logger.error(f"STT service initialization failed: {e}")
            raise
    
    async def transcribe(
        self,
        request: SttRequest,
    ) -> SttResponse:
        """
        Transcribe audio from request.
        
        Args:
            request: SttRequest with audio data
            
        Returns:
            SttResponse with transcription results
        """
        from .exceptions import SttErrorReasonCode
        import time
        
        start_time = time.time()
        self.metrics['total_requests'] += 1
        
        # Create correlation ID
        request_id = request.request_id or self._generate_request_id()
        
        try:
            # Validate service is initialized
            if not self.is_initialized:
                raise ModelNotInitializedError(
                    "STT service not initialized"
                )
            
            # Decode audio
            try:
                audio_bytes = base64.b64decode(request.audio_data)
            except Exception as e:
                raise InvalidAudioFormatError(
                    format_detected="invalid_base64",
                    supported_formats=["wav", "mp3", "flac", "ogg", "m4a"],
                )
            
            # Preprocess and validate
            audio_array, duration_seconds = await self._preprocess_audio(
                audio_bytes=audio_bytes,
                format=request.format.value,
                max_duration=request.max_duration_seconds,
            )
            
            # Acquire inference slot with timeout
            queue_acquired = False
            try:
                await asyncio.wait_for(
                    self.semaphore.acquire(),
                    timeout=self.queue_timeout_seconds,
                )
                queue_acquired = True
                self.queue_size += 1
            except asyncio.TimeoutError:
                raise InferenceQueueFullError(
                    queue_size=self.max_concurrent_inferences,
                    max_size=self.max_concurrent_inferences,
                )
            
            try:
                # Run inference
                infer_start = time.time()
                segments, info = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.model_manager.transcribe,
                        audio_array,
                        request.language.value if request.language else None,
                    ),
                    timeout=self.inference_timeout_seconds,
                )
                infer_duration = (time.time() - infer_start) * 1000  # ms
                
            finally:
                if queue_acquired:
                    self.semaphore.release()
                    self.queue_size -= 1
            
            # Extract transcription
            transcript = " ".join([segment.text for segment in segments])
            
            # Validate transcription quality
            avg_logprob = info.avg_logprob if hasattr(info, 'avg_logprob') else -1.0
            no_speech_prob = info.no_speech_prob if hasattr(info, 'no_speech_prob') else 0.0
            language = info.language if hasattr(info, 'language') else "unknown"
            
            # Score confidence
            confidence = self.confidence_scorer.score(
                transcript=transcript,
                segments=segments,
                avg_logprob=avg_logprob,
                no_speech_prob=no_speech_prob,
                language=language,
            )
            
            # Check for rejection
            should_reject, rejection_reason = self.confidence_scorer.should_reject(
                transcript=transcript,
                confidence=confidence,
                no_speech_prob=no_speech_prob,
                avg_logprob=avg_logprob,
                confidence_threshold=request.confidence_threshold,
            )
            
            if should_reject:
                if no_speech_prob > request.no_speech_threshold:
                    self.metrics['no_speech_rejections'] += 1
                    raise NoSpeechDetectedError(
                        no_speech_prob=no_speech_prob,
                        threshold=request.no_speech_threshold,
                    )
                else:
                    self.metrics['confidence_rejections'] += 1
                    raise ConfidenceTooLowError(
                        confidence=confidence,
                        threshold=request.confidence_threshold,
                        reason=rejection_reason,
                    )
            
            # Detect hallucination
            hallucination_detected = False
            hallucination_indicators = None
            # (Advanced detection could be implemented here)
            
            # Build response
            total_time = (time.time() - start_time) * 1000  # ms
            
            response = SttResponse(
                success=True,
                transcript=transcript,
                confidence=confidence,
                no_speech_prob=no_speech_prob,
                language=language,
                segments=[
                    TranscriptionSegment(
                        text=seg.text,
                        start_time=seg.start,
                        end_time=seg.end,
                        confidence=getattr(seg, 'avg_logprob', -1.0),
                        no_speech_prob=getattr(seg, 'no_speech_prob', 0.0),
                    )
                    for seg in segments
                ],
                processing_time_ms=total_time,
                device_used=self.device_manager.current_device.device_type,
                audio_duration_seconds=duration_seconds,
                is_hallucination_detected=hallucination_detected,
                hallucination_indicators=hallucination_indicators,
                request_id=request_id,
                model_name=self.model_manager.current_model_name,
                inference_duration_ms=infer_duration,
            )
            
            # Update metrics
            self.metrics['successful_requests'] += 1
            self.metrics['total_inference_time_ms'] += infer_duration
            self.metrics['total_audio_duration_seconds'] += duration_seconds
            self.metrics['confidence_scores'].append(confidence)
            
            lang_code = language or "unknown"
            self.metrics['language_distribution'][lang_code] = (
                self.metrics['language_distribution'].get(lang_code, 0) + 1
            )
            
            if self.device_manager.current_device.device_type == "gpu":
                self.metrics['gpu_used_count'] += 1
            else:
                self.metrics['cpu_used_count'] += 1
            
            self.last_inference_time = datetime.now()
            self.device_manager.record_inference_success()
            
            logger.info(
                f"Request {request_id}: Success | "
                f"Transcript length: {len(transcript)} | "
                f"Confidence: {confidence:.2f} | "
                f"Duration: {total_time:.0f}ms"
            )
            
            return response
        
        except SttServiceException as e:
            # Known service exceptions
            total_time = (time.time() - start_time) * 1000
            self.metrics['failed_requests'] += 1
            self.metrics['error_distribution'][e.reason_code.value] = (
                self.metrics['error_distribution'].get(e.reason_code.value, 0) + 1
            )
            
            if self.device_manager:
                self.device_manager.record_inference_error()
            
            logger.warning(
                f"Request {request_id}: Failed | "
                f"Code: {e.reason_code.value} | "
                f"Message: {e.message}"
            )
            
            return SttResponse(
                success=False,
                transcript="",
                confidence=0.0,
                processing_time_ms=total_time,
                device_used=self.device_manager.current_device.device_type if self.device_manager else "unknown",
                audio_duration_seconds=0.0,
                error_code=e.reason_code.value,
                error_message=e.message,
                user_friendly_message=e.user_friendly_message,
                request_id=request_id,
            )
        
        except Exception as e:
            # Unexpected exceptions
            total_time = (time.time() - start_time) * 1000
            self.metrics['failed_requests'] += 1
            
            logger.error(
                f"Request {request_id}: Unexpected error: {e}",
                exc_info=True,
            )
            
            return SttResponse(
                success=False,
                transcript="",
                confidence=0.0,
                processing_time_ms=total_time,
                device_used=self.device_manager.current_device.device_type if self.device_manager else "unknown",
                audio_duration_seconds=0.0,
                error_code="ERR_STT_011",
                error_message=f"Unexpected error: {str(e)}",
                user_friendly_message="An unexpected error occurred during processing",
                request_id=request_id,
            )
    
    async def _preprocess_audio(
        self,
        audio_bytes: bytes,
        format: str,
        max_duration: float,
    ) -> tuple:
        """
        Preprocess audio data.
        
        Returns:
            Tuple of (audio_array, duration_seconds)
        """
        import soundfile as sf
        import numpy as np
        
        try:
            # Read audio
            audio_array, sr = sf.read(io.BytesIO(audio_bytes))
            duration = len(audio_array) / sr
            
            # Validate duration
            if duration < 0.5:
                raise AudioTooShortError(
                    duration=duration,
                    minimum=0.5,
                )
            
            if duration > max_duration:
                raise AudioTooLongError(
                    duration=duration,
                    maximum=max_duration,
                )
            
            # Convert to mono if needed
            if len(audio_array.shape) > 1:
                audio_array = np.mean(audio_array, axis=1)
            
            # Resample to 16kHz if needed
            if sr != 16000:
                import librosa
                audio_array = await asyncio.to_thread(
                    librosa.resample,
                    audio_array,
                    orig_sr=sr,
                    target_sr=16000,
                )
                sr = 16000
            
            # Ensure float32
            if audio_array.dtype != np.float32:
                audio_array = audio_array.astype(np.float32)
            
            # Normalize
            max_val = np.abs(audio_array).max()
            if max_val > 0:
                audio_array = audio_array / max_val
            
            return audio_array, duration
        
        except Exception as e:
            if isinstance(e, (AudioTooShortError, AudioTooLongError)):
                raise
            raise InvalidAudioFormatError(
                format_detected=format,
                supported_formats=["wav", "mp3", "flac", "ogg", "m4a"],
            )
    
    def _generate_request_id(self) -> str:
        """Generate correlation ID"""
        from uuid import uuid4
        return f"stt-{uuid4().hex[:12]}"
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get service health status"""
        if not self.is_initialized:
            return {
                "status": "unhealthy",
                "model_loaded": False,
                "initialized": False,
                "error": self.initialization_error,
            }
        
        device_health = self.device_manager.health_check() if self.device_manager else {}
        model_status = self.model_manager.get_model_status()
        
        # Calculate metrics
        total_requests = self.metrics['total_requests']
        error_rate = (
            self.metrics['failed_requests'] / total_requests
            if total_requests > 0
            else 0.0
        )
        
        avg_latency = (
            self.metrics['total_inference_time_ms'] / self.metrics['successful_requests']
            if self.metrics['successful_requests'] > 0
            else 0.0
        )
        
        return {
            "status": "healthy" if error_rate < 0.1 else "degraded",
            "model_loaded": self.model_manager.is_loaded,
            "model_name": model_status.get('model_name'),
            "device": self.device_manager.current_device.device_type if self.device_manager else "unknown",
            "gpu_available": device_health.get('device') == 'gpu',
            "average_latency_ms": avg_latency,
            "error_rate": error_rate,
            "total_requests": total_requests,
            "successful_requests": self.metrics['successful_requests'],
            "failed_requests": self.metrics['failed_requests'],
            "queue_size": self.queue_size,
            "concurrent_capacity": self.max_concurrent_inferences,
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics"""
        import statistics
        
        total_requests = self.metrics['total_requests']
        successful = self.metrics['successful_requests']
        
        return {
            "total_requests": total_requests,
            "successful_requests": successful,
            "failed_requests": self.metrics['failed_requests'],
            "success_rate": successful / total_requests if total_requests > 0 else 0.0,
            "average_latency_ms": (
                self.metrics['total_inference_time_ms'] / successful
                if successful > 0
                else 0.0
            ),
            "average_audio_duration_seconds": (
                self.metrics['total_audio_duration_seconds'] / successful
                if successful > 0
                else 0.0
            ),
            "average_confidence": (
                statistics.mean(self.metrics['confidence_scores'])
                if self.metrics['confidence_scores']
                else 0.0
            ),
            "language_distribution": self.metrics['language_distribution'],
            "error_distribution": self.metrics['error_distribution'],
            "gpu_used_percentage": (
                100.0 * self.metrics['gpu_used_count'] / successful
                if successful > 0
                else 0.0
            ),
            "rejections": {
                "no_speech": self.metrics['no_speech_rejections'],
                "confidence": self.metrics['confidence_rejections'],
                "hallucination": self.metrics['hallucination_detections'],
            },
        }
