# EPMSSTS - Emotion-Preserving Multilingual Speech-to-Speech Translation System

## 🎯 System Overview

A complete, production-ready MVP for translating speech across multiple languages while **preserving emotion and dialect**.

### Core Pipeline
```
Audio Input → Preprocessing → STT → Dialect Detection → Emotion Detection → Translation → TTS → Audio Output
```

## 🏗️ Architecture

### Backend (FastAPI)
- **Services**: Modular, service-oriented architecture
  - `stt/`: Speech-to-Text (Whisper)
  - `emotion/`: Multi-modal emotion detection (Audio + Text)
  - `dialect/`: Regional dialect classification
  - `translation/`: Context-aware translation (NLLB-200)
  - `tts/`: Emotion-preserving TTS (YourTTS)
  
- **API Endpoints**:
  ```
  GET    /health                          - Health check
  POST   /stt/transcribe                 - Transcribe audio
  POST   /emotion/detect                 - Detect emotion from audio
  POST   /emotion/analyze                - Alias for emotion/detect
  POST   /dialect/detect                 - Detect dialect
  POST   /translate                      - Translate text
  POST   /tts/synthesize                 - Synthesize speech
  POST   /translate/speech               - Full pipeline (old)
  POST   /process/speech-to-speech       - Full pipeline (NEW)
  GET    /output/{session_id}.wav        - Get synthesized audio
  ```

### Frontend (Streamlit)
- Beautiful, modern MVP UI
- Two modes:
  - **Upload File**: Upload pre-recorded audio
  - **Live Recording**: Record audio directly in browser
- Real-time results display
- Emotion-aware badge visualization

## 🚀 Quick Start

### 1. Install Dependencies
```bash
# Using conda (RECOMMENDED for Python 3.11)
conda create -n epmssts python=3.11
conda activate epmssts
pip install -r requirements.txt
```

> **Note**: Python 3.13 has compatibility issues with some ML packages. Use Python 3.11 for best results.

### 2. Start Backend
```bash
# Terminal 1: Start the API server
cd c:\vivek\project_final_year\Epmssts\EPMSSTS
uvicorn epmssts.api.main:app --reload --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Waiting for application startup.
```

**First-time startup**:
- Models will download automatically (~2-3 minutes)
- Progress bars show download status
- Once complete, you'll see: `Application startup complete`

### 3. Start Frontend (New Terminal)
```bash
# Terminal 2: Start the Streamlit UI
cd c:\vivek\project_final_year\Epmssts\EPMSSTS
streamlit run frontend/app.py --server.port=8502
```

Access the UI at: **http://localhost:8502**

## 📋 API Endpoints Reference

### Health Check
```bash
curl http://localhost:8000/health
```

### Full Pipeline (END-TO-END)
```bash
curl -X POST "http://localhost:8000/process/speech-to-speech" \
  -F "file=@audio.wav" \
  -F "target_lang=en" \
  -F "target_emotion=happy"
```

**Response**:
```json
{
  "transcript": "Original text",
  "detected_language": "te",
  "detected_emotion": "neutral",
  "detected_dialect": "Telangana",
  "translated_text": "Translated text",
  "target_language": "en",
  "target_emotion": "happy",
  "output_audio_url": "/output/{session_id}.wav",
  "confidence": 0.95
}
```

### Individual Endpoints

#### Transcribe
```bash
curl -X POST "http://localhost:8000/stt/transcribe" \
  -F "file=@audio.wav"
```

#### Detect Emotion
```bash
curl -X POST "http://localhost:8000/emotion/analyze" \
  -F "file=@audio.wav"
```

#### Detect Dialect
```bash
curl -X POST "http://localhost:8000/dialect/detect" \
  -F "file=@audio.wav"
```

## 📊 System Architecture

### Services
1. **STT Service** (`services/stt/`)
   - Uses: Faster-Whisper
   - Input: Audio (any format)
   - Output: Transcript + detected language

2. **Emotion Service** (`services/emotion/`)
   - Audio: Wav2Vec2 SER
   - Text: BERT-based emotion classification
   - Output: Emotion + confidence scores

3. **Dialect Classifier** (`services/dialect/`)
   - Rule-based heuristics (MVP)
   - Supports: Telugu, Hindi, English
   - Output: Dialect tag

4. **Translation Service** (`services/translation/`)
   - Model: NLLB-200
   - Supports: Telugu ↔ Hindi ↔ English
   - Context-aware translation

5. **TTS Service** (`services/tts/`)
   - Model: YourTTS (Coqui)
   - Features:
     - Speed modulation (emotion)
     - Multilingual support
   - Note: Requires Python 3.11 or earlier

## 🧪 Testing

### Verify Endpoints
```bash
python test_endpoints.py
```

### Test with Sample Audio
```bash
python -m pytest tests/ -v
```

## 🐳 Dockerization (Coming Soon)

```bash
docker build -t epmssts:latest .
docker run -p 8000:8000 -p 8502:8502 epmssts:latest
```

##🔧 Troubleshooting

### Backend Not Starting
- **Issue**: `ModuleNotFoundError: No module named 'TTS'`
- **Solution**: Use Python 3.11 (TTS doesn't support 3.13 yet)

### Models Downloading Slowly
- Large models (NLLB-200, BERT) are 300-500MB
- First run takes 3-5 minutes
- Subsequent runs are instant (cached)

### Port Already in Use
```bash
# Find and kill the process
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

## 📚 Tech Stack

| Component | Tech | Purpose |
|-----------|------|---------|
| API | FastAPI | REST API |
| STT | Faster-Whisper | Speech recognition |
| Emotion | Wav2Vec2 + BERT | Emotion detection |
| Translation | NLLB-200 | Neural translation |
| TTS | YourTTS | Speech synthesis |
| Frontend | Streamlit | User interface |
| ML Framework | PyTorch | Deep learning |
| Audio | Librosa, SoundFile | Audio processing |

## 📝 Requirements

- **Python**: 3.11 (3.13 has package conflicts)
- **RAM**: 8GB minimum (16GB recommended)
- **Disk**: 10GB (for model caching)
- **GPU**: Optional (CUDA-enabled for faster inference)

## 🎯 Features

✅ **Implemented**
- Speech-to-Text (STT) with auto-language detection
- Emotion detection (audio + text fusion)
- Dialect classification
- Context-aware translation
- Emotion-preserving TTS
- Beautiful Streamlit UI
- File upload + live recording
- Real-time results

🚀 **Next Steps**
- Docker containerization
- Comprehensive test suite
- Database integration (PostgreSQL)
- Redis caching
- API rate limiting

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review the logs in terminal output
3. Verify all dependencies are installed

---

**Last Updated**: January 29, 2026
**Status**: MVP Ready ✅
