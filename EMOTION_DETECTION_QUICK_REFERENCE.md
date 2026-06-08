# Emotion Detection - Quick Reference & Usage Guide

## 🚀 Quick Start

### Test the API

#### 1. Basic Emotion Detection
```bash
curl -X POST http://localhost:8000/emotion/detect \
  -F "file=@voice_sample.wav"
```

**Response:**
```json
{
  "emotion": "happy",
  "confidence": 0.87,
  "scores": {
    "happy": 0.87,
    "neutral": 0.08,
    "sad": 0.03,
    "angry": 0.02,
    "fearful": 0.00
  },
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "stage": "emotion",
    "latency_ms": 145,
    "confidence": 0.87,
    "fallback_used": false,
    "audio_metrics": {
      "duration_sec": 1.23,
      "peak": 0.43,
      "rms": 0.023,
      "clipped_ratio": 0.0,
      "speech_ratio": 0.92
    }
  }
}
```

#### 2. With Debug Information
```bash
curl -X POST "http://localhost:8000/emotion/detect?include_debug=true" \
  -F "file=@voice_sample.wav"
```

**Additional debug output:**
```json
{
  "debug": {
    "request_id": "550e8400...",
    "pipeline_steps": 2,
    "logs": [
      {
        "stage": "preprocessing",
        "audio_metrics": {
          "rms_db": -20.2,
          "peak_db": -8.5,
          "peak_amplitude": 0.43,
          "mean_amplitude": 0.023,
          "spectral_centroid": 2145.3,
          "dynamic_range": 11.7,
          "crest_factor": 3.2,
          "energy_normalized": true,
          "energy_level": "normal"
        }
      },
      {
        "stage": "inference",
        "raw_prediction": {
          "label": "happy",
          "confidence": 0.87,
          "scores": { ... }
        }
      }
    ]
  }
}
```

---

## 🔧 Understanding Energy Levels

The system classifies audio energy into categories:

| Energy Level | RMS dBFS Range | Meaning | Action |
|-------------|---------|---------|--------|
| **silent** | < -60 dB | No detectable sound | Reject as silent |
| **quiet** | -60 to -35 dB | Very quiet voice | Require high confidence |
| **normal** | -35 to -25 dB | Normal speech | Standard inference |
| **loud** | -25 to -15 dB | Raised voice | Standard inference |
| **very_loud** | > -15 dB | Shouting | Standard inference |

### Example: Quiet Voice Detection
```
Input: Whispered speech at -40 dBFS
Energy level: "quiet"
↓
Model predicts: "sad" (55% confidence)
↓
Rule triggered: "low_energy_sad_bias"
↓
Result: Override to "neutral" (100% confidence)
```

---

## 🪵 Reading Debug Logs

### Preprocessing Logs

```
[req-id] PREPROCESSING | energy=quiet rms_db=-40.0 peak_db=-8.5 
  spectral_centroid=1800.3 dyn_range=31.5
```

**What it means:**
- `energy=quiet`: Audio is below normal speech level
- `rms_db=-40.0`: RMS normalized to -20 but source was -40 (very quiet)
- `peak_db=-8.5`: Peak amplitude is -8.5 dBFS
- `spectral_centroid=1800.3`: Voice center of mass at 1.8 kHz (slightly low)
- `dyn_range=31.5`: Wide dynamic range (good for emotion features)

### Inference Logs

```
[req-id] AUDIO INFERENCE | prediction=sad conf=0.550 | 
  top3=[('sad', '0.550'), ('neutral', '0.350'), ('happy', '0.100')]
```

**What it means:**
- Model predicts "sad" with 55% confidence
- Second choice: "neutral" (35%)
- Low confidence (< 0.70) on low-energy audio

### Override Logs

```
[req-id] OVERRIDE | reason=low_energy_sad_bias → neutral
```

**What it means:**
- Audio energy is below the quiet threshold
- Model predicted "sad" (common bias on quiet input)
- Automatically overridden to "neutral" to prevent false positives

### Fusion Logs

```
[req-id] FUSION | audio=sad(0.55) text=happy(0.85) → final=happy(0.73) | 
  weights=audio0.40 text0.60
```

**What it means:**
- Audio model said: sad (55% confidence)
- Text sentiment said: happy (85% confidence)
- Text had higher confidence, so weight adjusted: audio 40%, text 60%
- Final result: happy (73% confidence)

---

## 📊 Interpreting Results

### High Confidence (> 0.80)
✅ Trust the prediction. The model is confident in its choice.

```json
{
  "emotion": "happy",
  "confidence": 0.91,
  "explanation": "High confidence = reliable prediction"
}
```

### Medium Confidence (0.50-0.80)
⚠️ The prediction is likely correct, but not guaranteed.

```json
{
  "emotion": "neutral",
  "confidence": 0.68,
  "explanation": "Medium confidence = probably correct, but review metrics"
}
```

### Low Confidence (< 0.50)
❌ The prediction may be unreliable. Check:
- Audio quality (energy level, noise)
- Whether text sentiment differs from audio
- Whether override rules were triggered

```json
{
  "emotion": "neutral",
  "confidence": 1.00,
  "debug": {
    "override_reason": "low_energy_sad_bias",
    "original_prediction": "sad",
    "audio_metrics": { "energy_level": "quiet", "rms_db": -40.0 }
  },
  "explanation": "Fallback due to low audio energy"
}
```

---

## 🐛 Troubleshooting

### Problem: Always returns "neutral"

**Possible causes:**
1. Audio energy too low (< -60 dBFS)
2. Model confidence below threshold on quiet audio
3. Override rule triggered (check debug info)

