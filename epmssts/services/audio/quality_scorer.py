"""
Quality scoring system for audio preprocessing.

Deterministic quality score based on signal characteristics.
"""

from dataclasses import dataclass
from typing import Optional

from .schemas import SignalMetrics
from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class QualityScoreBoundaries:
    """Thresholds for quality scoring."""
    
    # SNR thresholds (dB)
    snr_excellent: float = 25.0
    snr_good: float = 15.0
    snr_fair: float = 5.0
    
    # Clipping threshold (peak dBFS)
    max_peak_dbfs: float = -1.0
    clipping_penalty: float = 20.0
    
    # Silence ratio threshold
    max_silence_ratio: float = 0.50
    silence_penalty_per_percent: float = 0.5
    
    # Dynamic range (peak - RMS)
    min_dynamic_range: float = 10.0  # dB
    dynamic_range_penalty: float = 10.0
    
    # Duration bonus (seconds)
    optimal_duration_min: float = 3.0
    optimal_duration_max: float = 10.0
    short_duration_penalty: float = 10.0
    long_duration_penalty: float = 5.0


class QualityScorer:
    """Computes deterministic quality score for audio."""
    
    def __init__(self, boundaries: Optional[QualityScoreBoundaries] = None):
        """Initialize quality scorer with thresholds."""
        self.boundaries = boundaries or QualityScoreBoundaries()
    
    def score(
        self,
        metrics: SignalMetrics,
        silence_ratio: float,
        duration_seconds: float,
    ) -> int:
        """
        Compute quality score (0-100).
        
        Factors:
        - SNR quality (40 points)
        - Clipping detection (20 points)
        - Silence ratio (20 points)
        - Dynamic range (10 points)
        - Duration validity (10 points)
        
        Args:
            metrics: Extracted signal metrics
            silence_ratio: Ratio of silence frames (0-1)
            duration_seconds: Audio duration in seconds
        
        Returns:
            int: Quality score 0-100
        """
        try:
            score = 100.0
            penalties = {}
            
            # SNR scoring (40 points)
            snr_score = self._score_snr(metrics.snr_estimate)
            snr_penalty = 40.0 * (1.0 - snr_score)
            score -= snr_penalty
            penalties['snr'] = snr_penalty
            
            # Clipping detection (20 points)
            clipping_penalty = self._score_clipping(metrics.peak_dbfs)
            score -= clipping_penalty
            penalties['clipping'] = clipping_penalty
            
            # Silence ratio (20 points)
            silence_penalty = self._score_silence(silence_ratio)
            score -= silence_penalty
            penalties['silence'] = silence_penalty
            
            # Dynamic range (10 points)
            dynamic_range = metrics.peak_dbfs - metrics.rms_dbfs
            dr_penalty = self._score_dynamic_range(dynamic_range)
            score -= dr_penalty
            penalties['dynamic_range'] = dr_penalty
            
            # Duration validity (10 points)
            duration_penalty = self._score_duration(duration_seconds)
            score -= duration_penalty
            penalties['duration'] = duration_penalty
            
            # Clamp to 0-100
            final_score = max(0, min(100, int(score)))
            
            logger.debug(
                "Quality score computed",
                score=final_score,
                snr_estimate=metrics.snr_estimate,
                peak_dbfs=metrics.peak_dbfs,
                silence_ratio=silence_ratio,
                duration=duration_seconds,
                penalties=penalties
            )
            
            return final_score
        
        except Exception as e:
            logger.error("Quality scoring failed", exc=e)
            return 0
    
    def _score_snr(self, snr_db: float) -> float:
        """
        SNR score (0-1, higher is better).
        
        Excellent: >= 25dB → 1.0
        Good: >= 15dB → 0.75
        Fair: >= 5dB → 0.50
        Poor: < 5dB → 0.25
        """
        if snr_db >= self.boundaries.snr_excellent:
            return 1.0
        elif snr_db >= self.boundaries.snr_good:
            return 0.75
        elif snr_db >= self.boundaries.snr_fair:
            return 0.50
        else:
            return 0.25
    
    def _score_clipping(self, peak_dbfs: float) -> float:
        """
        Clipping penalty (0-20 points).
        
        No clipping: 0 points
        Slight clipping (-1 to -0.5 dBFS): 5 points
        Moderate clipping (-0.5 to 0 dBFS): 10 points
        Severe clipping (> 0 dBFS): 20 points
        """
        if peak_dbfs < -2.0:
            return 0.0
        elif peak_dbfs < -0.5:
            return 5.0
        elif peak_dbfs < 0.0:
            return 10.0
        else:
            return 20.0
    
    def _score_silence(self, silence_ratio: float) -> float:
        """
        Silence ratio penalty (0-20 points).
        
        Linear penalty from 0% silence (0 points) to 50% silence (10 points).
        Above 50%: Hard penalty of 20 points.
        """
        if silence_ratio > self.boundaries.max_silence_ratio:
            return 20.0
        
        penalty = silence_ratio * self.boundaries.silence_penalty_per_percent * 100
        return min(10.0, penalty)
    
    def _score_dynamic_range(self, dynamic_range_db: float) -> float:
        """
        Dynamic range penalty (0-10 points).
        
        Dynamic range = peak - RMS (in dB)
        
        Good (>= 10dB): 0 points
        Fair (>= 5dB): 5 points
        Poor (< 5dB): 10 points
        """
        if dynamic_range_db >= self.boundaries.min_dynamic_range:
            return 0.0
        elif dynamic_range_db >= 5.0:
            return 5.0
        else:
            return 10.0
    
    def _score_duration(self, duration_seconds: float) -> float:
        """
        Duration validity penalty (0-10 points).
        
        Optimal: 3-10 seconds → 0 points
        Short: < 3 seconds → 10 points
        Long: > 10 seconds → 5 points
        """
        if self.boundaries.optimal_duration_min <= duration_seconds <= self.boundaries.optimal_duration_max:
            return 0.0
        elif duration_seconds < self.boundaries.optimal_duration_min:
            return self.boundaries.short_duration_penalty
        else:
            return self.boundaries.long_duration_penalty
    
    def is_low_quality(self, quality_score: int, threshold: int = 50) -> bool:
        """Check if audio is low quality."""
        return quality_score < threshold
