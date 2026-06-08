from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional
import time


@dataclass
class SessionContext:
    session_id: str
    emotion_ema: Dict[str, float] = field(default_factory=dict)
    speaker_states: Dict[str, Dict[str, float]] = field(default_factory=dict)
    dialect_persistent: Optional[str] = None
    last_updated_ts: float = field(default_factory=time.time)


class SessionMemoryEngine:
    def __init__(self, emotion_alpha: float = 0.35, dialect_persist_threshold: int = 3) -> None:
        self._sessions: Dict[str, SessionContext] = {}
        self.emotion_alpha = emotion_alpha
        self.dialect_persist_threshold = dialect_persist_threshold
        self._dialect_votes: Dict[str, Dict[str, int]] = {}

    def get_or_create(self, session_id: str) -> SessionContext:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionContext(session_id=session_id)
            self._dialect_votes[session_id] = {}
        return self._sessions[session_id]

    def update_emotion(self, session_id: str, emotion_scores: Dict[str, float]) -> Dict[str, float]:
        context = self.get_or_create(session_id)
        if not context.emotion_ema:
            context.emotion_ema = dict(emotion_scores)
        else:
            all_keys = set(context.emotion_ema.keys()) | set(emotion_scores.keys())
            updated: Dict[str, float] = {}
            for key in all_keys:
                prev = context.emotion_ema.get(key, 0.0)
                cur = emotion_scores.get(key, 0.0)
                updated[key] = self.emotion_alpha * cur + (1.0 - self.emotion_alpha) * prev
            context.emotion_ema = updated
        context.last_updated_ts = time.time()
        return context.emotion_ema

    def dominant_emotion(self, session_id: str) -> str:
        context = self.get_or_create(session_id)
        if not context.emotion_ema:
            return "neutral"
        return max(context.emotion_ema.items(), key=lambda item: item[1])[0]

    def update_speaker_state(self, session_id: str, speaker_id: str, embedding_norm: float) -> None:
        context = self.get_or_create(session_id)
        context.speaker_states[speaker_id] = {
            "embedding_norm": embedding_norm,
            "updated_at": time.time(),
        }
        context.last_updated_ts = time.time()

    def update_dialect(self, session_id: str, predicted_dialect: str) -> str:
        context = self.get_or_create(session_id)
        votes = self._dialect_votes[session_id]
        votes[predicted_dialect] = votes.get(predicted_dialect, 0) + 1

        top_label, top_count = max(votes.items(), key=lambda item: item[1])
        if top_count >= self.dialect_persist_threshold:
            context.dialect_persistent = top_label
        context.last_updated_ts = time.time()

        return context.dialect_persistent or predicted_dialect

    def get_context(self, session_id: str) -> SessionContext:
        return self.get_or_create(session_id)

    def cleanup_expired(self, ttl_seconds: int) -> int:
        now = time.time()
        expired = [sid for sid, ctx in self._sessions.items() if now - ctx.last_updated_ts > ttl_seconds]
        for sid in expired:
            self._sessions.pop(sid, None)
            self._dialect_votes.pop(sid, None)
        return len(expired)
