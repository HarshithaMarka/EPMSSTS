from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Callable, Optional
import asyncio
import time

from fastapi import HTTPException, Request, WebSocket, status

from .config import ProductionSettings


@dataclass
class SecurityError(Exception):
    code: str
    message: str
    status_code: int

    def as_http(self) -> HTTPException:
        return HTTPException(
            status_code=self.status_code,
            detail={"error": self.code, "message": self.message},
        )


def structured_error(code: str, message: str) -> dict:
    return {"status": "error", "error": code, "message": message}


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, tuple[int, int]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now_bucket = int(time.time() // self.window_seconds)
        async with self._lock:
            count, bucket = self._buckets.get(key, (0, now_bucket))
            if bucket != now_bucket:
                count = 0
                bucket = now_bucket
            count += 1
            self._buckets[key] = (count, bucket)
            return count <= self.max_requests


class ReplayProtector:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self._seen: dict[str, float] = {}

    def check_and_mark(self, token: str) -> bool:
        now = time.time()
        expired = [k for k, ts in self._seen.items() if now - ts > self.ttl_seconds]
        for key in expired:
            self._seen.pop(key, None)

        if token in self._seen:
            return False
        self._seen[token] = now
        return True


class SecurityRuntime:
    def __init__(self, settings: ProductionSettings) -> None:
        self.settings = settings
        self.rate_limiter = InMemoryRateLimiter(
            max_requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )
        self.replay_protector = ReplayProtector(ttl_seconds=settings.replay_ttl_seconds)
        self.allowed_api_keys = {
            part.strip() for part in settings.api_keys_csv.split(",") if part.strip()
        }

    async def validate_http(self, request: Request) -> None:
        if not self.settings.auth_enabled:
            return

        client_id = request.headers.get("x-client-id") or (request.client.host if request.client else "unknown")
        if not await self.rate_limiter.allow(client_id):
            raise SecurityError("rate_limited", "Rate limit exceeded", status.HTTP_429_TOO_MANY_REQUESTS)

        self._validate_api_key(request.headers.get("x-api-key"))
        self._validate_jwt(request.headers.get("authorization"))
        self._validate_replay(request.headers.get("x-replay-token"))

    async def validate_websocket(self, websocket: WebSocket) -> None:
        if not self.settings.auth_enabled:
            return

        client_id = websocket.headers.get("x-client-id") or (websocket.client.host if websocket.client else "unknown")
        if not await self.rate_limiter.allow(client_id):
            raise SecurityError("rate_limited", "Rate limit exceeded", status.HTTP_429_TOO_MANY_REQUESTS)

        self._validate_api_key(websocket.headers.get("x-api-key"))
        self._validate_jwt(websocket.headers.get("authorization"))
        self._validate_replay(websocket.headers.get("x-replay-token"))

    def validate_request_size(self, size_bytes: int) -> None:
        if size_bytes > self.settings.max_request_size_bytes:
            raise SecurityError("request_too_large", "Request size limit exceeded", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

    def validate_audio_duration(self, duration_seconds: float) -> None:
        if duration_seconds > self.settings.max_audio_duration_seconds:
            raise SecurityError("audio_too_long", "Audio duration limit exceeded", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

    def _validate_api_key(self, api_key: Optional[str]) -> None:
        if not self.allowed_api_keys:
            return
        if api_key is None or api_key not in self.allowed_api_keys:
            raise SecurityError("invalid_api_key", "Invalid or missing API key", status.HTTP_401_UNAUTHORIZED)

    def _validate_jwt(self, auth_header: Optional[str]) -> None:
        if not self.settings.jwt_required:
            return
        if auth_header is None or not auth_header.startswith("Bearer "):
            raise SecurityError("invalid_jwt", "Missing bearer token", status.HTTP_401_UNAUTHORIZED)

        token = auth_header.split(" ", 1)[1].strip()
        try:
            import jwt  # type: ignore

            jwt.decode(token, self.settings.jwt_secret, algorithms=[self.settings.jwt_algorithm])
        except SecurityError:
            raise
        except Exception as exc:
            raise SecurityError("invalid_jwt", f"JWT validation failed: {exc}", status.HTTP_401_UNAUTHORIZED)

    def _validate_replay(self, replay_token: Optional[str]) -> None:
        if not replay_token:
            return
        if not self.replay_protector.check_and_mark(replay_token):
            raise SecurityError("replay_detected", "Replay attack detected", status.HTTP_409_CONFLICT)


def rate_limit(max_requests: int = 100, window_seconds: int = 60):
    limiter = InMemoryRateLimiter(max_requests=max_requests, window_seconds=window_seconds)

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            if request is None:
                return await func(*args, **kwargs)

            client_id = request.headers.get("x-client-id") or (request.client.host if request.client else "unknown")
            allowed = await limiter.allow(client_id)
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=structured_error("rate_limited", "Rate limit exceeded"),
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator
