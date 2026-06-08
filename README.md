# EPMSSTS — Emotion-Preserving Multilingual Speech-to-Speech Translation System

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Production-ready MVP** for end-to-end speech-to-speech translation with emotion preservation across Telugu, Hindi, and English.

## 🎯 Features

- **Speech-to-Text**: faster-whisper (large-v3) with automatic language detection
- **Emotion Detection**: Wav2Vec2-based audio emotion recognition (5 emotions)
- **Dialect Detection**: Rule-based Telugu dialect classification (Telangana/Andhra)
- **Translation**: NLLB-200 for Telugu ↔ Hindi ↔ English
- **Emotion-Conditioned TTS**: Coqui TTS with prosody control via speaking speed
- **REST API**: FastAPI with comprehensive endpoints
- **Web UI**: Streamlit frontend for easy testing
- **Database Logging**: PostgreSQL for session tracking
- **Caching**: Redis for session management
- **Docker Ready**: Full containerization with docker-compose

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Usage](#-usage)
- [API Documentation](#-api-documentation)
- [Architecture](#-architecture)
- [Testing](#-testing)
- [Deployment](#-deployment)
- [Configuration](#-configuration)
- [Contributing](#-contributing)

## 🚀 Quick Start

### MVP - Fastest Way to Get Started

```bash
# 1. Create conda environment
conda create -n epmssts python=3.11
conda activate epmssts

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the backend (in one terminal)
uvicorn epmssts.api.main:app --reload

# 4. Start the frontend (in another terminal)
streamlit run frontend/app.py

# 5. Open in browser
# Frontend: http://localhost:8502
# API Docs: http://localhost:8000/docs
```

**Note**: Python 3.11 is recommended (3.13 has TTS compatibility issues). The system gracefully handles missing TTS, so the app starts even if TTS isn't available.

### Using Docker (Recommended for Production)

```bash
# Clone the repository
git clone <repository-url>
cd EPMSSTS

# Start all services
docker-compose up -d

# Access the services
# API: http://localhost:8000
# Frontend: http://localhost:8501
# API Docs: http://localhost:8000/docs
```

### Local Development (Full Stack)

```bash
# Create conda environment
conda create -n epmssts python=3.11
conda activate epmssts

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis (or use Docker)
docker-compose up -d postgres redis

# Run the API
uvicorn epmssts.api.main:app --reload

# In another terminal, run the frontend
streamlit run frontend/app.py
```

## 📦 Installation

### Prerequisites

- Python 3.11+ (3.13 supported with TTS fallback; TTS unavailable but system works)
- PostgreSQL 15+ (optional, for logging)
- Redis 7+ (optional, for caching)
- FFmpeg (for audio processing)
- CUDA-capable GPU (optional, for faster inference)

### Step-by-Step Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd EPMSSTS
   ```

2. **Create virtual environment**
   ```bash
   conda create -n epmssts python=3.11
   conda activate epmssts
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize database** (if using PostgreSQL)
   ```bash
   psql -U postgres -f epmssts/services/database/schema.sql
   ```

6. **Run the application**
   ```bash
   uvicorn epmssts.api.main:app --reload
   ```

## 💻 Usage

### Web Interface (MVP Frontend)

1. Start the frontend:
   ```bash
   streamlit run frontend/app.py
   ```

2. Open http://localhost:8502 in your browser

3. Two modes available:
   - **File Upload**: Upload a WAV/MP3 audio file, select target language and emotion
   - **Live Recording**: Record audio directly in the browser and translate in real-time

4. View results including:
   - Original transcript
   - Detected emotion (with confidence) and dialect
   - Translated text
   - Output audio (if TTS available)
   - Detailed JSON results

5. Click "Download Audio" to get the translated speech

### API Usage

#### Health Check
```bash
curl http://localhost:8000/health
```

#### Speech-to-Text
```bash
curl -X POST "http://localhost:8000/stt/transcribe" \
  -F "file=@sample.wav"
```

#### Emotion Detection
```bash
curl -X POST "http://localhost:8000/emotion/detect" \
  -F "file=@sample.wav"
```

#### Translation
```bash
curl -X POST "http://localhost:8000/translate" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello world",
    "source_lang": "en",
    "target_lang": "hi"
  }'
```

#### End-to-End Speech Translation
```bash
curl -X POST "http://localhost:8000/process/speech-to-speech" \
  -F "file=@sample.wav" \
  -F "target_lang=hi" \
  -F "target_emotion=happy"
```

#### Emotion Analysis (Frontend Compatible)
```bash
curl -X POST "http://localhost:8000/emotion/analyze" \
  -F "file=@sample.wav"
```

## 📚 API Documentation

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with service status |
| `/stt/transcribe` | POST | Transcribe audio to text |
| `/emotion/detect` | POST | Detect emotion from audio (raw) |
| `/emotion/analyze` | POST | Analyze emotion from audio (frontend-compatible) |
| `/dialect/detect` | POST | Detect Telugu dialect |
| `/translate` | POST | Translate text |
| `/tts/synthesize` | POST | Synthesize speech with emotion |
| `/process/speech-to-speech` | POST | **Complete pipeline**: Audio → Transcript → Emotion → Dialect → Translation → Audio Output |
| `/translate/speech` | POST | End-to-end speech translation (legacy) |
| `/output/{session_id}.wav` | GET | Retrieve output audio file |

### Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🏗️ Architecture

```
┌─────────────────┐
│  Audio Input    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Preprocessing  │ (16kHz mono)
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────┐   ┌─────────┐
│ STT │   │ Emotion │ (Parallel)
└──┬──┘   └────┬────┘
   │           │
   └─────┬─────┘
         │
         ▼
   ┌──────────┐
   │ Dialect  │ (Telugu only)
   └─────┬────┘
         │
         ▼
   ┌──────────┐
   │Translation│ (Pure text)
   └─────┬────┘
         │
         ▼
   ┌──────────┐
   │   TTS    │ (Emotion-conditioned)
   └─────┬────┘
         │
         ▼
   ┌──────────┐
   │  Output  │
   └──────────┘
```

### Technology Stack

- **Backend**: FastAPI, Python 3.11+
- **STT**: faster-whisper (large-v3)
- **Emotion**: Wav2Vec2 (superb/wav2vec2-base-superb-er) + BERT for text emotion
- **Dialect**: Rule-based heuristics for Telugu (Telangana/Andhra detection)
- **Translation**: NLLB-200-distilled-600M (transformer-based, supports 200+ languages)
- **TTS**: Coqui TTS YourTTS (optional, emotion-conditioned prosody)
- **Audio Processing**: Librosa + SoundFile (16kHz mono normalization)
- **Database**: PostgreSQL 15 (optional, for session logging)
- **Cache**: Redis 7 (optional, for session management)
- **Frontend**: Streamlit with custom CSS styling
- **Deployment**: Docker, docker-compose

## 🧪 Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run Unit Tests Only
```bash
pytest tests/unit/ -v
```

### Run Integration Tests Only
```bash
pytest tests/integration/ -v
```

### Run with Coverage
```bash
pytest tests/ --cov=epmssts --cov-report=html
```

### Test Structure
```
tests/
├── unit/
│   ├── test_stt.py
│   ├── test_emotion.py
│   ├── test_dialect.py
│   ├── test_translation.py
│   └── test_tts.py
└── integration/
    └── test_api.py
```

## 🐳 Deployment

### Docker Deployment

1. **Build and start all services**
   ```bash
   docker-compose up -d
   ```

2. **View logs**
   ```bash
   docker-compose logs -f
   ```

3. **Stop services**
   ```bash
   docker-compose down
   ```

4. **Rebuild after code changes**
   ```bash
   docker-compose up -d --build
   ```

### Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed production deployment instructions.

## ⚙️ Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# API Settings
API_HOST=0.0.0.0
API_PORT=8000

# Database
DATABASE_URL=postgresql://epmssts:epmssts@localhost:5432/epmssts

# Redis
REDIS_URL=redis://localhost:6379

# Device (cuda/cpu)
# DEVICE=cuda

# Logging
LOG_LEVEL=INFO
```

See [`.env.example`](.env.example) for all available options.

## 📊 Performance

### Latency (CPU)
- STT: 3-5s
- Emotion: 1-2s
- Translation: 1-2s
- TTS: 2-4s
- **Total**: ~7-13s

### Latency (GPU)
- STT: 1-2s
- Emotion: 0.5-1s
- Translation: 0.5-1s
- TTS: 1-2s
- **Total**: ~3-6s

## 🎨 Supported Languages & Emotions

### Languages
- Telugu (te)
- Hindi (hi)
- English (en)

### Emotions
- neutral
- happy
- sad
- angry
- fearful

### Dialects (Telugu only)
- Telangana
- Andhra
- Standard Telugu

## 🔒 Security

- No authentication (MVP - add for production)
- File size limits enforced
- Input validation on all endpoints
- CORS configured for frontend
- SQL injection protection via parameterized queries

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- faster-whisper for STT
- Hugging Face Transformers for emotion and translation models
- Coqui TTS for speech synthesis
- FastAPI for the excellent web framework

## 📧 Contact

For questions or support, please open an issue on GitHub.

---

**Built with ❤️ for multilingual communication**
