# EPMSSTS - Quick Reference Guide

## 🚀 Start System (5 minutes)

### Option 1: Local Development
```bash
# Terminal 1: Backend
cd c:\vivek\project_final_year\Epmssts\EPMSSTS
conda activate epmssts
uvicorn epmssts.api.main:app --reload

# Terminal 2: Frontend
cd c:\vivek\project_final_year\Epmssts\EPMSSTS
conda activate epmssts
streamlit run frontend/app.py
```

**Access:**
- Frontend: http://localhost:8501
- API Docs: http://localhost:8000/docs

### Option 2: Docker (Recommended for Production)
```bash
cd c:\vivek\project_final_year\Epmssts\EPMSSTS
docker-compose up -d
```

**Access:**
- Frontend: http://localhost:8501
- API: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

---

## 📡 API Quick Reference

### Health Check
```bash
curl http://localhost:8000/health
```

### Transcribe Audio
```bash
curl -X POST "http://localhost:8000/stt/transcribe" \
  -F "file=@audio.wav"
```

### Detect Emotion
```bash
curl -X POST "http://localhost:8000/emotion/detect" \
  -F "file=@audio.wav"
```

### Translate Text
```bash
curl -X POST "http://localhost:8000/translate" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello",
    "source_lang": "en",
    "target_lang": "hi"
  }'
```

### Complete Pipeline (Audio → Transcript → Emotion → Translation → Audio)
```bash
curl -X POST "http://localhost:8000/process/speech-to-speech" \
  -F "file=@audio.wav" \
  -F "target_lang=hi" \
  -F "target_emotion=happy"
```

---

## 🧪 Testing Quick Reference

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test Suite
```bash
pytest tests/integration/test_api_comprehensive.py -v
```

### Run End-to-End Test
```bash
python test_complete_flow.py
```

### Run with Coverage
```bash
pytest tests/ --cov=epmssts --cov-report=html
# Open htmlcov/index.html in browser
```

### Run Specific Test Class
```bash
pytest tests/integration/test_api_comprehensive.py::TestTranslationEndpoints -v
```

---

## 📁 Project Structure

```
EPMSSTS/
├── epmssts/                          # Main package
│   ├── api/                          # FastAPI application
│   │   └── main.py                   # 10 endpoints
│   └── services/                     # Microservices
│       ├── stt/                      # Speech-to-text
│       ├── emotion/                  # Emotion detection
│       ├── dialect/                  # Dialect classifier
│       ├── translation/              # Translation service
│       ├── tts/                      # Text-to-speech
│       ├── cache/                    # Redis
│       └── database/                 # PostgreSQL
├── frontend/                         # Streamlit UI
│   └── app.py                        # Frontend application
├── tests/                            # Test suites
│   ├── unit/                         # Unit tests
│   └── integration/                  # Integration tests
├── Dockerfile                        # Container image
├── docker-compose.yml                # Multi-service setup
├── requirements.txt                  # Dependencies
└── README.md                         # Documentation
```

---

## 🔑 Key Files

| File | Purpose |
|------|---------|
| `epmssts/api/main.py` | All 10 API endpoints |
| `frontend/app.py` | Beautiful Streamlit UI |
| `test_complete_flow.py` | End-to-end test |
| `TESTING_GUIDE.md` | Testing documentation |
| `README.md` | Project overview |
| `COMPLETION_SUMMARY.md` | Final status report |

---

## ⚙️ Configuration

### Environment Variables
Create `.env` file (copy from `.env.example`):
```bash
API_HOST=0.0.0.0
API_PORT=8000
DATABASE_URL=postgresql://user:pass@localhost:5432/epmssts
REDIS_URL=redis://localhost:6379
DEVICE=cpu  # or 'cuda' for GPU
```

### Python Version
- **Recommended**: Python 3.11
- **Also Works**: Python 3.10, 3.12
- **Note**: Python 3.13 works but TTS unavailable

---

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Find process on port 8000
netstat -ano | findstr ":8000"

