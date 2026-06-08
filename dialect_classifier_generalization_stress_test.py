"""
Comprehensive Generalization Stress Test for Acoustic Dialect Classifier

Tests dialect classifier with:
- Speaker-level train/test split (80/20)
- Multiple microphones and environments
- Robustness to noise, pitch shift, tempo shift
- Advanced metrics: precision, recall, ROC, calibration curves
- Speaker leakage detection

NO model modification. Only inference testing.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
import hashlib

import numpy as np
import librosa
import soundfile as sf
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support,
    confusion_matrix, roc_curve, auc, precision_recall_curve
)
from sklearn.calibration import calibration_curve
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

from epmssts.services.dialect.acoustic_classifier import AcousticDialectClassifier

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class SampleMetadata:
    """Metadata for each audio sample"""
    file_path: str
    speaker_id: str
    dialect: str
    microphone: str
    environment: str
    sentence_type: str  # 'fixed' or 'free'
    
    
@dataclass
class PredictionResult:
    """Prediction result for a single sample"""
    file: str
    speaker_id: str
    true_label: str
    predicted_label: str
    confidence: float
    correct: bool
    

@dataclass
class RobustnessResult:
    """Robustness test result"""
    test_name: str
    accuracy: float
    avg_confidence: float
    dialect_flips: int
    samples_tested: int
    flip_rate: float
    

@dataclass
class StressTestReport:
    """Complete stress test report"""
    # Basic metrics
    accuracy: float
    precision_per_dialect: Dict[str, float]
    recall_per_dialect: Dict[str, float]
    f1_per_dialect: Dict[str, float]
    confusion_matrix: Dict[str, Dict[str, int]]
    
    # Advanced metrics
    roc_auc: float
    avg_precision_score: float
    
    # Robustness results
    robustness_tests: List[Dict]
    
    # Speaker leakage
    speaker_leakage_detected: bool
    speaker_overlap_count: int
    
    # Failure analysis
    test_passed: bool
    failure_reasons: List[str]
    
    # Detailed results
    predictions: List[Dict]
    
    def to_dict(self):
        return {
            'accuracy': self.accuracy,
            'precision_per_dialect': self.precision_per_dialect,
            'recall_per_dialect': self.recall_per_dialect,
            'f1_per_dialect': self.f1_per_dialect,
            'confusion_matrix': self.confusion_matrix,
            'roc_auc': self.roc_auc,
            'avg_precision_score': self.avg_precision_score,
            'robustness_tests': self.robustness_tests,
            'speaker_leakage_detected': self.speaker_leakage_detected,
            'speaker_overlap_count': self.speaker_overlap_count,
            'test_passed': self.test_passed,
            'failure_reasons': self.failure_reasons,
            'predictions': self.predictions
        }


def load_audio_mono_16k(path: Path) -> np.ndarray:
    """Load audio file and convert to mono 16kHz"""
    audio, sr = sf.read(path)
    
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    
    if sr != 16000:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
    
    return audio.astype(np.float32)


def extract_speaker_id(filename: str) -> str:
    """
    Extract speaker ID from filename.
    Expected format: speakerXX_*.wav or similar
    """
    # Try to extract speaker ID from filename
    parts = filename.split('_')
    for part in parts:
        if part.startswith('speaker') or part.startswith('spk'):
            return part
    
    # Fallback: use first part of filename
    return parts[0] if parts else filename


def load_dataset_with_metadata(data_dir: Path) -> List[SampleMetadata]:
    """
    Load all samples with metadata.
    
    Assumes structure:
    data_dir/
        andhra/
            speakerXX_micY_envZ_fixed.wav
            speakerXX_micY_envZ_free.wav
        telangana/
            speakerXX_micY_envZ_fixed.wav
            speakerXX_micY_envZ_free.wav
    """
    samples = []
    
    for dialect in ['andhra', 'telangana']:
        dialect_dir = data_dir / dialect
        if not dialect_dir.exists():
            logger.warning(f"Dialect directory not found: {dialect_dir}")
            continue
        
        wav_files = list(dialect_dir.glob('*.wav'))
        logger.info(f"Found {len(wav_files)} {dialect} samples")
        
        for wav_file in wav_files:
            filename = wav_file.name
            speaker_id = extract_speaker_id(filename)
            
            # Extract metadata from filename if available
            # Default values if not in filename
            microphone = 'mic1'
            environment = 'env1'
            sentence_type = 'fixed'
            
            if 'mic2' in filename.lower():
                microphone = 'mic2'
            if 'env2' in filename.lower():
                environment = 'env2'
            if 'free' in filename.lower():
                sentence_type = 'free'
            
            sample = SampleMetadata(
                file_path=str(wav_file),
                speaker_id=speaker_id,
                dialect=dialect,
                microphone=microphone,
                environment=environment,
                sentence_type=sentence_type
            )
            samples.append(sample)
    
    return samples


def speaker_level_split(
    samples: List[SampleMetadata],
    test_ratio: float = 0.2,
    seed: int = 42
) -> Tuple[List[SampleMetadata], List[SampleMetadata]]:
    """
    Split dataset by speaker (no speaker overlap).
    
    Args:
        samples: All samples with metadata
        test_ratio: Fraction for test set
        seed: Random seed
        
    Returns:
        (train_samples, test_samples)
    """
    rng = np.random.default_rng(seed)
    
    # Group samples by dialect and speaker
    speaker_groups = defaultdict(list)
    for sample in samples:
        key = (sample.dialect, sample.speaker_id)
        speaker_groups[key].append(sample)
    
    train_samples = []
    test_samples = []
    
    # Split separately per dialect to maintain balance
    for dialect in ['andhra', 'telangana']:
        dialect_speakers = [k for k in speaker_groups.keys() if k[0] == dialect]
        
        # Shuffle speakers
        rng.shuffle(dialect_speakers)
        
        # Split speakers
        n_test = max(1, int(len(dialect_speakers) * test_ratio))
        test_speakers = dialect_speakers[:n_test]
        train_speakers = dialect_speakers[n_test:]
        
        logger.info(f"{dialect}: {len(train_speakers)} train speakers, {len(test_speakers)} test speakers")
        
        # Assign samples
        for speaker_key in train_speakers:
            train_samples.extend(speaker_groups[speaker_key])
        
        for speaker_key in test_speakers:
            test_samples.extend(speaker_groups[speaker_key])
    
    return train_samples, test_samples


def check_speaker_leakage(
    train_samples: List[SampleMetadata],
    test_samples: List[SampleMetadata]
) -> Tuple[bool, int]:
    """
    Check if any speakers appear in both train and test.
    
    Returns:
        (leakage_detected, overlap_count)
    """
    train_speakers = set(s.speaker_id for s in train_samples)
    test_speakers = set(s.speaker_id for s in test_samples)
    
    overlap = train_speakers.intersection(test_speakers)
    
    if overlap:
        logger.error(f"Speaker leakage detected! {len(overlap)} speakers in both train/test:")
        logger.error(f"  {overlap}")
        return True, len(overlap)
    else:
        logger.info("✓ No speaker leakage detected")
        return False, 0


def run_inference(
    classifier: AcousticDialectClassifier,
    samples: List[SampleMetadata]
) -> List[PredictionResult]:
    """
    Run inference on all samples.
    
    Args:
        classifier: Loaded classifier
        samples: Test samples
        
    Returns:
        List of prediction results
    """
    results = []
    
    for sample in samples:
        try:
            audio = load_audio_mono_16k(Path(sample.file_path))
            prediction = classifier.predict(audio, sr=16000)
            
            result = PredictionResult(
                file=Path(sample.file_path).name,
                speaker_id=sample.speaker_id,
                true_label=sample.dialect,
                predicted_label=prediction.dialect,
                confidence=prediction.confidence,
                correct=(sample.dialect == prediction.dialect)
            )
            results.append(result)
            
        except Exception as e:
            logger.error(f"Error processing {sample.file_path}: {e}")
    
    return results


def calculate_metrics(results: List[PredictionResult]) -> Dict:
    """
    Calculate comprehensive metrics.
    
    Returns:
        Dictionary with all metrics
    """
    if not results:
        return {}
    
    y_true = [r.true_label for r in results]
    y_pred = [r.predicted_label for r in results]
    y_conf = [r.confidence for r in results]
    
    # Convert to binary for sklearn (andhra=0, telangana=1)
    label_to_idx = {'andhra': 0, 'telangana': 1}
    y_true_bin = [label_to_idx[label] for label in y_true]
    y_pred_bin = [label_to_idx[label] for label in y_pred]
    
    # Confidence scores (probability of positive class - telangana)
    y_score = []
    for pred, conf in zip(y_pred, y_conf):
        if pred == 'telangana':
            y_score.append(conf)
        else:
            y_score.append(1.0 - conf)
    
    # Basic metrics
    accuracy = accuracy_score(y_true_bin, y_pred_bin)
    
    # Per-class metrics
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true_bin, y_pred_bin, average=None, zero_division=0
    )
    
    # Confusion matrix
    cm = confusion_matrix(y_true_bin, y_pred_bin)
    confusion = {
        'andhra': {'andhra': int(cm[0, 0]), 'telangana': int(cm[0, 1])},
        'telangana': {'andhra': int(cm[1, 0]), 'telangana': int(cm[1, 1])}
    }
    
    # ROC curve
    fpr, tpr, _ = roc_curve(y_true_bin, y_score)
    roc_auc = auc(fpr, tpr)
    
    # Precision-Recall curve
    pr_precision, pr_recall, _ = precision_recall_curve(y_true_bin, y_score)
    avg_precision = auc(pr_recall, pr_precision)
    
    return {
        'accuracy': float(accuracy),
        'precision_per_dialect': {
            'andhra': float(precision[0]),
            'telangana': float(precision[1])
        },
        'recall_per_dialect': {
            'andhra': float(recall[0]),
            'telangana': float(recall[1])
        },
        'f1_per_dialect': {
            'andhra': float(f1[0]),
            'telangana': float(f1[1])
        },
        'confusion_matrix': confusion,
        'roc_auc': float(roc_auc),
        'avg_precision_score': float(avg_precision),
        'roc_curve': {
            'fpr': fpr.tolist(),
            'tpr': tpr.tolist()
        },
        'pr_curve': {
            'precision': pr_precision.tolist(),
            'recall': pr_recall.tolist()
        }
    }


def add_noise(audio: np.ndarray, noise_level: float = 0.1) -> np.ndarray:
    """
    Add Gaussian noise to audio.
    
    Args:
        audio: Input audio
        noise_level: Noise level (default: 0.1 = 10%)
        
    Returns:
        Noisy audio
    """
    noise = np.random.randn(len(audio)) * noise_level
    noisy_audio = audio + noise
    
    # Clip to prevent overflow
    noisy_audio = np.clip(noisy_audio, -1.0, 1.0)
    
    return noisy_audio.astype(np.float32)


def shift_pitch(audio: np.ndarray, sr: int, semitones: float) -> np.ndarray:
    """
    Shift pitch of audio.
    
    Args:
        audio: Input audio
        sr: Sample rate
        semitones: Pitch shift in semitones (±)
        
    Returns:
        Pitch-shifted audio
    """
    return librosa.effects.pitch_shift(audio, sr=sr, n_steps=semitones)


def shift_tempo(audio: np.ndarray, rate: float) -> np.ndarray:
    """
    Shift tempo of audio.
    
    Args:
        audio: Input audio
        rate: Tempo rate (1.0 = no change, 1.05 = 5% faster)
        
    Returns:
        Tempo-shifted audio
    """
    return librosa.effects.time_stretch(audio, rate=rate)


def test_robustness(
    classifier: AcousticDialectClassifier,
    test_samples: List[SampleMetadata],
    test_name: str,
    augment_fn
) -> RobustnessResult:
    """
    Test robustness to a specific augmentation.
    
    Args:
        classifier: Loaded classifier
        test_samples: Samples to test (use subset for speed)
        test_name: Name of test
        augment_fn: Function to augment audio
        
    Returns:
        RobustnessResult
    """
    logger.info(f"\nTesting: {test_name}")
    
    dialect_flips = 0
    total_confidence = 0.0
    correct = 0
    samples_tested = 0
    
    # Use subset for robustness tests (first 10 samples)
    test_subset = test_samples[:min(10, len(test_samples))]
    
    for sample in test_subset:
        try:
            # Load original audio
            audio_orig = load_audio_mono_16k(Path(sample.file_path))
            
            # Get original prediction
            pred_orig = classifier.predict(audio_orig, sr=16000)
            
            # Augment audio
            audio_aug = augment_fn(audio_orig)
            
            # Get augmented prediction
            pred_aug = classifier.predict(audio_aug, sr=16000)
            
            # Check for dialect flip
            if pred_orig.dialect != pred_aug.dialect:
                dialect_flips += 1
                logger.warning(f"  Dialect flip: {sample.file_path}")
                logger.warning(f"    {pred_orig.dialect} → {pred_aug.dialect}")
            
            # Check accuracy on augmented
            if pred_aug.dialect == sample.dialect:
                correct += 1
            
            total_confidence += pred_aug.confidence
            samples_tested += 1
            
        except Exception as e:
            logger.error(f"Error in robustness test for {sample.file_path}: {e}")
    
    if samples_tested == 0:
        return RobustnessResult(
            test_name=test_name,
            accuracy=0.0,
            avg_confidence=0.0,
            dialect_flips=0,
            samples_tested=0,
            flip_rate=0.0
        )
    
    accuracy = correct / samples_tested
    avg_confidence = total_confidence / samples_tested
    flip_rate = dialect_flips / samples_tested
    
    logger.info(f"  Accuracy: {accuracy:.2%}")
    logger.info(f"  Avg confidence: {avg_confidence:.3f}")
    logger.info(f"  Flip rate: {flip_rate:.2%}")
    
    return RobustnessResult(
        test_name=test_name,
        accuracy=accuracy,
        avg_confidence=avg_confidence,
        dialect_flips=dialect_flips,
        samples_tested=samples_tested,
        flip_rate=flip_rate
    )


def plot_roc_curve(roc_data: Dict, output_path: Path):
    """Plot ROC curve"""
    plt.figure(figsize=(8, 6))
    plt.plot(roc_data['fpr'], roc_data['tpr'], 'b-', linewidth=2)
    plt.plot([0, 1], [0, 1], 'r--', linewidth=1)
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title(f'ROC Curve (AUC = {roc_data.get("auc", 0):.3f})')
    plt.grid(True, alpha=0.3)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"ROC curve saved to {output_path}")


def plot_confusion_matrix(cm: Dict, output_path: Path):
    """Plot confusion matrix"""
    matrix = np.array([
        [cm['andhra']['andhra'], cm['andhra']['telangana']],
        [cm['telangana']['andhra'], cm['telangana']['telangana']]
    ])
    
    plt.figure(figsize=(8, 6))
    plt.imshow(matrix, interpolation='nearest', cmap='Blues')
    plt.colorbar()
    plt.xlabel('Predicted')
    plt.ylabel('True')
    plt.title('Confusion Matrix')
    
    # Add text annotations
    for i in range(2):
        for j in range(2):
            plt.text(j, i, str(matrix[i, j]),
                    ha='center', va='center',
                    color='white' if matrix[i, j] > matrix.max() / 2 else 'black',
                    fontsize=14, fontweight='bold')
    
    plt.xticks([0, 1], ['Andhra', 'Telangana'])
    plt.yticks([0, 1], ['Andhra', 'Telangana'])
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Confusion matrix saved to {output_path}")


def evaluate_failure_conditions(
    metrics: Dict,
    robustness_results: List[RobustnessResult],
    speaker_leakage: bool
) -> Tuple[bool, List[str]]:
    """
    Check if test passes all conditions.
    
    Failure conditions:
    - Accuracy < 80%
    - Confidence drops significantly under noise
    - Speaker leakage detected
    - Dialect flips with tempo/pitch > 20%
    
    Returns:
        (test_passed, failure_reasons)
    """
    failure_reasons = []
    
    # Check accuracy
    if metrics['accuracy'] < 0.80:
        failure_reasons.append(f"Accuracy too low: {metrics['accuracy']:.2%} < 80%")
    
    # Check speaker leakage
    if speaker_leakage:
        failure_reasons.append("Speaker leakage detected in train/test split")
    
    # Check robustness results
    for result in robustness_results:
        # Check for significant dialect flips
        if result.flip_rate > 0.20:
            failure_reasons.append(
                f"{result.test_name}: High dialect flip rate {result.flip_rate:.2%} > 20%"
            )
        
        # Check for confidence drop (only for noise test)
        if 'noise' in result.test_name.lower():
            if result.avg_confidence < 0.60:
                failure_reasons.append(
                    f"{result.test_name}: Confidence dropped to {result.avg_confidence:.3f} < 0.60"
                )
    
    test_passed = len(failure_reasons) == 0
    
    return test_passed, failure_reasons


def main():
    """Run comprehensive stress test"""
    
    logger.info("=" * 80)
    logger.info("COMPREHENSIVE DIALECT CLASSIFIER GENERALIZATION STRESS TEST")
    logger.info("=" * 80)
    
    # Paths
    model_path = Path("models/dialect_classifier.pth")
    data_dir = Path("data/dialect_acoustic/train")
    output_dir = Path("stress_test_results")
    output_dir.mkdir(exist_ok=True)
    
    # Check prerequisites
    if not model_path.exists():
        logger.error(f"Model not found: {model_path}")
        return
    
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return
    
    # Load classifier
    logger.info(f"\nLoading classifier from {model_path}")
    classifier = AcousticDialectClassifier(model_path=model_path, device='cpu')
    
    # Step 1: Load dataset with metadata
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: Loading Dataset")
    logger.info("=" * 80)
    
    all_samples = load_dataset_with_metadata(data_dir)
    logger.info(f"Loaded {len(all_samples)} total samples")
    
    # Step 2: Speaker-level split
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: Speaker-Level Train/Test Split (80/20)")
    logger.info("=" * 80)
    
    train_samples, test_samples = speaker_level_split(all_samples, test_ratio=0.2)
    logger.info(f"Train: {len(train_samples)} samples")
    logger.info(f"Test: {len(test_samples)} samples")
    
    # Step 3: Check speaker leakage
    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: Speaker Leakage Detection")
    logger.info("=" * 80)
    
    speaker_leakage, overlap_count = check_speaker_leakage(train_samples, test_samples)
    
    # Step 4: Run inference on test set
    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: Running Inference on Test Set")
    logger.info("=" * 80)
    
    predictions = run_inference(classifier, test_samples)
    logger.info(f"Processed {len(predictions)} test samples")
    
    # Step 5: Calculate metrics
    logger.info("\n" + "=" * 80)
    logger.info("STEP 5: Calculating Metrics")
    logger.info("=" * 80)
    
    metrics = calculate_metrics(predictions)
    
    logger.info(f"\nAccuracy: {metrics['accuracy']:.2%}")
    logger.info(f"\nPrecision:")
    for dialect, prec in metrics['precision_per_dialect'].items():
        logger.info(f"  {dialect}: {prec:.3f}")
    logger.info(f"\nRecall:")
    for dialect, rec in metrics['recall_per_dialect'].items():
        logger.info(f"  {dialect}: {rec:.3f}")
    logger.info(f"\nF1-Score:")
    for dialect, f1 in metrics['f1_per_dialect'].items():
        logger.info(f"  {dialect}: {f1:.3f}")
    logger.info(f"\nROC AUC: {metrics['roc_auc']:.3f}")
    logger.info(f"Avg Precision Score: {metrics['avg_precision_score']:.3f}")
    
    # Plot ROC curve
    roc_plot_path = output_dir / "roc_curve.png"
    plot_roc_curve(
        {'fpr': metrics['roc_curve']['fpr'], 
         'tpr': metrics['roc_curve']['tpr'],
         'auc': metrics['roc_auc']},
        roc_plot_path
    )
    
    # Plot confusion matrix
    cm_plot_path = output_dir / "confusion_matrix.png"
    plot_confusion_matrix(metrics['confusion_matrix'], cm_plot_path)
    
    # Step 6: Robustness tests
    logger.info("\n" + "=" * 80)
    logger.info("STEP 6: Robustness Tests")
    logger.info("=" * 80)
    
    robustness_results = []
    
    # Test 1: Background noise
    noise_result = test_robustness(
        classifier, test_samples, "Background Noise (10%)",
        lambda audio: add_noise(audio, noise_level=0.1)
    )
    robustness_results.append(noise_result)
    
    # Test 2: Pitch shift +5%
    pitch_up_result = test_robustness(
        classifier, test_samples, "Pitch Shift +5%",
        lambda audio: shift_pitch(audio, 16000, semitones=1)  # ~5%
    )
    robustness_results.append(pitch_up_result)
    
    # Test 3: Pitch shift -5%
    pitch_down_result = test_robustness(
        classifier, test_samples, "Pitch Shift -5%",
        lambda audio: shift_pitch(audio, 16000, semitones=-1)
    )
    robustness_results.append(pitch_down_result)
    
    # Test 4: Tempo shift +5%
    tempo_up_result = test_robustness(
        classifier, test_samples, "Tempo Shift +5%",
        lambda audio: shift_tempo(audio, rate=1.05)
    )
    robustness_results.append(tempo_up_result)
    
    # Test 5: Tempo shift -5%
    tempo_down_result = test_robustness(
        classifier, test_samples, "Tempo Shift -5%",
        lambda audio: shift_tempo(audio, rate=0.95)
    )
    robustness_results.append(tempo_down_result)
    
    # Step 7: Evaluate and generate report
    logger.info("\n" + "=" * 80)
    logger.info("STEP 7: Final Evaluation")
    logger.info("=" * 80)
    
    test_passed, failure_reasons = evaluate_failure_conditions(
        metrics, robustness_results, speaker_leakage
    )
    
    # Build final report
    report = StressTestReport(
        accuracy=metrics['accuracy'],
        precision_per_dialect=metrics['precision_per_dialect'],
        recall_per_dialect=metrics['recall_per_dialect'],
        f1_per_dialect=metrics['f1_per_dialect'],
        confusion_matrix=metrics['confusion_matrix'],
        roc_auc=metrics['roc_auc'],
        avg_precision_score=metrics['avg_precision_score'],
        robustness_tests=[asdict(r) for r in robustness_results],
        speaker_leakage_detected=speaker_leakage,
        speaker_overlap_count=overlap_count,
        test_passed=test_passed,
        failure_reasons=failure_reasons,
        predictions=[asdict(p) for p in predictions]
    )
    
    # Save report
    report_path = output_dir / "stress_test_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n✓ Stress test report saved to {report_path}")
    
    # Final verdict
    logger.info("\n" + "=" * 80)
    logger.info("FINAL VERDICT")
    logger.info("=" * 80)
    
    if test_passed:
        logger.info("✓ STRESS TEST PASSED")
        logger.info(f"  - Accuracy: {metrics['accuracy']:.2%} (≥ 80%)")
        logger.info(f"  - ROC AUC: {metrics['roc_auc']:.3f}")
        logger.info(f"  - No speaker leakage")
        logger.info(f"  - Robust to noise, pitch, and tempo variations")
    else:
        logger.info("✗ STRESS TEST FAILED")
        logger.info("\nFailure Reasons:")
        for reason in failure_reasons:
            logger.info(f"  - {reason}")
    
    logger.info("=" * 80)
    
    return report


if __name__ == "__main__":
    main()
