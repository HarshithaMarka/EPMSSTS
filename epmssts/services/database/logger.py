"""
Database service for logging translation sessions.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Optional
from uuid import UUID

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from epmssts.config import settings


@dataclass
class TranslationLog:
    """Translation session log entry."""
    
    session_id: UUID
    source_lang: str
    target_lang: str
    detected_language: Optional[str] = None
    detected_emotion: Optional[str] = None
    detected_dialect: Optional[str] = None
    emotion_confidence: Optional[float] = None
    dialect_confidence: Optional[float] = None
    transcript: Optional[str] = None
    translated_text: Optional[str] = None
    latency_ms: Optional[int] = None
    latency_stt_ms: Optional[int] = None
    latency_emotion_ms: Optional[int] = None
    latency_translation_ms: Optional[int] = None
    latency_tts_ms: Optional[int] = None
    audio_duration_seconds: Optional[float] = None
    status: str = "success"
    error_message: Optional[str] = None


class DatabaseService:
    """PostgreSQL database service for logging."""
    
    def __init__(self, database_url: Optional[str] = None) -> None:
        """
        Initialize database connection pool.
        
        Args:
            database_url: PostgreSQL connection URL. If None, uses settings.
        """
        self._url = database_url or settings.database_url
        self._pool: Optional[pool.SimpleConnectionPool] = None
        
    def connect(self) -> None:
        """Initialize connection pool."""
        try:
            self._pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=settings.database_pool_size,
                dsn=self._url,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to connect to database: {exc}") from exc
    
    def disconnect(self) -> None:
        """Close all connections."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
    
    @asynccontextmanager
    async def _get_connection(self) -> AsyncIterator[psycopg2.extensions.connection]:
        """Get a connection from the pool."""
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)
    
    async def log_translation(self, log: TranslationLog) -> None:
        """
        Log a translation session to the database.
        
        Args:
            log: Translation log entry.
        """
        query = """
        INSERT INTO translation_logs (
            session_id, source_lang, target_lang,
            detected_language, detected_emotion, detected_dialect,
            emotion_confidence, dialect_confidence,
            transcript, translated_text,
            latency_ms, latency_stt_ms, latency_emotion_ms,
            latency_translation_ms, latency_tts_ms,
            audio_duration_seconds, status, error_message
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        """
        
        values = (
            str(log.session_id),
            log.source_lang,
            log.target_lang,
            log.detected_language,
            log.detected_emotion,
            log.detected_dialect,
            log.emotion_confidence,
            log.dialect_confidence,
            log.transcript,
            log.translated_text,
            log.latency_ms,
            log.latency_stt_ms,
            log.latency_emotion_ms,
            log.latency_translation_ms,
            log.latency_tts_ms,
            log.audio_duration_seconds,
            log.status,
            log.error_message,
        )
        
        async with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, values)
                conn.commit()
    
    async def get_translation_by_session_id(
        self, session_id: UUID
    ) -> Optional[dict]:
        """
        Retrieve a translation log by session ID.
        
        Args:
            session_id: Session UUID.
            
        Returns:
            Dictionary with log data, or None if not found.
        """
        query = """
        SELECT * FROM translation_logs
        WHERE session_id = %s
        """
        
        async with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (str(session_id),))
                result = cursor.fetchone()
                return dict(result) if result else None
    
    async def get_recent_translations(
        self, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        """
        Get recent translation logs.
        
        Args:
            limit: Maximum number of records.
            offset: Number of records to skip.
            
        Returns:
            List of translation log dictionaries.
        """
        query = """
        SELECT * FROM translation_logs
        ORDER BY timestamp DESC
        LIMIT %s OFFSET %s
        """
        
        async with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (limit, offset))
                results = cursor.fetchall()
                return [dict(row) for row in results]
    
    async def get_statistics(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> dict:
        """
        Get translation statistics.
        
        Args:
            start_date: Start date filter (optional).
            end_date: End date filter (optional).
            
        Returns:
            Dictionary with statistics.
        """
        query = """
        SELECT 
            COUNT(*) as total_requests,
            COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_requests,
            COUNT(CASE WHEN status = 'error' THEN 1 END) as failed_requests,
            AVG(latency_ms) as avg_latency_ms,
            MAX(latency_ms) as max_latency_ms,
            MIN(latency_ms) as min_latency_ms
        FROM translation_logs
        WHERE 1=1
        """
        
        params = []
        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        
        async with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()
                return dict(result) if result else {}


__all__ = ["DatabaseService", "TranslationLog"]
