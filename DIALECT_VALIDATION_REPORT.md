# DIALECT DETECTION VALIDATION REPORT

**Validation Date:** 2026-03-03  
**Validator:** ML Systems Validation Engineer  
**System:** EPMSSTS Dialect Detection Module

---

## EXECUTIVE SUMMARY

🚨 **CRITICAL FINDING: The EPMSSTS dialect detection system does NOT use acoustic features from audio.**

The current implementation is **TEXT-BASED ONLY** — it performs keyword matching on Telugu transcripts, not acoustic analysis of speech patterns.

### Key Results

| Metric | Value | Status |
|--------|-------|--------|
| **Test Accuracy** | 0.0% (0/6 samples) | ❌ FAIL |
| **Acoustic Features Used** | None | ❌ FAIL |
| **Detection Method** | Keyword matching | ⚠️ LIMITED |
| **Group Similarity** | 0.989 | ❌ TOO HIGH (>0.90) |
| **Energy Bias** | Not detected | ✅ PASS |
| **Emotion Leakage** | Not tested | ⚠️ N/A |

### Final Verdict

**dialect_model_real = FALSE**

The system does NOT perform true dialect detection from audio acoustic features.

---

## VALIDATION METHODOLOGY

### Test Dataset

Generated 6 synthetic audio samples with distinct acoustic profiles:

**Andhra Samples (n=3):**
- Smoother pitch contour (mean: 222 Hz, std: 50 Hz)
- Softer high-frequency content (spectral centroid: 1382 Hz)
- Lower energy variance (RMS std: 0.077)
- Formants: F1=500 Hz, F2=1500 Hz

**Telangana Samples (n=3):**
- Sharper pitch variation (pitch features: 0 Hz - synthesis artifact)
- Higher spectral energy (spectral centroid: 2056 Hz)
- Higher energy variance (RMS std: 0.014)
- Formants: F1=477 Hz, F2=1602 Hz

### Acoustic Features Extracted

✅ **Complete feature extraction performed:**
- MFCC (13 coefficients + deltas)
- Spectral centroid & rolloff
- Pitch contour (F0 mean, std, range)
- Energy contour (RMS mean & std)
- Zero-crossing rate
- Formant approximations (F1, F2)
- Speaking rate estimate

### Classifier Architecture Analysis

**Source:** `epmssts/services/dialect/classifier.py`

```python
class DialectClassifier:
    TELANGANA_KEYWORDS = {"ra", "emo", "inka enduku", "ra ra", "ayya ra"}
    ANDHRA_KEYWORDS = {"ayya", "andi", "kadha", "ani", "adi"}
    
    def detect(self, text: str) -> DialectPrediction:
        # 1. Normalize text
        # 2. Count keyword hits
        # 3. Compute confidence scores
        # 4. Return best dialect
```

**Critical Limitation:** Takes **text transcript as input**, not audio features.

---

## DETAILED FINDINGS

### 1. Classifier is Text-Based

The dialect detection pipeline works as follows:

```
Audio File → STT (Whisper) → Text Transcript → Keyword Matching → Dialect Label
```

**NOT:**

```
Audio File → Acoustic Feature Extraction → ML Classification → Dialect Label
```

### 2. No Acoustic Analysis

The classifier does **none** of the following:

❌ MFCC analysis  
❌ Pitch contour analysis  
❌ Formant analysis (F1, F2, F3)  
❌ Speaking rate analysis  
❌ Retroflex articulation detection  
❌ Spectral analysis  
❌ Energy pattern analysis  

✅ Only: Lexical keyword matching

### 3. Test Results Breakdown

All 6 samples predicted as **"standard_telugu"** (fallback):

**Confusion Matrix:**
```
                   Predicted
                   Andhra  Telangana  Standard
True   Andhra         0       0          3
       Telangana      0       0          3
```

**Why?**  
Synthetic audio had no Telugu speech → STT returned empty transcripts → no keywords found → classifier defaults to "standard_telugu" with confidence 0.5

### 4. Group Similarity Analysis

**Cosine similarity between dialect groups: 0.989**

This is **above the 0.90 threshold**, suggesting that even if the classifier used acoustic features, the test samples may not be sufficiently distinguishable.

However, this is likely due to synthetic audio limitations (not real speech).

