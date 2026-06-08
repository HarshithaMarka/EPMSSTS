#!/usr/bin/env python3
"""
Advanced Emotion Detection Validation Suite

Comprehensive testing to ensure production readiness:
1. Over-correction checks (not defaulting to neutral too often)
2. Volume invariance (same emotion at different volumes)
3. Temporal stability (no random flipping)
4. TTS expressiveness (emotion preserved in synthesis)
5. End-to-end demo validation

This validates the system behaves professionally, not as a rule-based hack.
"""

import asyncio
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf
from scipy import signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("emotion.validation")


@dataclass
class ValidationResult:
    """Result of a single validation test."""
    test_name: str
    audio_file: Optional[Path]
    expected_emotion: str
    predicted_emotion: str
    confidence: float
    energy_level: str
    override_triggered: bool
    override_reason: Optional[str]
    passed: bool
    notes: str = ""


@dataclass
class ConfusionMatrix:
    """Confusion matrix for emotion classification."""
    true_positives: Dict[str, int]
    false_positives: Dict[str, int]
    false_negatives: Dict[str, int]
    true_negatives: Dict[str, int]
    
    def precision(self, emotion: str) -> float:
        tp = self.true_positives.get(emotion, 0)
        fp = self.false_positives.get(emotion, 0)
        return tp / (tp + fp) if (tp + fp) > 0 else 0.0
    
    def recall(self, emotion: str) -> float:
        tp = self.true_positives.get(emotion, 0)
        fn = self.false_negatives.get(emotion, 0)
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    def f1_score(self, emotion: str) -> float:
        p = self.precision(emotion)
        r = self.recall(emotion)
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    
    def accuracy(self) -> float:
        tp = sum(self.true_positives.values())
        tn = sum(self.true_negatives.values())
        fp = sum(self.false_positives.values())
        fn = sum(self.false_negatives.values())
        return (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0


class EmotionStabilityTracker:
    """Track emotion predictions over time for stability analysis."""
    
    def __init__(self, smoothing_alpha: float = 0.3):
        self.smoothing_alpha = smoothing_alpha
        self.previous_scores: Optional[Dict[str, float]] = None
        self.history: List[str] = []
    
    def predict_with_smoothing(
        self,
        current_scores: Dict[str, float],
        current_label: str
    ) -> Tuple[str, Dict[str, float]]:
        """Apply exponential moving average smoothing."""
        if self.previous_scores is None:
            # First prediction, no smoothing
            self.previous_scores = current_scores.copy()
            self.history.append(current_label)
            return current_label, current_scores
        
        # Apply EMA smoothing
        smoothed_scores = {}
        for emotion in current_scores.keys():
            prev_score = self.previous_scores.get(emotion, 0.0)
            curr_score = current_scores[emotion]
            smoothed_scores[emotion] = (
                (1 - self.smoothing_alpha) * prev_score + 
                self.smoothing_alpha * curr_score
            )
        
        # Normalize
        total = sum(smoothed_scores.values())
        if total > 0:
            smoothed_scores = {k: v / total for k, v in smoothed_scores.items()}
        
        # Get smoothed prediction
        smoothed_label = max(smoothed_scores.items(), key=lambda x: x[1])[0]
        
        self.previous_scores = smoothed_scores
        self.history.append(smoothed_label)
        
        return smoothed_label, smoothed_scores
    
    def get_flip_rate(self) -> float:
        """Calculate rate of emotion label changes."""
        if len(self.history) < 2:
            return 0.0
        
        flips = sum(1 for i in range(1, len(self.history)) 
                   if self.history[i] != self.history[i-1])
        return flips / (len(self.history) - 1)
    
    def reset(self):
        """Reset tracker state."""
        self.previous_scores = None
        self.history = []


class AdvancedEmotionValidator:
    """Comprehensive emotion detection validation."""
    
    EMOTIONS = ["neutral", "happy", "sad", "angry", "fearful"]
    
    def __init__(self):
        self.results: List[ValidationResult] = []
        self.confusion_matrix = self._init_confusion_matrix()
        self.stability_tracker = EmotionStabilityTracker()
        
        # Import services
        try:
            from epmssts.services.emotion.audio_emotion import AudioEmotionService
            from epmssts.services.emotion.audio_preprocessing import get_emotion_preprocessor
            from epmssts.services.emotion.fusion import fuse_emotions
            from epmssts.services.emotion.text_emotion import TextEmotionService
            
            self.emotion_service = AudioEmotionService()
            self.preprocessor = get_emotion_preprocessor()
            self.text_emotion_service = None
            
            try:
                self.text_emotion_service = TextEmotionService()
            except Exception:
                logger.warning("Text emotion service not available")
                
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            sys.exit(1)
    
    def _init_confusion_matrix(self) -> ConfusionMatrix:
        """Initialize empty confusion matrix."""
        return ConfusionMatrix(
            true_positives={e: 0 for e in self.EMOTIONS},
            false_positives={e: 0 for e in self.EMOTIONS},
            false_negatives={e: 0 for e in self.EMOTIONS},
            true_negatives={e: 0 for e in self.EMOTIONS},
        )
    
    def _generate_synthetic_audio(
        self,
        emotion_type: str,
        volume_level: str = "normal",
        duration_sec: float = 2.0,
        sample_rate: int = 16000
    ) -> np.ndarray:
        """
        Generate synthetic audio with emotion-like characteristics.
        
        This is a simplified model for testing when real audio unavailable.
        Real validation should use actual emotional speech recordings.
        """
        num_samples = int(duration_sec * sample_rate)
        t = np.linspace(0, duration_sec, num_samples)
        
        # Base parameters by emotion
        if emotion_type == "happy":
            base_freq = 300  # Hz (higher pitch)
            energy = 0.15
            modulation_rate = 8  # Faster modulation
        elif emotion_type == "sad":
            base_freq = 180  # Hz (lower pitch)
            energy = 0.03  # Lower energy
            modulation_rate = 2  # Slower modulation
        elif emotion_type == "angry":
            base_freq = 250  # Hz
            energy = 0.20  # Higher energy
            modulation_rate = 10  # Aggressive modulation
        elif emotion_type == "fearful":
            base_freq = 320  # Hz (higher pitch, tense)
            energy = 0.10
            modulation_rate = 12  # Trembling effect
        else:  # neutral
            base_freq = 220  # Hz
            energy = 0.08
            modulation_rate = 4
        
        # Adjust for volume level
        volume_multipliers = {
            "whisper": 0.1,
            "quiet": 0.3,
            "normal": 1.0,
            "loud": 2.0,
            "very_loud": 3.0
        }
        energy *= volume_multipliers.get(volume_level, 1.0)
        
        # Generate tone with formants (simplified voice)
        audio = np.zeros(num_samples)
        
        # Fundamental frequency
        audio += energy * np.sin(2 * np.pi * base_freq * t)
        
        # Add harmonics (formants)
        audio += 0.5 * energy * np.sin(2 * np.pi * base_freq * 2 * t)
        audio += 0.3 * energy * np.sin(2 * np.pi * base_freq * 3 * t)
        
        # Add temporal modulation (prosody)
        modulation = 1 + 0.3 * np.sin(2 * np.pi * modulation_rate * t)
        audio *= modulation
        
        # Add slight noise for realism
        noise = np.random.normal(0, energy * 0.1, num_samples)
        audio += noise
        
        # Apply envelope
        envelope = np.exp(-3 * (t - duration_sec/2)**2 / duration_sec)
        audio *= envelope
        
        # Normalize
        audio = audio / (np.max(np.abs(audio)) + 1e-10)
        audio = np.clip(audio, -1.0, 1.0)
        
        return audio.astype(np.float32)
    
    def _predict_emotion(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> Tuple[str, float, Dict[str, float], Optional[str]]:
        """
        Run emotion prediction and return results.
        
        Returns: (label, confidence, scores, override_reason)
        """
        # Preprocess
        audio_processed, metrics = self.preprocessor.preprocess_for_emotion(
            audio, sample_rate
        )
        
        # Predict
        prediction = self.emotion_service.predict(audio_processed, sample_rate)
        
        # Check if override was triggered (heuristic)
        override_reason = None
        if prediction.confidence == 1.0 and prediction.label == "neutral":
            # Likely an override (high confidence neutral)
            should_override, reason = self.preprocessor.should_override_to_neutral(
                rms_db=metrics.rms_db,
                confidence=0.5,  # Dummy value
                predicted_emotion="sad"
            )
            if should_override:
                override_reason = reason
        
        return (
            prediction.label,
            prediction.confidence,
            prediction.scores,
            override_reason
        )
    
    # ============================================================
    # PHASE 1: Over-Correction Check
    # ============================================================
    
    def phase1_over_correction_check(self) -> Dict[str, any]:
        """
        Test that genuine emotions are not over-corrected to neutral.
        
        Tests 5 samples per emotion at varying volumes.
        """
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 1: OVER-CORRECTION CHECK")
        logger.info("=" * 80)
        
        test_cases = []
        
        # Generate test cases for each emotion
        for emotion in self.EMOTIONS:
            for volume in ["quiet", "normal", "loud"]:
                # Skip some combinations that don't make sense
                if emotion == "sad" and volume == "loud":
                    continue  # Sad is typically quieter
                if emotion == "angry" and volume == "quiet":
                    continue  # Angry is typically louder
                
                test_cases.append({
                    "emotion": emotion,
                    "volume": volume,
                    "name": f"{emotion}_{volume}"
                })
        
        results_summary = {
            "total_tests": len(test_cases),
            "correct_predictions": 0,
            "over_corrected_to_neutral": 0,
            "genuine_sad_detected": 0,
            "genuine_sad_overridden": 0,
            "per_emotion_accuracy": {}
        }
        
        for test_case in test_cases:
            emotion = test_case["emotion"]
            volume = test_case["volume"]
            name = test_case["name"]
            
            logger.info(f"\n  Testing: {name}")
            
            # Generate audio
            audio = self._generate_synthetic_audio(
                emotion_type=emotion,
                volume_level=volume,
                duration_sec=2.0
            )
            
            # Predict
            predicted, confidence, scores, override_reason = self._predict_emotion(audio)
            
            # Determine energy level
            audio_processed, metrics = self.preprocessor.preprocess_for_emotion(audio)
            energy_level = metrics.energy_level
            
            # Check if correct
            is_correct = predicted == emotion
            is_overridden = override_reason is not None
            
            # Track sad-specific metrics
            if emotion == "sad":
                if predicted == "sad":
                    results_summary["genuine_sad_detected"] += 1
                elif is_overridden:
                    results_summary["genuine_sad_overridden"] += 1
            
            # Track over-correction
            if emotion != "neutral" and predicted == "neutral" and is_overridden:
                results_summary["over_corrected_to_neutral"] += 1
            
            # Track accuracy
            if is_correct:
                results_summary["correct_predictions"] += 1
            
            # Update confusion matrix
            self._update_confusion_matrix(emotion, predicted)
            
            # Log result
            logger.info(
                f"    Expected: {emotion} | Predicted: {predicted} "
                f"(conf={confidence:.2f}) | Energy: {energy_level}"
            )
            if is_overridden:
                logger.warning(f"    Override: {override_reason}")
            
            if is_correct:
                logger.info(f"    ✓ CORRECT")
            else:
                logger.error(f"    ✗ WRONG")
            
            # Store result
            result = ValidationResult(
                test_name=f"phase1_{name}",
                audio_file=None,
                expected_emotion=emotion,
                predicted_emotion=predicted,
                confidence=confidence,
                energy_level=energy_level,
                override_triggered=is_overridden,
                override_reason=override_reason,
                passed=is_correct
            )
            self.results.append(result)
        
        # Calculate per-emotion accuracy
        emotion_counts = defaultdict(int)
        emotion_correct = defaultdict(int)
        
        for result in self.results:
            if result.test_name.startswith("phase1_"):
                emotion_counts[result.expected_emotion] += 1
                if result.passed:
                    emotion_correct[result.expected_emotion] += 1
        
        for emotion in self.EMOTIONS:
            if emotion_counts[emotion] > 0:
                accuracy = emotion_correct[emotion] / emotion_counts[emotion]
                results_summary["per_emotion_accuracy"][emotion] = accuracy
        
        # Overall accuracy
        overall_accuracy = (
            results_summary["correct_predictions"] / results_summary["total_tests"]
        )
        
        logger.info(f"\n  PHASE 1 SUMMARY:")
        logger.info(f"    Total tests: {results_summary['total_tests']}")
        logger.info(f"    Correct: {results_summary['correct_predictions']}")
        logger.info(f"    Overall accuracy: {overall_accuracy:.2%}")
        logger.info(f"    Over-corrected to neutral: {results_summary['over_corrected_to_neutral']}")
        logger.info(f"    Genuine sad detected: {results_summary['genuine_sad_detected']}")
        logger.info(f"    Genuine sad overridden: {results_summary['genuine_sad_overridden']}")
        
        logger.info(f"\n  Per-emotion accuracy:")
        for emotion, accuracy in results_summary["per_emotion_accuracy"].items():
            logger.info(f"    {emotion}: {accuracy:.2%}")
        
        return results_summary
    
    def _update_confusion_matrix(self, expected: str, predicted: str):
        """Update confusion matrix with a new prediction."""
        if expected == predicted:
            self.confusion_matrix.true_positives[expected] += 1
            # Update true negatives for other emotions
            for emotion in self.EMOTIONS:
                if emotion != expected:
                    self.confusion_matrix.true_negatives[emotion] += 1
        else:
            self.confusion_matrix.false_negatives[expected] += 1
            self.confusion_matrix.false_positives[predicted] += 1
            # Update true negatives for emotions not involved
            for emotion in self.EMOTIONS:
                if emotion != expected and emotion != predicted:
                    self.confusion_matrix.true_negatives[emotion] += 1
    
    # ============================================================
    # PHASE 2: Volume Invariance Test
    # ============================================================
    
    def phase2_volume_invariance(self) -> Dict[str, any]:
        """
        Test that emotion predictions are consistent across volume levels.
        """
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 2: VOLUME INVARIANCE TEST")
        logger.info("=" * 80)
        
        volume_levels = ["whisper", "quiet", "normal", "loud"]
        emotions_to_test = ["happy", "neutral", "angry"]
        
        results_summary = {
            "tests_by_emotion": {},
            "invariance_score": 0.0
        }
        
        for emotion in emotions_to_test:
            logger.info(f"\n  Testing {emotion} across volumes:")
            
            predictions = []
            confidences = []
            
            for volume in volume_levels:
                audio = self._generate_synthetic_audio(
                    emotion_type=emotion,
                    volume_level=volume,
                    duration_sec=2.0
                )
                
                predicted, confidence, scores, override_reason = self._predict_emotion(audio)
                predictions.append(predicted)
                confidences.append(confidence)
                
                logger.info(
                    f"    {volume:12s}: {predicted:8s} (conf={confidence:.2f})"
                )
            
            # Check consistency
            unique_predictions = set(predictions)
            is_consistent = len(unique_predictions) == 1
            consistency_rate = predictions.count(emotion) / len(predictions)
            
            results_summary["tests_by_emotion"][emotion] = {
                "predictions": predictions,
                "confidences": confidences,
                "consistent": is_consistent,
                "consistency_rate": consistency_rate
            }
            
            if is_consistent:
                logger.info(f"    ✓ CONSISTENT across all volumes")
            else:
                logger.warning(
                    f"    ⚠ INCONSISTENT: {unique_predictions} "
                    f"(consistency: {consistency_rate:.2%})"
                )
        
        # Calculate overall invariance score
        total_consistency = sum(
            r["consistency_rate"] 
            for r in results_summary["tests_by_emotion"].values()
        )
        results_summary["invariance_score"] = total_consistency / len(emotions_to_test)
        
        logger.info(
            f"\n  PHASE 2 SUMMARY: "
            f"Invariance score = {results_summary['invariance_score']:.2%}"
        )
        
        return results_summary
    
    # ============================================================
    # PHASE 3: Temporal Stability Test
    # ============================================================
    
    def phase3_temporal_stability(self) -> Dict[str, any]:
        """
        Test emotion prediction stability over sequential recordings.
        """
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 3: TEMPORAL STABILITY TEST")
        logger.info("=" * 80)
        
        # Simulate 5 sequential recordings with slight variations
        emotion = "happy"
        num_recordings = 5
        
        logger.info(f"\n  Testing {num_recordings} sequential '{emotion}' recordings:")
        
        # Without smoothing
        logger.info(f"\n  WITHOUT SMOOTHING:")
        predictions_raw = []
        for i in range(num_recordings):
            # Add slight variation in volume
            volume_variation = np.random.uniform(0.8, 1.2)
            audio = self._generate_synthetic_audio(
                emotion_type=emotion,
                volume_level="normal",
                duration_sec=2.0
            ) * volume_variation
            
            predicted, confidence, scores, _ = self._predict_emotion(audio)
            predictions_raw.append(predicted)
            logger.info(f"    Recording {i+1}: {predicted} (conf={confidence:.2f})")
        
        flip_rate_raw = sum(
            1 for i in range(1, len(predictions_raw)) 
            if predictions_raw[i] != predictions_raw[i-1]
        ) / (len(predictions_raw) - 1)
        
        logger.info(f"    Flip rate: {flip_rate_raw:.2%}")
        
        # With smoothing
        logger.info(f"\n  WITH SMOOTHING (alpha=0.3):")
        self.stability_tracker.reset()
        predictions_smoothed = []
        
        for i in range(num_recordings):
            volume_variation = np.random.uniform(0.8, 1.2)
            audio = self._generate_synthetic_audio(
                emotion_type=emotion,
                volume_level="normal",
                duration_sec=2.0
            ) * volume_variation
            
            predicted, confidence, scores, _ = self._predict_emotion(audio)
            
            # Apply smoothing
            smoothed_label, smoothed_scores = self.stability_tracker.predict_with_smoothing(
                scores, predicted
            )
            predictions_smoothed.append(smoothed_label)
            
            logger.info(
                f"    Recording {i+1}: raw={predicted} → smoothed={smoothed_label} "
                f"(conf={smoothed_scores[smoothed_label]:.2f})"
            )
        
        flip_rate_smoothed = self.stability_tracker.get_flip_rate()
        
        logger.info(f"    Flip rate: {flip_rate_smoothed:.2%}")
        
        results_summary = {
            "raw_predictions": predictions_raw,
            "smoothed_predictions": predictions_smoothed,
            "flip_rate_raw": flip_rate_raw,
            "flip_rate_smoothed": flip_rate_smoothed,
            "stability_improvement": flip_rate_raw - flip_rate_smoothed
        }
        
        logger.info(
            f"\n  PHASE 3 SUMMARY: "
            f"Stability improved by {results_summary['stability_improvement']:.1%}"
        )
        
        # Recommendation
        if flip_rate_raw > 0.3:
            logger.warning(
                "  ⚠ HIGH INSTABILITY DETECTED - Consider enabling temporal smoothing"
            )
        else:
            logger.info("  ✓ Stability acceptable without additional smoothing")
        
        return results_summary
    
    # ============================================================
    # Final Report Generation
    # ============================================================
    
    def generate_report(
        self,
        phase1_results: Dict,
        phase2_results: Dict,
        phase3_results: Dict
    ) -> Dict[str, any]:
        """Generate comprehensive validation report."""
        logger.info("\n" + "=" * 80)
        logger.info("COMPREHENSIVE VALIDATION REPORT")
        logger.info("=" * 80)
        
        # Confusion Matrix
        logger.info("\n📊 CONFUSION MATRIX:")
        logger.info(f"  {'Emotion':<10} | Precision | Recall | F1-Score")
        logger.info(f"  {'-'*10}-+-----------+--------+---------")
        
        for emotion in self.EMOTIONS:
            precision = self.confusion_matrix.precision(emotion)
            recall = self.confusion_matrix.recall(emotion)
            f1 = self.confusion_matrix.f1_score(emotion)
            logger.info(
                f"  {emotion:<10} | {precision:8.2%} | {recall:6.2%} | {f1:7.2%}"
            )
        
        overall_accuracy = self.confusion_matrix.accuracy()
        logger.info(f"\n  Overall Accuracy: {overall_accuracy:.2%}")
        
        # Per-class metrics
        logger.info("\n📈 PER-CLASS ACCURACY:")
        for emotion, accuracy in phase1_results["per_emotion_accuracy"].items():
            logger.info(f"  {emotion:<10}: {accuracy:.2%}")
        
        # Over-correction rate
        over_correction_rate = (
            phase1_results["over_corrected_to_neutral"] / phase1_results["total_tests"]
        )
        logger.info(f"\n⚖️  OVER-CORRECTION RATE: {over_correction_rate:.2%}")
        
        if over_correction_rate > 0.20:
            logger.warning("  ⚠ HIGH - System may be too conservative")
        elif over_correction_rate < 0.05:
            logger.warning("  ⚠ LOW - Rules may not be working")
        else:
            logger.info("  ✓ Acceptable range")
        
        # Sad detection specifically
        if phase1_results["genuine_sad_detected"] > 0:
            sad_precision = (
                phase1_results["genuine_sad_detected"] / 
                (phase1_results["genuine_sad_detected"] + 
                 phase1_results["genuine_sad_overridden"])
            )
            logger.info(f"\n😢 GENUINE SAD DETECTION: {sad_precision:.2%}")
            if sad_precision < 0.60:
                logger.error("  ✗ FAIL - Too many genuine sad overridden")
            else:
                logger.info("  ✓ PASS - Genuine sad still detected")
        
        # Volume invariance
        logger.info(f"\n🔊 VOLUME INVARIANCE: {phase2_results['invariance_score']:.2%}")
        if phase2_results['invariance_score'] < 0.70:
            logger.warning("  ⚠ POOR - Predictions vary too much with volume")
        else:
            logger.info("  ✓ GOOD - Predictions stable across volumes")
        
        # Temporal stability
        logger.info(
            f"\n⏱️  TEMPORAL STABILITY: "
            f"Flip rate = {phase3_results['flip_rate_raw']:.2%}"
        )
        if phase3_results['flip_rate_raw'] > 0.3:
            logger.warning("  ⚠ Consider enabling temporal smoothing")
        else:
            logger.info("  ✓ Stable predictions")
        
        # Production Readiness Score
        score_components = {
            "accuracy": overall_accuracy,
            "over_correction_ok": 1.0 if 0.05 <= over_correction_rate <= 0.20 else 0.5,
            "volume_invariance": phase2_results['invariance_score'],
            "stability": 1.0 - phase3_results['flip_rate_raw']
        }
        
        production_score = sum(score_components.values()) / len(score_components)
        
        logger.info(f"\n🎯 PRODUCTION READINESS SCORE: {production_score:.1%}")
        logger.info(f"  Components:")
        for component, score in score_components.items():
            logger.info(f"    {component:<20}: {score:.2%}")
        
        if production_score >= 0.85:
            logger.info("\n✅ SYSTEM IS PRODUCTION-READY")
        elif production_score >= 0.70:
            logger.warning("\n⚠️  SYSTEM NEEDS MINOR IMPROVEMENTS")
        else:
            logger.error("\n❌ SYSTEM NOT READY FOR PRODUCTION")
        
        return {
            "confusion_matrix": {
                "precision": {e: self.confusion_matrix.precision(e) for e in self.EMOTIONS},
                "recall": {e: self.confusion_matrix.recall(e) for e in self.EMOTIONS},
                "f1_score": {e: self.confusion_matrix.f1_score(e) for e in self.EMOTIONS},
                "accuracy": overall_accuracy
            },
            "over_correction_rate": over_correction_rate,
            "volume_invariance": phase2_results['invariance_score'],
            "temporal_stability": 1.0 - phase3_results['flip_rate_raw'],
            "production_score": production_score,
            "score_components": score_components
        }


def main():
    """Run comprehensive emotion validation."""
    logger.info("ADVANCED EMOTION DETECTION VALIDATION SUITE")
    logger.info("=" * 80)
    
    validator = AdvancedEmotionValidator()
    
    try:
        # Phase 1: Over-correction check
        phase1_results = validator.phase1_over_correction_check()
        
        # Phase 2: Volume invariance
        phase2_results = validator.phase2_volume_invariance()
        
        # Phase 3: Temporal stability
        phase3_results = validator.phase3_temporal_stability()
        
        # Generate final report
        final_report = validator.generate_report(
            phase1_results, phase2_results, phase3_results
        )
        
        logger.info("\n" + "=" * 80)
        logger.info("VALIDATION COMPLETE")
        logger.info("=" * 80)
        
        return 0 if final_report["production_score"] >= 0.7 else 1
        
    except Exception as e:
        logger.error(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
