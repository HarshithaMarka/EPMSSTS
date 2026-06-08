#!/usr/bin/env python3
"""Quick TTS status check"""
import sys
import os

# Add repo to path
sys.path.insert(0, os.path.dirname(__file__))

from epmssts.services.tts.synthesizer import TtsService, TtsSynthesisRequest

def main():
    print("=" * 70)
    print("QUICK TTS STATUS CHECK")
    print("=" * 70)
    
    try:
        tts = TtsService()
        print(f"\nEngine: {tts._engine_kind}")
        
        # Test with very short text
        text = "Hi"
        print(f"Testing synthesis with text: '{text}'")
        
        req = TtsSynthesisRequest(text=text, language="en", emotion="neutral")
        wav_bytes = tts.synthesize(req)
        
        print(f"✓ Success! Generated {len(wav_bytes)} bytes")
        
        # Check size
        if len(wav_bytes) > 44:
            print(f"✓ Audio is not empty (header size is ~44 bytes)")
        else:
            print(f"✗ Audio appears empty (only {len(wav_bytes)} bytes)")
            
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
