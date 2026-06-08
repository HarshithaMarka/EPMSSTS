#!/usr/bin/env python
"""
Comprehensive TTS Endpoint Debug Test

Tests the exact flow:
1. Mimics frontend fetch request  
2. Logs response details
3. Validates WAV file structure
4. Checks if 46-byte issue occurs
"""

import requests
import json
from io import BytesIO
import struct

def test_tts_endpoint(text, language, emotion):
    print(f"\n{'='*70}")
    print(f"Testing TTS: text={repr(text)}, lang={language}, emotion={emotion}")
    print(f"{'='*70}")
    
    payload = {
        "text": text,
        "language": language,
        "emotion": emotion
    }
    
    url = "http://localhost:8000/tts/synthesize"
    headers = {"Content-Type": "application/json"}
    
    print(f"Request URL: {url}")
    print(f"Request Headers: {headers}")
    print(f"Request Body: {json.dumps(payload)}")
    
    try:
        # Make request with short timeout first
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30  # 30 second timeout
        )
        
        print(f"\nResponse Status: {response.status_code} {response.reason}")
        print(f"Response Headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        content = response.content
        print(f"\nResponse Body Size: {len(content)} bytes")
        
        if len(content) > 0:
            print(f"First 50 bytes (hex): {content[:50].hex()}")
            print(f"First 50 bytes (dec): {' '.join(str(b) for b in content[:50])}")
            
            # Validate WAV format
            if len(content) >= 12:
                riff_marker = content[0:4]
                file_size = struct.unpack('<I', content[4:8])[0]
                wave_marker = content[8:12]
                
                print(f"\nWAV Header Analysis:")
                print(f"  RIFF Marker: {riff_marker} (expected: b'RIFF')")
                print(f"  File Size Field: {file_size}")
                print(f"  WAVE Marker: {wave_marker} (expected: b'WAVE')")
                print(f"  Total bytes: {len(content)}")
                
                if riff_marker == b'RIFF' and wave_marker == b'WAVE':
                    print(f"  ✅ Valid WAV format detected")
                    if len(content) > 44:
                        print(f"  ✅ Contains audio data (not just header)")
                    else:
                        print(f"  ⚠️ Only header present, no audio data!")
                else:
                    print(f"  ❌ Invalid WAV format!")
                    
        if response.status_code == 200:
            print(f"\n✅ Request succeeded!")
        else:
            print(f"\n❌ Request failed with status {response.status_code}")
            if len(content) < 500:
                print(f"Response content: {content.decode('utf-8', errors='ignore')}")
        
        return len(content)
        
    except requests.exceptions.Timeout:
        print(f"❌ Request timed out after 30 seconds")
        return -1
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection error: {e}")
        return -1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return -1

# Test various inputs
print("\n" + "="*70)
print("COMPREHENSIVE TTS ENDPOINT TEST")
print("="*70)

test_cases = [
    ("Hi", "en", "neutral"),
    ("Hello world", "en", "neutral"),
    ("This is a test", "en", "happy"),
    ("Hello world this is a longer test of the TTS system", "en", "sad"),
]

results = []
for text, lang, emotion in test_cases:
    size = test_tts_endpoint(text, lang, emotion)
    results.append((text, size))

print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")
for text, size in results:
    status = "✅" if size > 1000 else ("⚠️" if size > 0 else "❌")
    print(f"{status} {repr(text[:30])}: {size} bytes")

print(f"\nNote: If any result shows 46 bytes, that indicates the issue!")
print(f"Expected: >10000 bytes for normal text")
