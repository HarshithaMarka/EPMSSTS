"""
PHASE 4: PROSODY REALISM VALIDATOR
Prosody preservation guarantee for authentic speech

Purpose:
- Extract F0 contour, energy envelope, pause timestamps from original
- After synthesis: compute pitch correlation, energy correlation, pause timing
- Fail if: pitch correlation <0.75 OR energy correlation <0.70

Author: Realism Engineering
Date: 2026-03-02
"""

import json
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, List, Dict, Optional
import librosa
import soundfile as sf
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class ProsodyFeatures:
    """Prosody feature set for an audio sample."""
    f0_contour: np.ndarray  # Pitch in Hz
    energy_envelope: np.ndarray  # Energy over time
    pause_timestamps: List[Tuple[float, float]]  # List of (start, end) pause times
    duration: float
    mean_f0: float
    f0_range: Tuple[float, float]  # (min, max)
    mean_energy: float
    energy_range: Tuple[float, float]  # (min, max)


@dataclass
class ProsodyCorrelation:
    """Correlation metrics between original and synthesized."""
    pitch_correlation: float
    energy_correlation: float
    pause_preservation: float
    overall_prosody_score: float
    is_valid: bool
    reasons_failed: List[str]


class ProsodyExtractor:
    """Extract prosody features from audio."""
    
    def __init__(self, sr: int = 16000, fmin: int = 50, fmax: int = 400):
        self.sr = sr
        self.fmin = fmin
        self.fmax = fmax
        self.frame_length = 2048
        self.hop_length = 512
    
    def extract_features(self, audio: np.ndarray) -> ProsodyFeatures:
        """Extract complete prosody feature set."""
        
        # 1. Extract F0 using librosa.yin
        f0 = librosa.yin(
            audio,
            fmin=self.fmin,
            fmax=self.fmax,
            sr=self.sr,
            frame_length=int(0.025 * self.sr),  # 25ms frames
            hop_length=self.hop_length
        )
        
        # Handle NaN values (unvoiced frames)
        f0_clean = self._interpolate_f0(f0)
        
        # 2. Extract energy envelope
        S = librosa.feature.melspectrogram(y=audio, sr=self.sr, n_mels=128)
        energy = np.mean(S, axis=0)
        energy_db = librosa.power_to_db(energy, ref=1.0)
        
        # Smooth energy
        energy_smooth = self._smooth_signal(energy_db, window_size=5)
        
        # 3. Detect pauses (low energy regions)
        pause_threshold = np.percentile(energy_smooth, 25)
        pauses = self._detect_pauses(energy_smooth, pause_threshold)
        
        # 4. Compute statistics
        f0_voiced = f0_clean[f0_clean > self.fmin]
        mean_f0 = float(np.mean(f0_voiced)) if len(f0_voiced) > 0 else 0.0
        f0_range = (float(np.min(f0_voiced)), float(np.max(f0_voiced))) if len(f0_voiced) > 0 else (0.0, 0.0)
        
        mean_energy = float(np.mean(energy_smooth))
        energy_range = (float(np.min(energy_smooth)), float(np.max(energy_smooth)))
        
        duration = len(audio) / self.sr
        
        return ProsodyFeatures(
            f0_contour=f0_clean,
            energy_envelope=energy_smooth,
            pause_timestamps=pauses,
            duration=float(duration),
            mean_f0=mean_f0,
            f0_range=f0_range,
            mean_energy=mean_energy,
            energy_range=energy_range
        )
    
    def _interpolate_f0(self, f0: np.ndarray) -> np.ndarray:
        """Interpolate NaN values in F0 contour."""
        f0_copy = f0.copy()
        
        # Find valid frames
        valid_mask = ~np.isnan(f0_copy)
        
        # If all NaN, return zeros
        if np.sum(valid_mask) == 0:
            return np.zeros_like(f0_copy)
        
        # Linear interpolation
        indices = np.arange(len(f0_copy))
        f0_interp = np.interp(indices, indices[valid_mask], f0_copy[valid_mask])
        
        return f0_interp
    
    def _smooth_signal(self, signal: np.ndarray, window_size: int = 5) -> np.ndarray:
        """Smooth signal with moving average."""
        from scipy.ndimage import uniform_filter1d
        return uniform_filter1d(signal, size=window_size, mode='nearest')
    
    def _detect_pauses(self, energy: np.ndarray, threshold: float) -> List[Tuple[float, float]]:
        """Detect pauses (periods of low energy)."""
        
        is_pause = energy < threshold
        
        # Find contiguous pause regions
        pauses = []
        in_pause = False
        start_idx = 0
        
        for i, val in enumerate(is_pause):
            if val and not in_pause:
                start_idx = i
                in_pause = True
            elif not val and in_pause:
                # Pause ended
                start_time = start_idx * self.hop_length / self.sr
                end_time = i * self.hop_length / self.sr
                
                # Only include pauses longer than 100ms
                if (end_time - start_time) > 0.1:
                    pauses.append((start_time, end_time))
                
                in_pause = False
        
        return pauses


