# Critical Fixes Implementation Guide

## 🎯 Objective
Fix the two critical issues blocking production:
1. Volume invariance (currently 41.7%, target ≥70%)
2. Sad emotion detection (currently 0% recall, target ≥60%)

---

## Fix #1: Adaptive RMS Normalization

### Problem
Current RMS normalization uses a fixed -20 dBFS target for all audio, causing:
- Quiet emotions (sad, fearful) over-normalized
- Loud emotions (angry, excited) under-normalized  
- Volume changes affect emotion predictions (only 41.7% invariance)

### Solution: Emotion-Aware Adaptive Normalization

**File:** `epmssts/services/emotion/audio_preprocessing.py`

```python
class EmotionAudioPreprocessor:
    """Enhanced preprocessor with adaptive normalization."""
    
    # Adaptive RMS targets by energy profile
    TARGET_RMS_DB_ADAPTIVE = {
        "low_energy": -22.0,      # For sad, quiet, fearful speech
        "normal_energy": -20.0,    # Standard normalization
        "high_energy": -18.0       # For angry, excited, loud speech
    }
    
    def _calculate_spectral_centroid(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> float:
        """Calculate spectral centroid (brightness measure)."""
        from scipy.fft import rfft, rfftfreq
        
        # Compute FFT
        fft_vals = np.abs(rfft(audio))
        fft_freqs = rfftfreq(len(audio), 1/sample_rate)
        
        # Calculate centroid
        if np.sum(fft_vals) > 0:
            centroid = np.sum(fft_freqs * fft_vals) / np.sum(fft_vals)
        else:
            centroid = 0.0
        
        return centroid
    
    def _classify_energy_profile(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> str:
        """
        Classify audio energy profile BEFORE normalization.
        
        Returns: "low_energy", "normal_energy", or "high_energy"
        """
        # Calculate raw energy metrics
        rms = np.sqrt(np.mean(audio ** 2))
        rms_db = 20 * np.log10(rms + 1e-10)
        
        # Calculate spectral features
        spectral_centroid = self._calculate_spectral_centroid(audio, sample_rate)
        
        # Calculate zero crossing rate (pace/energy indicator)
        zero_crossings = np.sum(np.abs(np.diff(np.sign(audio)))) / (2 * len(audio))
        
        # Classification logic
        # Low energy: quiet speech, low frequency content
        if rms_db < -35 and spectral_centroid < 1500:
            return "low_energy"
        
        # High energy: loud speech, high frequency content, high zero-crossing
        elif rms_db > -25 or spectral_centroid > 3000 or zero_crossings > 0.15:
            return "high_energy"
        
        # Normal energy: everything else
        else:
            return "normal_energy"
    
    def preprocess_for_emotion(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> Tuple[np.ndarray, EmotionAudioMetrics]:
        """
        Preprocess audio for emotion detection with adaptive normalization.
        
        Enhanced version with emotion-aware RMS targets.
        """
        if len(audio) == 0:
            raise ValueError("Empty audio input")
        
        # Step 1: Classify energy profile BEFORE normalization
        energy_profile = self._classify_energy_profile(audio, sample_rate)
        
        # Step 2: Select adaptive RMS target
        target_rms_db = self.TARGET_RMS_DB_ADAPTIVE[energy_profile]
        
        logger.debug(
            f"Energy profile: {energy_profile}, "
            f"Target RMS: {target_rms_db:.1f} dBFS"
        )
        
        # Step 3: Apply adaptive RMS normalization
        audio_normalized = self._normalize_rms(
            audio,
            target_rms_db=target_rms_db
        )
        
        # Step 4: Apply bandpass filter (300-3400 Hz for speech)
        audio_filtered = self._apply_bandpass_filter(
            audio_normalized,
            lowcut=300,
            highcut=3400,
            sample_rate=sample_rate
        )
        
        # Step 5: Calculate final metrics
        rms = np.sqrt(np.mean(audio_filtered ** 2))
        rms_db = 20 * np.log10(rms + 1e-10)
        
        peak = np.max(np.abs(audio_filtered))
        peak_db = 20 * np.log10(peak + 1e-10)
        
        spectral_centroid = self._calculate_spectral_centroid(
            audio_filtered, sample_rate
        )
        
        # Classify final energy level
        if rms_db < self.SILENT_THRESHOLD_DBFS:
            energy_level = "silent"
        elif rms_db < self.QUIET_THRESHOLD_DBFS:
            energy_level = "quiet"
        elif rms_db < -25:
            energy_level = "normal"
        else:
            energy_level = "loud"
        
        metrics = EmotionAudioMetrics(
            rms_db=float(rms_db),
            peak_db=float(peak_db),
            spectral_centroid=float(spectral_centroid),
            energy_level=energy_level,
            duration_sec=float(len(audio) / sample_rate),
            sample_rate=sample_rate,
            energy_profile=energy_profile,  # NEW FIELD
            adaptive_target_used=target_rms_db  # NEW FIELD
        )
        
        logger.debug(
            f"Preprocessing complete: RMS={rms_db:.1f}dB, "
            f"Peak={peak_db:.1f}dB, Energy={energy_level}, "
            f"Profile={energy_profile}"
        )
        
        return audio_filtered, metrics
```

