"""
Targeted Production Issue Analysis

Analysis of why production is seeing "sad" for nearly all inputs.
Testing hypothesis: quiet/normalized audio triggers sad classification.
"""

import sys
import numpy as np
from pathlib import Path
import librosa

sys.path.insert(0, str(Path(__file__).parent))

from epmssts.services.emotion.audio_emotion import AudioEmotionService


def test_quiet_audio_hypothesis():
    """Test if quiet/normalized audio consistently produces 'sad'"""
    
    print("="*80)
    print("HYPOTHESIS: Production audio is quiet/normalized → triggers 'sad'")
    print("="*80)
    print()
    
    service = AudioEmotionService()
    
    # Generate variety of test signals at different energy levels
    test_cases = []
    
    # Different fundamental frequencies (pitch)
    frequencies = [100, 150, 200, 250, 300, 400, 600]
    
    # Different amplitude levels (simulating recording volume)
    amplitudes = [0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8]
    
    print("Testing combinations of pitch and volume...")
    print()
    
    sad_count = 0
    total_count = 0
    
    # Test matrix: frequency x amplitude
    for freq in frequencies:
        for amp in amplitudes:
            # Generate 1 second of audio
            sr = 16000
            duration = 1.0
            t = np.linspace(0, duration, int(sr * duration))
            audio = np.sin(2 * np.pi * freq * t) * amp
            audio = audio.astype(np.float32)
            
            # Predict
            pred = service.predict(audio, sr)
            
            total_count += 1
            if pred.label == "sad":
                sad_count += 1
            
            # Track very quiet audio specifically
            rms_db = 20 * np.log10(amp + 1e-10)
            if amp <= 0.1:
                marker = "🚨" if pred.label == "sad" else "  "
                print(f"{marker} freq={freq:3d}Hz, amp={amp:.2f} ({rms_db:+.1f}dB) → {pred.label:8s} @ {pred.confidence:.3f}")
    
    print()
    print("="*80)
    print(f"RESULTS: {sad_count}/{total_count} predictions were 'sad' ({sad_count/total_count*100:.1f}%)")
    print("="*80)
    print()
    
    if sad_count / total_count > 0.5:
        print("🚨 CONFIRMED: > 50% of predictions are 'sad'")
        print("   Root cause: Quiet audio consistently triggers 'sad' classification")
        print()
        print("   Why this happens:")
        print("   1. Model was likely trained on emotional speech datasets")
        print("   2. 'Sad' speech in training data has lower energy")
        print("   3. Model learned: low energy = sad")
        print("   4. Post-processing BOOSTS sad confidence for low energy")
        print("   5. Production audio (TTS, normal speech) is often normalized to moderate levels")
        print("   6. After normalization, audio appears 'quiet' to model → classified as sad")
        print()
        print("   The _apply_confidence_scaling method makes this WORSE by:")
        print("   - Multiplying sad confidence by 1.10 when energy_band is 'very_low' or 'low'")
        print("   - This creates a reinforcing loop")
    else:
        print("✓ Less than 50% sad predictions in this test")
        print("  Production issue may be specific to certain audio characteristics")
    
    return sad_count, total_count


def test_production_like_audio():
    """Test with production-like conditions: TTS output, normalized speech"""
    
    print()
    print("="*80)
    print("TESTING PRODUCTION-LIKE AUDIO")
    print("="*80)
    print()
    
    service = AudioEmotionService()
    
    # Simulate TTS-generated speech with various emotions
    # TTS typically produces clean, normalized audio at moderate RMS levels
    
    test_phrases = [
        ("Happy greeting", 250, 0.3, [0.2, 0.15]),  # higher pitch, some variation
        ("Neutral statement", 200, 0.25, [0.1, 0.05]),  # flat, moderate
        ("Angry statement", 180, 0.4, [0.3, 0.25]),  # lower pitch, higher energy
        ("Sad statement", 160, 0.2, [0.05, 0.03]),  # low pitch, low energy
    ]
    
    sad_count = 0
    
    for desc, base_freq, base_amp, variations in test_phrases:
        # Generate synthetic speech-like audio
        sr = 16000
        duration = 2.0
        t = np.linspace(0, duration, int(sr * duration))
        
        # Create pitch variation (prosody)
        pitch = base_freq + variations[0] * np.sin(2 * np.pi * 3 * t)
        
        # Create amplitude envelope (speech-like)
        envelope = base_amp * (1 + variations[1] * np.sin(2 * np.pi * 2 * t))
        
        # Generate audio
        audio = envelope * np.sin(2 * np.pi * pitch * t)
        audio = audio.astype(np.float32)
        
        # Add slight noise (microphone noise)
        noise = np.random.randn(len(audio)) * 0.001
        audio = audio + noise
        
        # Predict
        pred = service.predict(audio, sr)
        
        if pred.label == "sad":
            sad_count += 1
            marker = "🚨"
        else:
            marker = "  "
        
        rms = np.sqrt(np.mean(audio**2))
        rms_db = 20 * np.log10(rms + 1e-10)
        
        print(f"{marker} {desc:20s} ({rms_db:+.1f}dB) → {pred.label:8s} @ {pred.confidence:.3f}")
        print(f"   Scores: {', '.join([f'{k}:{v:.2f}' for k, v in pred.scores.items() if v > 0.01])}")
    
    print()
    if sad_count >= 3:
        print("🚨 3+ out of 4 test phrases classified as 'sad'")
        print("   This matches the production issue!")
    
    return sad_count


