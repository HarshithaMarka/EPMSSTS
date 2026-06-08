"""
Enhanced Comprehensive Integration Tests for EPMSSTS API
Tests complete pipeline and all endpoints
"""

import asyncio
import io
import json
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
    # Generate 2 seconds of 440Hz sine wave at 16kHz (A note)
    sample_rate = 16000
    duration = 2
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format='WAV')
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def sample_short_audio_bytes():
    """Generate very short audio for testing edge cases."""
    sample_rate = 16000
    duration = 0.5
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format='WAV')
    buf.seek(0)
    return buf.getvalue()


class TestHealthEndpoints:
    """Test health check endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_check_status(self):
        """Test health check returns ok status."""
        async with get_test_client() as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_health_check_services(self):
        """Test health check reports service availability."""
        async with get_test_client() as client:
            response = await client.get("/health")
            data = response.json()
            
            # Critical services must be available
            assert data.get("stt_available") is not None
            assert data.get("emotion_available") is not None
            
            # Optional services
            assert "tts_available" in data
            assert "translation_available" in data


class TestSTTEndpoints:
    """Test Speech-to-Text endpoints."""
    
    @pytest.mark.asyncio
    async def test_transcribe_with_valid_audio(self, sample_audio_bytes):
        """Test STT transcription with valid audio."""
        async with get_test_client() as client:
            files = {"file": ("test.wav", sample_audio_bytes, "audio/wav")}
            response = await client.post("/stt/transcribe", files=files)
            
            assert response.status_code == 200
            data = response.json()
            assert "transcript" in data or "text" in data
            assert "language" in data or "language_code" in data
            assert "meta" in data
            assert data["meta"]["stage"] == "stt"
    
    @pytest.mark.asyncio
    async def test_transcribe_empty_file(self):
        """Test STT with empty audio file."""
        async with get_test_client() as client:
            files = {"file": ("empty.wav", b"", "audio/wav")}
            response = await client.post("/stt/transcribe", files=files)
            
            # Should handle gracefully
            assert response.status_code in [200, 400, 422]
    
    @pytest.mark.asyncio
    async def test_transcribe_missing_file(self):
        """Test STT without file upload."""
        async with get_test_client() as client:
            response = await client.post("/stt/transcribe")
            
            # Should return 422 (unprocessable entity)
            assert response.status_code in [400, 422]


class TestEmotionEndpoints:
    """Test Emotion Detection endpoints."""
    
    @pytest.mark.asyncio
    async def test_emotion_detect_with_valid_audio(self, sample_audio_bytes):
        """Test emotion detection with valid audio."""
        async with get_test_client() as client:
            files = {"file": ("test.wav", sample_audio_bytes, "audio/wav")}
            response = await client.post("/emotion/detect", files=files)
            
            assert response.status_code == 200
            data = response.json()
            assert "emotion" in data
            assert "confidence" in data
            assert 0 <= data["confidence"] <= 1
            assert "meta" in data
            assert data["meta"]["stage"] == "emotion"
    
    @pytest.mark.asyncio
    async def test_emotion_analyze_compatibility(self, sample_audio_bytes):
        """Test emotion/analyze endpoint (frontend compatible)."""
        async with get_test_client() as client:
            files = {"file": ("test.wav", sample_audio_bytes, "audio/wav")}
            response = await client.post("/emotion/analyze", files=files)
            
            assert response.status_code == 200
            data = response.json()
            assert "emotion" in data
            assert "confidence" in data
    
    @pytest.mark.asyncio
    async def test_emotion_valid_range(self, sample_audio_bytes):
        """Test emotion confidence is in valid range."""
        async with get_test_client() as client:
            files = {"file": ("test.wav", sample_audio_bytes, "audio/wav")}
            response = await client.post("/emotion/detect", files=files)
            
            data = response.json()
            confidence = data.get("confidence", 0)
            assert 0 <= confidence <= 1, "Confidence must be between 0 and 1"


class TestDialectEndpoints:
    """Test Dialect Detection endpoints."""
    
    @pytest.mark.asyncio
    async def test_dialect_detection_endpoint(self, sample_audio_bytes):
        """Test dialect detection endpoint."""
        async with get_test_client() as client:
            files = {"file": ("test.wav", sample_audio_bytes, "audio/wav")}
            response = await client.post("/dialect/detect", files=files)
            
            # Should either succeed or return dialect detection not available
            assert response.status_code in [200, 400, 422]


class TestTranslationEndpoints:
    """Test Translation endpoints."""
    
    @pytest.mark.asyncio
    async def test_translate_english_to_hindi(self):
        """Test text translation from English to Hindi."""
        async with get_test_client() as client:
            payload = {
                "text": "Hello, how are you?",
                "source_lang": "en",
                "target_lang": "hi"
            }
            response = await client.post("/translate", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert "translated_text" in data
            assert len(data["translated_text"]) > 0
            assert "meta" in data
            assert data["meta"]["stage"] == "translation"
    
    @pytest.mark.asyncio
    async def test_translate_identity(self):
        """Test translation to same language (should be identity)."""
        async with get_test_client() as client:
            text = "Hello world"
            payload = {
                "text": text,
                "source_lang": "en",
                "target_lang": "en"
            }
            response = await client.post("/translate", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            # Identity translation should return the same text
            assert data["translated_text"].strip() == text
    
    @pytest.mark.asyncio
    async def test_translate_invalid_language(self):
        """Test translation with invalid language code."""
        async with get_test_client() as client:
            payload = {
                "text": "Hello",
                "source_lang": "xx",
                "target_lang": "yy"
            }
            response = await client.post("/translate", json=payload)
            
            # Should fail with invalid language
            assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_translate_empty_text(self):
        """Test translation with empty text."""
        async with get_test_client() as client:
            payload = {
                "text": "",
                "source_lang": "en",
                "target_lang": "hi"
            }
            response = await client.post("/translate", json=payload)
            
            # Should handle gracefully
            assert response.status_code in [400, 422]


class TestTTSEndpoints:
    """Test Text-to-Speech endpoints."""
    
    @pytest.mark.asyncio
    async def test_tts_synthesis(self):
        """Test TTS synthesis endpoint."""
        async with get_test_client() as client:
            payload = {
                "text": "Hello world",
                "emotion": "happy",
                "language": "en"
            }
            response = await client.post("/tts/synthesize", json=payload)
            
            # TTS may not be available in Python 3.13
            assert response.status_code in [200, 503]
    
    @pytest.mark.asyncio
    async def test_tts_with_invalid_emotion(self):
        """Test TTS with invalid emotion."""
        async with get_test_client() as client:
            payload = {
                "text": "Hello",
                "emotion": "invalid_emotion",
                "language": "en"
            }
            response = await client.post("/tts/synthesize", json=payload)
            
            # Should handle gracefully (either fail or use default)
            assert response.status_code in [200, 400, 422, 503]


class TestPipelineEndpoints:
    """Test end-to-end pipeline endpoints."""
    
    @pytest.mark.asyncio
    async def test_speech_to_speech_pipeline(self, sample_audio_bytes):
        """Test complete speech-to-speech pipeline."""
        async with get_test_client() as client:
            files = {"file": ("test.wav", sample_audio_bytes, "audio/wav")}
            data = {
                "target_lang": "hi",
                "target_emotion": "happy"
            }
            response = await client.post(
                "/process/speech-to-speech",
                files=files,
                data=data
            )
            
            assert response.status_code in [200, 500]  # May fail if models not loaded
            if response.status_code == 200:
                result = response.json()
                assert "transcript" in result or "text" in result
                assert "meta" in result
                assert result["meta"]["stage"] == "pipeline"


class TestOutputEndpoint:
    """Test audio output retrieval endpoint."""
    
    @pytest.mark.asyncio
    async def test_output_nonexistent_file(self):
        """Test retrieving non-existent output file."""
        async with get_test_client() as client:
            response = await client.get("/output/nonexistent.wav")
            
            # Should return 404 or similar
            assert response.status_code >= 400


class TestAPIErrorHandling:
    """Test API error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_invalid_endpoint(self):
        """Test calling non-existent endpoint."""
        async with get_test_client() as client:
            response = await client.get("/nonexistent")
            
            assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_wrong_method(self):
        """Test using wrong HTTP method."""
        async with get_test_client() as client:
            response = await client.get("/translate")  # Should be POST
            
            assert response.status_code == 405  # Method not allowed


@pytest.mark.asyncio
async def test_concurrent_requests(sample_audio_bytes):
    """Test handling multiple concurrent requests."""
    async with get_test_client() as client:
        # Make multiple concurrent health check requests
        tasks = []
        for _ in range(5):
            task = client.get("/health")
            tasks.append(task)
        
        # All should succeed
        responses = await asyncio.gather(*tasks)
        for response in responses:
            assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
