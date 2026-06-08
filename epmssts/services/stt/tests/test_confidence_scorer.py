"""
Tests for STT Confidence Scorer

Tests multi-factor confidence scoring algorithm.
"""

import pytest
from ..confidence_scorer import TranscriptionConfidenceScorer, ConfidenceFactors
from .test_fixtures import SttAudioFixtures, MockWhisperSegment


class TestConfidenceScorer:
    """Unit tests for TranscriptionConfidenceScorer"""
    
    @pytest.fixture
    def scorer(self):
        return TranscriptionConfidenceScorer()
    
    def test_logprob_scoring(self, scorer):
        """Test log probability factor scoring"""
        # Best case: logprob near 0
        score = scorer._score_logprob(-0.1)
        assert score > 0.95
        
        # Acceptable: logprob around -0.5
        score = scorer._score_logprob(-0.5)
        assert 0.8 < score <= 1.0
        
        # Poor: logprob very negative
        score = scorer._score_logprob(-3.0)
        assert score <= 0.1
    
    def test_no_speech_scoring(self, scorer):
        """Test no-speech probability inversion"""
        # Clean speech
        factor = 1.0 - 0.05
        assert factor == 0.95
        
        # Mostly silence
        factor = 1.0 - 0.85
        assert factor == 0.15
    
    def test_segment_consistency_empty(self, scorer):
        """Test segment consistency with no segments"""
        score = scorer._score_segment_consistency([])
        assert score == 0.5
    
    def test_segment_consistency_single(self, scorer):
        """Test segment consistency with single segment"""
        segments = [MockWhisperSegment("hello", 0, 1)]
        score = scorer._score_segment_consistency(segments)
        assert score > 0.7
    
    def test_segment_consistency_variable(self, scorer):
        """Test segment consistency with variable logprobs"""
        segments = [
            MockWhisperSegment("hello", 0, 1, avg_logprob=-0.1),
            MockWhisperSegment("world", 1, 2, avg_logprob=-2.0),  # Much worse
        ]
        score = scorer._score_segment_consistency(segments)
        assert score < 0.8  # Should show inconsistency
    
    def test_repetition_detection_clean(self, scorer):
        """Test that clean text gets high score"""
        text = "This is a normal sentence with varied words and unique phrases"
        score = scorer._score_repetition(text)
        assert score > 0.9
    
    def test_repetition_detection_repeated(self, scorer):
        """Test detection of repeated words"""
        text = "I don't know I don't know I don't know I don't know"
        score = scorer._score_repetition(text)
        assert score < 0.5  # Should penalize repetition
    
    def test_repetition_detection_um_um(self, scorer):
        """Test detection of 'um' repetition"""
        text = "um um um um um um the person spoke"
        score = scorer._score_repetition(text)
        assert score < 0.6
    
    def test_language_certainty_scoring(self, scorer):
        """Test language certainty factor"""
        # High certainty
        score = scorer._score_language_certainty("en", language_logprob=-0.05)
        assert score > 0.95
        
        # Medium certainty
        score = scorer._score_language_certainty("en", language_logprob=-0.5)
        assert 0.7 < score < 0.95
        
        # Low certainty
        score = scorer._score_language_certainty("en", language_logprob=-3.0)
        assert score < 0.3
    
    def test_language_certainty_no_logprob(self, scorer):
        """Test language certainty without logprob"""
        score = scorer._score_language_certainty("en", language_logprob=None)
        assert score == 0.8
    
    def test_overall_confidence_clean_speech(self, scorer):
        """Test overall confidence for clean speech"""
        transcript = "The quick brown fox jumps over the lazy dog"
        segments = SttAudioFixtures.generate_mock_segments(transcript, 5.0)
        
        confidence = scorer.score(
            transcript=transcript,
            segments=segments,
            avg_logprob=-0.3,
            no_speech_prob=0.05,
            language="en",
            language_logprob=-0.1,
        )
        
        assert 0.7 < confidence <= 1.0
    
    def test_overall_confidence_noisy_speech(self, scorer):
        """Test overall confidence for noisy speech"""
        transcript = "Something unclear here maybe"
        segments = SttAudioFixtures.generate_mock_segments(transcript, 5.0)
        
        confidence = scorer.score(
            transcript=transcript,
            segments=segments,
            avg_logprob=-1.5,
            no_speech_prob=0.3,
            language="en",
            language_logprob=-0.5,
        )
        
        assert 0.3 < confidence < 0.7
    
    def test_overall_confidence_poor_speech(self, scorer):
        """Test overall confidence for very poor speech"""
        transcript = "I don't know I don't know um um um"
        segments = SttAudioFixtures.generate_mock_segments(transcript, 5.0)
        
        confidence = scorer.score(
            transcript=transcript,
            segments=segments,
            avg_logprob=-2.5,
            no_speech_prob=0.65,
            language="en",
            language_logprob=-1.5,
        )
        
        assert confidence < 0.4
    
    def test_should_reject_low_confidence(self, scorer):
        """Test rejection due to low confidence"""
        should_reject, reason = scorer.should_reject(
            transcript="hello world",
            confidence=0.3,
            no_speech_prob=0.2,
            avg_logprob=-0.5,
            confidence_threshold=0.5,
        )
        assert should_reject
        assert "Confidence" in reason or "below" in reason.lower()
    
    def test_should_reject_no_speech(self, scorer):
        """Test rejection due to high no-speech probability"""
        should_reject, reason = scorer.should_reject(
            transcript="hello",
            confidence=0.8,
            no_speech_prob=0.8,
            avg_logprob=-0.5,
            confidence_threshold=0.5,
        )
        assert should_reject
        assert "speech" in reason.lower()
    
    def test_should_reject_empty_transcript(self, scorer):
        """Test rejection of empty transcript"""
        should_reject, reason = scorer.should_reject(
            transcript="",
            confidence=0.8,
            no_speech_prob=0.1,
            avg_logprob=-0.5,
            confidence_threshold=0.5,
        )
        assert should_reject
        assert "empty" in reason.lower()
    
    def test_should_accept_good_transcription(self, scorer):
        """Test acceptance of good transcription"""
        should_reject, reason = scorer.should_reject(
            transcript="The quick brown fox",
            confidence=0.85,
            no_speech_prob=0.05,
            avg_logprob=-0.3,
            confidence_threshold=0.5,
        )
        assert not should_reject
    
    def test_metrics_history(self, scorer):
        """Test score history tracking"""
        assert len(scorer.scores_history) == 0
        
        # Add some scores
        for _ in range(5):
            score = scorer.score(
                transcript="hello",
                segments=[],
                avg_logprob=-0.5,
                no_speech_prob=0.1,
                language="en",
            )
        
        assert len(scorer.scores_history) == 5
        
        stats = scorer.get_statistics()
        assert stats['sample_count'] == 5
        assert 'average_score' in stats
        assert 'median_score' in stats
    
    def test_max_history_limit(self, scorer):
        """Test that history doesn't exceed max"""
        max_h = scorer.max_history
        
        # Add more than max
        for i in range(max_h + 100):
            scorer.score(
                transcript="test",
                segments=[],
                avg_logprob=-0.5,
                no_speech_prob=0.1,
                language="en",
            )
        
        assert len(scorer.scores_history) == max_h
