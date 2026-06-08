"""
PHASE 4: WAVEFORM-LEVEL PROSODY VALIDATION
Real F0, energy, and pause preservation analysis

Purpose:
- Extract F0 contours from waveforms (source vs synthesized)
- Compare energy envelopes
- Validate pause timing alignment
- Compute correlations: pitch >= 0.75, energy >= 0.70, pauses >= 80%
- Generate PROSODY_REALISM_REPORT.json

Author: Production Hardening
Date: 2026-03-02
"""

import json
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import librosa
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProsodyMetrics:
    """Prosody metrics for a waveform pair."""
    source_file: str
    synthesis_file: str
    f0_source: np.ndarray
    f0_synthesis: np.ndarray
    energy_source: np.ndarray
    energy_synthesis: np.ndarray
    pauses_source: List[Tuple[float, float]]
    pauses_synthesis: List[Tuple[float, float]]
    pitch_correlation: float
    energy_correlation: float
    pause_alignment: float
    overall_score: float


class WaveformProsodyValidator:
    """
    Extract and validate prosody from real waveforms.
    
    F0 extraction via librosa.yin
    Energy via mel-spectrogram
    Pauses via energy thresholding
    """
    
    def __init__(self, sr: int = 16000):
        self.sr = sr
        self.results: List[Dict] = []
    
    def extract_f0_contour(self, audio: np.ndarray,
                          fmin: float = 50,
                          fmax: float = 400) -> np.ndarray:
        """Extract F0 contour using librosa.yin."""
        
        f0 = librosa.yin(
            audio,
            fmin=fmin,
            fmax=fmax,
            sr=self.sr,
            frame_length=int(0.025 * self.sr)
        )
        
        # Interpolate NaN values (unvoiced frames)
        f0_interp = self._interpolate_nan(f0)
        
        return f0_interp
    
    def extract_energy_envelope(self, audio: np.ndarray) -> np.ndarray:
        """Extract smoothed energy envelope."""
        
        S = librosa.feature.melspectrogram(y=audio, sr=self.sr, n_mels=128)
        energy = np.mean(S, axis=0)
        energy_db = librosa.power_to_db(energy, ref=1.0)
        
        # Smooth
        from scipy.ndimage import uniform_filter1d
        energy_smooth = uniform_filter1d(energy_db, size=5, mode='nearest')
        
        return energy_smooth
    
    def detect_pauses(self, audio: np.ndarray,
                     percentile: int = 25) -> List[Tuple[float, float]]:
        """Detect pause regions (low energy >200ms)."""
        
        S = librosa.feature.melspectrogram(y=audio, sr=self.sr, n_mels=64)
        energy = np.mean(S, axis=0)
        energy_db = librosa.power_to_db(energy, ref=1.0)
        
        threshold = np.percentile(energy_db, percentile)
        is_pause = energy_db < threshold
        
        # Find pause blocks
        pauses = []
        hop_length = 512
        in_pause = False
        start_idx = 0
        
        for i, val in enumerate(is_pause):
            if val and not in_pause:
                start_idx = i
                in_pause = True
            elif not val and in_pause:
                start_time = start_idx * hop_length / self.sr
                end_time = i * hop_length / self.sr
                
                # Only pauses >200ms
                if (end_time - start_time) > 0.20:
                    pauses.append((start_time, end_time))
                
                in_pause = False
        
        return pauses
    
    def compare_waveform_pair(self,
                             source_audio: np.ndarray,
                             synthesis_audio: np.ndarray) -> Dict:
        """
        Compare prosody between source and synthesis.
        
        Returns:
            Dict with pitch, energy, pause correlations
        """
        
        # Extract features
        f0_src = self.extract_f0_contour(source_audio)
        f0_syn = self.extract_f0_contour(synthesis_audio)
        
        energy_src = self.extract_energy_envelope(source_audio)
        energy_syn = self.extract_energy_envelope(synthesis_audio)
        
        pauses_src = self.detect_pauses(source_audio)
        pauses_syn = self.detect_pauses(synthesis_audio)
        
        # Align contours
        f0_src_aligned, f0_syn_aligned = self._align_contours(f0_src, f0_syn)
        energy_src_aligned, energy_syn_aligned = self._align_contours(energy_src, energy_syn)
        
        # Compute correlations
        pitch_corr = self._pearson_correlation(f0_src_aligned, f0_syn_aligned)
        energy_corr = self._pearson_correlation(energy_src_aligned, energy_syn_aligned)
        pause_align = self._pause_alignment_score(pauses_src, pauses_syn)
        
        # Overall score
        overall = float((pitch_corr + energy_corr + pause_align) / 3)
        
        # Validation
        passes = (
            pitch_corr >= 0.75 and
            energy_corr >= 0.70 and
            pause_align >= 0.80
        )
        
        result = {
            'pitch_correlation': float(pitch_corr),
            'energy_correlation': float(energy_corr),
            'pause_alignment': float(pause_align),
            'overall_score': float(overall),
            'passes_validation': passes,
            'reasons_failed': []
        }
        
        if pitch_corr < 0.75:
            result['reasons_failed'].append(f"Pitch {pitch_corr:.3f} < 0.75")
        if energy_corr < 0.70:
            result['reasons_failed'].append(f"Energy {energy_corr:.3f} < 0.70")
        if pause_align < 0.80:
            result['reasons_failed'].append(f"Pauses {pause_align:.1%} < 80%")
        
        self.results.append(result)
        
        return result
    
    @staticmethod
    def _interpolate_nan(arr: np.ndarray) -> np.ndarray:
        """Interpolate NaN values."""
        mask = ~np.isnan(arr)
        if np.sum(mask) == 0:
            return np.zeros_like(arr)
        
        indices = np.arange(len(arr))
        arr_interp = np.interp(indices, indices[mask], arr[mask])
        
        return arr_interp
    
    @staticmethod
    def _align_contours(c1: np.ndarray, c2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Align contours to same length."""
        min_len = min(len(c1), len(c2))
        return c1[:min_len], c2[:min_len]
    
    @staticmethod
    def _pearson_correlation(x: np.ndarray, y: np.ndarray) -> float:
        """Compute Pearson correlation coefficient."""
        if len(x) < 2 or len(y) < 2:
            return 0.0
        
        x = np.asarray(x, dtype=np.float32)
        y = np.asarray(y, dtype=np.float32)
        
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        
        num = np.sum((x - x_mean) * (y - y_mean))
        denom = np.sqrt(np.sum((x - x_mean) ** 2) * np.sum((y - y_mean) ** 2))
        
        if denom < 1e-8:
            return 0.0
        
        return float(np.clip(num / denom, -1.0, 1.0))
    
    @staticmethod
    def _pause_alignment_score(pauses1: List[Tuple[float, float]],
                              pauses2: List[Tuple[float, float]]) -> float:
        """Score pause structure alignment."""
        
        if len(pauses1) == 0 and len(pauses2) == 0:
            return 1.0
        
        if len(pauses1) == 0 or len(pauses2) == 0:
            return 0.3
        
        # Compute overlap
        total_duration = sum(end - start for start, end in pauses1)
        overlap = 0.0
        
        for s1, e1 in pauses1:
            for s2, e2 in pauses2:
                overlap_start = max(s1, s2)
                overlap_end = min(e1, e2)
                if overlap_end > overlap_start:
                    overlap += (overlap_end - overlap_start)
        
        if total_duration == 0:
            return 0.0
        
        return float(min(1.0, overlap / total_duration))
    
    def generate_prosody_report(self, output_file: Optional[str] = None) -> Dict:
        """Generate PROSODY_REALISM_REPORT.json"""
        
        if not self.results:
            return {'status': 'NO_DATA', 'results': []}
        
        # Aggregate
        pitch_corrs = [r['pitch_correlation'] for r in self.results]
        energy_corrs = [r['energy_correlation'] for r in self.results]
        pause_aligns = [r['pause_alignment'] for r in self.results]
        
        pass_count = sum(1 for r in self.results if r['passes_validation'])
        
        report = {
            'timestamp': str(np.datetime64('now')),
            'total_samples': len(self.results),
            'samples_passed': pass_count,
            'pass_rate': float(pass_count / len(self.results)) if self.results else 0.0,
            'pitch_correlation': {
                'mean': float(np.mean(pitch_corrs)),
                'std': float(np.std(pitch_corrs)),
                'min': float(np.min(pitch_corrs)),
                'threshold': 0.75
            },
            'energy_correlation': {
                'mean': float(np.mean(energy_corrs)),
                'std': float(np.std(energy_corrs)),
                'min': float(np.min(energy_corrs)),
                'threshold': 0.70
            },
            'pause_alignment': {
                'mean': float(np.mean(pause_aligns)),
                'std': float(np.std(pause_aligns)),
                'min': float(np.min(pause_aligns)),
                'threshold': 0.80
            },
            'validation_thresholds': {
                'pitch_correlation_minimum': 0.75,
                'energy_correlation_minimum': 0.70,
                'pause_alignment_minimum': 0.80
            },
            'results': self.results
        }
        
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"✓ Prosody report saved: {output_file}")
        
        return report


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    validator = WaveformProsodyValidator(sr=16000)
    
    # Create synthetic test pair
    logger.info("Creating synthetic test audio pair...")
    sr = validator.sr
    duration = 3
    t = np.linspace(0, duration, int(sr * duration))
    
    # Source
    source = np.sin(2 * np.pi * 100 * t) * 0.2 + 0.05 * np.random.randn(len(t))
    
    # Synthesis (similar)
    synthesis = np.sin(2 * np.pi * 102 * t) * 0.22 + 0.06 * np.random.randn(len(t))
    
    result = validator.compare_waveform_pair(source, synthesis)
    
    logger.info(f"\nProsody Comparison:")
    logger.info(f"  Pitch correlation: {result['pitch_correlation']:.3f} (threshold: 0.75)")
    logger.info(f"  Energy correlation: {result['energy_correlation']:.3f} (threshold: 0.70)")
    logger.info(f"  Pause alignment: {result['pause_alignment']:.1%} (threshold: 80%)")
    logger.info(f"  Passes: {result['passes_validation']}")
    
    report = validator.generate_prosody_report(
        "outputs/production/PROSODY_REALISM_REPORT.json"
    )
    
    logger.info(f"\n✓ Prosody validation complete")
