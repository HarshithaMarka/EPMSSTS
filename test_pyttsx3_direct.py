import sys
sys.path.insert(0, '.')

from epmssts.services.tts.synthesizer import TtsService, TtsSynthesisRequest
import os

print("=" * 60)
print("Direct pyttsx3 Test")
print("=" * 60)

service = TtsService()
print(f"Engine: {service._engine_kind}")
print(f"Sample rate: {service._sample_rate}")

texts = [
    "Hi",
    "Hello world",
    "Hello world this is a test of the text to speech system",
]

for text in texts:
    print(f"\nTesting: {repr(text)}")
    
    try:
        request = TtsSynthesisRequest(
            text=text,
            language="en",
            emotion="neutral"
        )
        
        result = service.synthesize(request)
        print(f"  Generated: {len(result)} bytes")
        print(f"  WAV Header: {result[:12].hex()}")
        print(f"  First 50 bytes: {result[:50].hex()}")
        
        # Check if it's a valid WAV
        if result[:4] == b'RIFF' and result[8:12] == b'WAVE':
            print(f"  ✅ Valid WAV file")
        else:
            print(f"  ❌ Invalid WAV file")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