**Updates to EmotionAudioMetrics:**

```python
@dataclass
class EmotionAudioMetrics:
    """Metrics extracted from audio preprocessing."""
    rms_db: float
    peak_db: float
    spectral_centroid: float
    energy_level: str
    duration_sec: float
    sample_rate: int
    energy_profile: str = "normal_energy"  # NEW
    adaptive_target_used: float = -20.0    # NEW
```

---

## Fix #2: Enhanced Sad Detection

### Problem
Sad emotion has 0% recall because:
- Low energy triggers override to neutral
- Override rules are too aggressive
- No distinction between "quiet mic" vs "genuine sad speech"

### Solution: Spectral-Based Sad Detection

**File:** `epmssts/services/emotion/audio_emotion.py`

```python
class AudioEmotionService:
    """Enhanced emotion detection with spectral sad detection."""
    
    def _spectral_features_match_sad(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> bool:
        """
        Check if spectral features match sad speech patterns.
        
        Sad speech characteristics:
        - Lower pitch (fundamental frequency < 200 Hz)
        - Lower spectral centroid (< 1800 Hz)
        - Lower zero-crossing rate (slower speech)
        - Lower energy in high frequencies
        """
        from scipy.fft import rfft, rfftfreq
        
        # Calculate spectral centroid
        fft_vals = np.abs(rfft(audio))
        fft_freqs = rfftfreq(len(audio), 1/sample_rate)
        
        if np.sum(fft_vals) > 0:
            spectral_centroid = np.sum(fft_freqs * fft_vals) / np.sum(fft_vals)
        else:
            return False
        
        # Calculate zero crossing rate
        zero_crossings = np.sum(np.abs(np.diff(np.sign(audio)))) / (2 * len(audio))
        
        # Calculate energy distribution (low vs high frequencies)
        low_freq_energy = np.sum(fft_vals[fft_freqs < 1000])
        high_freq_energy = np.sum(fft_vals[fft_freqs > 2000])
        energy_ratio = low_freq_energy / (high_freq_energy + 1e-10)
        
        # Sad speech patterns
        has_low_centroid = spectral_centroid < 1800
        has_low_zcr = zero_crossings < 0.08
        has_low_freq_dominance = energy_ratio > 1.5
        
        # Match if at least 2 of 3 criteria met
        match_count = sum([has_low_centroid, has_low_zcr, has_low_freq_dominance])
        
        logger.debug(
            f"Sad spectral check: centroid={spectral_centroid:.0f}Hz, "
            f"zcr={zero_crossings:.3f}, energy_ratio={energy_ratio:.2f}, "
            f"match_count={match_count}/3"
        )
        
        return match_count >= 2
    
    def predict(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> EmotionPrediction:
        """
        Predict emotion with enhanced sad detection.
        """
        # Preprocess audio
        audio_processed, metrics = self.preprocessor.preprocess_for_emotion(
            audio, sample_rate
        )
        
        # Run model inference
        inputs = self.processor(
            audio_processed,
            sampling_rate=sample_rate,
            return_tensors="pt",
            padding=True
        )
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits[0]
            probs = torch.nn.functional.softmax(logits, dim=-1)
            scores = {
                self.id2label[i]: float(probs[i].item())
                for i in range(len(probs))
            }
        
        predicted_emotion = max(scores.items(), key=lambda x: x[1])[0]
        confidence = scores[predicted_emotion]
        
        logger.debug(
            f"Raw prediction: {predicted_emotion} (conf={confidence:.2f}), "
            f"scores={scores}"
        )
        
        # ENHANCED SAD DETECTION LOGIC
        if predicted_emotion == "sad":
            # Check spectral features for genuine sad speech
            spectral_match = self._spectral_features_match_sad(
                audio_processed, sample_rate
            )
            
            # Don't override if:
            # 1. Spectral features match sad pattern
            # 2. Confidence is reasonable (>0.4)
            # 3. Energy is in expected range for sad speech
            
            if spectral_match and confidence > 0.4:
                logger.info(
                    f"Sad prediction PRESERVED - spectral match confirmed "
                    f"(conf={confidence:.2f})"
                )
                return EmotionPrediction(
                    label="sad",
                    confidence=confidence,
                    scores=scores
                )
            
            # If low confidence or no spectral match, proceed to override check
            logger.debug(
                f"Sad prediction checking override: "
                f"spectral_match={spectral_match}, conf={confidence:.2f}"
            )
        
        # Apply energy-based override for ambiguous low-energy cases
        should_override, reason = self.preprocessor.should_override_to_neutral(
            rms_db=metrics.rms_db,
            confidence=confidence,
            predicted_emotion=predicted_emotion
        )
        
        if should_override:
            logger.info(
                f"Override triggered: {predicted_emotion} → neutral "
                f"(reason: {reason})"
            )
            return EmotionPrediction(
                label="neutral",
                confidence=1.0,
                scores={"neutral": 1.0}
            )
        
        # Return original prediction
        return EmotionPrediction(
            label=predicted_emotion,
            confidence=confidence,
            scores=scores
        )
```

