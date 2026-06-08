"""Distributed-aware circuit breaker for stage isolation."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum

from .state_store import OrchestrationStateStore


logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitConfig:
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 30
    half_open_max_calls: int = 2


class CircuitBreakerManager:
    def __init__(self, state_store: OrchestrationStateStore, config: CircuitConfig | None = None):
        self.state_store = state_store
        self.config = config or CircuitConfig()

    async def allow_request(self, stage: str) -> bool:
        state = await self._get_state(stage)
        if state == CircuitState.CLOSED.value:
            return True

        if state == CircuitState.OPEN.value:
            open_until = await self.state_store.get_int(self._open_until_key(stage), default=0)
            now = int(time.time())
            if now >= open_until:
                await self._set_state(stage, CircuitState.HALF_OPEN.value)
                await self.state_store.set_json(self._half_open_calls_key(stage), {"value": 0})
                return True
            return False

        # half-open path
        calls = await self.state_store.get_int(self._half_open_calls_key(stage), default=0)
        if calls >= self.config.half_open_max_calls:
            return False
        await self.state_store.incr(self._half_open_calls_key(stage), ttl=self.config.recovery_timeout_seconds)
        return True

    async def record_success(self, stage: str):
        await self._set_state(stage, CircuitState.CLOSED.value)
        await self.state_store.set_json(self._failure_count_key(stage), {"value": 0})

    async def record_failure(self, stage: str):
        failures = await self.state_store.incr(
            self._failure_count_key(stage), ttl=self.config.recovery_timeout_seconds * 10
        )
        state = await self._get_state(stage)

        if state == CircuitState.HALF_OPEN.value:
            await self._trip(stage)
            return

        if failures >= self.config.failure_threshold:
            await self._trip(stage)

    async def get_states(self) -> dict[str, str]:
        states: dict[str, str] = {}
        for stage in ["audio_preprocessing", "stt", "emotion", "translation", "tts"]:
            states[stage] = await self._get_state(stage)
        return states

    async def _trip(self, stage: str):
        logger.warning("Circuit opened for stage=%s", stage)
        await self._set_state(stage, CircuitState.OPEN.value)
        await self.state_store.set_json(
            self._open_until_key(stage),
            {"value": int(time.time()) + self.config.recovery_timeout_seconds},
            ttl=self.config.recovery_timeout_seconds * 2,
        )

    async def _set_state(self, stage: str, state: str):
        await self.state_store.set_json(self._state_key(stage), {"value": state}, ttl=24 * 3600)

    async def _get_state(self, stage: str) -> str:
        data = await self.state_store.get_json(self._state_key(stage))
        if not data:
            return CircuitState.CLOSED.value
        return str(data.get("value", CircuitState.CLOSED.value))

    @staticmethod
    def _state_key(stage: str) -> str:
        return f"orchestrator:circuit:{stage}:state"

    @staticmethod
    def _failure_count_key(stage: str) -> str:
        return f"orchestrator:circuit:{stage}:failures"

    @staticmethod
    def _open_until_key(stage: str) -> str:
        return f"orchestrator:circuit:{stage}:open_until"

    @staticmethod
    def _half_open_calls_key(stage: str) -> str:
        return f"orchestrator:circuit:{stage}:half_open_calls"
