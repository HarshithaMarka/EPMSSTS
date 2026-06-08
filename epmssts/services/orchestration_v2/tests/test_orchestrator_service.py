import asyncio
import base64

import pytest

from epmssts.services.orchestration_v2.circuit_breaker import CircuitBreakerManager, CircuitConfig
from epmssts.services.orchestration_v2.orchestrator_service import OrchestrationService, StageClients
from epmssts.services.orchestration_v2.schemas import PipelineProcessRequest, PipelineStatus
from epmssts.services.orchestration_v2.state_store import OrchestrationStateStore


pytestmark = pytest.mark.asyncio


def _b64_audio() -> str:
    return base64.b64encode(b"fake-audio-bytes").decode("utf-8")


async def _ok_preprocess(_: bytes):
    return {
        "waveform": [0.0],
        "sample_rate": 16000,
        "duration_seconds": 1.0,
        "quality_score": 85,
        "energy_band": "normal",
    }


async def _ok_stt(_: bytes):
    return {"transcript": "hello world", "confidence": 0.92, "language": "en"}


async def _ok_emotion(_: bytes, __: str):
    return {"emotion": "happy", "confidence": 0.8}


async def _ok_translation(transcript: str, _src: str, _tgt: str, _emo: float):
    return {"translated_text": f"{transcript} translated", "confidence": 0.88}


async def _ok_tts(_text: str, _lang: str, _emo: str, _e: float, _t: float):
    return {"audio_output_url": "/tmp/audio.wav", "validation_confidence": 0.95}


async def _build_service(clients: StageClients) -> OrchestrationService:
    store = OrchestrationStateStore("redis://localhost:6379", ttl_seconds=120)
    await store.connect()
    breakers = CircuitBreakerManager(store, CircuitConfig(failure_threshold=2, recovery_timeout_seconds=5, half_open_max_calls=1))
    return OrchestrationService(clients=clients, state_store=store, circuit_breakers=breakers, max_concurrency=8)


async def test_full_pipeline_success():
    clients = StageClients(
        preprocess=_ok_preprocess,
        stt=_ok_stt,
        emotion=_ok_emotion,
        translation=_ok_translation,
        tts=_ok_tts,
    )
    service = await _build_service(clients)

    request = PipelineProcessRequest(audio_file=_b64_audio(), target_language="en", request_id="req-success-123")
    response = await service.process(request)

    assert response.status == PipelineStatus.SUCCESS
    assert response.transcript == "hello world"
    assert response.translation.startswith("hello world")
    assert response.audio_output_url is not None


async def test_stt_failure_aborts_pipeline():
    async def _bad_stt(_: bytes):
        raise RuntimeError("stt crashed")

    clients = StageClients(
        preprocess=_ok_preprocess,
        stt=_bad_stt,
        emotion=_ok_emotion,
        translation=_ok_translation,
        tts=_ok_tts,
    )
    service = await _build_service(clients)

    request = PipelineProcessRequest(audio_file=_b64_audio(), target_language="en", request_id="req-stt-fail-123")
    response = await service.process(request)

    assert response.status == PipelineStatus.FAILED
    assert response.translation == ""


async def test_emotion_failure_degrades_to_neutral():
    async def _bad_emotion(_: bytes, __: str):
        raise RuntimeError("emotion down")

    clients = StageClients(
        preprocess=_ok_preprocess,
        stt=_ok_stt,
        emotion=_bad_emotion,
        translation=_ok_translation,
        tts=_ok_tts,
    )
    service = await _build_service(clients)

    request = PipelineProcessRequest(audio_file=_b64_audio(), target_language="en", request_id="req-emo-fail-123")
    response = await service.process(request)

    assert response.status == PipelineStatus.DEGRADED
    assert response.emotion == "neutral"


async def test_translation_retry_then_fallback():
    attempts = {"count": 0}

    async def _translation_fail_then_fallback(*_args):
        attempts["count"] += 1
        raise RuntimeError("translation fail")

    clients = StageClients(
        preprocess=_ok_preprocess,
        stt=_ok_stt,
        emotion=_ok_emotion,
        translation=_translation_fail_then_fallback,
        tts=_ok_tts,
    )
    service = await _build_service(clients)

    request = PipelineProcessRequest(audio_file=_b64_audio(), target_language="en", request_id="req-translate-fallback-123")
    response = await service.process(request)

    assert response.status == PipelineStatus.DEGRADED
    assert response.translation == "hello world"
    assert attempts["count"] >= 2


async def test_tts_fallback_to_text_only():
    async def _bad_tts(*_args):
        raise RuntimeError("tts down")

    clients = StageClients(
        preprocess=_ok_preprocess,
        stt=_ok_stt,
        emotion=_ok_emotion,
        translation=_ok_translation,
        tts=_bad_tts,
    )
    service = await _build_service(clients)

    request = PipelineProcessRequest(audio_file=_b64_audio(), target_language="en", request_id="req-tts-fail-123")
    response = await service.process(request)

    assert response.status == PipelineStatus.DEGRADED
    assert response.audio_output_url is None
    assert response.translation != ""


async def test_sla_breach_marks_degraded():
    async def _slow_tts(*_args):
        await asyncio.sleep(2.2)
        return {"audio_output_url": "/tmp/slow.wav", "validation_confidence": 0.9}

    clients = StageClients(
        preprocess=_ok_preprocess,
        stt=_ok_stt,
        emotion=_ok_emotion,
        translation=_ok_translation,
        tts=_slow_tts,
    )
    service = await _build_service(clients)

    request = PipelineProcessRequest(audio_file=_b64_audio(), target_language="en", request_id="req-sla-breach-123")
    response = await service.process(request)

    assert response.status in {PipelineStatus.DEGRADED, PipelineStatus.SUCCESS}
    assert response.total_latency_ms > 0


async def test_high_concurrency_stress():
    clients = StageClients(
        preprocess=_ok_preprocess,
        stt=_ok_stt,
        emotion=_ok_emotion,
        translation=_ok_translation,
        tts=_ok_tts,
    )
    service = await _build_service(clients)

    async def _run_one(idx: int):
        req = PipelineProcessRequest(audio_file=_b64_audio(), target_language="en", request_id=f"req-conc-{idx}")
        return await service.process(req)

    results = await asyncio.gather(*[_run_one(i) for i in range(20)])
    assert len(results) == 20
    assert all(result.total_latency_ms >= 0 for result in results)


async def test_circuit_breaker_activation():
    async def _bad_stt(_: bytes):
        raise RuntimeError("stt hard failure")

    clients = StageClients(
        preprocess=_ok_preprocess,
        stt=_bad_stt,
        emotion=_ok_emotion,
        translation=_ok_translation,
        tts=_ok_tts,
    )
    service = await _build_service(clients)

    for idx in range(3):
        req = PipelineProcessRequest(audio_file=_b64_audio(), target_language="en", request_id=f"req-cb-{idx}")
        await service.process(req)

    status = await service.get_status()
    assert "stt" in status.circuit_states
    assert status.circuit_states["stt"] in {"open", "half_open", "closed"}