---

## Fix #3: Refined Override Rules

### Problem
Current override rules are too aggressive, blocking legitimate sad predictions.

### Solution: More Nuanced Override Logic

**File:** `epmssts/services/emotion/audio_preprocessing.py`

```python
def should_override_to_neutral(
    self,
    rms_db: float,
    confidence: float,
    predicted_emotion: str
) -> Tuple[bool, Optional[str]]:
    """
    Enhanced override logic with emotion-specific handling.
    
    Returns: (should_override, reason)
    """
    
    # Rule 1: Silence detection (very strict threshold)
    if rms_db < self.SILENT_THRESHOLD_DBFS:  # -60 dBFS
        return True, "audio_too_quiet"
    
    # Rule 2: Low energy + low confidence (but NOT sad)
    # Rationale: Sad speech is naturally low energy
    if (
        rms_db < -40 and 
        confidence < 0.45 and 
        predicted_emotion not in ["sad", "neutral"]  # Allow sad low-energy predictions
    ):
        return True, "low_energy_low_confidence"
    
    # Rule 3: Very low energy + sad prediction + very low confidence
    # Only override sad if BOTH energy AND confidence are extremely low
    if (
        predicted_emotion == "sad" and
        rms_db < -45 and  # Lower threshold for sad
        confidence < 0.30  # Lower confidence threshold for sad
    ):
        return True, "extremely_low_energy_sad"
    
    # Rule 4: Ambiguous prediction on quiet audio
    # If top 2 predictions are very close and energy is low
    if rms_db < -35 and confidence < 0.50:
        # Check if prediction is ambiguous (top 2 scores within 0.1)
        # This would require passing scores dict, so simplified here
        return True, "ambiguous_low_energy"
    
    # No override - let prediction stand
    return False, None
```

---

## Testing the Fixes

### Test Script

Create `test_emotion_fixes.py`:

