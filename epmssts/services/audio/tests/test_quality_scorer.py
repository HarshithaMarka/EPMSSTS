"""
Unit tests for quality scoring module.

Tests deterministic quality score computation.
"""

import pytest
from epmssts.services.audio.quality_scorer import QualityScorer, QualityScoreBoundaries
from epmssts.services.audio.schemas import SignalMetrics


class TestQualityScorer:
    """Test suite for QualityScorer."""
    
    @pytest.fixture
    def scorer(self):
        """Create quality scorer instance."""
        return QualityScorer()
    
    def test_perfect_audio_high_score(self, scorer):
        """Test high-quality audio gets high score."""
        metrics = SignalMetrics(
            rms_dbfs=-20.0,
            peak_dbfs=-3.0,
            snr_estimate=30.0,  # Excellent SNR
            spectral_centroid=1500.0,
            zero_crossing_rate=0.15,
            energy_variance=1.0,
            pitch_mean=120.0,
            pitch_variance=50.0,
        )
        
        score = scorer.score(
            metrics=metrics,
            silence_ratio=0.1,  # 10% silence
            duration_seconds=5.0,
        )
        
        assert score > 75
    
    def test_noisy_audio_low_score(self, scorer):
        """Test noisy audio gets lower score."""
        metrics = SignalMetrics(
            rms_dbfs=-20.0,
            peak_dbfs=-3.0,
            snr_estimate=3.0,  # Low SNR
            spectral_centroid=1500.0,
            zero_crossing_rate=0.15,
            energy_variance=1.0,
            pitch_mean=120.0,
            pitch_variance=50.0,
        )
        
        score = scorer.score(
            metrics=metrics,
            silence_ratio=0.1,
            duration_seconds=5.0,
        )
        
        assert score < 75
    
    def test_clipped_audio_penalty(self, scorer):
        """Test clipped audio receives penalty."""
        # Normal audio
        metrics_normal = SignalMetrics(
            rms_dbfs=-20.0,
            peak_dbfs=-3.0,
            snr_estimate=20.0,
            spectral_centroid=1500.0,
            zero_crossing_rate=0.15,
            energy_variance=1.0,
            pitch_mean=120.0,
            pitch_variance=50.0,
        )
        score_normal = scorer.score(metrics_normal, 0.1, 5.0)
        
        # Clipped audio (peak at 0dBFS)
        metrics_clipped = SignalMetrics(
            rms_dbfs=-20.0,
            peak_dbfs=0.0,  # Clipping!
            snr_estimate=20.0,
            spectral_centroid=1500.0,
            zero_crossing_rate=0.15,
            energy_variance=1.0,
            pitch_mean=120.0,
            pitch_variance=50.0,
        )
        score_clipped = scorer.score(metrics_clipped, 0.1, 5.0)
        
        # Clipped should be lower
        assert score_clipped < score_normal
    
    def test_silence_ratio_penalty(self, scorer):
        """Test silence ratio receives penalty."""
        metrics = SignalMetrics(
            rms_dbfs=-20.0,
            peak_dbfs=-3.0,
            snr_estimate=20.0,
            spectral_centroid=1500.0,
            zero_crossing_rate=0.15,
            energy_variance=1.0,
            pitch_mean=120.0,
            pitch_variance=50.0,
        )
        
        # Low silence
        score_low_silence = scorer.score(metrics, silence_ratio=0.1, duration_seconds=5.0)
        
        # High silence
        score_high_silence = scorer.score(metrics, silence_ratio=0.6, duration_seconds=5.0)
        
        assert score_high_silence < score_low_silence
    
    def test_duration_too_short_penalty(self, scorer):
        """Test short duration receives penalty."""
        metrics = SignalMetrics(
            rms_dbfs=-20.0,
            peak_dbfs=-3.0,
            snr_estimate=20.0,
            spectral_centroid=1500.0,
            zero_crossing_rate=0.15,
            energy_variance=1.0,
            pitch_mean=120.0,
            pitch_variance=50.0,
        )
        
        # Optimal duration
        score_optimal = scorer.score(metrics, 0.1, duration_seconds=5.0)
        
        # Too short
        score_short = scorer.score(metrics, 0.1, duration_seconds=1.0)
        
        assert score_short < score_optimal
    
    def test_duration_too_long_penalty(self, scorer):
        """Test long duration receives penalty."""
        metrics = SignalMetrics(
            rms_dbfs=-20.0,
            peak_dbfs=-3.0,
            snr_estimate=20.0,
            spectral_centroid=1500.0,
            zero_crossing_rate=0.15,
            energy_variance=1.0,
            pitch_mean=120.0,
            pitch_variance=50.0,
        )
        
        # Optimal duration
        score_optimal = scorer.score(metrics, 0.1, duration_seconds=5.0)
        
        # Too long
        score_long = scorer.score(metrics, 0.1, duration_seconds=15.0)
        
        assert score_long < score_optimal
    
    def test_low_quality_detection(self, scorer):
        """Test low quality score detection."""
        poor_metrics = SignalMetrics(
            rms_dbfs=-20.0,
            peak_dbfs=0.0,  # Clipping
            snr_estimate=2.0,  # Very low SNR
            spectral_centroid=1500.0,
            zero_crossing_rate=0.15,
            energy_variance=1.0,
            pitch_mean=120.0,
            pitch_variance=50.0,
        )
        
        score = scorer.score(poor_metrics, silence_ratio=0.7, duration_seconds=1.0)
        
        assert scorer.is_low_quality(score, threshold=50)
        assert score < 50
    
    def test_score_bounds(self, scorer):
        """Test scores are always between 0 and 100."""
        metrics = SignalMetrics(
            rms_dbfs=-20.0,
            peak_dbfs=-3.0,
            snr_estimate=20.0,
            spectral_centroid=1500.0,
            zero_crossing_rate=0.15,
            energy_variance=1.0,
            pitch_mean=120.0,
            pitch_variance=50.0,
        )
        
        # Test multiple conditions
        for silence_ratio in [0.0, 0.5, 1.0]:
            for duration in [0.5, 5.0, 60.0]:
                score = scorer.score(metrics, silence_ratio, duration)
                assert 0 <= score <= 100


class TestCustomQualityScoreBoundaries:
    """Test custom quality score boundaries."""
    
    def test_custom_snr_thresholds(self):
        """Test custom SNR thresholds."""
        boundaries = QualityScoreBoundaries(
            snr_excellent=40.0,
            snr_good=30.0,
            snr_fair=20.0,
        )
        scorer = QualityScorer(boundaries=boundaries)
        
        assert scorer.boundaries.snr_excellent == 40.0
        assert scorer.boundaries.snr_good == 30.0
        assert scorer.boundaries.snr_fair == 20.0
    
    def test_custom_dynamic_range_threshold(self):
        """Test custom dynamic range threshold."""
        boundaries = QualityScoreBoundaries(min_dynamic_range=15.0)
        scorer = QualityScorer(boundaries=boundaries)
        
        assert scorer.boundaries.min_dynamic_range == 15.0
