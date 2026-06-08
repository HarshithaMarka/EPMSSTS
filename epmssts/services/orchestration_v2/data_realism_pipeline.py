"""
PHASE 1: DATA REALISM PIPELINE
Audio Cleaning and Normalization for Production Realism

Purpose:
- Auto silence trimming with adaptive energy thresholds
- Duration normalization (3-6 seconds) with intelligent cropping
- RMS band calibration (preserve emotional contours)
- Honest quality scoring (reject only invalid samples)

Author: Realism Engineering
Date: 2026-03-02
"""

import json
import numpy as np
from dataclasses import dataclass
from typing import Tuple, Dict, List, Optional
import librosa
import soundfile as sf
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class RMSBandInfo:
    """RMS band classification."""
    band: str  # 'very_low', 'low', 'normal', 'high'
    rms_dbfs: float
    rms_linear: float
    speech_ratio: float
    duration: float


@dataclass
class QualityScore:
    """Quality assessment for audio sample."""
    is_valid: bool
    reasons_rejected: List[str]
    speech_ratio: float
    clipping_ratio: float
    duration: float
    rms_band: str
    rms_dbfs: float
    confidence: float


class SilenceDetector:
    """Adaptive silence detection using energy thresholds."""
    
    def __init__(self, sr: int = 16000, frame_length: int = 2048):
        self.sr = sr
        self.frame_length = frame_length
        self.hop_length = frame_length // 4
    
    def detect_silence(
        self, 
        audio: np.ndarray, 
        percentile: int = 10
    ) -> Tuple[np.ndarray, float, float]:
        """
        Detect silence using adaptive energy threshold.
        
        Args:
            audio: waveform [n_samples]
            percentile: threshold percentile for silence detection
            
        Returns:
            is_silent: [n_frames] boolean array
            threshold_db: threshold in dBFS
            mean_energy_db: mean energy in dBFS
        """
        # Compute frame energy
        S = librosa.feature.melspectrogram(y=audio, sr=self.sr, n_mels=128)
        energy = np.mean(S, axis=0)  # [n_frames]
        energy_db = librosa.power_to_db(energy, ref=1.0)
        
        # Adaptive threshold: percentile-based
        threshold_db = np.percentile(energy_db, percentile)
        is_silent = energy_db < threshold_db
        
        mean_energy_db = np.mean(energy_db)
        
        return is_silent, threshold_db, mean_energy_db
    
    def trim_silence(
        self,
        audio: np.ndarray,
        margin_ms: int = 100
    ) -> Tuple[np.ndarray, int, int]:
        """
        Remove leading/trailing silence.
        
        Args:
            audio: waveform
            margin_ms: keep margin after silence edge
            
        Returns:
            trimmed_audio: silence removed
            start_sample: where trimming started
            end_sample: where trimming ended
        """
        # Detect silence
        is_silent, _, _ = self.detect_silence(audio, percentile=10)
        
        # Convert to sample indices
        frame_to_sample = lambda f: f * self.hop_length
        
        # Find first non-silent frame
        non_silent_frames = np.where(~is_silent)[0]
        if len(non_silent_frames) == 0:
            return audio, 0, len(audio)  # All silent
        
        start_frame = max(0, non_silent_frames[0] - margin_ms * self.sr // 1000 // self.hop_length)
        end_frame = min(len(is_silent) - 1, non_silent_frames[-1] + margin_ms * self.sr // 1000 // self.hop_length)
        
        start_sample = frame_to_sample(start_frame)
        end_sample = frame_to_sample(end_frame)
        
        trimmed = audio[start_sample:end_sample]
        
        return trimmed, start_sample, end_sample
    
    def remove_internal_silence(
        self,
        audio: np.ndarray,
        max_silence_duration_ms: int = 600
    ) -> Tuple[np.ndarray, int]:
        """
        Remove internal silence >600ms.
        
        Args:
            audio: waveform
            max_silence_duration_ms: max allowed silence gap
            
        Returns:
            audio_compressed: silence removed
            compressed_frames: number of frames removed
        """
        is_silent, _, _ = self.detect_silence(audio, percentile=20)
        
        max_frames = max_silence_duration_ms * self.sr // 1000 // self.hop_length
        
        # Find silence blocks
        silence_blocks = self._find_blocks(is_silent)
        
        audio_out = []
        total_removed = 0
        
        prev_end = 0
        for start, end in silence_blocks:
            if (end - start) <= max_frames:
                # Keep short silence
                block_start_sample = start * self.hop_length
                block_end_sample = end * self.hop_length
                audio_out.append(audio[prev_end:block_end_sample])
                prev_end = block_end_sample
            else:
                # Skip long silence
                block_start_sample = start * self.hop_length
                audio_out.append(audio[prev_end:block_start_sample])
                prev_end = end * self.hop_length
                total_removed += (end - start)
        
        audio_out.append(audio[prev_end:])
        audio_compressed = np.concatenate(audio_out)
        
        return audio_compressed, total_removed
    
    @staticmethod
    def _find_blocks(is_silent: np.ndarray) -> List[Tuple[int, int]]:
        """Find contiguous silence blocks."""
        blocks = []
        in_block = False
        start = 0
        
        for i, val in enumerate(is_silent):
            if val and not in_block:
                start = i
                in_block = True
            elif not val and in_block:
                blocks.append((start, i))
                in_block = False
        
        if in_block:
            blocks.append((start, len(is_silent)))
        
        return blocks


class DurationNormalizer:
    """Duration normalization with intelligent cropping."""
    
    def __init__(self, sr: int = 16000, target_duration_s: Tuple[float, float] = (3.0, 6.0)):
        self.sr = sr
        self.target_min = int(target_duration_s[0] * sr)
        self.target_max = int(target_duration_s[1] * sr)
    
    def normalize(self, audio: np.ndarray) -> Tuple[np.ndarray, str]:
        """
        Normalize duration to 3-6 seconds.
        
        Args:
            audio: waveform
            
        Returns:
            normalized_audio: cropped/set audio
            action: 'kept', 'cropped', 'padded'
        """
        current_samples = len(audio)
        
        if self.target_min <= current_samples <= self.target_max:
            return audio, "kept"
        
        if current_samples < self.target_min:
            # Pad with silence
            pad_samples = self.target_min - current_samples
            audio = np.pad(audio, (0, pad_samples), mode='constant')
            return audio, "padded"
        
        # Crop to center of highest energy region
        audio_cropped = self._intelligent_crop(audio)
        return audio_cropped, "cropped"
    
    def _intelligent_crop(self, audio: np.ndarray) -> np.ndarray:
        """
        Intelligently crop by finding highest energy + speech density region.
        """
        # Compute frame energy
        S = librosa.feature.melspectrogram(y=audio, sr=self.sr, n_mels=64)
        energy = np.mean(S, axis=0)
        
        # Smooth energy curve
        energy_smooth = np.convolve(energy, np.ones(10) / 10, mode='same')
        
        # Find peak region
        frame_length = 2048
        hop_length = frame_length // 4
        target_frames = self.target_max // hop_length
        
        # Compute energy-weighted position for center of window
        frame_scores = np.maximum(0, energy_smooth)
        cumsum = np.cumsum(frame_scores)
        total_energy = cumsum[-1]
        
        if total_energy == 0:
            # Fallback: crop from start
            end_frame = min(len(energy), target_frames)
            return audio[:end_frame * hop_length]
        
        # Find position where we capture 50% of energy
        mid_energy = total_energy / 2
        mid_frame = np.searchsorted(cumsum, mid_energy)
        mid_frame = max(target_frames // 2, min(mid_frame, len(energy) - target_frames // 2))
        
        start_frame = max(0, mid_frame - target_frames // 2)
        end_frame = min(len(energy), start_frame + target_frames)
        
        start_sample = start_frame * hop_length
        end_sample = end_frame * hop_length
        
        return audio[start_sample:end_sample]


class RMSBandCalibrator:
    """RMS band calibration without peak normalization."""
    
    def __init__(self, sr: int = 16000):
        self.sr = sr
        self.band_thresholds = {
            'very_low': (-80, -50),    # dBFS range
            'low': (-50, -30),
            'normal': (-30, -10),
            'high': (-10, 0)
        }
        self.band_targets = {
            'very_low': -65,
            'low': -35,
            'normal': -20,
            'high': -5
        }
    
    def compute_rms_band(self, audio: np.ndarray) -> RMSBandInfo:
        """Compute RMS and assign band."""
        rms_linear = np.sqrt(np.mean(audio ** 2))
        rms_dbfs = 20 * np.log10(rms_linear + 1e-8)
        
        # Assign band
        band = 'normal'
        for b, (low, high) in self.band_thresholds.items():
            if low <= rms_dbfs < high:
                band = b
                break
        
        # Compute speech ratio (non-silent frames)
        S = librosa.feature.melspectrogram(y=audio, sr=self.sr)
        energy = np.mean(S, axis=0)
        energy_db = librosa.power_to_db(energy, ref=1.0)
        threshold = np.percentile(energy_db, 20)
        speech_ratio = np.sum(energy_db > threshold) / len(energy)
        
        duration = len(audio) / self.sr
        
        return RMSBandInfo(
            band=band,
            rms_dbfs=float(rms_dbfs),
            rms_linear=float(rms_linear),
            speech_ratio=float(speech_ratio),
            duration=float(duration)
        )
    
    def normalize_within_band(self, audio: np.ndarray, band: str) -> np.ndarray:
        """
        Normalize within RMS band WITHOUT peak normalization.
        
        Preserves emotional energy contours.
        """
        rms_info = self.compute_rms_band(audio)
        
        if rms_info.rms_linear < 1e-8:
            return audio
        
        target_db = self.band_targets[band]
        current_db = rms_info.rms_dbfs
        
        # Compute gain to reach target
        gain_db = target_db - current_db
        gain_linear = 10 ** (gain_db / 20)
        
        # Apply gain with saturation prevention (soft clipping)
        audio_normalized = audio * gain_linear
        
        # Soft clipping to prevent harsh artifacts
        threshold = 0.99
        mask = np.abs(audio_normalized) > threshold
        if np.any(mask):
            audio_normalized[mask] = threshold * np.sign(audio_normalized[mask])
        
        return audio_normalized.astype(np.float32)


class QualityValidator:
    """Honest quality assessment."""
    
    def __init__(self, sr: int = 16000):
        self.sr = sr
    
    def validate(self, audio: np.ndarray, audio_path: str = "") -> QualityScore:
        """
        Validate audio with honest pass/fail criteria.
        
        Reject ONLY if:
        - Speech ratio <60%
        - Clipping detected >1%
        - Duration <2.5s
        """
        reasons = []
        
        # Check duration
        duration = len(audio) / self.sr
        if duration < 2.5:
            reasons.append(f"Duration too short: {duration:.2f}s < 2.5s")
        
        # Compute speech ratio
        S = librosa.feature.melspectrogram(y=audio, sr=self.sr)
        energy = np.mean(S, axis=0)
        energy_db = librosa.power_to_db(energy, ref=1.0)
        threshold = np.percentile(energy_db, 20)
        speech_ratio = np.sum(energy_db > threshold) / len(energy)
        
        if speech_ratio < 0.60:
            reasons.append(f"Speech ratio too low: {speech_ratio:.1%} < 60%")
        
        # Check for clipping
        clipping_threshold = 0.99
        clipped_samples = np.sum(np.abs(audio) > clipping_threshold)
        clipping_ratio = clipped_samples / len(audio)
        
        if clipping_ratio > 0.01:
            reasons.append(f"Clipping detected: {clipping_ratio:.2%} > 1%")
        
        # RMS band classification
        rms_linear = np.sqrt(np.mean(audio ** 2))
        rms_dbfs = 20 * np.log10(rms_linear + 1e-8)
        
        band = 'normal'
        for b, (low, high) in {
            'very_low': (-80, -50),
            'low': (-50, -30),
            'normal': (-30, -10),
            'high': (-10, 0)
        }.items():
            if low <= rms_dbfs < high:
                band = b
                break
        
        is_valid = len(reasons) == 0
        confidence = 0.9 if is_valid else 0.1
        
        return QualityScore(
            is_valid=is_valid,
            reasons_rejected=reasons,
            speech_ratio=float(speech_ratio),
            clipping_ratio=float(clipping_ratio),
            duration=float(duration),
            rms_band=band,
            rms_dbfs=float(rms_dbfs),
            confidence=float(confidence)
        )


class DataRealismPipeline:
    """Complete data realism pipeline."""
    
    def __init__(self, sr: int = 16000, output_dir: Optional[Path] = None):
        self.sr = sr
        self.output_dir = output_dir or Path("outputs/data_realism")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.silence_detector = SilenceDetector(sr=sr)
        self.duration_normalizer = DurationNormalizer(sr=sr)
        self.rms_calibrator = RMSBandCalibrator(sr=sr)
        self.quality_validator = QualityValidator(sr=sr)
        
        self.processed_samples = []
    
    def process_sample(self, audio_path: str, save_cleaned: bool = False) -> Dict:
        """
        Process single audio sample through full pipeline.
        
        Returns:
            result dict with all metrics
        """
        try:
            # Load audio
            audio, _ = librosa.load(audio_path, sr=self.sr)
            original_length = len(audio)
            
            # Phase 1: Trim silence
            audio_trimmed, _, _ = self.silence_detector.trim_silence(audio)
            
            # Phase 2: Remove internal silence
            audio_compressed, _ = self.silence_detector.remove_internal_silence(audio_trimmed)
            
            # Phase 3: Normalize duration
            audio_normalized, duration_action = self.duration_normalizer.normalize(audio_compressed)
            
            # Phase 4: RMS calibration
            rms_info = self.rms_calibrator.compute_rms_band(audio_normalized)
            audio_calibrated = self.rms_calibrator.normalize_within_band(
                audio_normalized, rms_info.band
            )
            
            # Phase 5: Quality validation
            quality = self.quality_validator.validate(audio_calibrated, audio_path)
            
            result = {
                'file': Path(audio_path).name,
                'original_samples': int(original_length),
                'original_duration_s': float(original_length / self.sr),
                'trimmed_samples': int(len(audio_trimmed)),
                'compressed_samples': int(len(audio_compressed)),
                'normalized_samples': int(len(audio_normalized)),
                'final_samples': int(len(audio_calibrated)),
                'final_duration_s': float(len(audio_calibrated) / self.sr),
                'duration_action': duration_action,
                'rms_band': rms_info.band,
                'rms_dbfs': rms_info.rms_dbfs,
                'rms_linear': rms_info.rms_linear,
                'speech_ratio': float(rms_info.speech_ratio),
                'quality': {
                    'is_valid': quality.is_valid,
                    'reasons_rejected': quality.reasons_rejected,
                    'speech_ratio': quality.speech_ratio,
                    'clipping_ratio': quality.clipping_ratio,
                    'duration': quality.duration,
                    'rms_band': quality.rms_band,
                    'rms_dbfs': quality.rms_dbfs,
                    'confidence': quality.confidence
                },
                'status': 'PASS' if quality.is_valid else 'FAIL'
            }
            
            # Save cleaned audio
            if save_cleaned and quality.is_valid:
                output_path = self.output_dir / f"cleaned_{Path(audio_path).name}"
                sf.write(str(output_path), audio_calibrated, self.sr)
                result['output_path'] = str(output_path)
            
            self.processed_samples.append(result)
            return result
            
        except Exception as e:
            return {
                'file': Path(audio_path).name,
                'status': 'ERROR',
                'error': str(e)
            }
    
    def generate_report(self, output_file: Optional[str] = None) -> Dict:
        """Generate DATA_REALISM_REPORT.json"""
        
        valid_samples = [s for s in self.processed_samples if s.get('status') == 'PASS']
        fail_samples = [s for s in self.processed_samples if s.get('status') == 'FAIL']
        error_samples = [s for s in self.processed_samples if s.get('status') == 'ERROR']
        
        report = {
            'timestamp': str(np.datetime64('now')),
            'total_samples': len(self.processed_samples),
            'valid_samples': len(valid_samples),
            'failed_samples': len(fail_samples),
            'error_samples': len(error_samples),
            'pass_rate': float(len(valid_samples) / len(self.processed_samples)) if self.processed_samples else 0.0,
            'samples': self.processed_samples,
            'summary': {
                'mean_final_duration_s': float(np.mean([s['final_duration_s'] for s in valid_samples])) if valid_samples else 0.0,
                'mean_rms_dbfs': float(np.mean([s['rms_dbfs'] for s in valid_samples])) if valid_samples else 0.0,
                'mean_speech_ratio': float(np.mean([s['speech_ratio'] for s in valid_samples])) if valid_samples else 0.0,
            }
        }
        
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
        
        return report


# Example usage
if __name__ == "__main__":
    pipeline = DataRealismPipeline()
    
    # Find test audio files
    test_audio_dir = Path("outputs")
    audio_files = list(test_audio_dir.glob("**/*.wav")) + list(test_audio_dir.glob("**/*.mp3"))
    
    if audio_files:
        for audio_file in audio_files[:5]:  # Process first 5
            print(f"Processing {audio_file.name}...")
            result = pipeline.process_sample(str(audio_file), save_cleaned=True)
            print(f"  Status: {result.get('status')}")
            if result.get('status') == 'FAIL':
                print(f"  Reasons: {result['quality']['reasons_rejected']}")
    
    report = pipeline.generate_report("outputs/v3_realism/DATA_REALISM_REPORT.json")
    print(f"\n✓ Processed {report['total_samples']} samples")
    print(f"  Pass rate: {report['pass_rate']:.1%}")
    print(f"  Valid samples: {report['valid_samples']}/{report['total_samples']}")
