"""
Translation Intelligence Service

Production-grade translation orchestrator with:
- Language detection
- Context-aware NLLB-200 translation
- Multi-factor confidence scoring
- Emotion tone preservation
- Intelligent retry with parameter adjustment
- Drift monitoring
"""

import logging
import time
from typing import Optional, Dict, List
import asyncio

from .exceptions import (
    TranslationServiceError,
    EmptyTranscriptError,
    TranscriptTooLongError,
    STTConfidenceTooLowError,
    MaxRetriesExceededError,
    TranslationTimeoutError,
)
from .schemas import (
    TranslationRequest,
    TranslationResponse,
    TranslationHealthResponse,
    TranslationMetricsSnapshot,
    DriftAlert,
)
from .language_detector import LanguageDetector
from .translation_engine import TranslationEngine
from .emotion_preserver import EmotionPreserver
from .confidence_scorer import ConfidenceScorer
from .retry_handler import RetryHandler
from .drift_monitor import TranslationDriftMonitor


logger = logging.getLogger(__name__)


class TranslationService:
    """
    Main translation intelligence service.
    
    Orchestrates:
    1. Input validation
    2. Language detection (with code-switching detection)
    3. NLLB-200 translation (with beam search)
    4. Confidence scoring (5 factors)
    5. Emotion preservation validation (3 factors)
    6. Intelligent retry (if quality insufficient)
    7. Drift monitoring
    
    Performance targets:
    - p95 latency < 1s (short), < 2s (moderate)
    - Translation confidence > 0.75
    - Emotion preservation > 0.70
    """
    
    def __init__(
        self,
        model_name: str = "facebook/nllb-200-distilled-600M",
        device: str = "cuda",
        fasttext_model_path: Optional[str] = None,
        max_transcript_length: int = 2000,
        min_stt_confidence: float = 0.4,
        min_translation_confidence: float = 0.75,
        min_emotion_preservation: float = 0.70,
        enable_drift_monitoring: bool = True,
    ):
        self.max_transcript_length = max_transcript_length
        self.min_stt_confidence = min_stt_confidence
        self.min_translation_confidence = min_translation_confidence
        self.min_emotion_preservation = min_emotion_preservation
        self.enable_drift_monitoring = enable_drift_monitoring
        
        # Initialize components
        logger.info("Initializing translation service components...")
        
        self.language_detector = LanguageDetector(
            fasttext_model_path=fasttext_model_path
        )
        
        self.translation_engine = TranslationEngine(
            model_name=model_name,
            device=device
        )
        
        self.emotion_preserver = EmotionPreserver()
        
        self.confidence_scorer = ConfidenceScorer()
        
        self.retry_handler = RetryHandler(
            translation_engine=self.translation_engine,
            confidence_scorer=self.confidence_scorer,
            emotion_preserver=self.emotion_preserver,
        )
        
        if self.enable_drift_monitoring:
            self.drift_monitor = TranslationDriftMonitor()
        
        # Service metadata
        self.model_name = model_name
        self.device = device
        self.service_start_time = time.time()
        
        logger.info("Translation service initialized successfully")
    
    async def translate(self, request: TranslationRequest) -> TranslationResponse:
        """
        Main translation endpoint.
        
        Pipeline:
        1. Validate input
        2. Detect language (if source not provided)
        3. Translate with NLLB-200
        4. Score translation confidence (5 factors)
        5. Validate emotion preservation (3 factors)
        6. Retry if quality insufficient (max 2 retries)
        7. Record drift metrics
        
        Returns:
            TranslationResponse with translated text, confidence, emotion metrics
        """
        start_time = time.time()
        latency_breakdown: Dict[str, float] = {}
        
        try:
            # Step 1: Validate input
            validation_start = time.time()
            self._validate_request(request)
            latency_breakdown["validation_ms"] = (time.time() - validation_start) * 1000
            
            # Step 2: Language detection
            detection_start = time.time()
            language_result = await self._detect_language(request)
            latency_breakdown["language_detection_ms"] = (time.time() - detection_start) * 1000
            
            # Use detected language if not provided
            source_lang = request.source_lang or language_result.detected_language
            
            # Step 3: Initialize context
            context_sentences = self._prepare_context(request.context_window)
            
            # Step 4: Attempt translation with retry loop
            retry_start = time.time()
            translation_result = await self.retry_handler.translate_with_retry(
                transcript=request.transcript,
                source_lang=source_lang,
                target_lang=request.target_lang,
                emotion_label=request.emotion_label,
                emotion_confidence=request.emotion_confidence,
                context_sentences=context_sentences,
                min_translation_confidence=request.min_translation_confidence or self.min_translation_confidence,
                min_emotion_preservation=request.min_emotion_preservation or self.min_emotion_preservation,
            )
            latency_breakdown["translation_and_retry_ms"] = (time.time() - retry_start) * 1000
            
            # Extract results
            translated_text = translation_result["translated_text"]
            confidence_metrics = translation_result["confidence_metrics"]
            emotion_metrics = translation_result["emotion_metrics"]
            retry_info = translation_result["retry_info"]
            
            # Step 5: Determine status
            status = self._determine_status(
                confidence_metrics.overall_confidence,
                emotion_metrics.preservation_score if emotion_metrics else None,
                request,
            )
            
            # Step 6: Record drift metrics
            if self.enable_drift_monitoring:
                self.drift_monitor.record_translation(
                    status=status,
                    translation_confidence=confidence_metrics.overall_confidence,
                    emotion_preservation_score=emotion_metrics.preservation_score if emotion_metrics else None,
                    latency_ms=(time.time() - start_time) * 1000,
                    source_language=source_lang,
                    had_retry=retry_info.retry_count > 0,
                    retry_reason=retry_info.retry_reasons[0] if retry_info.retry_reasons else None,
                )
            
            # Step 7: Build response
            total_latency_ms = (time.time() - start_time) * 1000
            
            return TranslationResponse(
                status=status,
                translated_text=translated_text,
                language_detection=language_result,
                confidence_metrics=confidence_metrics,
                emotion_metrics=emotion_metrics,
                model_version=self.model_name,
                retry_info=retry_info,
                latency_ms=total_latency_ms,
                latency_breakdown=latency_breakdown,
                request_id=request.request_id,
            )
        
        except MaxRetriesExceededError as e:
            # Max retries exceeded, return partial result if available
            logger.error(f"Max retries exceeded: {e}")
            return self._build_failed_response(
                request=request,
                error_message=str(e),
                status="failed",
                latency_ms=(time.time() - start_time) * 1000,
                latency_breakdown=latency_breakdown,
            )
        
        except TranslationServiceError as e:
            logger.error(f"Translation service error: {e}")
            return self._build_failed_response(
                request=request,
                error_message=str(e),
                status="failed",
                latency_ms=(time.time() - start_time) * 1000,
                latency_breakdown=latency_breakdown,
            )
        
        except Exception as e:
            logger.exception(f"Unexpected error in translation: {e}")
            return self._build_failed_response(
                request=request,
                error_message=f"Unexpected error: {str(e)}",
                status="failed",
                latency_ms=(time.time() - start_time) * 1000,
                latency_breakdown=latency_breakdown,
            )
    
    def _validate_request(self, request: TranslationRequest):
        """Validate translation request"""
        # Check transcript length
        if not request.transcript or len(request.transcript.strip()) == 0:
            raise EmptyTranscriptError("Transcript is empty")
        
        if len(request.transcript) > self.max_transcript_length:
            raise TranscriptTooLongError(
                f"Transcript length {len(request.transcript)} exceeds maximum {self.max_transcript_length}"
            )
        
        # Check STT confidence if provided
        if request.stt_confidence is not None and request.stt_confidence < self.min_stt_confidence:
            raise STTConfidenceTooLowError(
                f"STT confidence {request.stt_confidence:.2f} below minimum {self.min_stt_confidence:.2f}"
            )
    
    async def _detect_language(self, request: TranslationRequest):
        """Detect source language if not provided"""
        if request.source_lang:
            # Source language provided, just validate
            return self.language_detector.detect(request.transcript)
        else:
            # Detect language
            return self.language_detector.detect(request.transcript)
    
    def _prepare_context(self, context_window: Optional[List[str]]) -> List[str]:
        """Prepare context sentences for translation"""
        if not context_window:
            return []
        # Use last 1-2 sentences as context
        return context_window[-2:]
    
    def _determine_status(
        self,
        confidence: float,
        emotion_score: Optional[float],
        request: TranslationRequest,
    ) -> str:
        """Determine translation status"""
        min_confidence = request.min_translation_confidence or self.min_translation_confidence
        min_emotion = request.min_emotion_preservation or self.min_emotion_preservation
        
        # Success: meets all thresholds
        if confidence >= min_confidence:
            if emotion_score is None or emotion_score >= min_emotion:
                return "success"
        
        # Partial: translation exists but below quality thresholds
        if confidence >= 0.5:
            return "partial"
        
        # Failed: very low quality
        return "failed"
    
    def _build_failed_response(
        self,
        request: TranslationRequest,
        error_message: str,
        status: str,
        latency_ms: float,
        latency_breakdown: Dict[str, float],
    ) -> TranslationResponse:
        """Build response for failed translation"""
        from .schemas import (
            LanguageDetectionResult,
            TranslationConfidenceMetrics,
            RetryInfo,
        )
        
        return TranslationResponse(
            status=status,
            translated_text="",
            language_detection=LanguageDetectionResult(
                detected_language=request.source_lang or "unknown",
                confidence=0.0,
                alternatives=[],
                is_code_switching=False,
            ),
            confidence_metrics=TranslationConfidenceMetrics(
                overall_confidence=0.0,
                model_log_probability=0.0,
                length_consistency_score=0.0,
                repetition_score=0.0,
                language_consistency_score=0.0,
                entity_preservation_score=0.0,
            ),
            emotion_metrics=None,
            model_version=self.model_name,
            retry_info=RetryInfo(
                retry_count=0,
                retry_reasons=[error_message],
                retry_adjustments=[],
                final_attempt=True,
            ),
            latency_ms=latency_ms,
            latency_breakdown=latency_breakdown,
            request_id=request.request_id,
        )
    
    def get_health(self) -> TranslationHealthResponse:
        """Get service health status"""
        metrics = self.drift_monitor.get_metrics_snapshot() if self.enable_drift_monitoring else None
        
        return TranslationHealthResponse(
            status="healthy",
            models_loaded={
                "translation_engine": self.translation_engine.model is not None,
                "language_detector": self.language_detector.fasttext_model is not None,
            },
            error_rate=metrics.failed_count / max(metrics.total_requests, 1) if metrics else 0.0,
            retry_rate=metrics.retry_rate if metrics else 0.0,
            average_confidence=metrics.average_confidence if metrics else 0.0,
            average_emotion_preservation=metrics.average_emotion_preservation if metrics else 0.0,
            uptime_seconds=time.time() - self.service_start_time,
        )
    
    def get_metrics(self) -> TranslationMetricsSnapshot:
        """Get detailed metrics snapshot"""
        if not self.enable_drift_monitoring:
            raise ValueError("Drift monitoring not enabled")
        return self.drift_monitor.get_metrics_snapshot()
    
    def get_drift_alerts(self) -> List[DriftAlert]:
        """Get active drift alerts"""
        if not self.enable_drift_monitoring:
            return []
        return self.drift_monitor.get_active_alerts()
