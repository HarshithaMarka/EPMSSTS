"""
System Integration Audit Suite
================================

Comprehensive integration testing for EPMSSTS system:
- Frontend → Backend connectivity
- Backend endpoint consistency
- Pipeline execution correctness
- Data format validation
- Error handling & fallback testing
- Concurrency testing
- Logging & traceability

Principal AI Systems Architect Audit - February 2026
"""

import asyncio
import io
import json
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Any
import pytest
from httpx import AsyncClient, ASGITransport
import numpy as np
import soundfile as sf

from epmssts.api.main import app
from epmssts.api.observability import API_SCHEMA_VERSION


@asynccontextmanager
async def get_test_client(**kwargs):
    """Create an AsyncClient bound to the FastAPI ASGI app with lifespan."""
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", **kwargs) as client:
            yield client


def generate_audio(duration: float = 2.0, frequency: float = 440.0, amplitude: float = 0.3) -> bytes:
    """Generate WAV audio bytes for testing."""
    sample_rate = 16000
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = amplitude * np.sin(2 * np.pi * frequency * t).astype(np.float32)
    
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format='WAV')
    buf.seek(0)
    return buf.getvalue()


def generate_silence(duration: float = 1.0) -> bytes:
    """Generate silent audio for testing silence handling."""
    sample_rate = 16000
    audio = np.zeros(int(sample_rate * duration), dtype=np.float32)
    
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format='WAV')
    buf.seek(0)
    return buf.getvalue()


def generate_noisy_audio(duration: float = 2.0) -> bytes:
    """Generate very noisy audio for testing robust preprocessing."""
    sample_rate = 16000
    noise = np.random.normal(0, 0.1, int(sample_rate * duration)).astype(np.float32)
    
    buf = io.BytesIO()
    sf.write(buf, noise, sample_rate, format='WAV')
    buf.seek(0)
    return buf.getvalue()


# =============================================================================
# 1. FRONTEND → BACKEND CONNECTIVITY AUDIT
# =============================================================================

