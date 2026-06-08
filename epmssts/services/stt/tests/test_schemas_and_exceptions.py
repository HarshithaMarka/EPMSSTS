"""
Tests for STT Schemas and Exceptions

Tests request/response validation and exception handling.
"""

import pytest
from ..schemas import (
    SttRequest,
    SttResponse,
    TranscriptionSegment,
    AudioFormat,
    LanguageCode,
)
from ..exceptions import (
    SttServiceException,
    ModelNotInitializedError,
    NoSpeechDetectedError,
    ConfidenceTooLowError,
    AudioTooShortError,
    AudioTooLongError,
    InferenceTimeoutError,
)
import base64


class TestSttRequestSchema:
    """Tests for SttRequest validation"""
    
    def test_minimal_valid_request(self):
        """Test creating request with minimal fields"""
        audio_data = base64.b64encode(b"test audio").decode()
        request = SttRequest(audio_data=audio_data)
        
        assert request.audio_data == audio_data
        assert request.format == AudioFormat.WAV
        assert request.confidence_threshold == 0.5
    
    def test_request_with_all_fields(self):
        """Test request with all optional fields"""
        audio_data = base64.b64encode(b"test").decode()
        request = SttRequest(
            audio_data=audio_data,
            format=AudioFormat.MP3,
            language=LanguageCode.EN,
            confidence_threshold=0.7,
            no_speech_threshold=0.2,
            request_id="test-123",
            max_duration_seconds=300.0,
        )
        
        assert request.format == AudioFormat.MP3
        assert request.language == LanguageCode.EN
        assert request.confidence_threshold == 0.7
        assert request.request_id == "test-123"
    
    def test_invalid_threshold_too_high(self):
        """Test validation rejects threshold > 1.0"""
        audio_data = base64.b64encode(b"test").decode()
        
        with pytest.raises(ValueError):
            SttRequest(
                audio_data=audio_data,
                confidence_threshold=1.5,
            )
    
    def test_invalid_threshold_negative(self):
        """Test validation rejects negative threshold"""
        audio_data = base64.b64encode(b"test").decode()
        
        with pytest.raises(ValueError):
            SttRequest(
                audio_data=audio_data,
                confidence_threshold=-0.1,
            )
    
    def test_empty_audio_data_fails(self):
        """Test validation fails for empty audio"""
        with pytest.raises(ValueError):
            SttRequest(audio_data="")
    
    def test_supported_audio_formats(self):
        """Test all audio formats accepted"""
        audio_data = base64.b64encode(b"test").decode()
        
        for fmt in AudioFormat:
            request = SttRequest(
                audio_data=audio_data,
                format=fmt,
            )
            assert request.format == fmt
    
    def test_supported_languages(self):
        """Test language support"""
        audio_data = base64.b64encode(b"test").decode()
        
        for lang in [LanguageCode.EN, LanguageCode.ES, LanguageCode.FR]:
            request = SttRequest(
                audio_data=audio_data,
                language=lang,
            )
            assert request.language == lang


class TestSttResponseSchema:
    """Tests for SttResponse"""
    
    def test_successful_response(self):
        """Test creating successful response"""
        response = SttResponse(
            success=True,
            transcript="Hello world",
            confidence=0.95,
            language="en",
            processing_time_ms=250.5,
            device_used="gpu",
            audio_duration_seconds=3.5,
        )
        
        assert response.success
        assert response.transcript == "Hello world"
        assert response.confidence == 0.95
    
    def test_error_response(self):
        """Test creating error response"""
        response = SttResponse(
            success=False,
            transcript="",
            confidence=0.0,
            processing_time_ms=100.0,
            device_used="cpu",
            audio_duration_seconds=0.0,
            error_code="ERR_STT_020",
            error_message="No speech detected",
            user_friendly_message="No speech in audio",
        )
        
        assert not response.success
        assert response.error_code == "ERR_STT_020"
        assert response.user_friendly_message is not None
    
    def test_response_with_segments(self):
        """Test response with transcription segments"""
        segments = [
            TranscriptionSegment(
                text="Hello",
                start_time=0.0,
                end_time=1.0,
                confidence=0.95,
                no_speech_prob=0.05,
            ),
            TranscriptionSegment(
                text="world",
                start_time=1.0,
                end_time=2.0,
                confidence=0.92,
                no_speech_prob=0.08,
            ),
        ]
        
        response = SttResponse(
            success=True,
            transcript="Hello world",
            confidence=0.93,
            segments=segments,
            processing_time_ms=150.0,
            device_used="gpu",
            audio_duration_seconds=2.0,
        )
        
        assert len(response.segments) == 2
        assert response.segments[0].text == "Hello"
        assert response.segments[1].text == "world"


