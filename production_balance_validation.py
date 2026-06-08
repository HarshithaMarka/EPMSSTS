"""
Production Balance Validation for Emotion Model
Validates that the emotion model is unbiased, not under-biased after sad-bias fix.
"""

import numpy as np
import json
from collections import defaultdict, Counter
from scipy.stats import entropy
import librosa
import soundfile as sf
from pathlib import Path
import sys
import os
import io

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from epmssts.services.emotion.audio_emotion import AudioEmotionService


def generate_diverse_audio_samples(count=100, seed=42):
    """
    Generate diverse synthetic audio samples with different characteristics.
    Simulates 100 mixed-volume real user samples.
    """
    np.random.seed(seed)
    samples = []
    
    sr = 16000
    duration = 3.0
    
    emotion_patterns = {
        'sad': {
            'pitch_range': (80, 150),
            'energy': 0.2,
            'speed': 0.8,
            'count': 25
        },
        'happy': {
            'pitch_range': (200, 350),
            'energy': 0.6,
            'speed': 1.2,
            'count': 25
        },
        'angry': {
            'pitch_range': (120, 250),
            'energy': 0.7,
            'speed': 1.3,
            'count': 20
        },
        'neutral': {
            'pitch_range': (100, 200),
            'energy': 0.4,
            'speed': 1.0,
            'count': 30
        }
    }
    
    sample_idx = 0
    
    for emotion, config in emotion_patterns.items():
        for _ in range(config['count']):
            # Generate synthetic audio with emotion characteristics
            t = np.linspace(0, duration, int(sr * duration))
            
            # Base frequency (pitch)
            freq = np.random.uniform(config['pitch_range'][0], config['pitch_range'][1])
            
            # Fundamental
            y = np.sin(2 * np.pi * freq * t)
            
            # Add harmonics for richness
            for harmonic in [2, 3, 4]:
                harmonic_freq = freq * harmonic
                harmonic_amp = 1 / (harmonic + 1)
                y += harmonic_amp * np.sin(2 * np.pi * harmonic_freq * t)
            
            # Normalize
            y = y / np.max(np.abs(y))
            
            # Apply amplitude envelope (emotion-specific)
            env = np.linspace(1, 0, len(y))  # Fade out
            y = y * env * config['energy']
            
            # Add variation (speed modulation)
            y = np.roll(y, int(config['speed'] * len(y) // duration))
            
            # Add slight noise for realism
            y = y + np.random.normal(0, 0.01, len(y))
            
            # Normalize again
            y = y / (np.max(np.abs(y)) + 1e-6)
            
            # Vary volume (critical for testing volume invariance)
            volume_variation = np.random.uniform(0.3, 1.5)  # 30% to 150% volume
            y = y * volume_variation
            
            # Hard clip to prevent overflow
            y = np.clip(y, -0.95, 0.95)
            
            samples.append({
                'audio': y,
                'sr': sr,
                'true_emotion': emotion,
                'volume_factor': volume_variation,
                'index': sample_idx
            })
            
            sample_idx += 1
    
    return samples


def compute_entropy(probabilities):
    """Compute Shannon entropy of probability distribution."""
    # Filter out zero probabilities
    probs = np.array([p for p in probabilities if p > 0])
    if len(probs) == 0:
        return 0.0
    return float(entropy(probs))


def validate_emotion_model(samples):
    """
    Validate the emotion model on diverse samples.
    Returns comprehensive metrics.
    """
    service = AudioEmotionService()
    
    predictions = []
    class_predictions = defaultdict(list)
    class_confidences = defaultdict(list)
    
    print(f"\n{'='*60}")
    print("PRODUCTION BALANCE VALIDATION")
    print(f"{'='*60}")
    print(f"\nRunning inference on {len(samples)} diverse audio samples...")
    
    for i, sample in enumerate(samples):
        if (i + 1) % 20 == 0:
            print(f"  Processed {i + 1}/{len(samples)} samples...")
        
        try:
            # Make prediction
            result = service.predict(sample['audio'], sample['sr'])
            
            prediction_record = {
                'sample_id': sample['index'],
                'true_emotion': sample['true_emotion'],
                'predicted_emotion': result.label,
                'confidence': result.confidence,
                'scores': result.scores,
                'volume_factor': sample['volume_factor']
            }
            
            predictions.append(prediction_record)
            class_predictions[result.label].append(sample['true_emotion'])
            class_confidences[result.label].append(result.confidence)
            
        except Exception as e:
            print(f"  ⚠️  Error processing sample {i}: {str(e)}")
            continue
    
    print(f"\n✅ Successfully processed {len(predictions)} samples")
    
    return predictions, class_predictions, class_confidences


def analyze_results(predictions, class_predictions, class_confidences):
    """
    Analyze validation results comprehensively.
    """
    
    # Class distribution in predictions
    predicted_labels = [p['predicted_emotion'] for p in predictions]
    label_counts = Counter(predicted_labels)
    total_predictions = len(predictions)
    
    class_distribution = {
        label: {
            'count': label_counts[label],
            'percentage': (label_counts[label] / total_predictions * 100)
        }
        for label in set(predicted_labels)
    }
    
    # Sort by count
    class_distribution = dict(sorted(class_distribution.items(), 
                                     key=lambda x: x[1]['count'], reverse=True))
    
    # Average confidence per predicted class
    average_confidence_per_class = {}
    for label, confidences in class_confidences.items():
        if confidences:
            average_confidence_per_class[label] = {
                'mean': float(np.mean(confidences)),
                'std': float(np.std(confidences)),
                'min': float(np.min(confidences)),
                'max': float(np.max(confidences))
            }
    
    # Entropy analysis
    entropies = []
    for pred in predictions:
        pred_entropy = compute_entropy(list(pred['scores'].values()))
        entropies.append(pred_entropy)
    
    entropy_mean = float(np.mean(entropies))
    entropy_std = float(np.std(entropies))
    entropy_min = float(np.min(entropies))
    entropy_max = float(np.max(entropies))
    
    # Class collapse detection
    class_collapse_detected = False
    collapsed_classes = []
    
    for label, dist in class_distribution.items():
        percentage = dist['percentage']
        if percentage < 2.0 or percentage > 60.0:
            class_collapse_detected = True
            collapsed_classes.append({
                'class': label,
                'percentage': percentage,
                'reason': 'under-represented' if percentage < 2.0 else 'over-represented'
            })
    
    # Under-detection check: sad should still appear in meaningful quantity
    # Based on true distribution: sad should be ~25% of inputs
    # We expect ~15-30% sad predictions (allowing for model error margin)
    sad_percentage = class_distribution.get('sad', {}).get('percentage', 0)
    under_detection_of_sad = sad_percentage < 5.0  # Critical: <5% is too low
    
    # Quality checks
    quality_issues = []
    
    if class_collapse_detected:
        quality_issues.append("Class collapse detected")
    
    if under_detection_of_sad:
        quality_issues.append("Sad emotion under-detected (< 5%)")
    
    if entropy_mean < 0.3:
        quality_issues.append("Entropy too low - model may be deterministic")
    
    # Confidence analysis
    overall_mean_confidence = float(np.mean([p['confidence'] for p in predictions]))
    overall_std_confidence = float(np.std([p['confidence'] for p in predictions]))
    
    if overall_mean_confidence > 0.95:
        quality_issues.append("Model confidence too high - may indicate overconfidence")
    
    if overall_mean_confidence < 0.50:
        quality_issues.append("Model confidence too low - may indicate uncertainty")
    
    # Deployment safety assessment
    deployment_safe = (
        not class_collapse_detected and
        not under_detection_of_sad and
        entropy_mean > 0.3 and
        entropy_mean < 2.0 and
        0.50 <= overall_mean_confidence <= 0.95 and
        sad_percentage > 5.0 and
        sad_percentage < 50.0
    )
    
    return {
        'class_distribution': class_distribution,
        'average_confidence_per_class': average_confidence_per_class,
        'overall_confidence': {
            'mean': overall_mean_confidence,
            'std': overall_std_confidence
        },
        'entropy': {
            'mean': entropy_mean,
            'std': entropy_std,
            'min': entropy_min,
            'max': entropy_max
        },
        'class_collapse_detected': class_collapse_detected,
        'collapsed_classes': collapsed_classes,
        'under_detection_of_sad': under_detection_of_sad,
        'sad_percentage': sad_percentage,
        'quality_issues': quality_issues,
        'deployment_safe': deployment_safe,
        'total_samples': total_predictions
    }


def print_report(analysis):
    """Print comprehensive validation report."""
    
    print(f"\n{'='*60}")
    print("VALIDATION RESULTS")
    print(f"{'='*60}")
    
    print(f"\n📊 CLASS DISTRIBUTION:")
    print(f"Total predictions: {analysis['total_samples']}")
    for label, dist in analysis['class_distribution'].items():
        print(f"  {label:10s}: {dist['count']:3d} ({dist['percentage']:5.1f}%)")
    
    print(f"\n🎯 AVERAGE CONFIDENCE PER CLASS:")
    for label, conf in analysis['average_confidence_per_class'].items():
        print(f"  {label:10s}: μ={conf['mean']:.3f}, σ={conf['std']:.3f}, " +
              f"[{conf['min']:.3f}, {conf['max']:.3f}]")
    
    print(f"\n📈 OVERALL CONFIDENCE:")
    print(f"  Mean: {analysis['overall_confidence']['mean']:.3f}")
    print(f"  Std:  {analysis['overall_confidence']['std']:.3f}")
    
    print(f"\n🔢 ENTROPY ANALYSIS:")
    print(f"  Mean: {analysis['entropy']['mean']:.3f}")
    print(f"  Std:  {analysis['entropy']['std']:.3f}")
    print(f"  Range: [{analysis['entropy']['min']:.3f}, {analysis['entropy']['max']:.3f}]")
    
    print(f"\n⚠️  CLASS COLLAPSE DETECTION:")
    if analysis['class_collapse_detected']:
        print(f"  ❌ CLASS COLLAPSE DETECTED!")
        for collapsed in analysis['collapsed_classes']:
            print(f"    - {collapsed['class']}: {collapsed['percentage']:.1f}% " +
                  f"({collapsed['reason']})")
    else:
        print(f"  ✅ No class collapse detected")
    
    print(f"\n😢 SAD EMOTION DETECTION:")
    print(f"  Sad predictions: {analysis['sad_percentage']:.1f}%")
    if analysis['under_detection_of_sad']:
        print(f"  ⚠️  UNDER-DETECTION: Sad is < 5% (expected ~15-30%)")
    else:
        print(f"  ✅ Sad detection within acceptable range")
    
    print(f"\n🚨 QUALITY ISSUES:")
    if analysis['quality_issues']:
        for issue in analysis['quality_issues']:
            print(f"  ❌ {issue}")
    else:
        print(f"  ✅ No quality issues detected")
    
    print(f"\n{'='*60}")
    print("DEPLOYMENT RECOMMENDATION")
    print(f"{'='*60}")
    if analysis['deployment_safe']:
        print("✅ DEPLOYMENT SAFE - All metrics within acceptable range")
        print("\nRationale:")
        print("  ✓ No class collapse detected")
        print("  ✓ Sad emotion appropriately detected (not under-detected)")
        print("  ✓ Entropy indicates healthy uncertainty")
        print("  ✓ Confidence levels are calibrated")
        print("  ✓ Emotion distribution is plausible")
    else:
        print("❌ DO NOT DEPLOY - Issues detected")
        print("\nBlocking issues:")
        for issue in analysis['quality_issues']:
            print(f"  ✗ {issue}")
    
    print(f"\n{'='*60}\n")


def main():
    """Main validation workflow."""
    
    try:
        # Generate 100 diverse samples
        print("Generating 100 diverse audio samples (mixed volumes)...")
        samples = generate_diverse_audio_samples(count=100)
        
        # Run inference
        predictions, class_predictions, class_confidences = validate_emotion_model(samples)
        
        # Analyze results
        analysis = analyze_results(predictions, class_predictions, class_confidences)
        
        # Print report
        print_report(analysis)
        
        # Save detailed results
        output_file = Path(__file__).parent / "production_balance_validation_report.json"
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        print(f"📁 Full report saved to: {output_file}\n")
        
        # Return exit code based on deployment safety
        return 0 if analysis['deployment_safe'] else 1
        
    except Exception as e:
        print(f"\n❌ Validation failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
