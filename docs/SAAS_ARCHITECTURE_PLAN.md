# EPMSSTS SaaS Architecture Plan

## Overview
EPMSSTS is organized as a SaaS-ready platform with a clear separation between the frontend UI, API gateway, and ML service boundaries. This plan does not change model logic; it focuses on production structure, scaling readiness, and clean interfaces.

## Logical System Layers
1. Frontend (React + Tailwind)
   - SaaS shell, dashboards, live translation studio, history, analytics, settings.
   - Talks only to API gateway.

2. API Gateway (FastAPI)
   - Single ingress point for the UI.
   - Handles request validation, timeouts, logging, rate limits, and error shaping.

3. ML Services (Service boundaries)
   - STT Service: audio -> transcript + segments + detected language.
   - Emotion Service: audio + text -> emotion + confidence + scores.
   - Dialect Service: text -> dialect label.
   - Translation Service: text + source/target -> translated text.
   - TTS Service: text + emotion + language -> audio.

4. Storage Layer
   - Session metadata (timestamps, latency, language, emotion).
   - Output artifacts (translated audio, transcripts).
   - Metrics (per-stage timing, error rates, usage).

## API Gateway Endpoints
- GET /health
- POST /stt/transcribe
- POST /emotion/detect
- POST /dialect/detect
- POST /translate
- POST /tts/synthesize
- GET /session/{id}
- GET /session/list

## Request Flow
1. Audio upload or live recording.
2. /stt/transcribe -> transcript + segments + language.
3. /emotion/detect -> emotion + scores.
4. /dialect/detect -> dialect label.
5. /translate -> translated text.
6. /tts/synthesize -> audio output.
7. Persist session summary.

## Cross-Cutting Requirements
- Input validation
  - Audio MIME checks, size limits, language list validation.
- Silence detection and fallback
  - If silent, return structured error + optional retry hint.
- Timeouts and graceful failures
  - Per-stage timeouts, partial response handling.
- Error format
  - Consistent JSON error shape: { code, message, hint, trace_id }.

## Future SaaS Compatibility
- Auth readiness
  - Session-level auth tokens and user scoping.
- Multi-tenant usage
  - Namespace sessions by account_id.
- Usage metering
  - Track minutes processed and request counts.
- Monetization
  - Tiered limits per account with throttling in gateway.

## Deployment Notes
- Containerize services individually (STT, Emotion, Dialect, Translation, TTS).
- Keep API gateway stateless for horizontal scaling.
- Store artifacts in object storage (S3-compatible) when ready.

## UI Integration Notes
- Frontend should only call the API gateway and never direct model endpoints.
- Frontend expects JSON with consistent response shapes for progress UX.
