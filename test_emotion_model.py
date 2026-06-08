#!/usr/bin/env python3
"""Quick test to verify emotion model is working correctly"""

import sys
sys.path.insert(0, '.')

from epmssts.services.emotion.audio_emotion import AudioEmotionService
import numpy as np

service = AudioEmotionService()

print("=== EMOTION MODEL DIAGNOSTICS ===\n")
print(f"Model available: {service._model_available}")
print(f"Model ID2Label mapping: {service._model_id2label}")
print(f"Label to emotion mapping: {service._label2emotion}")
print()

# Test 1: Synthetic happy-like audio (high frequency variation)
print("Test 1: High-energy audio (should detect happy/excited)")
duration = 3  # seconds
sample_rate = 16000
t = np.linspace(0, duration, int(sample_rate * duration))
happy_audio = 0.3 * np.sin(2 * np.pi * 500 * t) + 0.2 * np.sin(2 * np.pi * 1000 * t)
result = service.predict(happy_audio.astype(np.float32), sample_rate)
print(f"  Detected: {result.label} (confidence: {result.confidence:.2f})")
print(f"  All scores: {result.scores}")
print()

# Test 2: Synthetic sad-like audio (low frequency, quiet)
print("Test 2: Low-energy audio (should detect sad/neutral)")
sad_audio = 0.1 * np.sin(2 * np.pi * 200 * t)
result = service.predict(sad_audio.astype(np.float32), sample_rate)
print(f"  Detected: {result.label} (confidence: {result.confidence:.2f})")
print(f"  All scores: {result.scores}")
print()

# Test 3: Synthetic angry-like audio (loud, harsh)
print("Test 3: High-amplitude harsh audio (should detect angry)")
angry_audio = 0.5 * np.sin(2 * np.pi * 800 * t) + 0.3 * np.random.randn(len(t))
result = service.predict(angry_audio.astype(np.float32), sample_rate)
print(f"  Detected: {result.label} (confidence: {result.confidence:.2f})")
print(f"  All scores: {result.scores}")
print()

# Test 4: Near-silence (should detect neutral)
print("Test 4: Near-silent audio (should detect neutral)")
silent_audio = 0.001 * np.random.randn(int(sample_rate * duration))
result = service.predict(silent_audio.astype(np.float32), sample_rate)
print(f"  Detected: {result.label} (confidence: {result.confidence:.2f})")
print(f"  All scores: {result.scores}")
print()

print("=== DIAGNOSIS ===")
if all([result.label == "sad" for _ in range(3)]):
    print("⚠️  WARNING: Model appears to be stuck on 'sad' emotion")
    print("   Possible causes:")
    print("   - Model weights corrupted")
    print("   - Incorrect label mapping")
    print("   - Preprocessing issue")
else:
    print("✓ Model is producing varied emotion predictions")
