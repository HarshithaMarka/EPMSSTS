#!/usr/bin/env python3
"""Quick TTS debug test."""

import sys
from pathlib import Path

# Add the project to path
sys.path.insert(0, str(Path(__file__).parent))

from epmssts.services.tts.synthesizer import TtsService, TtsSynthesisRequest

try:
    print("[TEST] Initializing TTS service...")
    tts = TtsService()
    print(f"[OK] TTS initialized. Engine: {tts._engine_kind}")
    
    print("[TEST] Synthesizing test audio...")
    req = TtsSynthesisRequest(
        text="Hello, this is a test.",
        language="en",
        emotion="neutral"
    )
    wav_bytes = tts.synthesize(req)
    print(f"[OK] Audio synthesized: {len(wav_bytes)} bytes")
    
    # Save to file to test
    output_path = Path(__file__).parent / "test_output.wav"
    output_path.write_bytes(wav_bytes)
    print(f"[OK] Saved to {output_path}")
    
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
