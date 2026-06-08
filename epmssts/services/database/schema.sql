-- EPMSSTS Database Schema
-- PostgreSQL 15+

-- Create database (run as superuser)
-- CREATE DATABASE epmssts;
-- CREATE USER epmssts WITH PASSWORD 'epmssts';
-- GRANT ALL PRIVILEGES ON DATABASE epmssts TO epmssts;

-- Translation logs table
CREATE TABLE IF NOT EXISTS translation_logs (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL UNIQUE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Input metadata
    source_lang VARCHAR(2) NOT NULL,
    target_lang VARCHAR(2) NOT NULL,
    audio_duration_seconds FLOAT,
    
    -- Detection results
    detected_language VARCHAR(2),
    detected_emotion VARCHAR(20),
    detected_dialect VARCHAR(50),
    emotion_confidence FLOAT,
    dialect_confidence FLOAT,
    
    -- Translation data
    transcript TEXT,
    translated_text TEXT,
    
    -- Performance metrics
    latency_ms INTEGER,
    latency_stt_ms INTEGER,
    latency_emotion_ms INTEGER,
    latency_translation_ms INTEGER,
    latency_tts_ms INTEGER,
    
    -- Status
    status VARCHAR(20) DEFAULT 'success',  -- success, error, timeout
    error_message TEXT,
    
    -- Indexing
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_translation_logs_timestamp ON translation_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_translation_logs_session_id ON translation_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_translation_logs_source_lang ON translation_logs(source_lang);
CREATE INDEX IF NOT EXISTS idx_translation_logs_target_lang ON translation_logs(target_lang);
CREATE INDEX IF NOT EXISTS idx_translation_logs_status ON translation_logs(status);
CREATE INDEX IF NOT EXISTS idx_translation_logs_created_at ON translation_logs(created_at DESC);

-- Performance statistics view
CREATE OR REPLACE VIEW translation_stats AS
SELECT 
    DATE(timestamp) as date,
    source_lang,
    target_lang,
    detected_emotion,
    COUNT(*) as total_requests,
    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_requests,
    COUNT(CASE WHEN status = 'error' THEN 1 END) as failed_requests,
    AVG(latency_ms) as avg_latency_ms,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY latency_ms) as median_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency_ms,
    MAX(latency_ms) as max_latency_ms
FROM translation_logs
GROUP BY DATE(timestamp), source_lang, target_lang, detected_emotion;

-- Grant permissions
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO epmssts;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO epmssts;
