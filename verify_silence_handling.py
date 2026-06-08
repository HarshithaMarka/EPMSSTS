"""
Silence Handling Consistency Verification

Tests that both STT endpoint and full pipeline reject silent audio consistently.
"""

import asyncio
import io
from pathlib import Path

import numpy as np
import soundfile as sf
from httpx import AsyncClient, ASGITransport

from epmssts.api.main import app


def generate_valid_audio(duration=2.0, sample_rate=16000):
    """Generate valid audio with speech-like characteristics."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    # Mix of frequencies for more realistic audio
    audio = (
        0.3 * np.sin(2 * np.pi * 440 * t)  # A4
        + 0.2 * np.sin(2 * np.pi * 554 * t)  # C#5
        + 0.1 * np.sin(2 * np.pi * 659 * t)  # E5
    )
    return (audio * 32767 * 0.5).astype(np.int16)


def generate_silent_audio(duration=2.0, sample_rate=16000):
    """Generate completely silent audio."""
    return np.zeros(int(sample_rate * duration), dtype=np.int16)


def audio_to_wav_bytes(audio: np.ndarray, sample_rate: int = 16000) -> bytes:
    """Convert numpy array to WAV bytes."""
    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format="WAV", subtype="PCM_16")
    buffer.seek(0)
    return buffer.read()


async def test_stt_endpoint_valid_audio(client: AsyncClient):
    """Test STT endpoint with valid audio."""
    print("\n[TEST 1] STT Endpoint - Valid Audio")
    print("-" * 60)
    
    audio = generate_valid_audio()
    wav_bytes = audio_to_wav_bytes(audio)
    
    files = {"file": ("test.wav", wav_bytes, "audio/wav")}
    response = await client.post("/stt/transcribe", files=files)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Transcription: '{data.get('text', '')}'")
        print(f"Language: {data.get('language', 'N/A')}")
        print("✅ PASS - Valid audio processed")
        return True
    else:
        print(f"❌ FAIL - Unexpected status: {response.text}")
        return False


async def test_stt_endpoint_silent_audio(client: AsyncClient):
    """Test STT endpoint with silent audio."""
    print("\n[TEST 2] STT Endpoint - Silent Audio")
    print("-" * 60)
    
    audio = generate_silent_audio()
    wav_bytes = audio_to_wav_bytes(audio)
    
    files = {"file": ("silence.wav", wav_bytes, "audio/wav")}
    response = await client.post("/stt/transcribe", files=files)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 400:
        data = response.json()
        print(f"Error Message: {data.get('detail', '')}")
        if "silent" in data.get("detail", "").lower():
            print("✅ PASS - Silent audio rejected correctly")
            return True
        else:
            print("⚠️ PARTIAL - Rejected but wrong error message")
            return False
    else:
        print(f"❌ FAIL - Should return 400, got {response.status_code}")
        return False


async def test_pipeline_endpoint_valid_audio(client: AsyncClient):
    """Test full pipeline endpoint with valid audio."""
    print("\n[TEST 3] Full Pipeline - Valid Audio")
    print("-" * 60)
    
    audio = generate_valid_audio()
    wav_bytes = audio_to_wav_bytes(audio)
    
    files = {"file": ("test.wav", wav_bytes, "audio/wav")}
    data = {"target_lang": "te"}
    response = await client.post("/process/speech-to-speech", files=files, data=data)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        transcript = result.get("transcription", "")
        translation = result.get("translation", "")
        emotion = result.get("emotion", "")
        
        print(f"Transcription: '{transcript}'")
        print(f"Translation: '{translation}'")
        print(f"Emotion: {emotion}")
        print(f"Latency: {result.get('processing_time_ms', 0)}ms")
        
        # Valid audio should produce non-empty outputs
        if transcript and emotion:
            print("✅ PASS - Pipeline executed successfully")
            return True
        else:
            print("⚠️ PARTIAL - Pipeline ran but outputs incomplete")
            return False
    else:
        print(f"❌ FAIL - Unexpected status: {response.text}")
        return False


async def test_pipeline_endpoint_silent_audio(client: AsyncClient):
    """Test full pipeline endpoint with silent audio."""
    print("\n[TEST 4] Full Pipeline - Silent Audio (CRITICAL TEST)")
    print("-" * 60)
    
    audio = generate_silent_audio()
    wav_bytes = audio_to_wav_bytes(audio)
    
    files = {"file": ("silence.wav", wav_bytes, "audio/wav")}
    data = {"target_lang": "te"}
    response = await client.post("/process/speech-to-speech", files=files, data=data)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 400:
        result = response.json()
        error_msg = result.get("detail", "")
        print(f"Error Message: {error_msg}")
        
        if "silent" in error_msg.lower() or "quiet" in error_msg.lower():
            print("✅ PASS - Silent audio rejected correctly (CONSISTENT BEHAVIOR)")
            return True
        else:
            print("⚠️ PARTIAL - Rejected but unclear error message")
            return False
    elif response.status_code == 200:
        result = response.json()
        transcript = result.get("transcription", "")
        print(f"Transcription: '{transcript}'")
        print("❌ FAIL - Should reject silent audio with 400, got 200 (INCONSISTENT)")
        return False
    else:
        print(f"❌ FAIL - Unexpected status: {response.status_code}")
        return False


async def main():
    """Run all verification tests."""
    print("=" * 70)
    print("SILENCE HANDLING CONSISTENCY VERIFICATION")
    print("Principal ML Systems Engineer & Backend Production Architect")
    print("=" * 70)
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Wait for services to initialize by checking health endpoint
        print("\nWaiting for services to initialize...")
        max_retries = 30
        for i in range(max_retries):
            try:
                response = await client.get("/health")
                if response.status_code == 200:
                    data = response.json()
                    if data.get("stt_available") and data.get("emotion_available"):
                        print("✅ All services ready\n")
                        break
            except Exception:
                pass
            await asyncio.sleep(1)
            if i == max_retries - 1:
                print("❌ Services failed to initialize after 30s")
                return False
        
        results = []
        
        # Test 1: STT with valid audio (baseline)
        results.append(await test_stt_endpoint_valid_audio(client))
        
        # Test 2: STT with silent audio (baseline)
        results.append(await test_stt_endpoint_silent_audio(client))
        
        # Test 3: Pipeline with valid audio
        results.append(await test_pipeline_endpoint_valid_audio(client))
        
        # Test 4: Pipeline with silent audio (CRITICAL)
        results.append(await test_pipeline_endpoint_silent_audio(client))
    
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    test_names = [
        "STT - Valid Audio",
        "STT - Silent Audio",
        "Pipeline - Valid Audio",
        "Pipeline - Silent Audio (CRITICAL)",
    ]
    
    passed = sum(results)
    total = len(results)
    
    for i, (name, result) in enumerate(zip(test_names, results), 1):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  [{status}] Test {i}: {name}")
    
    print("-" * 70)
    print(f"Total: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print("=" * 70)
    
    if passed == total:
        print("\n🎉 SUCCESS: All tests passed!")
        print("✅ Silence handling is now CONSISTENT across all endpoints")
        print("✅ Valid audio processes normally")
        print("✅ Silent audio is rejected early with 400 error")
        print("✅ No unnecessary pipeline execution for invalid audio")
        print("\n📋 PRODUCTION READY: Pipeline validation logic fixed")
    else:
        print(f"\n⚠️ WARNING: {total - passed} test(s) failed")
        print("❌ Silence handling may still be inconsistent")
        print("🔧 Review pipeline.py and main.py for errors")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
