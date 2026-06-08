from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from epmssts.services.dialect.classifier import DialectClassifier
from epmssts.services.emotion.audio_emotion import AudioEmotionService
from epmssts.services.stt.transcriber import SpeechToTextService

from .calibration import ConfidenceCalibrator
from .config import ProductionSettings, validate_production_config
from .diarization import SpeakerDiarizer
from .drift_monitor import DriftMonitor
from .edge_defense import EdgeCaseDefenseSystem
from .metrics import ProductionMetrics
from .security import SecurityRuntime
from .session_memory import SessionMemoryEngine
from .streaming_engine import StreamingInferenceEngine


@dataclass
class ProductionRuntime:
    settings: ProductionSettings
    metrics: ProductionMetrics
    session_memory: SessionMemoryEngine
    edge_defense: EdgeCaseDefenseSystem
    diarizer: SpeakerDiarizer
    drift_monitor: DriftMonitor
    calibrator: ConfidenceCalibrator
    security: SecurityRuntime
    streaming_engine: StreamingInferenceEngine


def build_production_runtime(
    *,
    stt_service: SpeechToTextService,
    emotion_service: AudioEmotionService,
    dialect_classifier: DialectClassifier,
) -> ProductionRuntime:
    settings = ProductionSettings()
    validation = validate_production_config(settings)
    if not validation.valid:
        raise SystemExit(f"Invalid production configuration: {validation.errors}")

    metrics = ProductionMetrics()
    session_memory = SessionMemoryEngine()
    edge_defense = EdgeCaseDefenseSystem()
    diarizer = SpeakerDiarizer()
    drift_monitor = DriftMonitor(
        baseline_size=settings.drift_baseline_size,
        window_size=settings.drift_window_size,
        kl_threshold=settings.drift_kl_threshold,
        psi_threshold=settings.drift_psi_threshold,
    )
    calibrator = ConfidenceCalibrator(
        artifact_path=Path(settings.calibration_artifact_path),
        initial_temperature=settings.calibration_temperature,
        recompute_days=settings.calibration_recompute_days,
    )
    calibrator.maybe_recompute_from_dataset(Path("data/calibration/calibration_labels.jsonl"))
    security = SecurityRuntime(settings=settings)

    streaming_engine = StreamingInferenceEngine(
        stt_service=stt_service,
        emotion_service=emotion_service,
        dialect_classifier=dialect_classifier,
        session_memory=session_memory,
        edge_defense=edge_defense,
        diarizer=diarizer,
        drift_monitor=drift_monitor,
        calibrator=calibrator,
        metrics=metrics,
        max_latency_seconds=settings.stream_max_latency_seconds,
        queue_size=settings.stream_queue_size,
        session_ttl_seconds=settings.stream_session_ttl_seconds,
    )

    return ProductionRuntime(
        settings=settings,
        metrics=metrics,
        session_memory=session_memory,
        edge_defense=edge_defense,
        diarizer=diarizer,
        drift_monitor=drift_monitor,
        calibrator=calibrator,
        security=security,
        streaming_engine=streaming_engine,
    )
