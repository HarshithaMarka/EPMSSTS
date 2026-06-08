"""
Dialect detection services package.

Provides acoustic-based Telugu dialect classification (Andhra vs Telangana)
using Wav2Vec2 embeddings and trained classifier head.

NO keyword dependence. NO volume bias. NO speaker leakage.
"""

from .acoustic_classifier import (
    AcousticDialectClassifier,
    DialectPrediction,
    AcousticFeatures
)
from .classifier import DialectClassifier as KeywordDialectClassifier
from .production_pipeline import (
    ProductionDialectModel,
    load_real_corpus,
    validate_real_corpus,
    speaker_disjoint_split,
    check_no_speaker_overlap,
)
from .drift_monitor import DialectDriftMonitor

__all__ = [
    'AcousticDialectClassifier',
    'KeywordDialectClassifier',
    'DialectPrediction',
    'AcousticFeatures',
    'ProductionDialectModel',
    'load_real_corpus',
    'validate_real_corpus',
    'speaker_disjoint_split',
    'check_no_speaker_overlap',
    'DialectDriftMonitor',
]