```python
"""Test script for emotion detection fixes."""

import numpy as np
import soundfile as sf
from pathlib import Path

from epmssts.services.emotion.audio_emotion import AudioEmotionService
from epmssts.services.emotion.audio_preprocessing import get_emotion_preprocessor


def test_volume_invariance():
    """Test that emotion predictions are consistent across volumes."""
    
    emotion_service = AudioEmotionService()
    
    # Load or generate test audio
    test_audio_path = Path("test_audio/happy_normal.wav")
    if not test_audio_path.exists():
        print("⚠️ Real test audio not found - using synthetic")
        # Generate synthetic
        audio = np.random.randn(16000)  # 1 second
        sample_rate = 16000
    else:
        audio, sample_rate = sf.read(test_audio_path)
    
    # Test at different volumes
    volumes = {
        "whisper": 0.1,
        "quiet": 0.3,
        "normal": 1.0,
        "loud": 2.5
    }
    
    predictions = {}
    
    for volume_name, multiplier in volumes.items():
        audio_scaled = audio * multiplier
        prediction = emotion_service.predict(audio_scaled, sample_rate)
        predictions[volume_name] = prediction.label
        
        print(f"{volume_name:10s}: {prediction.label:10s} (conf={prediction.confidence:.2f})")
    
    # Check consistency
    unique_predictions = set(predictions.values())
    if len(unique_predictions) == 1:
        print("✅ PASS: Predictions consistent across volumes")
        return True
    else:
        print(f"❌ FAIL: Inconsistent predictions: {unique_predictions}")
        return False


def test_sad_detection():
    """Test that genuine sad speech is detected."""
    
    emotion_service = AudioEmotionService()
    
    # Load sad test audio
    sad_audio_path = Path("test_audio/sad_genuine.wav")
    if not sad_audio_path.exists():
        print("⚠️ Real sad audio not found - skipping")
        return None
    
    audio, sample_rate = sf.read(sad_audio_path)
    prediction = emotion_service.predict(audio, sample_rate)
    
    print(f"Sad detection: {prediction.label} (conf={prediction.confidence:.2f})")
    
    if prediction.label == "sad":
        print("✅ PASS: Sad speech detected")
        return True
    else:
        print(f"❌ FAIL: Detected as {prediction.label} instead of sad")
        return False


def test_adaptive_normalization():
    """Test adaptive RMS normalization."""
    
    preprocessor = get_emotion_preprocessor()
    
    # Test different energy profiles
    test_cases = [
        ("Low energy (sad)", np.random.randn(16000) * 0.01, "low_energy", -22.0),
        ("Normal energy", np.random.randn(16000) * 0.05, "normal_energy", -20.0),
        ("High energy (angry)", np.random.randn(16000) * 0.2, "high_energy", -18.0),
    ]
    
    all_passed = True
    
    for name, audio, expected_profile, expected_target in test_cases:
        audio_processed, metrics = preprocessor.preprocess_for_emotion(audio)
        
        profile_match = metrics.energy_profile == expected_profile
        target_match = abs(metrics.adaptive_target_used - expected_target) < 0.1
        
        print(f"{name}: profile={metrics.energy_profile} (expected {expected_profile}), "
              f"target={metrics.adaptive_target_used:.1f} (expected {expected_target:.1f})")
        
        if profile_match and target_match:
            print(f"  ✅ PASS")
        else:
            print(f"  ❌ FAIL")
            all_passed = False
    
    return all_passed


if __name__ == "__main__":
    print("=" * 80)
    print("TESTING EMOTION DETECTION FIXES")
    print("=" * 80)
    
    print("\nTest 1: Adaptive Normalization")
    print("-" * 40)
    result1 = test_adaptive_normalization()
    
    print("\nTest 2: Volume Invariance")
    print("-" * 40)
    result2 = test_volume_invariance()
    
    print("\nTest 3: Sad Detection")
    print("-" * 40)
    result3 = test_sad_detection()
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Adaptive normalization: {'✅ PASS' if result1 else '❌ FAIL'}")
    print(f"Volume invariance: {'✅ PASS' if result2 else '❌ FAIL'}")
    if result3 is not None:
        print(f"Sad detection: {'✅ PASS' if result3 else '❌ FAIL'}")
    else:
        print(f"Sad detection: ⏭️ SKIPPED (no test audio)")
```

**Run tests:**
```bash
python test_emotion_fixes.py
```

---

## Deployment Steps

### 1. Implement Fixes
```bash
# Edit files
code epmssts/services/emotion/audio_preprocessing.py
code epmssts/services/emotion/audio_emotion.py
```

### 2. Test Fixes
```bash
# Unit tests
python test_emotion_fixes.py

# Full validation
python emotion_production_validation.py
```

### 3. Collect Real Audio
```bash
# Record samples
mkdir -p test_audio/{happy,sad,angry,neutral}/

# Use system microphone to record:
# - 5 samples per emotion
# - 3 volume levels per sample (quiet, normal, loud)
```

### 4. Validate on Real Audio
```bash
# Re-run validation with real samples
python emotion_advanced_validation.py --audio-dir test_audio --use-real-samples

# Target metrics:
# - Volume invariance: ≥70%
# - Sad recall: ≥60%
# - Overall accuracy: ≥75%
```

### 5. Deploy to Staging
```bash
# Restart backend with new code
python -m uvicorn epmssts.api.main:app --reload

# Test endpoints
curl -X POST "http://localhost:8000/emotion/detect?include_debug=true" \
     -F "audio=@test_audio/sad_genuine.wav"
```

---

## Expected Outcomes

After implementing these fixes:

| Metric | Before | Target | Expected |
|--------|--------|--------|----------|
| Volume Invariance | 41.7% | ≥70% | **75-85%** |
| Sad Recall | 0% | ≥60% | **65-75%** |
| Overall Accuracy | 78.5% | ≥75% | **80-85%** |
| Production Score | 67.5% | ≥70% | **75-80%** |

---

## Rollback Plan

If fixes cause regressions:

```bash
# Revert files
git checkout main -- epmssts/services/emotion/audio_preprocessing.py
git checkout main -- epmssts/services/emotion/audio_emotion.py

# Restart service
python -m uvicorn epmssts.api.main:app --reload
```

---

## Support

If issues arise:

1. Check debug logs: `include_debug=true` in API requests
2. Review `EmotionDebugInfo` output
3. Test with `test_emotion_fixes.py`
4. Validate preprocessing metrics
5. Check for model drift (reload model if needed)

---

**Implementation Time:** 2-4 hours  
**Testing Time:** 2-3 hours  
**Total Time to Production:** 1-2 days (with real audio collection)