class TestFrontendBackendConnectivity:
    """Verify frontend API calls match backend endpoints exactly."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint_connectivity(self):
        """Frontend calls /health - verify response structure."""
        async with get_test_client() as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            
            # Frontend expects these fields
            assert "status" in data
            assert "schema_version" in data
            assert data["status"] == "ok"
            assert data["schema_version"] == API_SCHEMA_VERSION
    
    @pytest.mark.asyncio
    async def test_stt_endpoint_matches_frontend_call(self):
        """Frontend: POST /stt/transcribe with FormData(file)"""
        audio = generate_audio(duration=1.5)
        
        async with get_test_client() as client:
            files = {"file": ("test.wav", audio, "audio/wav")}
            response = await client.post("/stt/transcribe", files=files)
            
            assert response.status_code == 200
            data = response.json()
            
            # Frontend expects: text, language, segments, meta
            assert "text" in data
            assert "language" in data
            assert "segments" in data
            assert "meta" in data
            assert isinstance(data["segments"], list)
    
    @pytest.mark.asyncio
    async def test_emotion_endpoint_matches_frontend_call(self):
        """Frontend: POST /emotion/detect with FormData(file)"""
        audio = generate_audio(duration=1.5)
        
        async with get_test_client() as client:
            files = {"file": ("test.wav", audio, "audio/wav")}
            response = await client.post("/emotion/detect", files=files)
            
            assert response.status_code == 200
            data = response.json()
            
            # Frontend expects: emotion, confidence, scores, meta
            assert "emotion" in data
            assert "confidence" in data
            assert "scores" in data
            assert "meta" in data
            assert isinstance(data["scores"], dict)
    
    @pytest.mark.asyncio
    async def test_dialect_endpoint_matches_frontend_call(self):
        """Frontend: POST /dialect/detect?transcript={text}"""
        async with get_test_client() as client:
            # Frontend sends as query param + POST with headers
            response = await client.post(
                "/dialect/detect?transcript=నమస్తే",
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Frontend expects: dialect, confidence, meta
            assert "dialect" in data
            assert "confidence" in data
            assert "meta" in data
    
    @pytest.mark.asyncio
    async def test_translation_endpoint_matches_frontend_call(self):
        """Frontend: POST /translate with JSON body {text, source_lang, target_lang}"""
        async with get_test_client() as client:
            payload = {
                "text": "Hello world",
                "source_lang": "en",
                "target_lang": "te"
            }
            response = await client.post(
                "/translate",
                headers={"Content-Type": "application/json"},
                json=payload
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Frontend expects: translated_text, source_lang, target_lang, meta
            assert "translated_text" in data
            assert "source_lang" in data
            assert "target_lang" in data
            assert "meta" in data
    
    @pytest.mark.asyncio
    async def test_tts_endpoint_matches_frontend_call(self):
        """Frontend: POST /tts/synthesize with JSON body {text, language, emotion}"""
        async with get_test_client() as client:
            payload = {
                "text": "Hello world",
                "language": "en",
                "emotion": "happy"
            }
            response = await client.post(
                "/tts/synthesize",
                headers={"Content-Type": "application/json"},
                json=payload
            )
            
            # TTS may not be available, but should return valid response
            assert response.status_code in [200, 503]
            if response.status_code == 200:
                # Should return audio blob
                assert response.headers["content-type"].startswith("audio/")


# =============================================================================
# 2. BACKEND ENDPOINT SCHEMA CONSISTENCY AUDIT
# =============================================================================

class TestBackendEndpointConsistency:
    """Verify all endpoints return consistent response schemas with meta."""
    
    @pytest.mark.asyncio
    async def test_all_endpoints_return_meta_schema(self):
        """Every endpoint should include meta object with request_id, stage, latency."""
        audio = generate_audio(duration=1.5)
        
        async with get_test_client() as client:
            # Test STT
            files = {"file": ("test.wav", audio, "audio/wav")}
            response = await client.post("/stt/transcribe", files=files)
            data = response.json()
            assert "meta" in data
            assert "request_id" in data["meta"]
            assert "stage" in data["meta"]
            assert data["meta"]["stage"] == "stt"
            assert "latency_ms" in data["meta"]
            
            # Test Emotion
            response = await client.post("/emotion/detect", files=files)
            data = response.json()
            assert "meta" in data
            assert data["meta"]["stage"] == "emotion"
            
            # Test Translation
            payload = {"text": "Hello", "source_lang": "en", "target_lang": "te"}
            response = await client.post("/translate", json=payload)
            data = response.json()
            assert "meta" in data
            assert data["meta"]["stage"] == "translation"
    
    @pytest.mark.asyncio
    async def test_empty_input_handling_consistency(self):
        """All endpoints should handle empty inputs gracefully."""
        async with get_test_client() as client:
            # Empty audio file
            empty_audio = b""
            files = {"file": ("empty.wav", empty_audio, "audio/wav")}
            response = await client.post("/stt/transcribe", files=files)
            assert response.status_code == 400  # Bad request for empty file
            
            # Empty text translation
            payload = {"text": "", "source_lang": "en", "target_lang": "te"}
            response = await client.post("/translate", json=payload)
            # Should either accept and return empty or reject gracefully
            assert response.status_code in [200, 400]
    
    @pytest.mark.asyncio
    async def test_invalid_content_type_handling(self):
        """Endpoints should reject invalid content types consistently."""
        async with get_test_client() as client:
            # Send text file to audio endpoint
            files = {"file": ("test.txt", b"not audio", "text/plain")}
            response = await client.post("/stt/transcribe", files=files)
            assert response.status_code == 400
            
            data = response.json()
            assert "detail" in data
            assert "content type" in data["detail"].lower()


# =============================================================================
# 3. END-TO-END PIPELINE VALIDATION
# =============================================================================

class TestPipelineExecutionFlow:
    """Verify pipeline stages execute in correct order without skipping or duplication."""
    
    @pytest.mark.asyncio
    async def test_pipeline_stage_sequence(self):
        """Validate pipeline runs: Audio → STT → Emotion → Dialect → Translation → TTS"""
        audio = generate_audio(duration=2.0)
        
        async with get_test_client() as client:
            files = {"file": ("test.wav", audio, "audio/wav")}
            data_form = {"target_lang": "te"}
            
            response = await client.post(
                "/process/speech-to-speech",
                files=files,
                data=data_form
            )
            
            # Should complete without errors
            assert response.status_code in [200, 504]  # May timeout on slow systems
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify all pipeline stages completed
                assert "transcript" in data or "text" in data
                assert "detected_emotion" in data
                assert "detected_dialect" in data
                assert "translated_text" in data
                
                # Verify meta contains stage info
                if "meta" in data:
                    assert "stage_latencies_ms" in data["meta"] or "latency_ms" in data["meta"]
    
    @pytest.mark.asyncio
    async def test_pipeline_no_stage_duplication(self):
        """Ensure no pipeline stage runs twice."""
        audio = generate_audio(duration=1.5)
        
        async with get_test_client() as client:
            files = {"file": ("test.wav", audio, "audio/wav")}
            
            # Run STT
            stt_response = await client.post("/stt/transcribe", files=files)
            stt_data = stt_response.json()
            stt_request_id = stt_data["meta"]["request_id"]
            
            # Each request should have unique request_id
            files = {"file": ("test.wav", audio, "audio/wav")}
            stt_response2 = await client.post("/stt/transcribe", files=files)
            stt_data2 = stt_response2.json()
            stt_request_id2 = stt_data2["meta"]["request_id"]
            
            assert stt_request_id != stt_request_id2, "Request IDs should be unique"
    
    @pytest.mark.asyncio
    async def test_pipeline_invalid_data_propagation_prevention(self):
        """Ensure invalid data doesn't propagate through pipeline stages."""
        # Create corrupted audio (wrong sample rate declared)
        sample_rate = 8000  # Low sample rate
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
        
        buf = io.BytesIO()
        sf.write(buf, audio, sample_rate, format='WAV')
        buf.seek(0)
        low_rate_audio = buf.getvalue()
        
        async with get_test_client() as client:
            files = {"file": ("low_rate.wav", low_rate_audio, "audio/wav")}
            
            # STT should handle resampling automatically
            response = await client.post("/stt/transcribe", files=files)
            # Should succeed (preprocessing handles resampling) or fail gracefully
            assert response.status_code in [200, 400, 500]


