"""
Basic sanity tests for STT wiring.

These are intentionally lightweight and do not assert on specific
transcriptions, only that the pipeline is callable.
"""

import numpy as np

from epmssts.services.stt.transcriber import SpeechToTextService


def test_stt_service_initializes():
    service = SpeechToTextService()
    assert service is not None


def test_is_silent_detects_zero_audio():
    service = SpeechToTextService()
    audio = np.zeros(16000, dtype=np.float32)
    assert service.is_silent(audio)

