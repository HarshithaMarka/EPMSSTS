from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from io import BytesIO
import soundfile as sf

from epmssts.services.production.runtime import ProductionRuntime
from epmssts.services.production.security import SecurityError


router = APIRouter(prefix="/stream", tags=["Streaming Inference"])
_runtime: ProductionRuntime | None = None


def set_streaming_runtime(runtime: ProductionRuntime) -> None:
    global _runtime
    _runtime = runtime


@router.websocket("/ws")
async def stream_websocket(websocket: WebSocket):
    await websocket.accept()

    runtime = _runtime
    if runtime is None:
        await websocket.send_json({"status": "error", "error": "runtime_unavailable"})
        await websocket.close(code=1011)
        return

    try:
        await runtime.security.validate_websocket(websocket)
    except SecurityError as exc:
        await websocket.send_json({"status": "error", "error": exc.code, "message": exc.message})
        await websocket.close(code=1008)
        return

    session_id = websocket.headers.get("x-session-id") or str(uuid4())
    await websocket.send_json({"status": "connected", "session_id": session_id})

    try:
        while True:
            packet = await websocket.receive_bytes()
            try:
                runtime.security.validate_request_size(len(packet))
                with sf.SoundFile(BytesIO(packet)) as snd_file:
                    duration_sec = len(snd_file) / max(1, snd_file.samplerate)
                runtime.security.validate_audio_duration(duration_sec)
                result = await runtime.streaming_engine.enqueue_chunk(
                    session_id=session_id,
                    chunk_bytes=packet,
                    sample_rate=16000,
                )
            except SecurityError as exc:
                result = {"status": "error", "error": exc.code, "message": exc.message}
            except TimeoutError:
                result = {
                    "status": "degraded",
                    "reason": "processing_timeout",
                    "partial_transcript": "",
                    "emotion": "neutral",
                    "dialect": "standard_telugu",
                    "confidence": 0.0,
                }
            await websocket.send_json(result)
    except WebSocketDisconnect:
        pass
    finally:
        runtime.streaming_engine.cleanup_sessions()


@router.get("/drift")
async def get_drift_report():
    runtime = _runtime
    if runtime is None:
        return {"status": "error", "error": "runtime_unavailable"}

    report = runtime.drift_monitor.report()
    return report.to_dict()


@router.get("/session/{session_id}")
async def get_session_state(session_id: str):
    runtime = _runtime
    if runtime is None:
        return {"status": "error", "error": "runtime_unavailable"}

    context = runtime.session_memory.get_context(session_id)
    return {
        "session_id": session_id,
        "emotion_ema": context.emotion_ema,
        "dialect_persistent": context.dialect_persistent,
        "speaker_states": context.speaker_states,
        "last_updated_ts": context.last_updated_ts,
    }
