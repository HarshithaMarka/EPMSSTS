You are a senior AI systems engineer and backend ML engineer.

You are responsible for implementing a COMPLETE, working MVP of the following system:

PROJECT NAME:
EPMSSTS — Emotion-Preserving Multilingual Speech-to-Speech Translation System

GOAL:
Build an end-to-end speech-to-speech translation pipeline that:
- Transcribes speech
- Detects emotion from audio (primary) and text (optional)
- Tags dialect (metadata only)
- Translates text across languages
- Synthesizes speech with emotion-preserved prosody
- Runs locally on a single machine
- Exposes a REST API and a minimal UI

THIS IS NOT A TOY PROJECT.
Write production-quality, readable, maintainable code.

--------------------------------
SYSTEM CONSTRAINTS (STRICT)
--------------------------------
- Language: Python 3.10+
- Backend: FastAPI
- ML: Pre-trained models ONLY (no training)
- Deployment: Single-machine, Docker-ready
- GPU optional (must fallback to CPU)
- No real-time streaming (v2 feature)
- No SaaS features (auth, billing, users)
- No voice cloning (v2 feature)

--------------------------------
FINAL CORE PIPELINE (LOCKED)
--------------------------------
Audio Input
→ Audio Preprocessing (16kHz mono)
→ Speech-to-Text (language detection)
→ Emotion Detection (audio-first)
→ Dialect Detection (rule-based, metadata only)
→ Translation (PURE text, NO emotion injection)
→ Emotion-conditioned Text-to-Speech
→ Audio Output

Emotion affects ONLY TTS prosody.
Emotion must NOT affect translation text.

--------------------------------
MVP SCOPE (LOCKED)
--------------------------------
Languages:
- Telugu
- Hindi
- English

Emotions:
- neutral
- happy
- sad
- angry
- fearful

Dialect:
- Telugu only: Telangana vs Andhra (rule-based)
- All others: standard

--------------------------------
TECH STACK (MANDATORY)
--------------------------------
STT:
- faster-whisper (large-v3)

Emotion (audio):
- Wav2Vec2 SER model (superb/wav2vec2-base-superb-er)

Emotion (text):
- OPTIONAL
- Use ONLY if language == English
- Otherwise skip

Translation:
- facebook/nllb-200-distilled-600M

TTS:
- Coqui TTS (YourTTS or VITS)
- Emotion preserved via SPEED control ONLY (safe)

Backend:
- FastAPI

UI:
- Streamlit

Storage:
- PostgreSQL (logs)
- Redis (session cache)
- Local filesystem for audio outputs

--------------------------------
REPOSITORY STRUCTURE (MUST FOLLOW)
--------------------------------
epmssts/
├── api/
│   ├── main.py
│   └── pipeline.py
├── services/
│   ├── stt/
│   │   ├── audio_handler.py
│   │   └── transcriber.py
│   ├── emotion/
│   │   ├── audio_emotion.py
│   │   ├── text_emotion.py
│   │   └── fusion.py
│   ├── dialect/
│   │   └── classifier.py
│   ├── translation/
│   │   └── translator.py
│   └── tts/
│       └── synthesizer.py
├── frontend/
│   └── app.py
├── tests/
├── docker/
├── outputs/
├── requirements.txt
└── README.md

--------------------------------
IMPLEMENTATION RULES (VERY IMPORTANT)
--------------------------------
1. Implement the project PHASE BY PHASE
2. Each phase must compile and run before moving forward
3. Load ML models ONCE at startup
4. Add clear error handling
5. Keep code readable (no hacks)
6. No over-engineering
7. No new features beyond the plan

--------------------------------
PHASES TO IMPLEMENT (IN ORDER)
--------------------------------

PHASE 0: Environment & FastAPI Skeleton
- requirements.txt
- FastAPI app
- /health endpoint

PHASE 1: Speech-to-Text
- Audio preprocessing (16kHz mono)
- faster-whisper STT
- Language detection
- POST /stt/transcribe endpoint

PHASE 2: Emotion Detection
- Audio-based emotion detection (primary)
- Text-based emotion ONLY for English
- Emotion fusion with confidence thresholds
- POST /emotion/detect endpoint

PHASE 3: Dialect Detection
- Rule-based Telugu dialect tagging
- Metadata only (no translation impact)
- POST /dialect/detect endpoint

PHASE 4: Translation
- Pure text translation
- NO emotion injection
- Telugu ↔ Hindi ↔ English
- POST /translate endpoint

PHASE 5: Emotion-Conditioned TTS
- Coqui TTS
- Emotion preserved via SPEED control only
- POST /tts/synthesize endpoint

PHASE 6: End-to-End Orchestration
- POST /translate/speech
- Chain all modules
- Log results
- Save output audio
- Return audio URL

PHASE 7: Frontend
- Streamlit UI
- Upload audio
- Show transcript, emotion, dialect
- Play output audio

PHASE 8: Testing
- Unit tests (STT, emotion)
- Integration test (full pipeline)
- Latency checks

PHASE 9: Deployment Readiness
- Docker-ready structure
- README with setup + usage

--------------------------------
SAFE PROSODY RULES (MANDATORY)
--------------------------------
Use ONLY speed control:

happy   → 1.05
sad     → 0.92
angry   → 1.10
neutral → 1.00

Pitch shifting is OPTIONAL and must be extremely subtle if used.

--------------------------------
ERROR HANDLING
--------------------------------
- Invalid audio → HTTP 400
- Silence → neutral emotion
- Model failure → graceful error
- Timeout >10s → abort request

--------------------------------
OUTPUT EXPECTATION
--------------------------------
At the end, the system must:
- Run locally
- Accept speech input
- Return translated speech
- Preserve emotion audibly
- Be demo-ready
- Be interview-ready

--------------------------------
CRITICAL INSTRUCTION
--------------------------------
DO NOT redesign the architecture.
DO NOT add SaaS features.
DO NOT add streaming.
DO NOT train models.

Follow the plan strictly.
Implement clean, professional code.

Start with PHASE 0 and proceed sequentially.
