"""
Quick Silence Handling Verification
=====================================
Tests that silence is consistently rejected across endpoints.
"""

import asyncio
import io
from pathlib import Path
import sys

import numpy as np
import soundfile as sf
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent))
from epmssts.api.main import app


def generate_valid_audio():
    """Valid speech-like audio."""
    t = np.linspace(0, 2.0, 32000)
    audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, 16000, format='WAV')
    buf.seek(0)
    return buf.getvalue()


def generate_silent_audio():
    """Completely silent audio."""
    audio = np.zeros(32000, dtype=np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, 16000, format='WAV')
    buf.seek(0)
    return buf.getvalue()


async def main():
    print("=" * 70)
    print("SILENCE HANDLING CONSISTENCY VERIFICATION")
    print("=" * 70)
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60.0) as client:
        valid_audio = generate_valid_audio()
        silent_audio = generate_silent_audio()
        
        # Test 1: STT with silence
        print("\n[TEST 1] STT Endpoint + Silent Audio")
        print("-" * 70)
        files = {"file": ("silence.wav", silent_audio, "audio/wav")}
        response = await client.post("/stt/transcribe", files=files)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:100]}")
        stt_rejects_silence = (response.status_code == 400 and "silent" in response.text.lower())
        print(f"Result: {'✅ PASS' if stt_rejects_silence else '❌ FAIL'} - {'Rejected' if stt_rejects_silence else 'Accepted'}")
        
        # Test 2: Full pipeline with silence
        print("\n[TEST 2] Full Pipeline + Silent Audio (CRITICAL)")
        print("-" * 70)
        files = {"file": ("silence.wav", silent_audio, "audio/wav")}
        data = {"target_lang": "te"}
        response = await client.post("/process/speech-to-speech", files=files, data=data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:100]}")
        pipeline_rejects_silence = (response.status_code == 400 and ("silent" in response.text.lower() or "quiet" in response.text.lower()))
        print(f"Result: {'✅ PASS' if pipeline_rejects_silence else '❌ FAIL'} - {'Rejected' if pipeline_rejects_silence else 'Accepted'}")
        
        # Test 3: Full pipeline with valid audio
        print("\n[TEST 3] Full Pipeline + Valid Audio")
        print("-" * 70)
        files = {"file": ("valid.wav", valid_audio, "audio/wav")}
        data = {"target_lang": "te"}
        response = await client.post("/process/speech-to-speech", files=files, data=data)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Transcription: {result.get('transcription', '')[:50]}")
            print(f"Emotion: {result.get('emotion', 'N/A')}")
            pipeline_processes_valid = True
        else:
            print(f"Error: {response.text[:100]}")
            pipeline_processes_valid = False
        print(f"Result: {'✅ PASS' if pipeline_processes_valid else '❌ FAIL'} - {'Processed' if pipeline_processes_valid else 'Rejected'}")
        
        # Summary
        print("\n" + "=" * 70)
        print("VERIFICATION SUMMARY")
        print("=" * 70)
        
        consistent = stt_rejects_silence and pipeline_rejects_silence
        all_pass = consistent and pipeline_processes_valid
        
        print(f"\n  {'✅' if stt_rejects_silence else '❌'} STT Endpoint rejects silence")
        print(f"  {'✅' if pipeline_rejects_silence else '❌'} Full Pipeline rejects silence")
        print(f"  {'✅' if pipeline_processes_valid else '❌'} Full Pipeline processes valid audio")
        print(f"\n  {'✅' if consistent else '❌'} Silence handling is {'CONSISTENT' if consistent else 'INCONSISTENT'}")
        
        print("\n" + "=" * 70)
        if all_pass:
            print("🎉 SUCCESS: All validation checks passed!")
            print("\n✅ Silence detection is now CONSISTENT")
            print("✅ Valid speech processes normally")
            print("✅ Silent audio rejected early with 400 error")
            print("✅ No unnecessary pipeline execution")
            print("\n📋 PRODUCTION READY")
        else:
            print("⚠️ ISSUES DETECTED")
            if not consistent:
                print("❌ Silence handling is INCONSISTENT between endpoints")
            if not pipeline_processes_valid:
                print("❌ Valid audio not processing correctly")
        print("=" * 70)
        
        return all_pass


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
