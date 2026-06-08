"""Security guards for orchestration endpoints."""

from __future__ import annotations

import os
import time
from typing import Optional

from fastapi import Header, HTTPException, Request, status

from .state_store import OrchestrationStateStore


MAX_AUDIO_PAYLOAD_BYTES = 12_000_000


def enforce_request_id(request_id: Optional[str]):
    if not request_id or len(request_id.strip()) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="request_id is required and must be at least 8 characters",
        )


def enforce_payload_size(audio_file_b64: str):
    if len(audio_file_b64.encode("utf-8")) > MAX_AUDIO_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="audio_file payload exceeded allowed size",
        )


async def validate_jwt_token(authorization: Optional[str] = Header(default=None)):
    if os.getenv("EPMSSTS_ORCH_AUTH_ENABLED", "true").lower() != "true":
        return

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    secret = os.getenv("EPMSSTS_ORCH_JWT_SECRET", "change-me")
    algorithm = os.getenv("EPMSSTS_ORCH_JWT_ALGO", "HS256")

    try:
        import jwt  # type: ignore
    except Exception:
        if os.getenv("EPMSSTS_ORCH_ALLOW_AUTH_FALLBACK", "false").lower() != "true":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="JWT validator dependency unavailable",
            )
        return

    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        exp = payload.get("exp")
        if exp is not None and int(exp) < int(time.time()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT token")


class RedisRateLimiter:
    def __init__(
        self,
        state_store: OrchestrationStateStore,
        requests: int = 20,
        window_seconds: int = 60,
    ):
        self.state_store = state_store
        self.requests = requests
        self.window_seconds = window_seconds

    async def enforce(self, request: Request):
        client_ip = request.client.host if request.client else "unknown"
        bucket = int(time.time() // self.window_seconds)
        key = f"orchestrator:ratelimit:{client_ip}:{bucket}"

        current = await self.state_store.incr(key, ttl=self.window_seconds + 2)
        if current > self.requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
