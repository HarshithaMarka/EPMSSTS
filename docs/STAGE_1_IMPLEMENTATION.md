# Stage 1 Implementation: Speech Understanding

Date: January 29, 2026

## Scope
Stage 1 focuses on **Speech Understanding**, which includes:
- **Speech-to-Text (STT)**
- **Emotion Recognition** (audio + text fusion)
- **Dialect Classification**

This document maps the Stage 1 requirements to the actual implementation in the EPMSSTS project.

---

## 1) Stage 1 Architecture Overview
Stage 1 receives an input audio stream or audio file and produces three outputs:
1. **Transcription** (text)
2. **Emotion label + confidence**
3. **Dialect classification**

**Data Flow (Stage 1):**
1. Audio Input → STT → Transcribed Text
2. Audio Input → Audio Emotion Model
3. Transcribed Text → Text Emotion Model
4. Audio + Text Emotion → Fusion → Final Emotion
5. Transcribed Text → Dialect Classifier

---

## 1.1 Presentation Code Walkthrough (Stage 1 Flow)
Use the following snippet to show the full Stage 1 flow in a single slide:

```python
# Stage 1: Speech Understanding (STT + Emotion + Dialect)
from epmssts.services.stt.transcriber import SpeechToTextService
from epmssts.services.emotion.audio_emotion import AudioEmotionService
from epmssts.services.emotion.text_emotion import TextEmotionService
from epmssts.services.emotion.fusion import EmotionFusionService
from epmssts.services.dialect.classifier import DialectClassifier

stt = SpeechToTextService()
audio_emotion = AudioEmotionService()
text_emotion = TextEmotionService()
fusion = EmotionFusionService()
dialect = DialectClassifier()

# audio: numpy array or bytes, sample_rate: int
text, segments = stt.transcribe(audio, sample_rate)
audio_pred = audio_emotion.predict(audio, sample_rate)
text_pred = text_emotion.predict(text)
final_emotion = fusion.fuse(audio_pred, text_pred)
dialect_pred = dialect.detect(text)

stage1_output = {
	"transcription": {"text": text, "segments": segments},
	"emotion": final_emotion,
	"dialect": dialect_pred,
}
```

---

## 2) Core Implementations

### 2.1 Speech-to-Text (STT)
**Implementation File:** [epmssts/services/stt/transcriber.py](epmssts/services/stt/transcriber.py)

**Key Class:** `SpeechToTextService`
- Loads Faster-Whisper model
- Handles audio normalization
- Returns transcription text + metadata

**Primary Method:** `transcribe(audio, sample_rate)`
- Input: audio bytes/array + sample rate
- Output: transcription text + segments

**Initialization:**
- Created during API startup in [epmssts/api/main.py](epmssts/api/main.py)

**Presentation Code (STT only):**
```python
from epmssts.services.stt.transcriber import SpeechToTextService

stt = SpeechToTextService()
text, segments = stt.transcribe(audio, sample_rate)
print(text)
```

---

### 2.2 Emotion Recognition (Audio + Text Fusion)
**Audio Emotion Service**
- **File:** [epmssts/services/emotion/audio_emotion.py](epmssts/services/emotion/audio_emotion.py)
- **Class:** `AudioEmotionService`
- **Method:** `predict(audio, sample_rate)`

**Text Emotion Service**
- **File:** [epmssts/services/emotion/text_emotion.py](epmssts/services/emotion/text_emotion.py)
- **Class:** `TextEmotionService`
- **Method:** `predict(text)`

**Fusion Logic**
- **File:** [epmssts/services/emotion/fusion.py](epmssts/services/emotion/fusion.py)
- **Class:** `EmotionFusionService`
- **Method:** `fuse(audio_emotion, text_emotion)`

**API Integration:**
- Emotion detection pipeline is invoked in [epmssts/api/main.py](epmssts/api/main.py)

**Presentation Code (Emotion only):**
```python
from epmssts.services.emotion.audio_emotion import AudioEmotionService
from epmssts.services.emotion.text_emotion import TextEmotionService
from epmssts.services.emotion.fusion import EmotionFusionService

audio_emotion = AudioEmotionService()
text_emotion = TextEmotionService()
fusion = EmotionFusionService()

audio_pred = audio_emotion.predict(audio, sample_rate)
text_pred = text_emotion.predict(text)
final_emotion = fusion.fuse(audio_pred, text_pred)
print(final_emotion)
```

---

### 2.3 Dialect Classification
**Implementation File:** [epmssts/services/dialect/classifier.py](epmssts/services/dialect/classifier.py)

**Key Class:** `DialectClassifier`
- Rule-based keyword detection
- Supports Telugu dialect categories

**Primary Method:** `detect(text)`
- Input: transcribed text
- Output: dialect label + confidence

**API Integration:**
- Dialect detection used in [epmssts/api/main.py](epmssts/api/main.py)

**Presentation Code (Dialect only):**
```python
from epmssts.services.dialect.classifier import DialectClassifier

dialect = DialectClassifier()
label = dialect.detect(text)
print(label)
```

---

## 3) API Endpoints for Stage 1
Stage 1 is exposed via the following endpoints in [epmssts/api/main.py](epmssts/api/main.py):

- `POST /stt/transcribe` → STT only
- `POST /emotion/detect` → Emotion only (audio/text)
- `POST /dialect/detect` → Dialect only
- `POST /pipeline/process` → Full Stage 1 pipeline (STT + Emotion + Dialect)

**Presentation Code (API example):**
```bash
curl -X POST http://127.0.0.1:8000/pipeline/process \
	-H "Content-Type: multipart/form-data" \
	-F "audio=@sample.wav"
```

**Example Response (Stage 1):**
```json
{
	"transcription": {
		"text": "...",
		"segments": []
	},
	"emotion": {
		"label": "neutral",
		"confidence": 0.83,
		"audio_score": 0.81,
		"text_score": 0.85
	},
	"dialect": {
		"label": "standard_telugu",
		"confidence": 0.74
	}
}
```

---

## 4) Testing Coverage (Stage 1)

**STT Tests**
- [tests/unit/test_stt.py](tests/unit/test_stt.py)

**Emotion Tests**
- [tests/unit/test_emotion.py](tests/unit/test_emotion.py)

**Dialect Tests**
- [tests/unit/test_dialect.py](tests/unit/test_dialect.py)

**Pipeline/Integration Tests**
- [tests/unit/test_services_comprehensive.py](tests/unit/test_services_comprehensive.py)
- [tests/integration/test_api.py](tests/integration/test_api.py)
- [tests/integration/test_api_comprehensive.py](tests/integration/test_api_comprehensive.py)

---

## 5) Stage 1 Outputs
Stage 1 produces the following data outputs:

- **Transcription**: `{ text, segments }`
- **Emotion**: `{ label, confidence, audio_score, text_score }`
- **Dialect**: `{ label, confidence }`

These outputs are consumed by **Stage 2** for translation and emotion-aware TTS.

---

## 6) Stage 1 Runtime Components

**Required Models:**
- Faster-Whisper (STT)
- Wav2Vec2 (Audio Emotion)
- Text Emotion model (Transformers)

**Runtime Services:**
- FastAPI backend

---

## 7) Summary
Stage 1 is fully implemented with clear separation of services for STT, Emotion, and Dialect. The pipeline is exposed via API endpoints and validated through unit and integration tests. The outputs from this stage feed directly into Stage 2 (Translation + Emotion-aware TTS).