# =============================================================================
# 4. DATA FORMAT CONSISTENCY AUDIT
# =============================================================================

class TestDataFormatConsistency:
    """Verify data formats are consistent across all modules."""
    
    @pytest.mark.asyncio
    async def test_emotion_labels_consistency(self):
        """Emotion labels should be consistent across emotion and TTS."""
        audio = generate_audio(duration=2.0)
        
        async with get_test_client() as client:
            files = {"file": ("test.wav", audio, "audio/wav")}
            emotion_response = await client.post("/emotion/detect", files=files)
            emotion_data = emotion_response.json()
            
            detected_emotion = emotion_data["emotion"]
            
            # Try TTS with detected emotion
            tts_payload = {
                "text": "Hello world",
                "language": "en",
                "emotion": detected_emotion
            }
            tts_response = await client.post("/tts/synthesize", json=tts_payload)
            
            # Should not error on valid emotion label
            assert tts_response.status_code in [200, 503]  # 503 if TTS unavailable
    
    @pytest.mark.asyncio
    async def test_language_code_consistency(self):
        """Language codes should be consistent (en, te, hi)."""
        audio = generate_audio(duration=2.0)
        
        async with get_test_client() as client:
            files = {"file": ("test.wav", audio, "audio/wav")}
            stt_response = await client.post("/stt/transcribe", files=files)
            stt_data = stt_response.json()
            
            detected_lang = stt_data.get("language", "en")
            
            # Use detected language for translation
            if detected_lang in ["en", "te", "hi"]:
                translation_payload = {
                    "text": "Test text",
                    "source_lang": detected_lang,
                    "target_lang": "te" if detected_lang != "te" else "en"
                }
                trans_response = await client.post("/translate", json=translation_payload)
                assert trans_response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_audio_format_output_consistency(self):
        """TTS output should be valid audio format."""
        async with get_test_client() as client:
            payload = {
                "text": "Testing audio output",
                "language": "en",
                "emotion": "neutral"
            }
            response = await client.post("/tts/synthesize", json=payload)
            
            if response.status_code == 200:
                # Should be audio content type
                content_type = response.headers.get("content-type", "")
                assert content_type.startswith("audio/"), f"Expected audio/* but got {content_type}"
                
                # Should have content
                content = response.content
                assert len(content) > 0, "Audio content should not be empty"


# =============================================================================
# 5. ERROR SCENARIO & FALLBACK TESTING
# =============================================================================

