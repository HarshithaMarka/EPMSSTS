"""
End-to-End TTS System Test

Simulates what happens in the frontend:
1. Record audio → STT
2. Detect emotion → Confirm detected_emotion exists
3. Translate text
4. Call TTS with detected emotion
5. Verify audio blob size

This will identify exactly where the 46-byte issue comes from.
"""

import requests
import json
import numpy as np
from io import BytesIO
import soundfile as sf

API_BASE = "http://localhost:8000"

print("=" * 80)
print("END-TO-END TTS SYSTEM DIAGNOSTIC")
print("=" * 80)

# Step 1: Create test audio
print("\n[STEP 1] Creating test audio...")
try:
    # Generate 2 seconds of speech at 16kHz
    sr = 16000
    duration = 2
    t = np.linspace(0, duration, int(sr * duration))
    frequency = 440  # A4 note
    amplitude = 0.3
    audio = amplitude * np.sin(2 * np.pi * frequency * t).astype(np.float32)
    
    audio_buffer = BytesIO()
    sf.write(audio_buffer, audio, sr, format='WAV')
    audio_bytes = audio_buffer.getvalue()
    print(f"OK - Created test audio: {len(audio_bytes)} bytes")
except Exception as e:
    print(f"ERROR - Failed to create audio: {e}")
    exit(1)

# Step 2: Transcribe (STT)
print("\n[STEP 2] Testing STT endpoint...")
try:
    files = {'file': ('test.wav', audio_bytes, 'audio/wav')}
    response = requests.post(f"{API_BASE}/stt/transcribe", files=files, timeout=30)
    stt_result = response.json()
    print(f"STT Response: {json.dumps(stt_result, indent=2)}")
    if 'text' in stt_result:
        transcribed_text = stt_result['text']
        print(f"OK - STT Success: '{transcribed_text}'")
    else:
        print(f"ERROR - STT failed - no text in response")
except Exception as e:
    print(f"ERROR - STT failed: {e}")
    exit(1)

# Step 3: Detect emotion
print("\n[STEP 3] Testing Emotion Detection...")
try:
    emotion_payload = {"audio_bytes": audio_bytes.hex()}  # Send hex for testing
    response = requests.post(f"{API_BASE}/emotion/detect", json={"audio_bytes": audio_bytes.hex()}, timeout=30)
    print(f"Response status: {response.status_code}")
    
    # Try direct endpoint instead
    files = {'file': ('test.wav', audio_bytes, 'audio/wav')}
    response = requests.post(f"{API_BASE}/emotion/detect", files=files, timeout=30)
    emotion_result = response.json()
    print(f"Emotion Response: {json.dumps(emotion_result, indent=2)}")
    if 'emotion' in emotion_result:
        detected_emotion = emotion_result['emotion']
        confidence = emotion_result.get('confidence', 0.5)
        print(f"OK - Emotion Detected: {detected_emotion} (confidence: {confidence})")
    else:
        print(f"ERROR - Emotion detection failed")
        detected_emotion = "neutral"
except Exception as e:
    print(f"ERROR - Emotion detection failed: {e}")
    detected_emotion = "neutral"

# Step 4: Translate text
print("\n[STEP 4] Testing Translation...")
try:
    if 'transcribed_text' in locals() and transcribed_text:
        trans_payload = {
            "text": transcribed_text,
            "source_lang": "en",
            "target_lang": "en"
        }
        response = requests.post(f"{API_BASE}/translate", json=trans_payload, timeout=30)
        translation_result = response.json()
        print(f"Translation Response: {json.dumps(translation_result, indent=2)}")
        if 'translated_text' in translation_result:
            translated_text = translation_result['translated_text']
            print(f"OK - Translation: '{translated_text}'")
        else:
            print(f"ERROR - Translation failed")
            translated_text = transcribed_text
    else:
        translated_text = "Hello world this is a test"
        print(f"WARNING - Using fallback text: '{translated_text}'")
except Exception as e:
    print(f"ERROR - Translation failed: {e}")
    translated_text = "Hello world test"

# Step 5: TTS (The critical part)
print("\n[STEP 5] Testing TTS Endpoint (CRITICAL)...")
try:
    tts_payload = {
        "text": translated_text,
        "language": "en",
        "emotion": detected_emotion
    }
    
    print(f"TTS Payload: {json.dumps(tts_payload)}")
    print(f"Sending to: {API_BASE}/tts/synthesize")
    
    response = requests.post(
        f"{API_BASE}/tts/synthesize",
        json=tts_payload,
        timeout=60,  # Long timeout for pyttsx3
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Response Status: {response.status_code} {response.reason}")
    print(f"Response Headers:")
    for key, value in response.headers.items():
        if key.lower() in ['content-type', 'content-length', 'transfer-encoding']:
            print(f"  {key}: {value}")
    
    audio_blob = response.content
    print(f"\nAUDIO BLOB ANALYSIS:")
    print(f"  Size: {len(audio_blob)} bytes")
    
    if len(audio_blob) >= 12:
        print(f"  First 12 bytes (hex): {audio_blob[:12].hex()}")
        print(f"  WAV Header Check: RIFF={audio_blob[0:4]}, WAVE={audio_blob[8:12]}")
        
        if audio_blob[:4] == b'RIFF' and audio_blob[8:12] == b'WAVE':
            print(f"  OK - Valid WAV format")
            if len(audio_blob) > 100:
                print(f"  OK - Contains audio data (not just header)")
            else:
                print(f"  PROBLEM - Only {len(audio_blob)} bytes (header + minimal data)")
        else:
            print(f"  ERROR - Invalid WAV format!")
    
    if len(audio_blob) == 46:
        print(f"\nCRITICAL ISSUE: 46-byte response detected!")
        print(f"This matches the reported issue. Contents:")
        print(f"  Hex: {audio_blob.hex()}")
        print(f"  ASCII: {repr(audio_blob)}")
        print(f"\nThis is likely: A minimal WAV header + 2 bytes of data")
        print(f"Expected: >10000 bytes")
    
except Exception as e:
    print(f"ERROR - TTS failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
