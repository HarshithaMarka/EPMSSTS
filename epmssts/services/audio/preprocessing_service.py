"""
Main Audio Preprocessing Service.

Orchestrates validation, processing, metrics extraction, quality scoring, and observability.
"""

import time
import uuid
from typing import Tuple, Optional, Dict, List
from datetime import datetime
import numpy as np
from collections import defaultdict

from .validators import AudioValidator
from .pipeline import SignalProcessingPipeline, PipelineConfig
from .metrics import SignalMetricsExtractor
from .quality_scorer import QualityScorer
from .schemas import (
    AudioPreprocessResponse,
    AudioPreprocessErrorResponse,
    SignalMetrics,
    EnergyBand,
)
from .exceptions import AudioPreprocessingException, ErrorReasonCode
from .logging_config import get_logger

logger = get_logger(__name__)


class PreprocessingMetrics:
    """Tracks metrics for observability."""
    
    def __init__(self):
        """Initialize metrics."""
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        
        self.latencies: List[float] = []
        self.quality_scores: List[int] = []
        self.energy_band_distribution: Dict[str, int] = defaultdict(int)
        self.error_codes: Dict[str, int] = defaultdict(int)
    
    def record_request(
        self,
        success: bool,
        latency_ms: float,
        quality_score: Optional[int] = None,
        energy_band: Optional[str] = None,
        error_code: Optional[str] = None,
    ):
        """Record metrics from a request."""
        self.total_requests += 1
        
        if success:
            self.successful_requests += 1
            self.latencies.append(latency_ms)
            self.quality_scores.append(quality_score)
            self.energy_band_distribution[energy_band] += 1
        else:
            self.failed_requests += 1
            if error_code:
                self.error_codes[error_code] += 1
    
    def get_percentile(self, arr: List[float], p: int) -> float:
        """Get percentile from array."""
        if not arr:
            return 0.0
        sorted_arr = sorted(arr)
        idx = int(len(sorted_arr) * p / 100)
        return sorted_arr[min(idx, len(sorted_arr) - 1)]


class AudioPreprocessingService:
    """Production-grade audio preprocessing service."""
    
    def __init__(
        self,
        pipeline_config: Optional[PipelineConfig] = None,
        validator_config: Optional[Dict] = None,
    ):
        """Initialize preprocessing service."""
        self.pipeline = SignalProcessingPipeline(pipeline_config)
        self.validator = AudioValidator(**(validator_config or {}))
        self.metrics_extractor = SignalMetricsExtractor()
        self.quality_scorer = QualityScorer()
        
        self.metrics = PreprocessingMetrics()
    
    def preprocess(self, file_path: str) -> Tuple[AudioPreprocessResponse, Dict]:
        """
        Preprocess audio file end-to-end.
        
        Args:
            file_path: Path to audio file
        
        Returns:
            Tuple[response, internal_data]
        """
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.set_context(request_id=request_id, file_path=file_path)
        
        try:
            # 1. Validate input
            is_valid, error_msg = self.validator.validate(file_path)
            if not is_valid:
                raise AudioPreprocessingException(
                    error_msg,
                    ErrorReasonCode.CORRUPT_FILE,
                    {"file_path": file_path}
                )
            
            # 2. Process audio through pipeline
            waveform, mel_spec, energy_band, silence_ratio = self.pipeline.process(file_path)
            
            # 3. Extract metrics BEFORE normalization
            # Note: pipeline returns post-processed waveform, so metrics reflect final state
            metrics = self.metrics_extractor.extract(waveform, self.pipeline.config.target_sample_rate)
            
            # 4. Compute quality score
            duration = len(waveform) / self.pipeline.config.target_sample_rate
            quality_score = self.quality_scorer.score(metrics, silence_ratio, duration)
            
            # 5. Build response
            latency_ms = (time.time() - start_time) * 1000
            
            response = AudioPreprocessResponse(
                status="success",
                duration_seconds=duration,
                sample_rate=self.pipeline.config.target_sample_rate,
                metrics=metrics,
                energy_band=energy_band,
                silence_ratio=silence_ratio,
                quality_score=quality_score,
                preprocessing_latency_ms=latency_ms,
                waveform_shape=list(waveform.shape),
                mel_shape=list(mel_spec.shape),
                request_id=request_id,
                timestamp=datetime.utcnow(),
            )
            
            # 6. Record metrics
            self.metrics.record_request(
                success=True,
                latency_ms=latency_ms,
                quality_score=quality_score,
                energy_band=energy_band.value,
            )
            
            logger.info(
                "Preprocessing successful",
                latency_ms=latency_ms,
                quality_score=quality_score,
                duration=duration,
                energy_band=energy_band.value,
            )
            
            logger.clear_context()
            
            return response, {
                "waveform": waveform,
                "mel_spec": mel_spec,
            }
        
        except AudioPreprocessingException as e:
            return self._handle_error(
                e,
                request_id,
                start_time,
                file_path
            )
        except Exception as e:
            return self._handle_error(
                AudioPreprocessingException(
                    str(e),
                    ErrorReasonCode.INTERNAL_ERROR,
                    {"file_path": file_path}
                ),
                request_id,
                start_time,
                file_path
            )
    
    def _handle_error(
        self,
        exc: AudioPreprocessingException,
        request_id: str,
        start_time: float,
        file_path: str,
    ) -> Tuple[AudioPreprocessErrorResponse, Dict]:
        """Handle preprocessing error with structured response."""
        latency_ms = (time.time() - start_time) * 1000
        
        error_response = AudioPreprocessErrorResponse(
            status="error",
            reason_code=exc.reason_code.value,
            message=exc.message,
            details=exc.details,
            request_id=request_id,
            timestamp=datetime.utcnow(),
        )
        
        # Record metrics
        self.metrics.record_request(
            success=False,
            latency_ms=latency_ms,
            error_code=exc.reason_code.value,
        )
        
        logger.warning(
            "Preprocessing failed",
            reason_code=exc.reason_code.value,
            latency_ms=latency_ms,
        )
        
        logger.clear_context()
        
        return error_response, {}
    
    def get_metrics_summary(self) -> Dict:
        """Get metrics summary for observability."""
        return {
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "success_rate": (
                self.metrics.successful_requests / self.metrics.total_requests
                if self.metrics.total_requests > 0
                else 0.0
            ),
            "latency": {
                "p50_ms": self.metrics.get_percentile(self.metrics.latencies, 50),
                "p95_ms": self.metrics.get_percentile(self.metrics.latencies, 95),
                "p99_ms": self.metrics.get_percentile(self.metrics.latencies, 99),
                "count": len(self.metrics.latencies),
            },
            "quality": {
                "avg_score": (
                    sum(self.metrics.quality_scores) / len(self.metrics.quality_scores)
                    if self.metrics.quality_scores
                    else 0.0
                ),
                "low_quality_count": sum(
                    1 for score in self.metrics.quality_scores if score < 50
                ),
            },
            "energy_bands": dict(self.metrics.energy_band_distribution),
            "errors": dict(self.metrics.error_codes),
        }
