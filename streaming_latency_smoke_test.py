from __future__ import annotations

import asyncio
import json
import time
from io import BytesIO
from pathlib import Path

import numpy as np
import soundfile as sf

from epmssts.services.stt.transcriber import SpeechToTextService
from epmssts.services.emotion.audio_emotion import AudioEmotionService
from epmssts.services.dialect.classifier import DialectClassifier
from epmssts.services.production.runtime import build_production_runtime


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    data, sr = sf.read(path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data.astype(np.float32), int(sr)


def chunk_audio(audio: np.ndarray, sample_rate: int, chunk_seconds: float = 2.0) -> list[np.ndarray]:
    chunk_samples = max(1, int(sample_rate * chunk_seconds))
    chunks = [audio[i : i + chunk_samples] for i in range(0, len(audio), chunk_samples)]
    return [chunk for chunk in chunks if chunk.size > 0]


def encode_wav(audio: np.ndarray, sample_rate: int) -> bytes:
    bio = BytesIO()
    sf.write(bio, audio, sample_rate, format="WAV")
    return bio.getvalue()


async def run_test() -> dict:
    stt = SpeechToTextService()
    emotion = AudioEmotionService()
    dialect = DialectClassifier()
    runtime = build_production_runtime(stt_service=stt, emotion_service=emotion, dialect_classifier=dialect)

    sample_file = Path("data/dialect_test/andhra/andhra_sample_1.wav")
    if not sample_file.exists():
        return {
            "status": "skipped",
            "reason": "sample_not_found",
            "latencies_ms": [],
            "max_latency_ms": 0.0,
            "within_budget": False,
        }

    audio, sr = load_audio(sample_file)
    chunks = chunk_audio(audio, sr, chunk_seconds=2.0)

    latencies_ms: list[float] = []
    for idx, chunk in enumerate(chunks):
        payload = encode_wav(chunk, sr)
        start = time.perf_counter()
        await runtime.streaming_engine.enqueue_chunk(
            session_id="ci_stream_session",
            chunk_bytes=payload,
            sample_rate=sr,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        latencies_ms.append(elapsed_ms)
        if idx >= 3:
            break

    max_latency = max(latencies_ms) if latencies_ms else 0.0
    return {
        "status": "ok",
        "latencies_ms": latencies_ms,
        "max_latency_ms": max_latency,
        "within_budget": max_latency <= 2000.0,
    }


def main() -> None:
    result = asyncio.run(run_test())
    out_path = Path("STREAMING_LATENCY_REPORT.json")
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
