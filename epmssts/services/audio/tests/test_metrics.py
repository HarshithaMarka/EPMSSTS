"""
Unit tests for metrics extraction module.

Tests signal metrics computation.
"""

import pytest
import numpy as np

from epmssts.services.audio.metrics import SignalMetricsExtractor
from epmssts.services.audio.schemas import SignalMetrics
from .test_fixtures import AudioTestFixtures


class TestSignalMetricsExtractor:
    """Test suite for SignalMetricsExtractor."""
    
    @pytest.fixture
    def extractor(self):
        """Create extractor instance."""
        return SignalMetricsExtractor()
    
    def test_extract_clean_speech_metrics(self, extractor):
        """Test metrics extraction from clean speech."""
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=3.0)
        
        metrics = extractor.extract(audio, sample_rate=16000)
        
        assert isinstance(metrics, SignalMetrics)
        assert -120.0 <= metrics.rms_dbfs <= 0.0
        assert -120.0 <= metrics.peak_dbfs <= 1.0
        assert metrics.snr_estimate >= 0.0
        assert metrics.spectral_centroid >= 0.0
        assert 0.0 <= metrics.zero_crossing_rate <= 1.0
        assert metrics.energy_variance >= 0.0
    
    def test_rms_computation(self, extractor):
        """Test RMS level computation."""
        # Create signal with known RMS
        amplitude = 0.1
        audio = np.ones(16000, dtype=np.float32) * amplitude
        
        metrics = extractor.extract(audio, sample_rate=16000)
        
        expected_dbfs = 20 * np.log10(amplitude)
        # Allow 1 dB tolerance
        assert abs(metrics.rms_dbfs - expected_dbfs) < 1.0
    
    def test_peak_computation(self, extractor):
        """Test peak level computation."""
        audio = np.zeros(16000, dtype=np.float32)
        audio[8000] = 0.5  # Single peak
        
        metrics = extractor.extract(audio, sample_rate=16000)
        
        expected_peak_dbfs = 20 * np.log10(0.5)
        assert abs(metrics.peak_dbfs - expected_peak_dbfs) < 0.1
    
    def test_silence_metrics(self, extractor):
        """Test metrics for nearly silent audio."""
        audio = AudioTestFixtures.create_silence(duration_seconds=1.0)
        
        metrics = extractor.extract(audio, sample_rate=16000)
        
        # Silence should have very low RMS
        assert metrics.rms_dbfs < -100.0
        assert metrics.snr_estimate < 5.0
    
    def test_noisy_audio_metrics(self, extractor):
        """Test metrics for noisy audio."""
        clean = AudioTestFixtures.create_clean_speech(duration_seconds=2.0)
        noisy = AudioTestFixtures.create_noisy_audio(clean, snr_db=5.0)
        
        metrics = extractor.extract(noisy, sample_rate=16000)
        
        # Noisy audio should have lower SNR
        assert metrics.snr_estimate < 15.0
        # ZCR should be higher for noisy audio
        assert metrics.zero_crossing_rate > 0.05
    
    def test_metric_bounds(self, extractor):
        """Test all metrics are within expected bounds."""
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=5.0)
        
        metrics = extractor.extract(audio, sample_rate=16000)
        
        # Verify all metrics are within valid ranges
        assert -120.0 <= metrics.rms_dbfs <= 0.0
        assert -120.0 <= metrics.peak_dbfs <= 1.0
        assert 0.0 <= metrics.snr_estimate <= 100.0
        assert 0.0 <= metrics.spectral_centroid <= 8000.0
        assert 0.0 <= metrics.zero_crossing_rate <= 1.0
        assert metrics.energy_variance >= 0.0
        assert metrics.pitch_mean >= 0.0
        assert metrics.pitch_variance >= 0.0
    
    def test_high_energy_audio_metrics(self, extractor):
        """Test metrics for high-energy audio."""
        audio = AudioTestFixtures.create_loud_speech(duration_seconds=2.0)
        
        metrics = extractor.extract(audio, sample_rate=16000)
        
        # High-energy audio should have RMS around -10dBFS
        assert metrics.rms_dbfs > -20.0
    
    def test_low_energy_audio_metrics(self, extractor):
        """Test metrics for low-energy (whisper) audio."""
        audio = AudioTestFixtures.create_whisper(duration_seconds=2.0)
        
        metrics = extractor.extract(audio, sample_rate=16000)
        
        # Whisper should have RMS around -38dBFS
        assert metrics.rms_dbfs < -30.0
    
    def test_clipped_audio_metrics(self, extractor):
        """Test metrics for clipped audio."""
        clean = AudioTestFixtures.create_clean_speech(duration_seconds=2.0)
        clipped = AudioTestFixtures.create_clipped_audio(clean, clip_percentage=5.0)
        
        metrics = extractor.extract(clipped, sample_rate=16000)
        
        # Clipped audio should have peak near threshold
        assert metrics.peak_dbfs > -5.0


class TestMetricsConsistency:
    """Test metrics consistency across variations."""
    
    @pytest.fixture
    def extractor(self):
        """Create extractor instance."""
        return SignalMetricsExtractor()
    
    def test_same_audio_same_metrics(self, extractor):
        """Test same audio produces consistent metrics."""
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=3.0)
        
        metrics1 = extractor.extract(audio, sample_rate=16000)
        metrics2 = extractor.extract(audio, sample_rate=16000)
        
        # Metrics should be identical for same input
        assert metrics1.rms_dbfs == metrics2.rms_dbfs
        assert metrics1.peak_dbfs == metrics2.peak_dbfs
    
    def test_scaled_audio_metrics(self, extractor):
        """Test metrics for scaled (amplified) audio."""
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=2.0)
        scaled = audio * 2.0  # Double amplitude
        
        metrics_orig = extractor.extract(audio, sample_rate=16000)
        metrics_scaled = extractor.extract(scaled, sample_rate=16000)
        
        # Doubled amplitude = +6dB
        assert metrics_scaled.rms_dbfs > metrics_orig.rms_dbfs
        assert metrics_scaled.peak_dbfs > metrics_orig.peak_dbfs
