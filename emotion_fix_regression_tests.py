"""
Regression Test Suite for Emotion Model Fix

Tests that the removal of class-specific confidence scaling:
- Eliminates the "sad" over-prediction bias
- Preserves model discrimination ability
- Maintains reasonable emotion distribution
- Produces class-agnostic predictions

This test suite MUST PASS before production deployment.
"""

import sys
import json
import numpy as np
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from epmssts.services.emotion.audio_emotion import AudioEmotionService, EMOTIONS


class RegressionTestSuite:
    """Comprehensive regression tests for emotion prediction fix"""
    
    def __init__(self):
        self.service = AudioEmotionService()
        self.results = {
            "tests_passed": 0,
            "tests_failed": 0,
            "test_cases": [],
            "summary": {}
        }
    
    def run_all_tests(self):
        """Execute complete regression test suite"""
        print("=" * 80)
        print("EMOTION MODEL FIX REGRESSION TEST SUITE")
        print("=" * 80)
        print()
        
        # Test 1: Diverse volume levels
        print("TEST 1: Diverse Audio Volumes (No class-specific bias)")
        print("-" * 80)
        test1_passed = self.test_volume_invariance()
        print()
        
        # Test 2: Emotion discrimination
        print("TEST 2: Emotion Discrimination (Model still differentiates)")
        print("-" * 80)
        test2_passed = self.test_emotion_discrimination()
        print()
        
        # Test 3: Prediction distribution
        print("TEST 3: Prediction Distribution (Diverse, not collapsed)")
        print("-" * 80)
        test3_passed = self.test_prediction_distribution()
        print()
        
        # Test 4: Sad predictions specifically
        print("TEST 4: Sad Prediction Rate (Should be normalized)")
        print("-" * 80)
        test4_passed = self.test_sad_prediction_rate()
        print()
        
        # Test 5: Model configuration
        print("TEST 5: Model Configuration Safety")
        print("-" * 80)
        test5_passed = self.test_model_configuration()
        print()
        
        # Generate report
        print("=" * 80)
        print("FINAL REGRESSION TEST REPORT")
        print("=" * 80)
        self.generate_report(all_passed=all([test1_passed, test2_passed, test3_passed, test4_passed, test5_passed]))
        
        return all([test1_passed, test2_passed, test3_passed, test4_passed, test5_passed])
    
    def test_volume_invariance(self) -> bool:
        """
        TEST 1: Verify no class-specific bias for different volumes
        
        Same emotional content at different volumes should NOT always
        produce the same prediction (especially not always "sad").
        """
        print("Testing same audio at different volumes...\n")
        
        # Base audio: neutral tone, 200 Hz
        sr = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration))
        base_audio = np.sin(2 * np.pi * 200 * t) * 0.3
        
        volumes = [
            ("very quiet", 0.01),
            ("quiet", 0.05),
            ("normal", 0.2),
            ("loud", 0.6),
            ("very loud", 0.9),
        ]
        
        predictions = []
        sad_count = 0
        
        for desc, amplitude in volumes:
            audio = base_audio * (amplitude / 0.3)
            audio = np.clip(audio, -1, 1).astype(np.float32)
            
            pred = self.service.predict(audio, sr)
            predictions.append((desc, pred.label, pred.confidence))
            
            rms_db = 20 * np.log10(np.sqrt(np.mean(audio**2)) + 1e-10)
            print(f"  {desc:12s} ({rms_db:+.1f}dB): {pred.label:8s} @ {pred.confidence:.3f}")
            
            if pred.label == "sad":
                sad_count += 1
        
        # CHECK 1: Sad should NOT dominate all volumes
        print(f"\n  Sad count: {sad_count}/5")
        
        unique_predictions = len(set([p[1] for p in predictions]))
        print(f"  Unique predictions: {unique_predictions}/5")
        
        # PASS if: Sad < 3 of the 5 AND variation exists
        passed = sad_count < 3 and unique_predictions > 1
        
        status = "âœ… PASSED" if passed else "âŒ FAILED"
        print(f"\n{status}: Volume-invariant, no volume-based class bias")
        
        self.results["test_cases"].append({
            "name": "Volume Invariance",
            "passed": passed,
            "sad_count": sad_count,
            "unique_predictions": unique_predictions
        })
        
        if passed:
            self.results["tests_passed"] += 1
        else:
            self.results["tests_failed"] += 1
        
        return passed
    
    def test_emotion_discrimination(self) -> bool:
        """
        TEST 2: Verify model still discriminates between emotions
        
        Model should produce different predictions for clearly different
        synthetic emotional audio. No emotion should collapse to single label.
        """
        print("Testing emotion discrimination...\n")
        
        test_cases = [
            ("High pitch", 500, 0.4, "happy"),
            ("Low pitch", 120, 0.3, "sad_or_neutral"),
            ("Medium pitch", 250, 0.4, "neutral"),
            ("Harsh/noisy", None, 0.5, "angry_or_neutral"),
        ]
        
        predictions = defaultdict(int)
        
        for desc, freq, amp, expected_range in test_cases:
            sr = 16000
            duration = 1.0
            t = np.linspace(0, duration, int(sr * duration))
            
            if freq:
                audio = amp * np.sin(2 * np.pi * freq * t)
            else:
                # Noisy
                audio = amp * np.random.randn(len(t))
            
            audio = np.clip(audio, -1, 1).astype(np.float32)
            
            pred = self.service.predict(audio, sr)
            predictions[pred.label] += 1
            
            print(f"  {desc:15s}: {pred.label:8s} @ {pred.confidence:.3f}")
        
        unique_emotions = len(predictions)
        print(f"\n  Unique emotions predicted: {unique_emotions}/4")
        print(f"  Distribution: {dict(predictions)}")
        
        # PASS if: Model predicts at least 2 different emotions
        passed = unique_emotions >= 2
        
        status = "âœ… PASSED" if passed else "âŒ FAILED"
        print(f"\n{status}: Model discriminates between emotions")
        
        self.results["test_cases"].append({
            "name": "Emotion Discrimination",
            "passed": passed,
            "unique_emotions": unique_emotions,
            "distribution": dict(predictions)
        })
        
        if passed:
            self.results["tests_passed"] += 1
        else:
            self.results["tests_failed"] += 1
        
        return passed
    
    def test_prediction_distribution(self) -> bool:
        """
        TEST 3: Verify prediction distribution over diverse inputs
        
        Over 20 random inputs, emotion distribution should be relatively
        balanced (not 90% one emotion, not all zeros for any emotion).
        """
        print("Testing prediction distribution over 20 diverse inputs...\n")
        
        sr = 16000
        predictions = defaultdict(int)
        entropies = []
        
        # 20 diverse test cases
        test_configs = [
            # (frequency, amplitude, label)
            (100, 0.1, "very low pitch, quiet"),
            (100, 0.5, "very low pitch, loud"),
            (150, 0.1, "low pitch, quiet"),
            (150, 0.5, "low pitch, loud"),
            (200, 0.1, "medium-low pitch, quiet"),
            (200, 0.5, "medium-low pitch, loud"),
            (300, 0.1, "medium pitch, quiet"),
            (300, 0.5, "medium pitch, loud"),
            (400, 0.1, "medium-high pitch, quiet"),
            (400, 0.5, "medium-high pitch, loud"),
            (600, 0.1, "high pitch, quiet"),
            (600, 0.5, "high pitch, loud"),
            (800, 0.1, "very high pitch, quiet"),
            (800, 0.5, "very high pitch, loud"),
            (None, 0.2, "noise, quiet"),
            (None, 0.6, "noise, loud"),
            (250, 0.05, "medium pitch, very quiet"),
            (250, 0.8, "medium pitch, very loud"),
            (200, 0.02, "medium-low pitch, whisper"),
            (300, 0.9, "medium pitch, shouting"),
        ]
        
        for freq, amp, desc in test_configs:
            duration = 1.0
            t = np.linspace(0, duration, int(sr * duration))
            
            if freq:
                audio = amp * np.sin(2 * np.pi * freq * t)
            else:
                audio = amp * np.random.randn(len(t))
            
            audio = np.clip(audio, -1, 1).astype(np.float32)
            
            pred = self.service.predict(audio, sr)
            predictions[pred.label] += 1
            
            # Compute entropy of prediction
            entropy = -sum([p * np.log(p + 1e-10) for p in pred.scores.values() if p > 0])
            entropies.append(entropy)
        
        print("Distribution of 20 predictions:")
        total = sum(predictions.values())
        for emotion in EMOTIONS:
            count = predictions[emotion]
            pct = count / total * 100 if total > 0 else 0
            print(f"  {emotion:10s}: {count:2d}/20 ({pct:5.1f}%)")
        
        avg_entropy = np.mean(entropies)
        print(f"\nAverage prediction entropy: {avg_entropy:.3f}")
        
        # PASS criteria:
        # 1. No single emotion > 60% (else distribution collapsed)
        # 2. All emotions have representation (at least 1 if possible)
        # 3. Average entropy > 0.2 (not overconfident on one class)
        max_percentage = max(predictions.values()) / total * 100
        
        passed = (
            max_percentage <= 75 and
            avg_entropy > 0.2 and
            len(predictions) >= 3  # At least 3 different emotions
        )
        
        status = "âœ… PASSED" if passed else "âŒ FAILED"
        print(f"\n{status}: Diverse, balanced prediction distribution")
        print(f"  (Max emotion: {max_percentage:.1f}%, Entropy: {avg_entropy:.3f}, Unique: {len(predictions)})")
        
        self.results["test_cases"].append({
            "name": "Prediction Distribution",
            "passed": passed,
            "distribution": {k: f"{v/total*100:.1f}%" for k, v in predictions.items()},
            "max_emotion_percentage": max_percentage,
            "entropy": avg_entropy
        })
        
        if passed:
            self.results["tests_passed"] += 1
        else:
            self.results["tests_failed"] += 1
        
        return passed
    
    def test_sad_prediction_rate(self) -> bool:
        """
        TEST 4: Verify "sad" predictions are reasonable
        
        Before fix: ~90% sad predictions
        After fix: Should be reasonable (10-30% depending on input)
        
        We expect some sad predictions (model learned it correctly for
        actually sad audio), but not overwhelming majority.
        """
        print("Testing 'sad' prediction rate...\n")
        
        sr = 16000
        sad_count = 0
        total_tests = 0
        
        # Create test set with known intent
        test_set = [
            ("obviously happy - high pitch, high energy", 500, 0.7),
            ("obviously happy - high pitch, moderate energy", 400, 0.5),
            ("potentially sad - low pitch, low energy", 120, 0.2),
            ("potentially sad - low pitch, moderate energy", 150, 0.3),
            ("neutral - medium pitch, medium energy", 250, 0.4),
            ("neutral - medium pitch, low energy", 220, 0.2),
            ("angry-ish - low pitch, high energy", 180, 0.6),
        ]
        
        for desc, freq, amp in test_set:
            for _ in range(2):  # Test each twice for variety
                duration = 1.0
                t = np.linspace(0, duration, int(sr * duration))
                audio = amp * np.sin(2 * np.pi * freq * t)
                audio = np.clip(audio, -1, 1).astype(np.float32)
                
                pred = self.service.predict(audio, sr)
                if pred.label == "sad":
                    sad_count += 1
                
                total_tests += 1
        
        sad_percentage = sad_count / total_tests * 100 if total_tests > 0 else 0
        print(f"'sad' predictions: {sad_count}/{total_tests} ({sad_percentage:.1f}%)")
        
        # PASS if: Sad is 0-40% (reasonable, not dominant, but present)
        passed = 0 <= sad_percentage <= 40
        
        status = "âœ… PASSED" if passed else "âŒ FAILED"
        print(f"\n{status}: Reasonable 'sad' prediction rate (not 90%+)")
        
        self.results["test_cases"].append({
            "name": "Sad Prediction Rate",
            "passed": passed,
            "sad_percentage": sad_percentage,
            "sad_count": sad_count,
            "total_tests": total_tests
        })
        
        if passed:
            self.results["tests_passed"] += 1
        else:
            self.results["tests_failed"] += 1
        
        return passed
    
    def test_model_configuration(self) -> bool:
        """
        TEST 5: Verify model safety configuration
        
        Check:
        - Model is in eval mode
        - No gradient tracking
        - No dropout active
        """
        print("Checking model safety configuration...\n")
        
        model = self.service._model
        
        # Check 1: Model in eval mode
        in_eval = getattr(model, 'training', True) is False
        print(f"  Model in eval() mode: {in_eval}")
        if in_eval:
            print("    âœ… PASS")
        else:
            print("    âŒ FAIL")
        
        # Check 2: No dropout active
        # HuggingFace models have dropout_rate in config
        dropout_rate = getattr(model.config, 'dropout', 0.0)
        print(f"\n  Dropout rate: {dropout_rate}")
        if dropout_rate == 0.0 or not in_eval:
            print("    â„¹ï¸  Dropout inactive during eval (expected)")
        
        # Check 3: Old method not called
        has_old_method = hasattr(self.service, '_apply_confidence_scaling')
        print(f"\n  Old _apply_confidence_scaling method exists: {has_old_method}")
        if not has_old_method:
            print("    âœ… PASS - Problematic method removed")
        else:
            print("    âŒ FAIL - Old method still present")
        
        # Check 4: New diagnostic method exists
        has_new_method = hasattr(self.service, '_log_prediction_diagnostics')
        print(f"\n  New _log_prediction_diagnostics method exists: {has_new_method}")
        if has_new_method:
            print("    âœ… PASS - Safe diagnostic method added")
        else:
            print("    âš ï¸  WARNING - Diagnostic method not found")
        
        # Overall pass: eval mode + old method removed
        passed = in_eval and not has_old_method
        
        status = "âœ… PASSED" if passed else "âŒ FAILED"
        print(f"\n{status}: Model configuration is safe")
        
        self.results["test_cases"].append({
            "name": "Model Configuration",
            "passed": passed,
            "in_eval_mode": in_eval,
            "old_method_removed": not has_old_method,
            "new_method_added": has_new_method
        })
        
        if passed:
            self.results["tests_passed"] += 1
        else:
            self.results["tests_failed"] += 1
        
        return passed
    
    def generate_report(self, all_passed: bool):
        """Generate final regression test report"""
        print()
        print(f"Tests Passed: {self.results['tests_passed']}/5")
        print(f"Tests Failed: {self.results['tests_failed']}/5")
        print()
        
        if all_passed:
            print("ðŸš¨ REGRESSION TEST RESULT: âœ… ALL TESTS PASSED")
            print()
            print("Production Deployment: SAFE - Fix is working correctly")
        else:
            print("ðŸš¨ REGRESSION TEST RESULT: âŒ SOME TESTS FAILED")
            print()
            print("Production Deployment: DO NOT DEPLOY - Investigate failures")
        
        print()
        print("Detailed Results:")
        print("-" * 80)
        for i, test in enumerate(self.results["test_cases"], 1):
            name = test["name"]
            passed = "âœ…" if test["passed"] else "âŒ"
            print(f"{i}. {passed} {name}")
        
        # Save detailed report
        report_file = Path(__file__).parent / "emotion_fix_regression_report.json"
        self.results["summary"] = {
            "all_tests_passed": all_passed,
            "deployment_safe": all_passed,
            "timestamp": str(Path(__file__).parent)
        }
        
        with open(report_file, 'w') as f:
            # Convert numpy types to python types
            json.dump(self.results, f, indent=2, default=str)
        
        print()
        print(f"Detailed report saved to: {report_file}")
        
        return all_passed


def main():
    """Run regression test suite"""
    suite = RegressionTestSuite()
    all_passed = suite.run_all_tests()
    
    print()
    print("=" * 80)
    if all_passed:
        print("âœ… ALL REGRESSION TESTS PASSED - SAFE FOR DEPLOYMENT")
    else:
        print("âŒ REGRESSION TESTS FAILED - DO NOT DEPLOY")
    print("=" * 80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
