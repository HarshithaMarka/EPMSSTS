"""
Unit tests for audio preprocessing service.

Tests the complete preprocessing pipeline end-to-end.
"""

import pytest
import tempfile
import os
import shutil

from epmssts.services.audio.preprocessing_service import AudioPreprocessingService
from epmssts.services.audio.schemas import AudioPreprocessResponse, AudioPreprocessErrorResponse
from epmssts.services.audio.exceptions import AudioPreprocessingException
from .test_fixtures import AudioTestFixtures


class TestAudioPreprocessingService:
    """Test suite for AudioPreprocessingService."""
    
    @pytest.fixture
    def service(self):
        """Create preprocessing service instance."""
        return AudioPreprocessingService()
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_preprocess_clean_speech(self, service, temp_dir):
        """Test preprocessing clean speech audio."""
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=3.0)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        response, internal_data = service.preprocess(file_path)
        
        assert response.status == "success"
        assert isinstance(response, AudioPreprocessResponse)
        assert response.duration_seconds > 0
        assert response.quality_score >= 0
        assert response.quality_score <= 100
        assert response.preprocessing_latency_ms > 0
        assert len(response.waveform_shape) == 1
        assert len(response.mel_shape) == 2
        
        # Check internal data
        assert "waveform" in internal_data
        assert "mel_spec" in internal_data
    
    def test_preprocess_whisper_audio(self, service, temp_dir):
        """Test preprocessing low-energy (whisper) audio."""
        audio = AudioTestFixtures.create_whisper(duration_seconds=3.0)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        response, _ = service.preprocess(file_path)
        
        assert response.status == "success"
        # Whisper should be classified as very_low energy
        assert response.energy_band == "very_low"
    
    def test_preprocess_loud_audio(self, service, temp_dir):
        """Test preprocessing high-energy audio."""
        audio = AudioTestFixtures.create_loud_speech(duration_seconds=3.0)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        response, _ = service.preprocess(file_path)
        
        assert response.status == "success"
        # Loud should be classified as high energy
        assert response.energy_band == "high"
    
    def test_preprocess_noisy_audio(self, service, temp_dir):
        """Test preprocessing noisy audio."""
        clean = AudioTestFixtures.create_clean_speech(duration_seconds=3.0)
        noisy = AudioTestFixtures.create_noisy_audio(clean, snr_db=5.0)
        file_path = AudioTestFixtures.save_wav_file(noisy, temp_dir=temp_dir)
        
        response, _ = service.preprocess(file_path)
        
        assert response.status == "success"
        assert response.metrics.snr_estimate < 15.0  # Low SNR
    
    def test_preprocess_clipped_audio(self, service, temp_dir):
        """Test preprocessing clipped audio."""
        clean = AudioTestFixtures.create_clean_speech(duration_seconds=3.0)
        clipped = AudioTestFixtures.create_clipped_audio(clean, clip_percentage=5.0)
        file_path = AudioTestFixtures.save_wav_file(clipped, temp_dir=temp_dir)
        
        response, _ = service.preprocess(file_path)
        
        assert response.status == "success"
        # Clipped audio should have lower quality score
        assert response.quality_score < 85
    
    def test_preprocess_corrupted_file(self, service, temp_dir):
        """Test preprocessing fails for corrupted file."""
        file_path = AudioTestFixtures.save_corrupt_file(temp_dir=temp_dir)
        
        response, _ = service.preprocess(file_path)
        
        assert response.status == "error"
        assert isinstance(response, AudioPreprocessErrorResponse)
        assert response.reason_code is not None
    
    def test_preprocess_too_short_audio(self, service, temp_dir):
        """Test preprocessing fails for audio shorter than 1.5s."""
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=0.8)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        response, _ = service.preprocess(file_path)
        
        assert response.status == "error"
        assert response.reason_code == "ERR_004_DURATION_TOO_SHORT"
    
    def test_preprocess_metrics_recorded(self, service, temp_dir):
        """Test metrics are recorded after preprocessing."""
        initial_total = service.metrics.total_requests
        
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=3.0)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        service.preprocess(file_path)
        
        assert service.metrics.total_requests == initial_total + 1
    
    def test_preprocess_latency_measurement(self, service, temp_dir):
        """Test latency is measured and recorded."""
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=3.0)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        response, _ = service.preprocess(file_path)
        
        assert response.preprocessing_latency_ms > 0
        assert len(service.metrics.latencies) > 0
        assert service.metrics.latencies[-1] == response.preprocessing_latency_ms
    
    def test_get_metrics_summary(self, service, temp_dir):
        """Test metrics summary generation."""
        # Do some preprocessing
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=3.0)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        service.preprocess(file_path)
        
        metrics = service.get_metrics_summary()
        
        assert metrics["total_requests"] > 0
        assert metrics["successful_requests"] > 0
        assert "latency" in metrics
        assert "p50_ms" in metrics["latency"]
        assert "p95_ms" in metrics["latency"]
        assert "p99_ms" in metrics["latency"]
        assert "quality" in metrics
        assert "energy_bands" in metrics


class TestPreprocessingPipeline:
    """Test complete signal processing pipeline."""
    
    @pytest.fixture
    def service(self):
        """Create preprocessing service instance."""
        return AudioPreprocessingService()
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_pipeline_deterministic(self, service, temp_dir):
        """Test pipeline produces deterministic results."""
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=3.0)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        response1, _ = service.preprocess(file_path)
        response2, _ = service.preprocess(file_path)
        
        # Same input should produce same metrics
        assert response1.metrics.rms_dbfs == response2.metrics.rms_dbfs
        assert response1.quality_score == response2.quality_score
    
    def test_pipeline_quality_variation(self, service, temp_dir):
        """Test quality scores vary based on audio content."""
        # Clean audio
        clean = AudioTestFixtures.create_clean_speech(duration_seconds=3.0)
        clean_path = AudioTestFixtures.save_wav_file(clean, temp_dir=temp_dir)
        
        # Noisy audio
        noisy = AudioTestFixtures.create_noisy_audio(clean, snr_db=5.0)
        noisy_path = AudioTestFixtures.save_wav_file(noisy, temp_dir=temp_dir)
        
        response_clean, _ = service.preprocess(clean_path)
        response_noisy, _ = service.preprocess(noisy_path)
        
        # Clean should have better quality
        assert response_clean.quality_score > response_noisy.quality_score
    
    def test_pipeline_energy_bands(self, service, temp_dir):
        """Test energy band classification."""
        # Whisper (very_low)
        whisper = AudioTestFixtures.create_whisper(duration_seconds=3.0)
        whisper_path = AudioTestFixtures.save_wav_file(whisper, temp_dir=temp_dir)
        
        # Loud (high)
        loud = AudioTestFixtures.create_loud_speech(duration_seconds=3.0)
        loud_path = AudioTestFixtures.save_wav_file(loud, temp_dir=temp_dir)
        
        response_whisper, _ = service.preprocess(whisper_path)
        response_loud, _ = service.preprocess(loud_path)
        
        assert response_whisper.energy_band == "very_low"
        assert response_loud.energy_band == "high"
    
    def test_pipeline_mel_spectrogram_shape(self, service, temp_dir):
        """Test mel-spectrogram has correct shape."""
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=5.0)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        response, internal_data = service.preprocess(file_path)
        
        mel_spec = internal_data["mel_spec"]
        
        # Check shape
        assert len(mel_spec.shape) == 2
        assert mel_spec.shape[1] == 128  # n_mels
        # Time frames should be reasonable
        assert mel_spec.shape[0] > 0