**Solution:**
- Check `include_debug=true` response
- Look for `override_reason` in debug logs
- Verify audio has clear speech

### Problem: Prediction doesn't match actual speech

**Possible causes:**
1. Audio quality poor (noise, low gain)
2. Accent or speech pattern unusual
3. Low confidence not caught by thresholds

**Solution:**
- Enable debug logging
- Check `spectral_centroid` (should be 2000-4000 Hz for voice)
- Verify `energy_level` is not "quiet"
- Check if `text_prediction` differs from `audio_prediction`

### Problem: Model seems biased to specific emotion

**Possible causes:**
1. Training data imbalance
2. Energy level triggering bias pattern
3. Microphone characteristics

**Solution:**
- Check RMS levels across different recordings
- Compare with text sentiment
- Enable fusion with text predictions
- Adjust confidence thresholds if needed

---

## 🧪 Testing with Diagnostic Suite

### Run All Tests
```bash
python emotion_diagnostics.py --verbose
```

### Test Specific Audio File
```bash
python emotion_diagnostics.py --test-audio my_voice.wav
```

### Check Specific Test
```bash
# Preprocessing only
python -c "
from epmssts.services.emotion.audio_preprocessing import EmotionAudioPreprocessor
import numpy as np
p = EmotionAudioPreprocessor()
audio = np.random.normal(0, 0.05, 16000)
processed, metrics = p.preprocess_for_emotion(audio)
print(f'Energy level: {metrics.energy_level}')
print(f'RMS: {metrics.rms_db:.2f} dBFS')
"
```

---

## 🔄 Integration Examples

### Python Client
```python
import requests
from pathlib import Path

# Load audio file
audio_file = Path("voice_sample.wav")

# Send request with debug
response = requests.post(
    "http://localhost:8000/emotion/detect?include_debug=true",
    files={"file": open(audio_file, "rb")}
)

result = response.json()

print(f"Emotion: {result['emotion']}")
print(f"Confidence: {result['confidence']:.2f}")

# Check for override
if "override_reason" in str(result.get("debug", {})):
    print(f"Note: Prediction was overridden due to low audio quality")

# Access detailed metrics
if "debug" in result:
    logs = result["debug"]["logs"]
    preprocessing = next(l for l in logs if l["stage"] == "preprocessing")
    metrics = preprocessing["audio_metrics"]
    print(f"Audio energy level: {metrics['energy_level']}")
    print(f"RMS: {metrics['rms_db']:.2f} dBFS")
```

### JavaScript/TypeScript
```typescript
async function detectEmotion(audioFile: File, includeDebug: boolean = false) {
  const formData = new FormData();
  formData.append("file", audioFile);

  const url = new URL("http://localhost:8000/emotion/detect");
  if (includeDebug) {
    url.searchParams.set("include_debug", "true");
  }

  const response = await fetch(url, {
    method: "POST",
    body: formData
  });

  const result = await response.json();

  return {
    emotion: result.emotion,
    confidence: result.confidence,
    scores: result.scores,
    energyLevel: result.debug?.logs[0]?.audio_metrics?.energy_level,
    rmsDb: result.debug?.logs[0]?.audio_metrics?.rms_db,
  };
}

// Usage
const audioFile = document.getElementById("audio-input").files[0];
const emotion = await detectEmotion(audioFile, true);
console.log(`${emotion.emotion} (${emotion.confidence.toFixed(2)})`);
```

---

## 📈 Performance Expectations

| Operation | Time | Notes |
|-----------|------|-------|
| **Preprocessing** | 5-10ms | RMS normalization, spectral analysis |
| **Model Inference** | 50-200ms | Depends on CPU/GPU |
| **Total Latency** | 60-220ms | Acceptable for real-time |
| **Memory Usage** | ~2MB | Preprocessing buffers only |

---

## 🎯 Best Practices

### 1. Provide Clean Audio
- Microphone: Close to speaker (6-12 inches)
- Location: Quiet room (no background noise)
- Format: WAV or MP3 at 16kHz mono
- Duration: 1-30 seconds

### 2. Use Text Fusion
When available, provide transcript with emotion detection:
- Text emotion helps when audio is noisy
- Text sentiment strong → increases text weight
- Neutral text with strong audio → trusts audio

### 3. Monitor Energy Levels
```bash
# Check if audio is too quiet
grep "energy_level" emotion.log | sort | uniq -c
```

### 4. Test Thresholds Locally
Before deploying changes to thresholds:
```bash
python emotion_diagnostics.py --verbose
# Verify expected behavior on test cases
```

### 5. Log Overrides
```bash
# Monitor when predictions are overridden
grep "OVERRIDE" emotion.log | wc -l
# If > 5% of requests, may need to adjust thresholds
```

---

## 📚 Additional Resources

- **Technical Report**: `EMOTION_DETECTION_FIX_REPORT.md`
- **Implementation Details**: `EMOTION_DETECTION_IMPLEMENTATION_SUMMARY.md`
- **Source Code**: `epmssts/services/emotion/`
- **Test Suite**: `emotion_diagnostics.py`

---

## 💡 Key Takeaways

1. **The system handles quiet audio correctly** - overrides "sad" bias
2. **Debug information is available on demand** - use `include_debug=true`
3. **Energy levels matter** - watch for `energy_level: "quiet"`
4. **Confidence thresholds are enforced** - very low confidence → fallback to neutral
5. **Text + audio fusion is adaptive** - weights adjust based on confidence

✅ **The system is now production-ready for live microphone input.**