class ProsodyComparator:
    """Compare prosody between original and synthesized."""
    
    @staticmethod
    def compare(original: ProsodyFeatures, synthesized: ProsodyFeatures) -> ProsodyCorrelation:
        """
        Compare prosody features.
        
        Thresholds:
        - pitch_correlation >= 0.75
        - energy_correlation >= 0.70
        """
        
        reasons_failed = []
        
        # 1. Compare F0 contours
        # Align contours if different lengths
        f0_orig, f0_syn = ProsodyComparator._align_contours(
            original.f0_contour,
            synthesized.f0_contour
        )
        
        pitch_correlation = ProsodyComparator._correlation_coefficient(f0_orig, f0_syn)
        if np.isnan(pitch_correlation):
            pitch_correlation = 0.0
        
        if pitch_correlation < 0.75:
            reasons_failed.append(f"Pitch correlation {pitch_correlation:.3f} < 0.75")
        
        # 2. Compare energy envelopes
        energy_orig, energy_syn = ProsodyComparator._align_contours(
            original.energy_envelope,
            synthesized.energy_envelope
        )
        
        energy_correlation = ProsodyComparator._correlation_coefficient(energy_orig, energy_syn)
        if np.isnan(energy_correlation):
            energy_correlation = 0.0
        
        if energy_correlation < 0.70:
            reasons_failed.append(f"Energy correlation {energy_correlation:.3f} < 0.70")
        
        # 3. Compare pause timing
        pause_preservation = ProsodyComparator._compare_pauses(
            original.pause_timestamps,
            synthesized.pause_timestamps
        )
        
        # Overall score
        overall_score = float((pitch_correlation + energy_correlation) / 2)
        
        is_valid = len(reasons_failed) == 0
        
        return ProsodyCorrelation(
            pitch_correlation=float(pitch_correlation),
            energy_correlation=float(energy_correlation),
            pause_preservation=float(pause_preservation),
            overall_prosody_score=overall_score,
            is_valid=is_valid,
            reasons_failed=reasons_failed
        )
    
    @staticmethod
    def _align_contours(c1: np.ndarray, c2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Align contours to same length."""
        min_len = min(len(c1), len(c2))
        return c1[:min_len], c2[:min_len]
    
    @staticmethod
    def _correlation_coefficient(x: np.ndarray, y: np.ndarray) -> float:
        """Compute Pearson correlation coefficient."""
        if len(x) < 2 or len(y) < 2:
            return 0.0
        
        x = x.astype(np.float32)
        y = y.astype(np.float32)
        
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        
        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sqrt(np.sum((x - x_mean) ** 2) * np.sum((y - y_mean) ** 2))
        
        if denominator < 1e-8:
            return 0.0
        
        return float(numerator / denominator)
    
    @staticmethod
    def _compare_pauses(pauses_orig: List[Tuple[float, float]],
                       pauses_syn: List[Tuple[float, float]]) -> float:
        """
        Compare pause structures.
        
        Returns:
            Score 0-1 indicating pause preservation quality
        """
        
        if len(pauses_orig) == 0 and len(pauses_syn) == 0:
            return 1.0  # Both have no pauses
        
        if len(pauses_orig) == 0 or len(pauses_syn) == 0:
            return 0.5  # One has pauses, other doesn't
        
        # Compute overlap score
        total_orig_duration = sum(end - start for start, end in pauses_orig)
        
        overlap = 0.0
        for orig_start, orig_end in pauses_orig:
            for syn_start, syn_end in pauses_syn:
                overlap_start = max(orig_start, syn_start)
                overlap_end = min(orig_end, syn_end)
                if overlap_end > overlap_start:
                    overlap += (overlap_end - overlap_start)
        
        preservation_score = overlap / total_orig_duration if total_orig_duration > 0 else 0.0
        
        return float(np.clip(preservation_score, 0.0, 1.0))


class ProsodyRealismValidator:
    """Complete prosody validation pipeline."""
    
    def __init__(self, sr: int = 16000, output_dir: Optional[Path] = None):
        self.sr = sr
        self.output_dir = output_dir or Path("outputs/v3_realism")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.extractor = ProsodyExtractor(sr=sr)
        self.comparator = ProsodyComparator()
        
        self.results: List[Dict] = []
    
    def validate_sample_pair(self,
                           original_audio_path: str,
                           synthesized_audio_path: str,
                           sample_id: str = "") -> ProsodyCorrelation:
        """
        Validate prosody preservation for audio pair.
        
        Args:
            original_audio_path: Path to original audio
            synthesized_audio_path: Path to synthesized audio
            sample_id: Sample identifier
            
        Returns:
            ProsodyCorrelation result
        """
        
        try:
            # Load audio files
            audio_orig, _ = librosa.load(original_audio_path, sr=self.sr)
            audio_syn, _ = librosa.load(synthesized_audio_path, sr=self.sr)
            
            # Extract features
            features_orig = self.extractor.extract_features(audio_orig)
            features_syn = self.extractor.extract_features(audio_syn)
            
            # Compare
            correlation = self.comparator.compare(features_orig, features_syn)
            
            # Store result
            result = {
                'sample_id': sample_id,
                'original_file': Path(original_audio_path).name,
                'synthesized_file': Path(synthesized_audio_path).name,
                'pitch_correlation': correlation.pitch_correlation,
                'energy_correlation': correlation.energy_correlation,
                'pause_preservation': correlation.pause_preservation,
                'overall_prosody_score': correlation.overall_prosody_score,
                'is_valid': correlation.is_valid,
                'reasons_failed': correlation.reasons_failed,
                'original_prosody': {
                    'mean_f0': features_orig.mean_f0,
                    'f0_range': features_orig.f0_range,
                    'mean_energy': features_orig.mean_energy,
                    'pause_count': len(features_orig.pause_timestamps)
                },
                'synthesized_prosody': {
                    'mean_f0': features_syn.mean_f0,
                    'f0_range': features_syn.f0_range,
                    'mean_energy': features_syn.mean_energy,
                    'pause_count': len(features_syn.pause_timestamps)
                }
            }
            
            self.results.append(result)
            
            return correlation
            
        except Exception as e:
            logger.error(f"Error validating {sample_id}: {e}")
            return ProsodyCorrelation(
                pitch_correlation=0.0,
                energy_correlation=0.0,
                pause_preservation=0.0,
                overall_prosody_score=0.0,
                is_valid=False,
                reasons_failed=[str(e)]
            )
    
    def generate_prosody_report(self, output_file: Optional[str] = None) -> Dict:
        """Generate PROSODY_REALISM_REPORT.json"""
        
        valid_samples = [r for r in self.results if r['is_valid']]
        invalid_samples = [r for r in self.results if not r['is_valid']]
        
        # Compute statistics
        if valid_samples:
            pitch_cors = [r['pitch_correlation'] for r in valid_samples]
            energy_cors = [r['energy_correlation'] for r in valid_samples]
            prosody_scores = [r['overall_prosody_score'] for r in valid_samples]
        else:
            pitch_cors = energy_cors = prosody_scores = []
        
        report = {
            'timestamp': str(np.datetime64('now')),
            'total_samples': len(self.results),
            'valid_samples': len(valid_samples),
            'invalid_samples': len(invalid_samples),
            'pass_rate': float(len(valid_samples) / len(self.results)) if self.results else 0.0,
            'pitch_correlation': {
                'mean': float(np.mean(pitch_cors)) if pitch_cors else 0.0,
                'min': float(np.min(pitch_cors)) if pitch_cors else 0.0,
                'max': float(np.max(pitch_cors)) if pitch_cors else 0.0,
                'threshold': 0.75
            },
            'energy_correlation': {
                'mean': float(np.mean(energy_cors)) if energy_cors else 0.0,
                'min': float(np.min(energy_cors)) if energy_cors else 0.0,
                'max': float(np.max(energy_cors)) if energy_cors else 0.0,
                'threshold': 0.70
            },
            'overall_prosody_score': {
                'mean': float(np.mean(prosody_scores)) if prosody_scores else 0.0,
                'min': float(np.min(prosody_scores)) if prosody_scores else 0.0,
                'max': float(np.max(prosody_scores)) if prosody_scores else 0.0
            },
            'samples': self.results
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
    validator = ProsodyRealismValidator()
    
    print("Prosody Realism Validator initialized")
    print("Ready to validate audio prosody preservation")
    print("\nThresholds:")
    print("  Pitch correlation: >= 0.75")
    print("  Energy correlation: >= 0.70")