class TestTranscriptionSegment:
    """Tests for TranscriptionSegment"""
    
    def test_segment_creation(self):
        """Test creating a segment"""
        segment = TranscriptionSegment(
            text="Hello",
            start_time=0.0,
            end_time=1.0,
            confidence=0.95,
            no_speech_prob=0.05,
        )
        
        assert segment.text == "Hello"
        assert segment.start_time == 0.0
        assert segment.end_time == 1.0
        assert segment.confidence == 0.95
    
    def test_segment_confidence_bounds(self):
        """Test confidence is bounded [0, 1]"""
        # Valid
        segment = TranscriptionSegment(
            text="test",
            start_time=0.0,
            end_time=1.0,
            confidence=0.5,
            no_speech_prob=0.5,
        )
        assert segment.confidence == 0.5
        
        # Invalid: > 1.0
        with pytest.raises(ValueError):
            TranscriptionSegment(
                text="test",
                start_time=0.0,
                end_time=1.0,
                confidence=1.5,
                no_speech_prob=0.5,
            )


class TestSttExceptions:
    """Tests for STT exception classes"""
    
    def test_base_exception_attributes(self):
        """Test base exception has all required attributes"""
        exc = ModelNotInitializedError()
        
        assert exc.reason_code is not None
        assert exc.message is not None
        assert exc.user_friendly_message is not None
    
    def test_no_speech_exception(self):
        """Test NoSpeechDetectedError"""
        exc = NoSpeechDetectedError(
            no_speech_prob=0.85,
            threshold=0.3,
        )
        
        assert "0.85" in exc.message or "0.85" in str(exc.details)
        assert exc.reason_code.value == "NO_SPEECH_DETECTED"
    
    def test_confidence_too_low_exception(self):
        """Test ConfidenceTooLowError"""
        exc = ConfidenceTooLowError(
            confidence=0.3,
            threshold=0.5,
            reason="Low logprob",
        )
        
        assert "0.3" in exc.message or "0.3" in str(exc.details)
        assert "0.5" in exc.message or "0.5" in str(exc.details)
        assert exc.reason_code.value == "CONFIDENCE_TOO_LOW"
    
    def test_audio_too_short_exception(self):
        """Test AudioTooShortError"""
        exc = AudioTooShortError(
            duration=0.3,
            minimum=0.5,
        )
        
        assert "0.3" in exc.message
        assert "0.5" in exc.message
        assert exc.reason_code.value == "AUDIO_TOO_SHORT"
    
    def test_audio_too_long_exception(self):
        """Test AudioTooLongError"""
        exc = AudioTooLongError(
            duration=1200.0,
            maximum=600.0,
        )
        
        assert "1200" in exc.message
        assert "600" in exc.message
        assert exc.reason_code.value == "AUDIO_TOO_LONG"
    
    def test_inference_timeout_exception(self):
        """Test InferenceTimeoutError"""
        exc = InferenceTimeoutError(
            timeout_seconds=30.0,
            audio_duration=5.0,
        )
        
        assert "30" in exc.message
        assert exc.reason_code.value == "INFERENCE_TIMEOUT"
        assert exc.details.get('timeout_seconds') == 30.0
        assert exc.details.get('audio_duration_seconds') == 5.0
    
    def test_exception_details_preserved(self):
        """Test exception details are preserved"""
        details = {"test_key": "test_value"}
        exc = NoSpeechDetectedError(
            no_speech_prob=0.9,
            threshold=0.3,
        )
        
        assert "no_speech_probability" in exc.details
        assert exc.details["no_speech_probability"] == 0.9