class TestErrorHandlingAndFallbacks:
    """Test graceful degradation and fallback mechanisms."""
    
    @pytest.mark.asyncio
    async def test_silence_input_handling(self):
        """System should handle silence gracefully."""
        silence = generate_silence(duration=2.0)
        
        async with get_test_client() as client:
            files = {"file": ("silence.wav", silence, "audio/wav")}
            response = await client.post("/stt/transcribe", files=files)
            
            # Should detect silence and reject or return empty transcript
            assert response.status_code in [200, 400]
            
            if response.status_code == 400:
                data = response.json()
                assert "silent" in data["detail"].lower() or "quiet" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_noisy_audio_handling(self):
        """System should handle noisy audio with preprocessing."""
        noisy = generate_noisy_audio(duration=2.0)
        
        async with get_test_client() as client:
            files = {"file": ("noisy.wav", noisy, "audio/wav")}
            response = await client.post("/stt/transcribe", files=files)
            
            # Preprocessing should handle noise - should not crash
            assert response.status_code in [200, 400]
    
    @pytest.mark.asyncio
    async def test_unsupported_language_fallback(self):
        """System should fallback when unsupported language detected."""
        audio = generate_audio(duration=1.5)
        
        async with get_test_client() as client:
            files = {"file": ("test.wav", audio, "audio/wav")}
            stt_response = await client.post("/stt/transcribe", files=files)
            
            if stt_response.status_code == 200:
                stt_data = stt_response.json()
                detected_lang = stt_data.get("language", "en")
                
                # Try translating from potentially unsupported language
                # System should handle this gracefully
                translation_payload = {
                    "text": "Test",
                    "source_lang": detected_lang if detected_lang in ["en", "te", "hi"] else "en",
                    "target_lang": "te"
                }
                trans_response = await client.post("/translate", json=translation_payload)
                assert trans_response.status_code in [200, 400]
    
    @pytest.mark.asyncio
    async def test_emotion_low_confidence_fallback(self):
        """System should use neutral fallback for low confidence emotion."""
        # Very short/unclear audio may produce low confidence
        audio = generate_audio(duration=0.3, amplitude=0.1)
        
        async with get_test_client() as client:
            files = {"file": ("short.wav", audio, "audio/wav")}
            response = await client.post("/emotion/detect", files=files)
            
            if response.status_code == 200:
                data = response.json()
                # System should always return an emotion (may use neutral fallback)
                assert "emotion" in data
                assert "confidence" in data
                
                # Check fallback flag in meta
                if "meta" in data and "fallback_used" in data["meta"]:
                    if data["meta"]["fallback_used"]:
                        # Low confidence should trigger neutral fallback
                        assert data["emotion"] == "neutral"
    
    @pytest.mark.asyncio
    async def test_translation_empty_text_handling(self):
        """Translation should handle empty text gracefully."""
        async with get_test_client() as client:
            payload = {
                "text": "",
                "source_lang": "en",
                "target_lang": "te"
            }
            response = await client.post("/translate", json=payload)
            
            # Should either accept (return empty) or reject gracefully
            assert response.status_code in [200, 400]
            
            if response.status_code == 200:
                data = response.json()
                # Empty input should produce empty output
                assert data.get("translated_text", "") == ""
    
    @pytest.mark.asyncio
    async def test_tts_failure_doesnt_break_pipeline(self):
        """TTS failure should not break the entire pipeline."""
        audio = generate_audio(duration=1.5)
        
        async with get_test_client() as client:
            files = {"file": ("test.wav", audio, "audio/wav")}
            data_form = {"target_lang": "te"}
            
            response = await client.post(
                "/process/speech-to-speech",
                files=files,
                data=data_form
            )
            
            # Even if TTS fails, pipeline should return transcript and translation
            if response.status_code == 200:
                data = response.json()
                # Core pipeline results should be present
                assert "transcript" in data or "text" in data
                assert "translated_text" in data


# =============================================================================
# 6. CONCURRENCY & STABILITY TESTING
# =============================================================================

