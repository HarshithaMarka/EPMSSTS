"""
Direct STT Diagnostic Test
============================

Test what STT actually returns for TTS-generated audio.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from epmssts.services.tts.synthesizer import TtsService, TtsSynthesisRequest
from epmssts.services.stt.transcriber import SpeechToTextService
import soundfile as sf
import numpy as np
from scipy.signal import resample

print("="*80)
print("STT DIAGNOSTIC TEST - Testing STT with TTS-generated audio")
print("="*80)

# Step 1: Generate test audio using TTS
print("\n[STEP 1] Generating test audio using TTS...")
try:
    tts = TtsService()
    print(f"  TTS engine: {tts._engine_kind}")
    
    request = TtsSynthesisRequest(
        text="Hello world, this is a test of speech recognition",
        language="en",
        emotion="neutral"
    )
    
    wav_bytes = tts.synthesize(request)
    print(f"  Generated audio: {len(wav_bytes)} bytes")
    
    # Save to file for inspection
    output_file = Path(__file__).parent / "test_tts_output.wav"
    output_file.write_bytes(wav_bytes)
    
    # Analyze the generated audio
    audio_data, sr = sf.read(output_file)
    if audio_data.ndim == 2:
        audio_data = audio_data.mean(axis=1)
    
    duration = len(audio_data) / sr
    rms = np.sqrt(np.mean(np.square(audio_data)))
    peak = np.max(np.abs(audio_data))
    
    print(f"  Duration: {duration:.3f}s")
    print(f"  RMS: {rms:.6f}")
    print(f"  Peak: {peak:.4f}")
    print(f"  Sample rate: {sr} Hz")
    
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 2: Check if STT considers this silent
print("\n[STEP 2] Checking STT silent detection...")
try:
    stt = SpeechToTextService()
    
    # Get the audio in the format STT expects (16kHz mono float32)
    if sr == 16000:
        audio_data_16k = audio_data.astype(np.float32)
    else:
        num_samples_16k = int(len(audio_data) * 16000 / sr)
        audio_data_16k = resample(audio_data, num_samples_16k)
        audio_data_16k = audio_data_16k.astype(np.float32) # IMPORTANT: Convert to float32
    
    is_silent = stt.is_silent(audio_data_16k)
    print(f"  STT considers audio silent: {is_silent}")
    
    # Check VAD
    from epmssts.services.stt.audio_handler import detect_voice_activity
    vad_score = detect_voice_activity(audio_data_16k, 16000)
    print(f"  Voice Activity Score: {vad_score:.3f}")
    
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

# Step 3: Actually transcribe
print("\n[STEP 3] Running STT transcription...")
try:
    stt = SpeechToTextService()
    
    result = stt.transcribe(audio_data_16k, 16000)
    
    print(f"  Transcript: '{result.text}'")
    print(f"  Language: {result.language}")
    print(f"  Confidence: {getattr(result, 'confidence', 'N/A')}")
    
    if not result.text.strip():
        print("  ⚠️  STT returned empty transcript!")
        
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("DIAGNOSTIC COMPLETE")
print("="*80)