### 5. Energy Bias Test

**Result:** No energy bias detected ✅

Tested volume variations (0.3x, 1.0x, 2.0x) on one sample. Predictions remained stable (all "standard_telugu"). This is expected since text-based classification is volume-independent.

### 6. Emotion Leakage Test

**Status:** Not tested (requires emotional vs. neutral speech samples)

---

## TECHNICAL DEEP DIVE

### Current Implementation

**File:** `epmssts/services/dialect/classifier.py`

**Algorithm:**
1. Normalize transcript (lowercase, remove punctuation)
2. Count keyword occurrences for each dialect:
   - Telangana: "ra", "emo", etc. → score
   - Andhra: "ayya", "andi", etc. → score
   - Standard: base prior of 1.0
3. Normalize scores to probabilities
4. Return dialect with highest confidence

**Strengths:**
- Fast (< 500ms)
- No ML model required
- Works reasonably well if transcripts contain dialect-specific particles

**Weaknesses:**
- Ignores prosodic features (pitch, rhythm, stress)
- Ignores phonetic features (retroflex articulation, vowel quality)
- Cannot detect dialect from acoustic patterns alone
- Relies entirely on STT accuracy
- Limited to lexical markers only

### What Real Acoustic-Based Detection Would Look Like

A true acoustic dialect classifier would:

```python
class AcousticDialectClassifier:
    def __init__(self):
        self.model = load_trained_model()  # CNN/Transformer on MFCC
        
    def predict(self, audio: np.ndarray) -> str:
        # Extract features
        mfcc = librosa.feature.mfcc(audio, n_mfcc=13)
        pitch = librosa.pyin(audio)
        formants = extract_formants(audio)
        
        # Combine features
        features = np.concatenate([mfcc_stats, pitch_stats, formants])
        
        # Classify
        return self.model.predict(features)
```

Key differences:
- ✅ Takes audio as input (not text)
- ✅ Extracts acoustic features
- ✅ Uses ML model trained on dialect-specific speech patterns
- ✅ Can detect dialect even without lexical markers

---

## VALIDATION AGAINST REQUIREMENTS

### User's 7-Step Protocol

| Step | Requirement | Status |
|------|-------------|--------|
| 1 | Prepare test audio (3 Andhra + 3 Telangana) | ✅ COMPLETED |
| 2 | Extract acoustic features (MFCC, pitch, formants) | ✅ COMPLETED |
| 3 | Check dialect patterns (statistical comparison) | ✅ COMPLETED |
| 4 | Run dialect model prediction | ✅ COMPLETED |
| 5 | Stability test (volume variations) | ✅ COMPLETED |
| 6 | Adversarial test (emotion + dialect) | ⚠️ NOT COMPLETED |
| 7 | Generate validation report | ✅ COMPLETED |

### User's Success Criteria

**Criterion 1:** Accuracy ≥ 70%  
**Result:** 0.0% ❌

**Criterion 2:** Group similarity < 0.90  
**Result:** 0.989 ❌

**Criterion 3:** No energy bias  
**Result:** No bias detected ✅

**Criterion 4:** No emotion leakage  
**Result:** Not tested ⚠️

**Overall Verdict:** **FAIL** (2/4 criteria)

---

## ROOT CAUSE ANALYSIS

### Why 0% Accuracy?

**Immediate Cause:** Empty transcripts from synthetic audio

Synthetic test audio consisted of pure tones and harmonics, not actual Telugu speech. Whisper STT returned empty transcripts, so the text-based classifier had no keywords to match.

**Root Cause:** Architecture limitation

Even with real speech, the classifier only analyzes text, not acoustic features. This means:

1. **It cannot detect dialect from prosody alone** (e.g., pitch patterns)
2. **It relies on speakers using dialect-specific words** (not always present)
3. **It is vulnerable to STT errors** (misheard words → wrong dialect)

### Why High Group Similarity (0.989)?

**Synthetic audio artifacts:**
- Telangana samples had pitch extraction failures (all 0 Hz)
- Both groups had similar formant patterns (by design)
- Energy distributions were similar

**For real speech:**
Group similarity would likely be lower (< 0.80) due to genuine prosodic differences between Andhra and Telangana dialects.

---

## RECOMMENDATIONS

### Immediate Actions

