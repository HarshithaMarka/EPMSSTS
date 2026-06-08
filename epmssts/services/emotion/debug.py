"""
Emotion Detection Debugging & Diagnostics

Real-time logging and visualization of emotion detection pipeline
for diagnosing "sad" bias and other prediction issues.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from epmssts.services.emotion.audio_emotion import EmotionPrediction
from epmssts.services.emotion.audio_preprocessing import EmotionAudioMetrics


logger = logging.getLogger("epmssts.emotion.debug")


@dataclass
class EmotionDebugInfo:
    """Complete debug information for emotion detection pipeline."""
    request_id: str
    stage: str                          # "preprocessing", "inference", "fusion", "override"
    audio_metrics: Optional[EmotionAudioMetrics] = None
    raw_prediction: Optional[EmotionPrediction] = None
    confidence: Optional[float] = None
    override_reason: Optional[str] = None
    override_to: Optional[str] = None
    text_prediction: Optional[EmotionPrediction] = None
    fusion_audio_weight: Optional[float] = None
    fusion_text_weight: Optional[float] = None
    final_prediction: Optional[EmotionPrediction] = None
    latency_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, handling nested dataclasses."""
        data = asdict(self)
        
        # Convert nested EmotionAudioMetrics
        if self.audio_metrics is not None:
            data["audio_metrics"] = self.audio_metrics.to_dict()
        
        # Convert EmotionPrediction objects
        if self.raw_prediction is not None:
            data["raw_prediction"] = {
                "label": self.raw_prediction.label,
                "confidence": round(self.raw_prediction.confidence, 4),
                "scores": {k: round(v, 4) for k, v in self.raw_prediction.scores.items()},
            }
        
        if self.text_prediction is not None:
            data["text_prediction"] = {
                "label": self.text_prediction.label,
                "confidence": round(self.text_prediction.confidence, 4),
                "scores": {k: round(v, 4) for k, v in self.text_prediction.scores.items()},
            }
        
        if self.final_prediction is not None:
            data["final_prediction"] = {
                "label": self.final_prediction.label,
                "confidence": round(self.final_prediction.confidence, 4),
                "scores": {k: round(v, 4) for k, v in self.final_prediction.scores.items()},
            }
        
        return data


class EmotionDebugger:
    """Comprehensive debugging for emotion detection pipeline."""
    
    def __init__(self, request_id: str, enable_verbose: bool = False):
        self.request_id = request_id
        self.enable_verbose = enable_verbose
        self.logs: list[EmotionDebugInfo] = []
    
    def log_preprocessing(
        self,
        audio_metrics: EmotionAudioMetrics,
        latency_ms: Optional[float] = None,
    ) -> None:
        """Log audio preprocessing metrics."""
        info = EmotionDebugInfo(
            request_id=self.request_id,
            stage="preprocessing",
            audio_metrics=audio_metrics,
            latency_ms=latency_ms,
        )
        self.logs.append(info)
        
        if self.enable_verbose:
            logger.info(
                "[%s] PREPROCESSING | energy=%s rms_db=%.2f peak_db=%.2f "
                "spectral_centroid=%.1f dyn_range=%.1f",
                self.request_id,
                audio_metrics.energy_level,
                audio_metrics.rms_db,
                audio_metrics.peak_db,
                audio_metrics.spectral_centroid,
                audio_metrics.dynamic_range,
            )
    
    def log_audio_inference(
        self,
        prediction: EmotionPrediction,
        latency_ms: Optional[float] = None,
    ) -> None:
        """Log raw audio emotion inference."""
        info = EmotionDebugInfo(
            request_id=self.request_id,
            stage="inference",
            raw_prediction=prediction,
            confidence=prediction.confidence,
            latency_ms=latency_ms,
        )
        self.logs.append(info)
        
        if self.enable_verbose:
            top_3 = sorted(
                prediction.scores.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3]
            logger.info(
                "[%s] AUDIO INFERENCE | prediction=%s conf=%.3f | top3=%s",
                self.request_id,
                prediction.label,
                prediction.confidence,
                [(e, f"{c:.3f}") for e, c in top_3],
            )
    
    def log_override(
        self,
        override_to: str,
        reason: str,
        audio_metrics: Optional[EmotionAudioMetrics] = None,
    ) -> None:
        """Log energy-based override."""
        info = EmotionDebugInfo(
            request_id=self.request_id,
            stage="override",
            override_to=override_to,
            override_reason=reason,
            audio_metrics=audio_metrics,
        )
        self.logs.append(info)
        
        logger.warning(
            "[%s] OVERRIDE | reason=%s → %s",
            self.request_id,
            reason,
            override_to,
        )
    
    def log_fusion(
        self,
        audio_pred: EmotionPrediction,
        text_pred: Optional[EmotionPrediction],
        audio_weight: float,
        text_weight: float,
        final_pred: EmotionPrediction,
    ) -> None:
        """Log emotion fusion results."""
        info = EmotionDebugInfo(
            request_id=self.request_id,
            stage="fusion",
            raw_prediction=audio_pred,
            text_prediction=text_pred,
            fusion_audio_weight=audio_weight,
            fusion_text_weight=text_weight,
            final_prediction=final_pred,
        )
        self.logs.append(info)
        
        if self.enable_verbose:
            text_info = f"text={text_pred.label}({text_pred.confidence:.2f})" if text_pred else "none"
            logger.info(
                "[%s] FUSION | audio=%s(%.2f) %s → final=%s(%.2f) | weights=audio%.2f text%.2f",
                self.request_id,
                audio_pred.label,
                audio_pred.confidence,
                text_info,
                final_pred.label,
                final_pred.confidence,
                audio_weight,
                text_weight,
            )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all debug logs."""
        return {
            "request_id": self.request_id,
            "pipeline_steps": len(self.logs),
            "logs": [log.to_dict() for log in self.logs],
        }


def create_emotion_debug_report(
    request_id: str,
    audio_metrics: EmotionAudioMetrics,
    raw_audio_prediction: EmotionPrediction,
    text_prediction: Optional[EmotionPrediction],
    final_prediction: EmotionPrediction,
    override_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a comprehensive debug report for emotion detection.
    
    Use this for POST-HOC analysis of failed predictions.
    """
    return {
        "request_id": request_id,
        "audio": {
            "metrics": audio_metrics.to_dict(),
            "raw_prediction": {
                "label": raw_audio_prediction.label,
                "confidence": round(raw_audio_prediction.confidence, 4),
                "scores": {k: round(v, 4) for k, v in raw_audio_prediction.scores.items()},
            },
        },
        "text": {
            "prediction": {
                "label": text_prediction.label,
                "confidence": round(text_prediction.confidence, 4),
                "scores": {k: round(v, 4) for k, v in text_prediction.scores.items()},
            } if text_prediction else None,
        },
        "final": {
            "label": final_prediction.label,
            "confidence": round(final_prediction.confidence, 4),
            "scores": {k: round(v, 4) for k, v in final_prediction.scores.items()},
            "override_reason": override_reason,
        },
    }


__all__ = [
    "EmotionDebugInfo",
    "EmotionDebugger",
    "create_emotion_debug_report",
]
