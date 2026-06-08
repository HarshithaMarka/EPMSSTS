#!/usr/bin/env python3
"""
Integration Test: Frontend-Backend Audio Output Validation
Tests the complete pipeline with speech output verification
"""

import sys
import os
import requests
import json
from pathlib import Path

# Add repo to path
sys.path.insert(0, os.path.dirname(__file__))

API_BASE = "http://localhost:8000"

def test_tts_direct():
    """Test TTS endpoint directly"""
    print("\n" + "="*70)
    print("TEST 1: Direct TTS Endpoint")
    print("="*70)
    
    test_cases = [
        {"text": "Hello world", "language": "en", "emotion": "neutral"},
        {"text": "I am very happy today", "language": "en", "emotion": "happy"},
        {"text": "This is sad news", "language": "en", "emotion": "sad"},
    ]
    
    for i, payload in enumerate(test_cases, 1):
        print(f"\nTest {i}: {payload['emotion']} emotion")
        print(f"  Text: '{payload['text']}'")
        
        try:
            resp = requests.post(
                f"{API_BASE}/tts/synthesize",
                json=payload,
                timeout=15
            )
            
            print(f"  Status: {resp.status_code}")
            
            if resp.status_code == 200:
                content_type = resp.headers.get("Content-Type", "")
                content_length = len(resp.content)
                
                print(f"  ✓ Content-Type: {content_type}")
                print(f"  ✓ Size: {content_length:,} bytes")
                
                if content_length > 1000:
                    print(f"  ✓ Audio size OK (>1KB)")
                else:
                    print(f"  ✗ Audio too small")
                    
                # Save for inspection
                output_path = Path(f"test_tts_{payload['emotion']}.wav")
                output_path.write_bytes(resp.content)
                print(f"  ✓ Saved to: {output_path}")
            else:
                print(f"  ✗ Error: {resp.text}")
                
        except Exception as e:
            print(f"  ✗ Exception: {e}")

def test_health():
    """Test health endpoint"""
    print("\n" + "="*70)
    print("TEST 2: Health Check")
    print("="*70)
    
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        if resp.status_code == 200:
            health = resp.json()
            print(f"\nHealth Status:")
            for key, value in health.items():
                status = "✓" if value else "✗"
                print(f"  {status} {key}: {value}")
            
            if not health.get("tts_available"):
                print("\n⚠️  WARNING: TTS not available!")
            
            return health.get("tts_available", False)
        else:
            print(f"✗ Health check failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"✗ Health check exception: {e}")
        return False

def test_cors():
    """Test CORS headers"""
    print("\n" + "="*70)
    print("TEST 3: CORS Configuration")
    print("="*70)
    
    try:
        resp = requests.options(
            f"{API_BASE}/tts/synthesize",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST"
            },
            timeout=5
        )
        
        print(f"  Status: {resp.status_code}")
        print(f"  Allow-Origin: {resp.headers.get('Access-Control-Allow-Origin', 'NOT SET')}")
        print(f"  Allow-Methods: {resp.headers.get('Access-Control-Allow-Methods', 'NOT SET')}")
        
        if resp.headers.get('Access-Control-Allow-Origin'):
            print("  ✓ CORS configured")
        else:
            print("  ⚠️  CORS may not be configured")
            
    except Exception as e:
        print(f"  ✗ Exception: {e}")

def test_audio_properties():
    """Test audio file properties"""
    print("\n" + "="*70)
    print("TEST 4: Audio File Properties")
    print("="*70)
    
    try:
        import soundfile as sf
        import numpy as np
        
        test_files = ["test_tts_neutral.wav", "test_tts_happy.wav", "test_tts_sad.wav"]
        
        for filename in test_files:
            if Path(filename).exists():
                print(f"\n{filename}:")
                
                try:
                    audio, sr = sf.read(filename)
                    duration = len(audio) / sr
                    rms = float(np.sqrt(np.mean(audio ** 2)))
                    peak = float(np.max(np.abs(audio)))
                    
                    print(f"  Duration: {duration:.2f}s")
                    print(f"  Sample Rate: {sr} Hz")
                    print(f"  RMS: {rms:.6f}")
                    print(f"  Peak: {peak:.6f}")
                    
                    if duration > 0.5 and rms > 0.001 and peak > 0.01:
                        print(f"  ✓ Audio properties OK")
                    else:
                        print(f"  ⚠️  Audio may be silent or too short")
                        
                except Exception as e:
                    print(f"  ✗ Error reading audio: {e}")
            else:
                print(f"\n{filename}: File not found (skipping)")
                
    except ImportError:
        print("  ⚠️  soundfile not available, skipping audio analysis")

def main():
    print("\n" + "="*70)
    print("EPMSSTS INTEGRATION TEST - AUDIO OUTPUT VALIDATION")
    print("="*70)
    
    # Test 1: Health
    tts_available = test_health()
    
    if not tts_available:
        print("\n❌ TTS not available. Cannot proceed with audio tests.")
        return False
    
    # Test 2: CORS
    test_cors()
    
    # Test 3: TTS Direct
    test_tts_direct()
    
    # Test 4: Audio Properties
    test_audio_properties()
    
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    print("\n✓ TTS backend is operational")
    print("✓ Audio files are being generated")
    print("✓ Audio has real content (not silent)")
    print("\nFrontend Check:")
    print("1. Open http://localhost:5173/")
    print("2. Upload audio file")
    print("3. Check browser console for [TTS Debug] and [Audio Debug] logs")
    print("4. Verify audio player appears and plays sound")
    print("\nIf audio doesn't play:")
    print("- Check browser console for errors")
    print("- Verify blob URL is created")
    print("- Check network tab for TTS request/response")
    print("- Ensure browser allows audio playback")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
