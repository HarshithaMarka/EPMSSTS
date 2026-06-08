"""
Emotion Intelligence Service

Production-grade ensemble-based emotion recognition service.
Orchestrates audio models, text model, calibration, fusion, uncertainty, and drift monitoring.
"""

import logging
import asyncio
import numpy as np
from typing import Optional, Dict
from datetime import datetime

from .audio_models import AudioEnsemble
from .text_model import TextEmotionModel
from .calibration import CalibrationLayer, CalibrationConfig
from .fusion import AdaptiveFusionEngine, FusionConfig
from .uncertainty import UncertaintyEstimator
from .drift_monitor import DriftMonitor
from .exceptions import (
    EmotionServiceError,
    InvalidAudioFeaturesError,
    QualityScoreTooLowError,
    DurationTooShortError,
    UncertaintyTooHighError,
    LowConfidenceOutputError,
)
from .schemas import (
    EmotionAnalysisRequest,
    EmotionAnalysisResponse,
    AnalysisStatus,
    ModelPrediction,
    HealthCheckResponse,
)


logger = logging.getLogger(__name__)


class EmotionIntelligenceService:
    """
    Enterprise emotion intelligence service with ensemble models.
    
    Features:
    - Multi-model ensemble (Wav2Vec2, HuBERT, DistilRoBERTa)
    - Adaptive Bayesian fusion (NO fixed weights)
    - Temperature scaling calibration
    - Comprehensive uncertainty quantification
    - Real-time drift monitoring
    - Edge case handling (whisper, loud anger, flat TTS-like)
    
    Target: < 500ms p95 latency
    """
    
    def __init__(
        self,
        device: str = "cpu",
        enable_secondary_audio: bool = True,
        calibration_config: Optional[CalibrationConfig] = None,
        fusion_config: Optional[FusionConfig] = None,
    ):
        self.device = device
        
        # Core components
        self.audio_ensemble = AudioEnsemble(
            device=device, use_secondary=enable_secondary_audio
        )
        self.text_model = TextEmotionModel(device=device)
        
        # Processing layers
        self.calibration = CalibrationLayer(config=calibration_config)
        self.fusion_engine = AdaptiveFusionEngine(config=fusion_config)
        self.uncertainty_estimator = UncertaintyEstimator()
        self.drift_monitor = DriftMonitor()
        
        # State
        self.is_initialized = False
        self.inference_count = 0
        self.error_count = 0
        
        # Concurrency control
        self._semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests
    
    async def initialize(self):
        """Initialize all models and components"""
        logger.info("Initializing Emotion Intelligence Service...")
        
        start_time = datetime.now()
        
        try:
            # Load audio models
            self.audio_ensemble.load_models()
            
            # Load text model
            self.text_model.load()
            
            self.is_initialized = True
            
            init_time = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Emotion Intelligence Service initialized successfully in {init_time:.2f}s"
            )
        
        except Exception as e:
            logger.error(f"Service initialization failed: {e}")
            raise EmotionServiceError(f"Initialization failed: {e}")
    
    async def analyze_emotion(
        self, request: EmotionAnalysisRequest
    ) -> EmotionAnalysisResponse:
        """
        Analyze emotion from audio and text with comprehensive uncertainty.
        
        Pipeline:
        1. Validate input
        2. Run audio ensemble inference
        3. Run text model inference
        4. Calibrate probabilities
        5. Adaptive fusion
        6. Estimate uncertainty
        7. Monitor drift
        8. Return structured response
        """
        if not self.is_initialized:
            raise EmotionServiceError("Service not initialized")
        
        async with self._semaphore:
            return await self._analyze_internal(request)
    
    async def _analyze_internal(
        self, request: EmotionAnalysisRequest
    ) -> EmotionAnalysisResponse:
        """Internal analysis implementation"""
        start_time = datetime.now()
        
        try:
            # Step 1: Validate input
            self._validate_request(request)
            
            # Step 2: Load audio (placeholder - in production, load from ref)
            audio, sample_rate = self._load_audio(request)
            
            # Step 3: Audio ensemble inference
            audio_start = datetime.now()
            audio_primary, audio_secondary = self.audio_ensemble.predict(
                audio, sample_rate
            )
            audio_inference_time = (
                datetime.now() - audio_start
            ).total_seconds() * 1000
            
            # Step 4: Text model inference
            text_start = datetime.now()
            text_prediction = self.text_model.predict(request.transcript)
            text_inference_time = (
                datetime.now() - text_start
            ).total_seconds() * 1000
            
            # Step 5: Calibrate audio predictions
            audio_calibrated, audio_cal_info = self.calibration.calibrate_audio_probs(
                probs=audio_primary.probabilities,
                volume_level=self._infer_volume_level(request.energy_band),
                energy_band=request.energy_band,
            )
            
            # Step 6: Calibrate text predictions
            text_calibrated, text_cal_info = self.calibration.calibrate_text_probs(
                probs=text_prediction.probabilities
            )
            
            # Step 7: Adaptive fusion
            fusion_start = datetime.now()
            fused_probs, fusion_weights = self.fusion_engine.fuse(
                audio_probs=audio_calibrated,
                text_probs=text_calibrated,
                audio_entropy=audio_primary.entropy,
                text_entropy=text_prediction.entropy,
                stt_confidence=request.stt_confidence,
                quality_score=request.quality_score,
                energy_band=request.energy_band,
                audio_confidence=audio_primary.model_confidence,
                text_confidence=text_prediction.model_confidence,
            )
            fusion_time = (datetime.now() - fusion_start).total_seconds() * 1000
            
            # Step 8: Estimate uncertainty
            model_predictions = [audio_primary, text_prediction]
            if audio_secondary:
                model_predictions.append(audio_secondary)
            
            uncertainty_metrics = self.uncertainty_estimator.estimate(
                fused_probs=fused_probs,
                model_predictions=model_predictions,
            )
            
            # Step 9: Determine final label and confidence
            final_label = max(fused_probs, key=fused_probs.get)
            final_confidence = fused_probs[final_label]
            
            # Step 10: Check uncertainty thresholds
            if request.max_entropy_threshold and uncertainty_metrics.entropy > request.max_entropy_threshold:
                logger.warning(
                    f"Entropy {uncertainty_metrics.entropy:.3f} exceeds threshold "
                    f"{request.max_entropy_threshold}"
                )
            
            if request.min_confidence_threshold and final_confidence < request.min_confidence_threshold:
                logger.warning(
                    f"Confidence {final_confidence:.3f} below threshold "
                    f"{request.min_confidence_threshold}"
                )
            
            # Step 11: Record for drift monitoring
            self.drift_monitor.record_prediction(
                predicted_label=final_label,
                entropy=uncertainty_metrics.entropy,
                confidence=final_confidence,
                uncertainty_flag=uncertainty_metrics.uncertainty_flag,
            )
            
            # Step 12: Build response
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            self.inference_count += 1
            
            response = EmotionAnalysisResponse(
                audio_id=request.audio_id,
                status=AnalysisStatus.SUCCESS,
                label=final_label,
                confidence=final_confidence,
                probabilities=fused_probs,
                uncertainty_metrics=uncertainty_metrics,
                model_predictions=model_predictions,
                calibration_info=audio_cal_info,  # Return audio calibration info
                fusion_weights=fusion_weights,
                processing_time_ms=processing_time,
                audio_inference_time_ms=audio_inference_time,
                text_inference_time_ms=text_inference_time,
                fusion_time_ms=fusion_time,
            )
            
            return response
        
        except Exception as e:
            self.error_count += 1
            logger.error(f"Emotion analysis failed: {e}")
            
            # Return error response
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return EmotionAnalysisResponse(
                audio_id=request.audio_id,
                status=AnalysisStatus.ERROR,
                label="neutral",  # Safe fallback
                confidence=0.0,
                probabilities={"angry": 0.0, "happy": 0.0, "neutral": 1.0, "sad": 0.0},
                uncertainty_metrics=None,
                model_predictions=[],
                calibration_info=None,
                fusion_weights=None,
                processing_time_ms=processing_time,
                audio_inference_time_ms=0.0,
                text_inference_time_ms=0.0,
                fusion_time_ms=0.0,
                error_message=str(e),
            )
    
    def _validate_request(self, request: EmotionAnalysisRequest):
        """Validate analysis request"""
        # Check quality score
        if request.quality_score < 0.3:
            raise QualityScoreTooLowError(
                quality_score=request.quality_score,
                threshold=0.3,
            )
        
        # Check duration
        if request.duration_seconds < 0.5:
            raise DurationTooShortError(
                duration=request.duration_seconds,
                minimum=0.5,
            )
    
    def _load_audio(
        self, request: EmotionAnalysisRequest
    ) -> tuple[np.ndarray, int]:
        """
        Load audio from reference.
        
        In production, would load from storage using waveform_ref or mel_features_ref.
        For now, return placeholder synthetic audio.
        """
        # Placeholder - generate synthetic audio
        sample_rate = 16000
        duration = request.duration_seconds
        
        # Generate simple sine wave
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = np.sin(2 * np.pi * 440 * t) * 0.3  # 440 Hz A note
        
        return audio, sample_rate
    
    def _infer_volume_level(self, energy_band: Optional[str]) -> float:
        """Infer volume level from energy band"""
        if energy_band == "low":
            return 0.2
        elif energy_band == "medium":
            return 0.5
        elif energy_band == "high":
            return 0.8
        else:
            return 0.5  # Default
    
    async def health_check(self) -> HealthCheckResponse:
        """Get service health status"""
        model_status = self.audio_ensemble.get_model_status()
        
        # Compute error rate
        total_requests = self.inference_count + self.error_count
        error_rate = self.error_count / total_requests if total_requests > 0 else 0.0
        
        # Get drift metrics
        metrics = self.drift_monitor.get_metrics_snapshot()
        
        return HealthCheckResponse(
            status="healthy" if self.is_initialized else "initializing",
            models_loaded={
                "audio_primary": model_status["primary_loaded"],
                "audio_secondary": model_status["secondary_loaded"],
                "text": self.text_model.is_loaded,
            },
            total_requests=total_requests,
            error_rate=error_rate,
            neutral_rate=metrics.neutral_rate,
            uncertainty_rate=metrics.uncertainty_rate,
            active_alerts=len(self.drift_monitor.get_active_alerts()),
        )
    
    def get_metrics_snapshot(self):
        """Get comprehensive metrics snapshot"""
        return self.drift_monitor.get_metrics_snapshot()
    
    def get_drift_alerts(self):
        """Get active drift alerts"""
        return self.drift_monitor.get_active_alerts()
