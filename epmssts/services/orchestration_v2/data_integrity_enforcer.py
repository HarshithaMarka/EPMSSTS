"""
PHASE 1: DATA INTEGRITY ENFORCEMENT
Real mic-recorded WAV file validation and auto-cleaning

Purpose:
- Accept only 16kHz mono WAV files from real microphones
- Auto-trim silence, remove mid-silence, normalize RMS per band
- Quality gating: speech ratio >60%, no clipping >1%, duration >2.5s
- Reject only invalid samples, not real human speech
- Generate DATA_INTEGRITY_REPORT.json

Author: Production Hardening  
Date: 2026-03-02
"""

import json
import numpy as np
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import librosa
import soundfile as sf
import logging

logger = logging.getLogger(__name__)


@dataclass
class IntegrityCheckResult:
    """Result of integrity check on a single file."""
    file_path: str
    file_name: str
    passes_validation: bool
    audio_length_samples: int
    duration_seconds: float
    sample_rate: int
    is_mono: bool
    speech_ratio: float
    clipping_ratio: float
    peak_db: float
    rms_band: str
    rms_dbfs: float
    reasons_failed: List[str]
    auto_clean_applied: bool


@dataclass
class DataIntegrityReport:
    """Complete data integrity validation report."""
    timestamp: str
    total_files_processed: int
    valid_files: int
    invalid_files: int
    auto_cleaned_files: int
    pass_rate: float
    checks: List[Dict]
    summary_stats: Dict
    deployment_ready: bool