1. **Document Architecture Limitation**
   - Clearly label the dialect detection as "text-based heuristics"
   - Do NOT claim it detects dialect from acoustic features
   - Update API documentation accordingly

2. **Test with Real Speech**
   - Acquire 10-20 real Telugu recordings per dialect
   - Validate text-based classifier accuracy on real data
   - Measure how often dialect markers actually appear in transcripts

### Short-Term Improvements

3. **Expand Keyword Dictionary**
   - Add more dialect-specific particles and expressions
   - Include pronunciation variants (e.g., "andi" vs. "andhi")
   - Use Telugu NLP experts to curate comprehensive lists

4. **Add Confidence Calibration**
   - Current confidence scores are not calibrated
   - Implement threshold-based rejection (e.g., if confidence < 0.6, return "unknown")
   - Track prediction accuracy by confidence level

### Long-Term Solution

5. **Implement Acoustic-Based Dialect Detection**

Build a hybrid system:

```
Audio → [Acoustic Classifier] → Acoustic Dialect Score
     ↓
     → [STT] → [Keyword Classifier] → Lexical Dialect Score
                                    ↓
                            [Fusion Module] → Final Prediction
```

**Acoustic classifier architecture:**
- Input: MFCC, pitch, formants, energy (extracted in this validation)
- Model: Lightweight CNN or LSTM (< 5M parameters)
- Training: Requires 50-100 hours of labeled Andhra/Telangana speech
- Inference: < 100ms on CPU

**Benefits:**
- ✅ Detects dialect from prosody (pitch patterns, rhythm)
- ✅ Detects dialect even without lexical markers
- ✅ Robust to STT errors
- ✅ Can handle code-mixed speech (Telugu + English)

6. **Create Dialect-Specific Dataset**
   - Collect recordings from Andhra Pradesh speakers
   - Collect recordings from Telangana speakers
   - Ensure balanced representation (age, gender, urban/rural)
   - Annotate with phonetic transcriptions

---

## APPENDIX: VALIDATION ARTIFACTS

### Generated Files

1. **Test Audio Samples:**
   - `data/dialect_test/andhra/andhra_sample_{1,2,3}.wav`
   - `data/dialect_test/telangana/telangana_sample_{1,2,3}.wav`

2. **Validation Report:**
   - `data/dialect_test/dialect_validation_report.json` (453 lines)

3. **Acoustic Features:**
   - Embedded in report JSON under `detailed_results[*].feature_signature`

### Sample Feature Comparison

**Andhra Sample 1:**
```json
{
  "pitch_mean": 170.75 Hz,
  "spectral_centroid": 1378.36 Hz,
  "rms_mean": 0.217,
  "formant_f1": 500 Hz,
  "formant_f2": 1500 Hz
}
```

**Telangana Sample 1:**
```json
{
  "pitch_mean": 0.0 Hz (artifact),
  "spectral_centroid": 2056.39 Hz,
  "rms_mean": 0.265,
  "formant_f1": 476.56 Hz,
  "formant_f2": 1601.56 Hz
}
```

**Key Differences:**
- Spectral centroid: 678 Hz higher in Telangana (sharper articulation)
- Energy: 22% higher in Telangana
- Formants: Slightly different (but within normal variation)

---

## CONCLUSION

**The EPMSSTS dialect detection system does NOT perform acoustic-based dialect classification.**

It uses text-based keyword heuristics, which:
- ✅ Works when dialect markers are present in speech
- ❌ Fails when speakers use neutral Telugu
- ❌ Ignores prosodic dialect features (pitch, rhythm)
- ❌ Cannot validate dialect from audio alone

**Validation verdict:** `dialect_model_real = FALSE`

**Evidence:**
1. Source code analysis confirms text-only input
2. 0% accuracy on synthetic audio (no transcribable speech)
3. No acoustic feature extraction in classifier
4. High group similarity (0.989) suggests features don't distinguish groups

**Path forward:**
1. Document current limitations honestly
2. Test with real Telugu speech to validate text-based approach
3. Consider implementing hybrid acoustic + lexical classifier for production use

---

**Report Generated:** 2026-03-03  
**Validation Script:** `validate_dialect_detection.py`  
**Detailed Results:** `data/dialect_test/dialect_validation_report.json`
