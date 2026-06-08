"""Quick TTS diagnostic"""
import sys
print(f"Python: {sys.version}")

try:
    from epmssts.services.tts.synthesizer import TtsService, TtsSynthesisRequest
    print("✓ TTS imports OK")
    
    service = TtsService()
    print(f"✓ TTS service created: engine={service._engine_kind}")
    
    request = TtsSynthesisRequest(text="Test", language="en", emotion="neutral")
    audio = service.synthesize(request)
    print(f"✓ TTS synthesis OK: {len(audio)} bytes")
    print("\n✅ TTS is working correctly!")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
