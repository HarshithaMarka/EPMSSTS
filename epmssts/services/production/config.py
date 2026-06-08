from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProductionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    env_name: str = "development"
    enforce_production_validation: bool = False

    stream_chunk_seconds_min: float = 1.0
    stream_chunk_seconds_max: float = 2.0
    stream_max_latency_seconds: float = 2.0
    stream_queue_size: int = 32
    stream_session_ttl_seconds: int = 1800

    auth_enabled: bool = False
    jwt_required: bool = False
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    api_keys_csv: str = ""
    replay_ttl_seconds: int = 300

    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    max_request_size_bytes: int = 12_000_000
    max_audio_duration_seconds: float = 30.0

    drift_window_size: int = 200
    drift_baseline_size: int = 200
    drift_kl_threshold: float = 0.25
    drift_psi_threshold: float = 0.20

    calibration_temperature: float = 1.0
    calibration_artifact_path: str = "artifacts/calibration/temperature_scaling.json"
    calibration_recompute_days: int = 30


class ConfigValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


def validate_production_config(settings: ProductionSettings) -> ConfigValidationResult:
    errors: list[str] = []

    if settings.stream_chunk_seconds_min <= 0:
        errors.append("stream_chunk_seconds_min must be > 0")
    if settings.stream_chunk_seconds_max < settings.stream_chunk_seconds_min:
        errors.append("stream_chunk_seconds_max must be >= stream_chunk_seconds_min")
    if settings.stream_max_latency_seconds > 2.0:
        errors.append("stream_max_latency_seconds must be <= 2.0")
    if settings.stream_queue_size < 4:
        errors.append("stream_queue_size must be >= 4")

    if settings.rate_limit_requests <= 0:
        errors.append("rate_limit_requests must be > 0")
    if settings.rate_limit_window_seconds <= 0:
        errors.append("rate_limit_window_seconds must be > 0")

    if settings.max_request_size_bytes <= 0:
        errors.append("max_request_size_bytes must be > 0")
    if settings.max_audio_duration_seconds <= 0:
        errors.append("max_audio_duration_seconds must be > 0")

    if settings.auth_enabled and settings.jwt_required and settings.jwt_secret == "change-me-in-prod":
        errors.append("jwt_secret must be changed when jwt_required is enabled")

    if settings.calibration_temperature <= 0:
        errors.append("calibration_temperature must be > 0")

    if settings.enforce_production_validation and settings.env_name.lower() == "production":
        if not settings.auth_enabled:
            errors.append("auth_enabled must be true in enforced production mode")

    return ConfigValidationResult(valid=len(errors) == 0, errors=errors)