# Kill process
taskkill /PID <PID> /F
```

### Models Not Loading
```bash
# Clear cache and retry
rm -rf ~/.cache/huggingface

# Check disk space (models are ~2-3GB)
df -h
```

### Memory Issues
```bash
# Limit memory in docker-compose.yml
# Or increase available RAM

# Run tests sequentially instead of parallel
pytest tests/ -p no:xdist
```

### Backend Connection Refused
```bash
# Check if backend is running
curl http://localhost:8000/health

# Restart backend
# Kill existing process and start fresh
```

---

## 📊 System Status

### Check Health
```bash
curl http://localhost:8000/health | python -m json.tool
```

Expected output:
```json
{
  "status": "ok",
  "stt_available": true,
  "emotion_available": true,
  "dialect_available": true,
  "translation_available": true,
  "tts_available": false
}
```

### Check Logs
```bash
# Backend logs
tail -f backend.log

# Frontend logs
# Check Streamlit console output
```

---

## 🎯 Common Tasks

### Test a Specific Feature
```bash
# Test translation
pytest tests/integration/test_api_comprehensive.py::TestTranslationEndpoints -v

# Test emotion detection
pytest tests/integration/test_api_comprehensive.py::TestEmotionEndpoints -v
```

### Add a New Test
1. Create test file in `tests/unit/` or `tests/integration/`
2. Use existing fixtures
3. Run: `pytest tests/your_test.py -v`

### Check Test Coverage
```bash
pytest tests/ --cov=epmssts --cov-report=html
# Open htmlcov/index.html
```

### Deploy to Docker
```bash
docker-compose up -d
docker-compose logs -f  # View logs
```

### Stop Services
```bash
# Ctrl+C in terminal, or
docker-compose down
```

---

## 📈 Performance Tips

### Speed Up on CPU
```bash
# Use smaller models or quantize
# In config: WHISPER_MODEL_SIZE=small
```

### Use GPU
```bash
# Install CUDA, then in .env:
DEVICE=cuda
```

### Optimize Models
```bash
# Enable caching (Redis)
# Models cached after first load
```

---

## 📚 Documentation Map

- **README.md** - Start here! Overview and features
- **MVP_SETUP_GUIDE.md** - Detailed setup steps
- **TESTING_GUIDE.md** - How to run tests
- **DEPLOYMENT.md** - Production deployment
- **COMPLETION_SUMMARY.md** - Project status
- **SYSTEM_STATUS.md** - Current runtime status
- **API Docs** - http://localhost:8000/docs (Swagger)

---

## ✨ Feature Matrix

| Feature | Status | Notes |
|---------|--------|-------|
| Speech-to-Text | ✅ | faster-whisper |
| Emotion Detection | ✅ | Wav2Vec2 + BERT |
| Dialect Classification | ✅ | Telugu only |
| Text Translation | ✅ | 200+ languages |
| Text-to-Speech | ⚠️ | Not in Python 3.13 |
| Web UI | ✅ | Streamlit |
| REST API | ✅ | 10 endpoints |
| Database | ✅ | PostgreSQL |
| Caching | ✅ | Redis |
| Docker | ✅ | Production ready |
| Tests | ✅ | 50+ test cases |

---

## 🚨 Important Notes

1. **First Run**: Models download on first run (~2-3GB), then cached
2. **Python 3.13**: TTS unavailable, system works with graceful fallback
3. **GPU Support**: Requires CUDA, automatically detected
4. **Database**: Optional, system works without it
5. **Security**: Add authentication for production use

---

## 🎓 Learning Resources

- **FastAPI**: https://fastapi.tiangolo.com/
- **Streamlit**: https://streamlit.io/
- **Hugging Face**: https://huggingface.co/
- **Docker**: https://www.docker.com/

---

## 💬 Support

For issues or questions:
1. Check TESTING_GUIDE.md
2. Review COMPLETION_SUMMARY.md
3. Check API docs at http://localhost:8000/docs
4. Review service logs

---

**Last Updated**: January 29, 2026  
**Status**: ✅ Production Ready  
**Version**: 1.0.0-final