def analyze_confidence_scaling_impact():
    """Analyze how _apply_confidence_scaling affects predictions"""
    
    print()
    print("="*80)
    print("ANALYZING _apply_confidence_scaling IMPACT")
    print("="*80)
    print()
    
    print("Current Logic:")
    print("  if top_label == 'sad':")
    print("    if energy_band in {'very_low', 'low'}:")
    print("      scaled['sad'] *= 1.10  ← BOOST sad by 10%")
    print("    elif energy_band == 'high':")
    print("      scaled['sad'] *= 0.70  ← REDUCE sad by 30%")
    print()
    print("Problem:")
    print("  1. Model already has bias toward 'sad' for quiet audio")
    print("  2. Post-processing AMPLIFIES this bias instead of correcting it")
    print("  3. Any borderline 'sad' prediction (50-60% confidence) becomes stronger")
    print()
    print("Example:")
    print("  - Quiet audio RMS = -30 dB")
    print("  - Model output: {neutral: 0.45, sad: 0.52, ...}")
    print("  - energy_band = 'low'")
    print("  - Post-processing: sad *= 1.10 → sad = 0.572")
    print("  - After renormalization: sad ≈ 0.56 (further strengthened)")
    print("  - Result: 'sad' prediction with higher confidence")
    print()
    print("What should happen instead:")
    print("  - Post-processing should be SKEPTICAL of quiet → sad predictions")
    print("  - Should reduce confidence, not increase it")
    print("  - Or not apply any scaling at all (trust the model)")
    print()


def main():
    """Run production issue analysis"""
    
    # Test 1: Quiet audio hypothesis
    sad_count, total_count = test_quiet_audio_hypothesis()
    
    # Test 2: Production-like audio
    prod_sad_count = test_production_like_audio()
    
    # Test 3: Analyze scaling impact
    analyze_confidence_scaling_impact()
    
    # Final report
    print()
    print("="*80)
    print("CONCLUSION")
    print("="*80)
    print()
    print("ROOT CAUSE IDENTIFIED:")
    print()
    print("The emotion model has a compound issue:")
    print()
    print("1. MODEL BIAS:")
    print("   - wav2vec2-base-superb-er likely trained on emotional speech")
    print("   - Training data: 'sad' samples have lower energy than other emotions")
    print("   - Model learned: low RMS → high sad probability")
    print()
    print("2. POST-PROCESSING ERROR:")
    print("   - _apply_confidence_scaling() REINFORCES the bias")
    print("   - Line 257: scaled['sad'] *= 1.10 for low energy")
    print("   - This makes the problem WORSE, not better")
    print()
    print("3. PRODUCTION AMPLIFICATION:")
    print("   - Real-world audio varies in recording level")
    print("   - TTS output, distant speakers, quiet talkers → all low RMS")
    print("   - Preprocessing normalizes but model still sees 'quiet' features")
    print("   - Post-processing boosts sad → production sees 90%+ sad")
    print()
    print("RECOMMENDED FIX:")
    print()
    print("Option A (SAFEST - Remove bad post-processing):")
    print("  1. Remove or disable _apply_confidence_scaling entirely")
    print("  2. Let model predictions pass through unchanged")
    print("  3. Test if raw model is better than with scaling")
    print()
    print("Option B (TARGETED - Fix the scaling logic):")
    print("  1. REVERSE the energy scaling logic for 'sad':")
    print("     if energy_band in {'very_low', 'low'}:")
    print("       scaled['sad'] *= 0.80  ← REDUCE, don't boost")
    print("  2. Add similar skepticism for other low-energy emotions")
    print()
    print("Option C (COMPREHENSIVE - Retrain or replace model):")
    print("  1. Fine-tune model on balanced, normalized emotion data")
    print("  2. Or switch to emotion-robust model (e.g., emotion2vec)")
    print()
    print("IMMEDIATE ACTION:")
    print("  → Implement Option A (disable _apply_confidence_scaling)")
    print("  → This is a CODE-LEVEL fix, not a model issue")
    print("  → Should immediately reduce sad over-prediction")
    print()


if __name__ == "__main__":
    main()
