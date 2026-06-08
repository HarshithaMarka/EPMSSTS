"""
Integration tests for API endpoints.
"""

import io
from contextlib import asynccontextmanager
import pytest
from httpx import AsyncClient, ASGITransport
import numpy as np
import soundfile as sf

from epmssts.api.main import app


@asynccontextmanager
async def get_test_client(**kwargs):
    """Create an AsyncClient bound to the FastAPI ASGI app with lifespan."""
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", **kwargs) as client:
            yield client


@pytest.fixture
def sample_audio_bytes():
    """Generate sample WAV audio bytes for testing."""
    # Generate 2 seconds of random audio at 16kHz
    audio = np.random.randn(32000).astype(np.float32) * 0.1
    buf = io.BytesIO()
    sf.write(buf, audio, 16000, format='WAV')
    return buf.getvalue()


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    async with get_test_client() as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_metrics_endpoint():
    """Test metrics endpoint is available or returns 503 if dependency missing."""
    async with get_test_client() as client:
        response = await client.get("/metrics")
        assert response.status_code in [200, 503]


@pytest.mark.asyncio
async def test_stt_transcribe_endpoint(sample_audio_bytes):
    """Test STT transcribe endpoint."""
    async with get_test_client() as client:
        files = {"file": ("test.wav", sample_audio_bytes, "audio/wav")}
        response = await client.post("/stt/transcribe", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "text" in data
        assert "language" in data
        assert "duration" in data
        assert "segments" in data
        assert "meta" in data
        assert data["meta"]["schema_version"]
        assert data["meta"]["stage"] == "stt"


@pytest.mark.asyncio
async def test_emotion_detect_endpoint(sample_audio_bytes):
    """Test emotion detection endpoint."""
    async with get_test_client() as client:
        files = {"file": ("test.wav", sample_audio_bytes, "audio/wav")}
        response = await client.post("/emotion/detect", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "emotion" in data
        assert "confidence" in data
        assert "scores" in data
        assert data["emotion"] in ["neutral", "happy", "sad", "angry", "fearful"]
        assert "meta" in data
        assert data["meta"]["schema_version"]
        assert data["meta"]["stage"] == "emotion"


@pytest.mark.asyncio
async def test_dialect_detect_endpoint():
    """Test dialect detection endpoint."""
    async with get_test_client() as client:
        response = await client.post(
            "/dialect/detect",
            params={"transcript": "ra emo test"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "dialect" in data
        assert "confidence" in data
        assert "meta" in data
        assert data["meta"]["stage"] == "dialect"


@pytest.mark.asyncio
async def test_translate_endpoint():
    """Test translation endpoint."""
    async with get_test_client() as client:
        payload = {
            "text": "Hello world",
            "source_lang": "en",
            "target_lang": "hi"
        }
        response = await client.post("/translate", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "translated_text" in data
        assert "model" in data
        assert len(data["translated_text"]) > 0
        assert "meta" in data
        assert data["meta"]["stage"] == "translation"


@pytest.mark.asyncio
async def test_tts_synthesize_endpoint():
    """Test TTS synthesis endpoint."""
    async with get_test_client() as client:
        payload = {
            "text": "Hello world",
            "language": "en",
            "emotion": "neutral"
        }
        response = await client.post("/tts/synthesize", json=payload)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        assert len(response.content) > 0
        # WAV files start with "RIFF"
        assert response.content[:4] == b"RIFF"


@pytest.mark.asyncio
async def test_translate_speech_endpoint(sample_audio_bytes):
    """Test end-to-end speech translation endpoint."""
    async with get_test_client(timeout=30.0) as client:
        files = {"file": ("test.wav", sample_audio_bytes, "audio/wav")}
        data = {"target_lang": "hi"}
        response = await client.post("/translate/speech", files=files, data=data)
        
        assert response.status_code == 200
        result = response.json()
        assert "session_id" in result
        assert "transcript" in result
        assert "detected_language" in result
        assert "detected_emotion" in result
        assert "detected_dialect" in result
        assert "translated_text" in result
        assert "audio_url" in result
        assert "latency_ms" in result
        assert "meta" in result
        assert result["meta"]["stage"] == "pipeline"


@pytest.mark.asyncio
async def test_invalid_audio_format():
    """Test that invalid audio format is rejected."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        files = {"file": ("test.txt", b"not an audio file", "text/plain")}
        response = await client.post("/stt/transcribe", files=files)
        
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_empty_audio_file():
    """Test that empty audio file is rejected."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        files = {"file": ("test.wav", b"", "audio/wav")}
        response = await client.post("/stt/transcribe", files=files)
        
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_translate_invalid_language():
    """Test that invalid language is rejected."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "text": "Hello",
            "source_lang": "fr",  # Invalid
            "target_lang": "en"
        }
        response = await client.post("/translate", json=payload)
        
        assert response.status_code == 400