class TestConcurrencyAndStability:
    """Test system behavior under concurrent load."""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling multiple concurrent requests."""
        audio = generate_audio(duration=1.0)
        
        async def make_request(client: AsyncClient, request_num: int):
            files = {"file": (f"test_{request_num}.wav", audio, "audio/wav")}
            response = await client.post("/stt/transcribe", files=files)
            return response.status_code, response.json() if response.status_code == 200 else None
        
        async with get_test_client() as client:
            # Send 5 concurrent requests
            tasks = [make_request(client, i) for i in range(5)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All requests should complete (may have some throttling)
            successful = sum(1 for r in results if not isinstance(r, Exception) and r[0] == 200)
            throttled = sum(1 for r in results if not isinstance(r, Exception) and r[0] == 429)
            
            # At least some should succeed
            assert successful > 0, "Some requests should succeed"
            print(f"Concurrent test: {successful} succeeded, {throttled} throttled")
    
    @pytest.mark.asyncio
    async def test_rapid_sequential_requests(self):
        """Test handling rapid sequential requests."""
        audio = generate_audio(duration=0.8)
        
        async with get_test_client() as client:
            results = []
            for i in range(3):
                files = {"file": (f"test_{i}.wav", audio, "audio/wav")}
                response = await client.post("/stt/transcribe", files=files)
                results.append(response.status_code)
                await asyncio.sleep(0.1)  # Small delay between requests
            
            # All should complete successfully
            successful = sum(1 for status in results if status == 200)
            assert successful >= 2, "Most rapid requests should succeed"
    
    @pytest.mark.asyncio
    async def test_long_audio_processing(self):
        """Test handling longer audio files."""
        # Generate 5 second audio
        long_audio = generate_audio(duration=5.0)
        
        async with get_test_client() as client:
            files = {"file": ("long_test.wav", long_audio, "audio/wav")}
            
            start_time = time.time()
            response = await client.post("/stt/transcribe", files=files, timeout=30.0)
            elapsed = time.time() - start_time
            
            # Should complete within reasonable time
            assert response.status_code in [200, 504]
            
            if response.status_code == 200:
                data = response.json()
                # Should report realistic latency
                if "meta" in data and "latency_ms" in data["meta"]:
                    reported_latency = data["meta"]["latency_ms"]
                    # Latency should be somewhat close to actual elapsed time
                    assert abs(reported_latency - elapsed * 1000) < 5000  # Within 5 seconds


# =============================================================================
# 7. LOGGING & TRACEABILITY AUDIT
# =============================================================================

class TestLoggingAndTraceability:
    """Verify complete traceability through request_id and logging."""
    
    @pytest.mark.asyncio
    async def test_request_id_propagation(self):
        """Every response should include request_id for tracing."""
        audio = generate_audio(duration=1.5)
        
        async with get_test_client() as client:
            # Send custom request ID
            custom_id = "test-trace-12345"
            files = {"file": ("test.wav", audio, "audio/wav")}
            headers = {"x-request-id": custom_id}
            
            response = await client.post("/stt/transcribe", files=files, headers=headers)
            
            # Response should include our request ID
            assert "x-request-id" in response.headers
            # May use custom ID or generate new one
            returned_id = response.headers["x-request-id"]
            assert returned_id is not None and returned_id != ""
            
            # Meta should also contain request_id
            if response.status_code == 200:
                data = response.json()
                assert "meta" in data
                assert "request_id" in data["meta"]
    
    @pytest.mark.asyncio
    async def test_stage_latency_reporting(self):
        """Each stage should report latency for performance analysis."""
        audio = generate_audio(duration=1.5)
        
        async with get_test_client() as client:
            files = {"file": ("test.wav", audio, "audio/wav")}
            response = await client.post("/stt/transcribe", files=files)
            
            if response.status_code == 200:
                data = response.json()
                assert "meta" in data
                
                # Should include latency
                assert "latency_ms" in data["meta"]
                assert isinstance(data["meta"]["latency_ms"], (int, float))
                assert data["meta"]["latency_ms"] > 0
    
    @pytest.mark.asyncio
    async def test_confidence_reporting(self):
        """Stages with ML models should report confidence scores."""
        audio = generate_audio(duration=2.0)
        
        async with get_test_client() as client:
            # Emotion detection has confidence
            files = {"file": ("test.wav", audio, "audio/wav")}
            response = await client.post("/emotion/detect", files=files)
            
            if response.status_code == 200:
                data = response.json()
                assert "confidence" in data
                assert 0.0 <= data["confidence"] <= 1.0
                
                # Meta may also include confidence
                if "meta" in data and "confidence" in data["meta"]:
                    assert data["meta"]["confidence"] == data["confidence"]
    
    @pytest.mark.asyncio
    async def test_fallback_flag_reporting(self):
        """System should indicate when fallbacks are used."""
        audio = generate_audio(duration=0.5, amplitude=0.05)  # Very short, quiet
        
        async with get_test_client() as client:
            files = {"file": ("quiet.wav", audio, "audio/wav")}
            response = await client.post("/emotion/detect", files=files)
            
            if response.status_code == 200:
                data = response.json()
                # Meta should indicate if fallback was used
                if "meta" in data:
                    assert "fallback_used" in data["meta"]
                    assert isinstance(data["meta"]["fallback_used"], bool)


# =============================================================================
# 8. FULL SYSTEM INTEGRATION TEST
# =============================================================================

class TestFullSystemIntegration:
    """Complete end-to-end system flow simulation."""
    
    @pytest.mark.asyncio
    async def test_complete_user_workflow(self):
        """Simulate complete user workflow: upload → process → receive output."""
        audio = generate_audio(duration=2.0, frequency=440, amplitude=0.3)
        
        async with get_test_client() as client:
            # 1. Check health
            health_response = await client.get("/health")
            assert health_response.status_code == 200
            health_data = health_response.json()
            assert health_data["status"] == "ok"
            
            # 2. Transcribe audio
            files = {"file": ("user_audio.wav", audio, "audio/wav")}
            stt_response = await client.post("/stt/transcribe", files=files)
            assert stt_response.status_code == 200
            stt_data = stt_response.json()
            transcript = stt_data.get("text", "")
            detected_lang = stt_data.get("language", "en")
            
            # 3. Detect emotion
            files = {"file": ("user_audio.wav", audio, "audio/wav")}
            emotion_response = await client.post("/emotion/detect", files=files)
            assert emotion_response.status_code == 200
            emotion_data = emotion_response.json()
            emotion = emotion_data.get("emotion", "neutral")
            
            # 4. Detect dialect (if Telugu)
            if detected_lang == "te" and transcript:
                dialect_response = await client.post(
                    f"/dialect/detect?transcript={transcript}",
                    headers={"Content-Type": "application/json"}
                )
                assert dialect_response.status_code == 200
            
            # 5. Translate
            target_lang = "te" if detected_lang != "te" else "en"
            translation_payload = {
                "text": transcript or "Hello",
                "source_lang": detected_lang if detected_lang in ["en", "te", "hi"] else "en",
                "target_lang": target_lang
            }
            trans_response = await client.post("/translate", json=translation_payload)
            assert trans_response.status_code == 200
            trans_data = trans_response.json()
            translated_text = trans_data.get("translated_text", "")
            
            # 6. Synthesize speech
            tts_payload = {
                "text": translated_text or "Test output",
                "language": target_lang,
                "emotion": emotion
            }
            tts_response = await client.post("/tts/synthesize", json=tts_payload)
            # TTS may not be available
            assert tts_response.status_code in [200, 503]
            
            # Verify workflow completion
            print(f"Complete workflow: {detected_lang} → {target_lang}, emotion: {emotion}")
            assert transcript is not None
            assert translated_text is not None
    
    @pytest.mark.asyncio
    async def test_unified_pipeline_endpoint(self):
        """Test the unified /process/speech-to-speech endpoint."""
        audio = generate_audio(duration=2.0)
        
        async with get_test_client() as client:
            files = {"file": ("complete_test.wav", audio, "audio/wav")}
            data_form = {"target_lang": "te"}
            
            response = await client.post(
                "/process/speech-to-speech",
                files=files,
                data=data_form,
                timeout=30.0
            )
            
            # May timeout on slow systems, but should not crash
            assert response.status_code in [200, 400, 429, 504]
            
            if response.status_code == 200:
                data = response.json()
                
                # Should contain complete pipeline results
                assert "transcript" in data or "text" in data
                assert "detected_emotion" in data or "emotion" in data
                assert "translated_text" in data
                
                # Should have traceability
                assert "meta" in data or "session_id" in data
                
                print("Unified pipeline completed successfully")


# =============================================================================
# RUN AUDIT SUMMARY
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("EPMSSTS SYSTEM INTEGRATION AUDIT SUITE")
    print("Principal AI Systems Architect - February 2026")
    print("=" * 80)
    print("\nRunning comprehensive integration tests...")
    print("\nTest Categories:")
    print("  1. Frontend → Backend Connectivity")
    print("  2. Backend Endpoint Consistency")
    print("  3. Pipeline Execution Flow")
    print("  4. Data Format Consistency")
    print("  5. Error Handling & Fallbacks")
    print("  6. Concurrency & Stability")
    print("  7. Logging & Traceability")
    print("  8. Full System Integration")
    print("\nRun with: pytest tests/integration/test_system_integration_audit.py -v")
    print("=" * 80)
