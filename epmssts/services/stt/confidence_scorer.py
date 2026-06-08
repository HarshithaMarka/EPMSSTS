"""
Confidence Scoring for STT

Multi-factor confidence scoring for transcription quality assessment.
Prevents garbage outputs and unreliable transcriptions.
"""

import logging
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class ConfidenceFactors:
    """Individual confidence factors"""
    avg_logprob: float  # Average log probability (-inf to 0, higher is better)
    no_speech_prob: float  # Probability of no speech (0-1, lower is better)
    segment_consistency: float  # Consistency across segments (0-1)
    repetition_score: float  # Penalty for repetition (0-1, higher is better)
    language_certainty: float  # Confidence in language detection (0-1)


class TranscriptionConfidenceScorer:
    """
    Score transcription confidence using multiple factors.
    
    Factors:
    1. Average log probability (from Whisper)
    2. No-speech probability (from Whisper)
    3. Segment consistency (variation between segments)
    4. Repetition detection (penalizes repeated sequences)
    5. Language certainty (confidence in language detection)
    
    Score is normalized to [0, 1] using sigmoid.
    """
    
    # Thresholds for different factors (calibrated empirically)
    LOGPROB_THRESHOLD = -0.5  # Good transcriptions have avg_logprob > -0.5
    NO_SPEECH_THRESHOLD = 0.3  # Reject if no_speech_prob > 0.3
    MIN_SEGMENT_CONSISTENCY = 0.4  # Segments should be somewhat consistent
    REPETITION_PENALTY_THRESHOLD = 0.2  # 20% repeated sequences triggers penalty
    
    def __init__(self):
        self.scores_history = []
        self.max_history = 1000
    
    def score(
        self,
        transcript: str,
        segments: List[Any],
        avg_logprob: float,
        no_speech_prob: float,
        language: str,
        language_logprob: Optional[float] = None,
    ) -> float:
        """
        Calculate overall confidence score.
        
        Args:
            transcript: Full transcribed text
            segments: List of segment objects from Whisper
            avg_logprob: Average log probability from Whisper
            no_speech_prob: No-speech probability from Whisper
            language: Detected language code
            language_logprob: Log probability of language detection
            
        Returns:
            Confidence score [0, 1]
        """
        factors = self._extract_factors(
            transcript=transcript,
            segments=segments,
            avg_logprob=avg_logprob,
            no_speech_prob=no_speech_prob,
            language=language,
            language_logprob=language_logprob,
        )
        
        score = self._combine_factors(factors)
        
        # Store for history
        if len(self.scores_history) >= self.max_history:
            self.scores_history.pop(0)
        self.scores_history.append(score)
        
        return score
    
    def _extract_factors(
        self,
        transcript: str,
        segments: List[Any],
        avg_logprob: float,
        no_speech_prob: float,
        language: str,
        language_logprob: Optional[float] = None,
    ) -> ConfidenceFactors:
        """Extract individual confidence factors"""
        
        # Factor 1: Average log probability
        logprob_factor = self._score_logprob(avg_logprob)
        
        # Factor 2: No-speech probability
        no_speech_factor = 1.0 - no_speech_prob  # Invert (higher is better)
        
        # Factor 3: Segment consistency
        consistency = self._score_segment_consistency(segments)
        
        # Factor 4: Repetition detection
        repetition = self._score_repetition(transcript)
        
        # Factor 5: Language certainty
        language_cert = self._score_language_certainty(language, language_logprob)
        
        return ConfidenceFactors(
            avg_logprob=logprob_factor,
            no_speech_prob=no_speech_factor,
            segment_consistency=consistency,
            repetition_score=repetition,
            language_certainty=language_cert,
        )
    
    def _score_logprob(self, avg_logprob: float) -> float:
        """
        Score based on average log probability.
        
        Good transcriptions have avg_logprob close to 0 (or slightly negative).
        Normalize to [0, 1].
        """
        import math
        
        # Clamp to reasonable range
        clamped = max(avg_logprob, -3.0)
        
        # Map: -3.0 → 0.0, -0.5 → 1.0
        if clamped >= -0.5:
            return 1.0
        elif clamped <= -3.0:
            return 0.0
        else:
            # Linear interpolation
            return (clamped - (-3.0)) / ((-0.5) - (-3.0))
    
    def _score_segment_consistency(self, segments: List[Any]) -> float:
        """
        Score based on consistency across segments.
        
        Extracts per-segment confidence and checks variance.
        High variance = less confident.
        """
        if not segments:
            return 0.5  # No segments = neutral
        
        # Extract per-segment log probabilities
        segment_logprobs = []
        for segment in segments:
            # Check different possible attribute names from Whisper
            if hasattr(segment, 'avg_logprob'):
                segment_logprobs.append(segment.avg_logprob)
            elif isinstance(segment, dict) and 'avg_logprob' in segment:
                segment_logprobs.append(segment['avg_logprob'])
        
        if len(segment_logprobs) < 2:
            return 0.8  # Single segment = fairly consistent
        
        # Calculate coefficient of variation
        import statistics
        mean = statistics.mean(segment_logprobs)
        stdev = statistics.stdev(segment_logprobs)
        
        if mean == 0:
            cv = 0
        else:
            cv = abs(stdev / mean)
        
        # Map: cv=0 → 1.0, cv=0.3 → 0.5, cv=1.0 → 0.0
        consistency = max(0, 1.0 - cv)
        return min(1.0, consistency)
    
    def _score_repetition(self, transcript: str) -> float:
        """
        Detect and penalize repetitive text.
        
        Hallucinations often manifest as repeated phrases.
        Examples: "I don't know I don't know I don't know" or "um um um um"
        """
        if not transcript:
            return 0.0
        
        # Normalize
        text_lower = transcript.lower().strip()
        words = text_lower.split()
        
        if len(words) < 3:
            return 1.0  # Too short to assess repetition
        
        # Check for word repetition
        max_repeat_ratio = 0.0
        for i in range(len(words) - 2):
            repeat_seq = [words[i], words[i], words[i]]
            repeat_ratio = text_lower.count(" ".join(repeat_seq)) / len(words)
            max_repeat_ratio = max(max_repeat_ratio, repeat_ratio)
        
        # Check for phrase-level repetition (2-word phrases)
        for i in range(len(words) - 3):
            phrase = " ".join(words[i:i+2])
            phrase_count = text_lower.count(phrase)
            phrase_ratio = phrase_count / (len(words) / 2)
            
            if phrase_ratio > 0.3:  # Same 2-word phrase appears 30%+ of the time
                max_repeat_ratio = max(max_repeat_ratio, phrase_ratio)
        
        # Score: high repetition = low score
        if max_repeat_ratio > self.REPETITION_PENALTY_THRESHOLD:
            penalty = min(1.0, max_repeat_ratio * 2)
            return 1.0 - penalty
        
        return 1.0
    
    def _score_language_certainty(
        self,
        language: str,
        language_logprob: Optional[float] = None,
    ) -> float:
        """
        Score confidence in language detection.
        
        Uses language log probability if available, otherwise assume decent certainty.
        """
        if language_logprob is None:
            # No log prob available - assume reasonable confidence
            return 0.8
        
        # Map log prob to certainty
        if language_logprob >= -0.1:
            return 1.0
        elif language_logprob >= -0.5:
            return 0.9
        elif language_logprob >= -1.0:
            return 0.7
        elif language_logprob >= -2.0:
            return 0.4
        else:
            return 0.1
    
    def _combine_factors(self, factors: ConfidenceFactors) -> float:
        """
        Combine individual factors into overall score.
        
        Uses weighted average with sigmoid smoothing.
        """
        import math
        
        # Weights (sum to 1.0)
        weights = {
            'avg_logprob': 0.35,
            'no_speech_prob': 0.25,
            'segment_consistency': 0.15,
            'repetition_score': 0.15,
            'language_certainty': 0.10,
        }
        
        # Weighted average
        weighted_score = (
            factors.avg_logprob * weights['avg_logprob'] +
            factors.no_speech_prob * weights['no_speech_prob'] +
            factors.segment_consistency * weights['segment_consistency'] +
            factors.repetition_score * weights['repetition_score'] +
            factors.language_certainty * weights['language_certainty']
        )
        
        # Apply sigmoid for smooth 0-1 mapping
        # sigmoid(x) = 1 / (1 + e^-x)
        # We scale to peak around 0.5, so shift input
        shifted = (weighted_score - 0.5) * 4  # Scaling factor
        sigmoid_score = 1.0 / (1.0 + math.exp(-shifted))
        
        return min(1.0, max(0.0, sigmoid_score))
    
    def should_reject(
        self,
        transcript: str,
        confidence: float,
        no_speech_prob: float,
        avg_logprob: float,
        confidence_threshold: float = 0.5,
    ) -> tuple:
        """
        Determine if transcription should be rejected.
        
        Returns:
            Tuple of (should_reject, reason)
        """
        # Rule 1: Confidence too low
        if confidence < confidence_threshold:
            return True, f"Confidence {confidence:.2f} below threshold {confidence_threshold}"
        
        # Rule 2: No speech detected
        if no_speech_prob > self.NO_SPEECH_THRESHOLD:
            return True, f"No speech detected (prob={no_speech_prob:.3f})"
        
        # Rule 3: Empty transcript
        if not transcript or not transcript.strip():
            return True, "Empty transcript"
        
        # Rule 4: Extreme log probability
        if avg_logprob < -2.5:
            return True, f"Very low log probability: {avg_logprob:.2f}"
        
        return False, ""
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics from scoring history"""
        if not self.scores_history:
            return {
                "sample_count": 0,
                "average_score": 0.0,
                "min_score": 0.0,
                "max_score": 0.0,
                "median_score": 0.0,
            }
        
        import statistics
        scores = self.scores_history
        
        return {
            "sample_count": len(scores),
            "average_score": statistics.mean(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "median_score": statistics.median(scores),
            "stdev": statistics.stdev(scores) if len(scores) > 1 else 0.0,
        }
