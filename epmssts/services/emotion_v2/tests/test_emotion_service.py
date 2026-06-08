"""
Comprehensive Test Suite for Emotion Intelligence Service v2

Tests:
- Audio models ensemble
- Text model
- Calibration layer
- Adaptive fusion engine
- Uncertainty estimation
- Drift monitoring
- Main emotion service
- Edge cases (whisper, loud anger, TTS-like)
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, AsyncMock

from epmssts.services.emotion_v2 import (
    EmotionIntelligenceService,
    EmotionAnalysisRequest,
    EmotionAnalysisResponse,
    AnalysisStatus,
    EmotionLabel,
)
from epmssts.services.emotion_v2.audio_models import (
    Wav2Vec2EmotionModel,
    HubertEmotionModel,
    AudioEnsemble,
)
from epmssts.services.emotion_v2.text_model import TextEmotionModel
from epmssts.services.emotion_v2.calibration import CalibrationLayer, CalibrationConfig
from epmssts.services.emotion_v2.fusion import AdaptiveFusionEngine, FusionConfig
from epmssts.services.emotion_v2.uncertainty import UncertaintyEstimator
from epmssts.services.emotion_v2.drift_monitor import DriftMonitor
from epmssts.services.emotion_v2.schemas import ModelPrediction


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def synthetic_audio():
    """Generate synthetic audio (1 second, 16kHz)"""
    sample_rate = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = np.sin(2 * np.pi * 440 * t) * 0.5  # 440 Hz sine wave
    return audio, sample_rate


@pytest.fixture
def sample_request():
    """Sample emotion analysis request"""
    return EmotionAnalysisRequest(
        audio_id="test_audio_001",
        waveform_ref="storage://waveforms/test_001.wav",
        mel_features_ref="storage://mels/test_001.npy",
        transcript="I am very happy today",
        stt_confidence=0.95,
        energy_band="medium",
        quality_score=0.85,
        duration_seconds=2.5,
    )


@pytest.fixture
def mock_audio_probabilities():
    """Mock audio model probabilities"""
    return {
        "angry": 0.1,
        "happy": 0.6,
        "neutral": 0.2,
        "sad": 0.1,
    }


@pytest.fixture
def mock_text_probabilities():
    """Mock text model probabilities"""
    return {
        "angry": 0.0,
        "happy": 0.8,
        "neutral": 0.1,
        "sad": 0.1,
    }


# ============================================================================
# Audio Models Tests
# ============================================================================


class TestAudioModels:
    """Test audio emotion models"""
    
    def test_wav2vec2_initialization(self):
        """Test Wav2Vec2 model initialization"""
        model = Wav2Vec2EmotionModel(device="cpu")
        assert model.model_name is not None
        assert not model.is_loaded
        assert model.label_map is not None
    
    def test_hubert_initialization(self):
        """Test HuBERT model initialization"""
        model = HubertEmotionModel(device="cpu")
        assert model.model_name is not None
        assert not model.is_loaded
        assert model.label_map is not None
    
    @pytest.mark.skipif(
        True, reason="Requires model download, enable for integration tests"
    )
    def test_audio_ensemble_load(self):
        """Test audio ensemble loading (integration test)"""
        ensemble = AudioEnsemble(device="cpu", use_secondary=False)
        ensemble.load_models()
        
        assert ensemble.is_initialized
        assert ensemble.primary_model.is_loaded
    
    def test_entropy_computation(self):
        """Test entropy computation"""
        model = Wav2Vec2EmotionModel()
        
        # Uniform distribution should have high entropy
        uniform_probs = np.array([0.25, 0.25, 0.25, 0.25])
        uniform_entropy = model._compute_entropy(uniform_probs)
        assert uniform_entropy > 1.0
        
        # Peaked distribution should have low entropy
        peaked_probs = np.array([0.9, 0.05, 0.03, 0.02])
        peaked_entropy = model._compute_entropy(peaked_probs)
        assert peaked_entropy < uniform_entropy


# ============================================================================
# Text Model Tests
# ============================================================================


class TestTextModel:
    """Test text emotion model"""
    
    def test_text_model_initialization(self):
        """Test text model initialization"""
        model = TextEmotionModel(device="cpu")
        assert model.model_name is not None
        assert not model.is_loaded
        assert len(model.supported_emotions) > 0
    
    def test_label_mapping(self):
        """Test emotion label mapping"""
        model = TextEmotionModel()
        
        raw_probs = {
            "anger": 0.5,
            "joy": 0.3,
            "neutral": 0.1,
            "sadness": 0.1,
        }
        
        mapped = model._map_to_standard_labels(raw_probs)
        
        assert "angry" in mapped
        assert "happy" in mapped
        assert "neutral" in mapped
        assert "sad" in mapped
        assert abs(sum(mapped.values()) - 1.0) < 0.01  # Should sum to 1
    
    def test_default_prediction_for_empty_text(self):
        """Test default prediction for empty text"""
        model = TextEmotionModel()
        default_pred = model._default_prediction()
        
        assert default_pred.probabilities["neutral"] == 1.0
        assert default_pred.entropy == 0.0


# ============================================================================
# Calibration Tests
# ============================================================================


class TestCalibration:
    """Test calibration layer"""
    
    def test_calibration_initialization(self):
        """Test calibration layer initialization"""
        calibration = CalibrationLayer()
        assert calibration.config is not None
        assert calibration.config.temperature_audio > 1.0  # Conservative
    
    def test_temperature_scaling(self, mock_audio_probabilities):
        """Test temperature scaling reduces overconfidence"""
        calibration = CalibrationLayer()
        
        # Apply temperature
        scaled = calibration._apply_temperature(
            mock_audio_probabilities, temperature=1.5
        )
        
        # Scaled probs should be less peaked
        original_max = max(mock_audio_probabilities.values())
        scaled_max = max(scaled.values())
        
        assert scaled_max < original_max
    
    def test_neutral_collapse_prevention(self):
        """Test neutral collapse prevention"""
        calibration = CalibrationLayer()
        
        # High neutral probability
        probs = {"angry": 0.05, "happy": 0.05, "neutral": 0.85, "sad": 0.05}
        
        adjusted, neutral_capped = calibration._prevent_neutral_collapse(probs)
        
        assert neutral_capped
        assert adjusted["neutral"] <= calibration.config.max_neutral_prob
    
    def test_volume_bias_correction(self):
        """Test volume bias correction (whisper sadness)"""
        calibration = CalibrationLayer()
        
        probs = {"angry": 0.1, "happy": 0.1, "neutral": 0.7, "sad": 0.1}
        
        # Low volume should boost sad
        corrected = calibration._correct_volume_bias(probs, volume_level=0.2)
        
        assert corrected["sad"] > probs["sad"]
        assert corrected["neutral"] < probs["neutral"]


# ============================================================================
# Fusion Tests
# ============================================================================


class TestAdaptiveFusion:
    """Test adaptive fusion engine"""
    
    def test_fusion_initialization(self):
        """Test fusion engine initialization"""
        fusion = AdaptiveFusionEngine()
        assert fusion.config is not None
        assert fusion.config.default_fusion_method == "bayesian"
    
    def test_adaptive_weights_computation(self):
        """Test dynamic weight computation"""
        fusion = AdaptiveFusionEngine()
        
        weights = fusion._compute_adaptive_weights(
            audio_entropy=0.5,  # Low entropy = confident
            text_entropy=1.5,   # High entropy = uncertain
            stt_confidence=0.9, # High STT confidence
            quality_score=0.8,  # Good audio quality
            energy_band="high", # High energy
            audio_confidence=0.8,
            text_confidence=0.6,
        )
        
        # Audio should be weighted higher (better signals)
        assert weights.audio_weight > weights.text_weight
        assert abs(weights.audio_weight + weights.text_weight - 1.0) < 0.01
    
    def test_bayesian_fusion(self, mock_audio_probabilities, mock_text_probabilities):
        """Test Bayesian fusion formula"""
        fusion = AdaptiveFusionEngine()
        
        fused = fusion._bayesian_fusion(
            mock_audio_probabilities,
            mock_text_probabilities,
            alpha=0.6,
            beta=0.4,
        )
        
        assert abs(sum(fused.values()) - 1.0) < 0.01
        assert "happy" in fused
        assert fused["happy"] > 0.5  # Both models predict happy
    
    def test_disagreement_detection(self):
        """Test disagreement score computation"""
        fusion = AdaptiveFusionEngine()
        
        # Models agree
        probs1 = {"angry": 0.1, "happy": 0.7, "neutral": 0.1, "sad": 0.1}
        probs2 = {"angry": 0.1, "happy": 0.6, "neutral": 0.2, "sad": 0.1}
        
        disagreement_agree = fusion._compute_disagreement(probs1, probs2)
        
        # Models disagree
        probs3 = {"angry": 0.7, "happy": 0.1, "neutral": 0.1, "sad": 0.1}
        probs4 = {"angry": 0.1, "happy": 0.7, "neutral": 0.1, "sad": 0.1}
        
        disagreement_disagree = fusion._compute_disagreement(probs3, probs4)
        
        assert disagreement_disagree > disagreement_agree


# ============================================================================
# Uncertainty Tests
# ============================================================================


class TestUncertaintyEstimation:
    """Test uncertainty estimator"""
    
    def test_uncertainty_initialization(self):
        """Test uncertainty estimator initialization"""
        estimator = UncertaintyEstimator()
        assert estimator.entropy_threshold > 0
        assert estimator.margin_threshold > 0
    
    def test_max_prob_margin(self):
        """Test max probability margin computation"""
        estimator = UncertaintyEstimator()
        
        # High margin (confident)
        confident_probs = {"angry": 0.05, "happy": 0.85, "neutral": 0.05, "sad": 0.05}
        margin_confident = estimator._compute_max_prob_margin(confident_probs)
        
        # Low margin (uncertain)
        uncertain_probs = {"angry": 0.2, "happy": 0.45, "neutral": 0.25, "sad": 0.1}
        margin_uncertain = estimator._compute_max_prob_margin(uncertain_probs)
        
        assert margin_confident > margin_uncertain
    
    def test_uncertainty_flag(self):
        """Test uncertainty flag determination"""
        estimator = UncertaintyEstimator()
        
        # High entropy should flag
        flag_high_entropy = estimator._determine_uncertainty_flag(
            entropy=1.2, max_prob_margin=0.5, confidence_dispersion=0.01, disagreement_score=0.1
        )
        assert flag_high_entropy
        
        # Low margin should flag
        flag_low_margin = estimator._determine_uncertainty_flag(
            entropy=0.3, max_prob_margin=0.1, confidence_dispersion=0.01, disagreement_score=0.1
        )
        assert flag_low_margin


# ============================================================================
# Drift Monitoring Tests
# ============================================================================


class TestDriftMonitoring:
    """Test drift monitor"""
    
    def test_drift_initialization(self):
        """Test drift monitor initialization"""
        monitor = DriftMonitor()
        assert monitor.window_size > 0
        assert monitor.neutral_collapse_threshold > 0
    
    def test_neutral_collapse_detection(self):
        """Test neutral collapse alert"""
        monitor = DriftMonitor()
        
        # Record mostly neutral predictions
        for _ in range(30):
            monitor.record_prediction("neutral", entropy=0.5, confidence=0.7, uncertainty_flag=False)
        
        for _ in range(10):
            monitor.record_prediction("happy", entropy=0.5, confidence=0.7, uncertainty_flag=False)
        
        # Check for alert
        alerts = monitor.get_active_alerts()
        neutral_alerts = [a for a in alerts if a.alert_type == "neutral_collapse"]
        
        assert len(neutral_alerts) > 0
    
    def test_metrics_snapshot(self):
        """Test metrics snapshot generation"""
        monitor = DriftMonitor()
        
        # Record some predictions
        monitor.record_prediction("happy", entropy=0.5, confidence=0.8, uncertainty_flag=False)
        monitor.record_prediction("sad", entropy=0.6, confidence=0.7, uncertainty_flag=False)
        monitor.record_prediction("angry", entropy=0.4, confidence=0.9, uncertainty_flag=False)
        
        snapshot = monitor.get_metrics_snapshot()
        
        assert snapshot.total_requests == 3
        assert "happy" in snapshot.emotion_distribution
        assert snapshot.average_entropy > 0
        assert snapshot.average_confidence > 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestEmotionServiceIntegration:
    """Integration tests for full emotion service"""
    
    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test service initialization"""
        service = EmotionIntelligenceService(device="cpu")
        
        # Mock model loading to avoid downloads
        with patch.object(service.audio_ensemble, 'load_models'):
            with patch.object(service.text_model, 'load'):
                await service.initialize()
        
        assert service.is_initialized
    
    @ pytest.mark.asyncio
    async def test_emotion_analysis_pipeline(self, sample_request):
        """Test full emotion analysis pipeline (mocked)"""
        service = EmotionIntelligenceService(device="cpu")
        
        # Mock components
        service.is_initialized = True
        
        mock_audio_pred = ModelPrediction(
            probabilities={"angry": 0.1, "happy": 0.6, "neutral": 0.2, "sad": 0.1},
            entropy=0.8,
            model_confidence=0.6,
            model_name="wav2vec2",
            inference_time_ms=100.0,
        )
        
        mock_text_pred = ModelPrediction(
            probabilities={"angry": 0.05, "happy": 0.75, "neutral": 0.1, "sad": 0.1},
            entropy=0.6,
            model_confidence=0.75,
            model_name="distilroberta",
            inference_time_ms=80.0,
        )
        
        # Patch predict methods
        with patch.object(
            service.audio_ensemble, 'predict', return_value=(mock_audio_pred, None)
        ):
            with patch.object(service.text_model, 'predict', return_value=mock_text_pred):
                response = await service.analyze_emotion(sample_request)
        
        assert response.status == AnalysisStatus.SUCCESS
        assert response.label in ["angry", "happy", "neutral", "sad"]
        assert 0 <= response.confidence <= 1.0
        assert response.uncertainty_metrics is not None
        assert response.fusion_weights is not None


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Test edge case handling"""
    
    def test_whisper_sadness_detection(self):
        """Test low volume sad emotion detection"""
        calibration = CalibrationLayer()
        
        # Low volume neutral prediction (might be whispered sadness)
        probs = {"angry": 0.1, "happy": 0.1, "neutral": 0.7, "sad": 0.1}
        
        calibrated, _ = calibration.calibrate_audio_probs(
            probs, volume_level=0.15, energy_band="low"
        )
        
        # Sad should be boosted
        assert calibrated["sad"] > probs["sad"]
    
    def test_loud_anger_handling(self):
        """Test high energy angry detection"""
        fusion = AdaptiveFusionEngine()
        
        # High energy should boost audio weight
        weights = fusion._compute_adaptive_weights(
            audio_entropy=0.4,
            text_entropy=0.8,
            stt_confidence=0.7,
            quality_score=0.8,
            energy_band="high",
            audio_confidence=0.8,
            text_confidence=0.6,
        )
        
        # Audio should dominate (high energy, good quality)
        assert weights.audio_weight > 0.55
    
    def test_low_quality_audio_fallback(self, sample_request):
        """Test low quality audio handling"""
        from epmssts.services.emotion_v2.exceptions import QualityScoreTooLowError
        
        service = EmotionIntelligenceService()
        service.is_initialized = True
        
        # Very low quality
        sample_request.quality_score = 0.2
        
        with pytest.raises(QualityScoreTooLowError):
            service._validate_request(sample_request)


# ============================================================================
# Performance Tests
# ============================================================================


class TestPerformance:
    """Test performance targets"""
    
    @pytest.mark.asyncio
    async def test_latency_target(self, sample_request):
        """Test p95 latency < 500ms target (mocked)"""
        service = EmotionIntelligenceService(device="cpu")
        service.is_initialized = True
        
        mock_pred = ModelPrediction(
            probabilities={"angry": 0.1, "happy": 0.6, "neutral": 0.2, "sad": 0.1},
            entropy=0.8,
            model_confidence=0.6,
            model_name="mock",
            inference_time_ms=50.0,
        )
        
        with patch.object(service.audio_ensemble, 'predict', return_value=(mock_pred, None)):
            with patch.object(service.text_model, 'predict', return_value=mock_pred):
                response = await service.analyze_emotion(sample_request)
        
        # Check latency (mocked, so should be fast)
        assert response.processing_time_ms < 500.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
