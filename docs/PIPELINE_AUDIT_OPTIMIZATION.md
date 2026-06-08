# EPMSSTS Backend Pipeline Audit and Optimization

## Goals
- Maximum inference accuracy without changing model weights.
- Robust real-time performance with minimal error propagation.
- Modular scalability and stage isolation.
- Low-latency inference with clear observability.

## Final Backend Pipeline Architecture
```
Client Audio
  -> API Gateway (FastAPI)
    -> Audio Preprocessing (normalize, trim, noise gate, VAD)
      -> STT (faster-whisper)
      -> Emotion (audio) + Emotion (text) -> Fusion
      -> Dialect (rule-based, Telugu only)
      -> Translation (NLLB-200)
      -> TTS (Coqui / pyttsx3 / fallback)
    -> Outputs + Metrics
```

## Module Interaction Flow
1. Audio preprocessing
   - Decode, convert to 16kHz mono, remove DC offset, high-pass filter.
   - Silence trimming + noise gating.
   - VAD ratio check for near-silent audio.

2. STT + Audio Emotion (parallel)
   - STT and emotion inference run concurrently to reduce latency.
   - STT retries once with less aggressive preprocessing if transcript is empty.
   - Emotion confidence threshold triggers neutral fallback.

3. Text Emotion (optional)
   - Only for English; fused with audio emotion if confidence allows.

4. Dialect detection
   - Text-only heuristics; confidence check falls back to standard Telugu.

5. Translation
   - Pure text translation; retries once if output is empty.

6. TTS
   - Emotion-conditioned synthesis with tiered fallback.
   - Stage latency captured for observability.

## Optimization Strategy
- Parallel STT + audio emotion inference.
- Single model load at startup.
- Lightweight preprocessing (no heavy DSP dependencies).
- Stage timeouts with controlled retries.

## Failure Handling Strategy
- Invalid audio is rejected early in preprocessing.
- Silence or low VAD ratio short-circuits with neutral output and empty audio.
- Emotion confidence below threshold -> neutral fallback.
- Dialect confidence below threshold -> standard_telugu fallback.
- Translation output empty -> retry once, then continue with safe fallback.
- TTS failures fall back to alternate engines or synthetic tone.

## Accuracy Improvement Strategy
- Normalize audio amplitude to stabilize STT and emotion performance.
- High-pass filtering and noise gating reduce rumble and background hiss.
- Speech-only trimming focuses models on voice segments.
- Emotion fusion uses confidence thresholds to prevent misclassification.

## Real-Time Optimization Plan
- Maintain low-latency stages (<2s) with parallel execution.
- Use per-stage timeouts and coarse retries.
- Keep preprocessing deterministic and fast.

## Testing Strategy
- Unit tests per service (STT, emotion, dialect, translation, TTS).
- Integration tests for /translate/speech and /process/speech-to-speech.
- Concurrency stress tests with multiple simultaneous audio requests.
- Low-quality audio tests (noise, clipping, silence).
- Multilingual and emotional speech samples for regression.

## Observability
- Log input audio metrics (duration, RMS, peak, clipped ratio, speech ratio).
- Log per-stage latency to monitor performance and bottlenecks.