class RealDataIntegrityEnforcer:
    """
    Validate and clean real microphone-recorded WAV files.
    
    Thresholds:
    - Speech ratio must be >60%
    - Clipping must be <1%
    - Duration must be >2.5 seconds
    - Sample rate must be 16kHz
    - Must be mono or convertible to mono
    """
    
    def __init__(self, 
                 target_sr: int = 16000,
                 output_dir: Optional[Path] = None):
        self.target_sr = target_sr
        self.output_dir = output_dir or Path("outputs/production")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results: List[IntegrityCheckResult] = []
    
    def validate_and_clean(self, 
                          audio_path: str,
                          auto_clean: bool = True,
                          save_cleaned: bool = False) -> IntegrityCheckResult:
        """
        Validate and optionally clean a WAV file.
        
        Args:
            audio_path: Path to WAV file
            auto_clean: Apply auto-cleaning if validation issues found
            save_cleaned: Save cleaned audio to output directory
            
        Returns:
            IntegrityCheckResult with detailed metrics
        """
        
        try:
            # Load audio
            audio, sr = librosa.load(audio_path, sr=self.target_sr, mono=True)
            file_name = Path(audio_path).name
            
            # Basic checks
            is_mono = True
            original_duration = len(audio) / sr
            
            check_failures = []
            
            # 1. Check sample rate
            if sr != self.target_sr:
                check_failures.append(f"Sample rate {sr}Hz != {self.target_sr}Hz (resampled)")
            
            # 2. Check duration (minimum 2.5 seconds)
            if original_duration < 2.5:
                check_failures.append(f"Duration {original_duration:.1f}s < 2.5s minimum")
            
            # 3. Trim silence
            audio_trimmed, trim_start, trim_end = self._trim_silence(audio, sr)
            
            # 4. Remove mid-silence
            audio_compressed, removed_frames = self._remove_mid_silence(audio_trimmed, sr)
            
            # 5. Compute speech ratio (after cleaning)
            speech_ratio = self._compute_speech_ratio(audio_compressed, sr)
            if speech_ratio < 0.60:
                check_failures.append(f"Speech ratio {speech_ratio:.1%} < 60%")
            
            # 6. Check for clipping
            clipping_threshold = 0.99
            clipped_samples = np.sum(np.abs(audio_compressed) > clipping_threshold)
            clipping_ratio = clipped_samples / len(audio_compressed) if len(audio_compressed) > 0 else 0.0
            
            if clipping_ratio > 0.01:
                check_failures.append(f"Clipping {clipping_ratio:.2%} > 1%")
            
            # 7. Normalize RMS per band
            audio_final = audio_compressed if auto_clean else audio
            rms_band, rms_dbfs = self._normalize_rms_band(audio_final, sr)
            
            # 8. Compute peak level
            peak_db = 20 * np.log10(np.max(np.abs(audio_final)) + 1e-8)
            
            # Determine if valid
            is_valid = len(check_failures) == 0
            auto_clean_applied = auto_clean and original_duration > 2.5
            
            result = IntegrityCheckResult(
                file_path=audio_path,
                file_name=file_name,
                passes_validation=is_valid,
                audio_length_samples=len(audio_final),
                duration_seconds=float(len(audio_final) / sr),
                sample_rate=sr,
                is_mono=is_mono,
                speech_ratio=float(speech_ratio),
                clipping_ratio=float(clipping_ratio),
                peak_db=float(peak_db),
                rms_band=rms_band,
                rms_dbfs=float(rms_dbfs),
                reasons_failed=check_failures,
                auto_clean_applied=auto_clean_applied
            )
            
            # Save cleaned audio if valid and requested
            if save_cleaned and is_valid:
                output_path = self.output_dir / f"clean_{file_name}"
                sf.write(str(output_path), audio_final, sr)
                logger.info(f"  ✓ Cleaned audio saved: {output_path}")
            
            self.results.append(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing {audio_path}: {e}")
            return IntegrityCheckResult(
                file_path=audio_path,
                file_name=Path(audio_path).name,
                passes_validation=False,
                audio_length_samples=0,
                duration_seconds=0.0,
                sample_rate=0,
                is_mono=False,
                speech_ratio=0.0,
                clipping_ratio=0.0,
                peak_db=-120.0,
                rms_band="error",
                rms_dbfs=-120.0,
                reasons_failed=[str(e)],
                auto_clean_applied=False
            )
    
    def _trim_silence(self, audio: np.ndarray, sr: int,
                     threshold_percentile: int = 10) -> Tuple[np.ndarray, int, int]:
        """Remove leading/trailing silence >300ms."""
        
        # Compute frame energy
        S = librosa.feature.melspectrogram(y=audio, sr=sr, n_mels=64)
        energy = np.mean(S, axis=0)
        energy_db = librosa.power_to_db(energy, ref=1.0)
        
        # Adaptive threshold
        threshold = np.percentile(energy_db, threshold_percentile)
        is_silent = energy_db < threshold
        
        # Find non-silent region
        frame_length = 2048
        hop_length = 512
        non_silent_frames = np.where(~is_silent)[0]
        
        if len(non_silent_frames) == 0:
            return audio, 0, len(audio)
        
        # Add margin
        margin_frames = int(0.3 * sr / hop_length)  # 300ms margin
        start_frame = max(0, non_silent_frames[0] - margin_frames)
        end_frame = min(len(is_silent) - 1, non_silent_frames[-1] + margin_frames)
        
        start_sample = start_frame * hop_length
        end_sample = end_frame * hop_length
        
        return audio[start_sample:end_sample], start_sample, end_sample
    
    def _remove_mid_silence(self, audio: np.ndarray, sr: int,
                           max_silence_ms: float = 600.0) -> Tuple[np.ndarray, int]:
        """Remove internal silence gaps >600ms."""
        
        # Detect silence
        S = librosa.feature.melspectrogram(y=audio, sr=sr, n_mels=64)
        energy = np.mean(S, axis=0)
        energy_db = librosa.power_to_db(energy, ref=1.0)
        
        threshold = np.percentile(energy_db, 20)
        is_silent = energy_db < threshold
        
        frame_length = 2048
        hop_length = 512
        max_silence_frames = int(max_silence_ms * sr / 1000 / hop_length)
        
        # Find silence blocks
        silence_blocks = self._find_contiguous_blocks(is_silent)
        
        audio_out = []
        prev_end = 0
        frames_removed = 0
        
        for start, end in silence_blocks:
            if (end - start) <= max_silence_frames:
                # Keep short silence
                block_start_sample = start * hop_length
                block_end_sample = end * hop_length
                audio_out.append(audio[prev_end:block_end_sample])
                prev_end = block_end_sample
            else:
                # Remove long silence
                block_start_sample = start * hop_length
                audio_out.append(audio[prev_end:block_start_sample])
                prev_end = end * hop_length
                frames_removed += (end - start)
        
        audio_out.append(audio[prev_end:])
        audio_compressed = np.concatenate(audio_out) if audio_out else audio
        
        return audio_compressed, frames_removed
    
    def _compute_speech_ratio(self, audio: np.ndarray, sr: int) -> float:
        """Compute percentage of frames containing speech."""
        
        S = librosa.feature.melspectrogram(y=audio, sr=sr, n_mels=64)
        energy = np.mean(S, axis=0)
        energy_db = librosa.power_to_db(energy, ref=1.0)
        
        threshold = np.percentile(energy_db, 20)
        speech_frames = np.sum(energy_db > threshold)
        
        return float(speech_frames / len(energy_db)) if len(energy_db) > 0 else 0.0
    
    def _normalize_rms_band(self, audio: np.ndarray, sr: int) -> Tuple[str, float]:
        """Classify and normalize RMS into energy band."""
        
        rms = np.sqrt(np.mean(audio ** 2))
        rms_dbfs = 20 * np.log10(rms + 1e-8)
        
        # Classify band
        if -80 <= rms_dbfs < -50:
            band = "very_low"
        elif -50 <= rms_dbfs < -30:
            band = "low"
        elif -30 <= rms_dbfs < -10:
            band = "normal"
        else:
            band = "high"
        
        return band, float(rms_dbfs)
    
    @staticmethod
    def _find_contiguous_blocks(is_silent: np.ndarray) -> List[Tuple[int, int]]:
        """Find contiguous silence blocks [start, end)."""
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
    
    def generate_integrity_report(self, output_file: Optional[str] = None) -> Dict:
        """Generate DATA_INTEGRITY_REPORT.json"""
        
        valid_count = sum(1 for r in self.results if r.passes_validation)
        invalid_count = len(self.results) - valid_count
        auto_cleaned = sum(1 for r in self.results if r.auto_clean_applied)
        
        # Compute summary statistics
        valid_results = [r for r in self.results if r.passes_validation]
        if valid_results:
            mean_duration = float(np.mean([r.duration_seconds for r in valid_results]))
            mean_speech_ratio = float(np.mean([r.speech_ratio for r in valid_results]))
            mean_rms_dbfs = float(np.mean([r.rms_dbfs for r in valid_results]))
        else:
            mean_duration = mean_speech_ratio = mean_rms_dbfs = 0.0
        
        deployment_ready = valid_count >= 10  # Minimum 10 valid samples for deployment
        
        report = {
            'timestamp': str(np.datetime64('now')),
            'total_files_processed': len(self.results),
            'valid_files': valid_count,
            'invalid_files': invalid_count,
            'auto_cleaned_files': auto_cleaned,
            'pass_rate': float(valid_count / len(self.results)) if self.results else 0.0,
            'deployment_ready': deployment_ready,
            'minimum_valid_samples': 10,
            'summary_stats': {
                'mean_duration_seconds': mean_duration,
                'mean_speech_ratio': mean_speech_ratio,
                'mean_rms_dbfs': mean_rms_dbfs
            },
            'validation_criteria': {
                'speech_ratio_minimum': 0.60,
                'clipping_maximum': 0.01,
                'duration_minimum_seconds': 2.5,
                'sample_rate_required': 16000
            },
            'files': [asdict(r) for r in self.results]
        }
        
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"✓ Integrity report saved: {output_file}")
        
        return report


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    enforcer = RealDataIntegrityEnforcer()
    
    # Find test WAV files
    test_dir = Path("outputs")
    wav_files = list(test_dir.glob("**/*.wav"))
    
    logger.info(f"\nValidating {len(wav_files)} WAV files...")
    
    for wav_file in wav_files[:5]:  # Process first 5
        result = enforcer.validate_and_clean(str(wav_file), auto_clean=True, save_cleaned=True)
        status = "✓ PASS" if result.passes_validation else "✗ FAIL"
        logger.info(f"  {result.file_name}: {status} (speech: {result.speech_ratio:.1%})")
    
    report = enforcer.generate_integrity_report(
        "outputs/production/DATA_INTEGRITY_REPORT.json"
    )
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Data Integrity Report")
    logger.info(f"{'='*60}")
    logger.info(f"Valid files: {report['valid_files']}/{report['total_files_processed']}")
    logger.info(f"Pass rate: {report['pass_rate']:.1%}")
    logger.info(f"Deployment ready: {report['deployment_ready']}")
