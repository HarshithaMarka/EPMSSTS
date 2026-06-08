"""
Configuration management for EPMSSTS using Pydantic Settings.
"""

from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore',  # Allow extra environment variables without validation errors
    )
    
    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False
    
    # Model Settings
    whisper_model: str = "large-v3"
    emotion_model: str = "superb/wav2vec2-base-superb-er"
    translation_model: str = "facebook/nllb-200-distilled-600M"
    tts_model: str = "tts_models/multilingual/multi-dataset/your_tts"
    
    # Device Settings
    device: Optional[str] = None  # None = auto-detect, "cuda", "cpu"
    
    # Timeout Settings (seconds)
    timeout_stt: int = 10
    timeout_emotion: int = 10
    timeout_translation: int = 10
    timeout_tts: int = 10
    timeout_pipeline: int = 15
    
    # File Upload Settings
    max_file_size_mb: int = 10
    allowed_audio_types: list[str] = ["audio/wav", "audio/mpeg", "audio/mp3", "audio/flac"]
    
    # Database Settings
    database_url: str = "postgresql://epmssts:epmssts@localhost:5432/epmssts"
    database_pool_size: int = 5
    database_max_overflow: int = 10
    
    # Redis Settings
    redis_url: str = "redis://localhost:6379"
    redis_ttl_seconds: int = 3600  # 1 hour
    
    # Storage Settings
    outputs_dir: str = "outputs"
    outputs_retention_hours: int = 24
    
    # Logging Settings
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: str = "json"  # "json" or "text"
    
    # CORS Settings
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]
    
    # Rate Limiting
    rate_limit_enabled: bool = False
    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60


# Global settings instance
settings = Settings()


__all__ = ["settings", "Settings"]
