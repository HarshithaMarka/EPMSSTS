# PILOT VALIDATION — 8 Sample Recording Checkpoint

## Objective
Validate recording quality, preprocessing behavior, and emotion classification **before** investing in 44-sample dataset.

---

## PILOT RECORDING REQUIREMENTS (8 Samples Total)

### Batch 1: Normal Volume Core Emotions (6 samples)
Record these first to establish baseline:

1. **happy_normal_pilot_01.wav**
   - Sentence: "I just got the job I wanted."
   - Emotion: Natural happiness (slight smile voice)
   - Volume: Normal conversational
   - Duration: 3-6 seconds

2. **happy_normal_pilot_02.wav**
   - Sentence: "This is the best day I've had."
   - Emotion: Natural happiness
   - Volume: Normal conversational
   - Duration: 3-6 seconds

3. **sad_normal_pilot_01.wav**
   - Sentence: "I miss you more than I can say."
   - Emotion: Natural sadness (slower, lower pitch, softer)
   - Volume: Normal conversational
   - Duration: 3-6 seconds

4. **sad_normal_pilot_02.wav**
   - Sentence: "I feel really tired today."
   - Emotion: Natural sadness (reduced energy)
   - Volume: Normal conversational
   - Duration: 3-6 seconds

5. **angry_normal_pilot_01.wav**
   - Sentence: "This is completely unacceptable."
   - Emotion: Natural anger (controlled tension, NOT shouting)
   - Volume: Normal conversational
   - Duration: 3-6 seconds

6. **angry_normal_pilot_02.wav**
   - Sentence: "I can't believe this happened again."
   - Emotion: Natural anger (sharp articulation)
   - Volume: Normal conversational
   - Duration: 3-6 seconds

### Batch 2: Volume Extremes (2 samples)

7. **sad_whisper_pilot_01.wav**
   - Sentence: "I don't know what to do anymore."
   - Emotion: Natural sadness
   - Volume: **Whisper** (clearly quieter, still intelligible)
   - Duration: 3-6 seconds

8. **angry_loud_pilot_01.wav**
   - Sentence: "That was not okay."
   - Emotion: Natural anger
   - Volume: **Loud** (strong projection, NO clipping)
   - Duration: 3-6 seconds

---

## RECORDING SETTINGS VERIFICATION
Before starting:
- [ ] Format: WAV
- [ ] Sample Rate: 16000 Hz
- [ ] Channels: Mono
- [ ] Mic distance: 15-20 cm
- [ ] Room quiet (no fan/AC noise)
- [ ] Gain set so normal speech peaks at -12 to -6 dB

---

## SAVE LOCATIONS
Place files in appropriate folders:
- `happy_normal_pilot_*.wav` → `data/happy/normal/`
- `sad_normal_pilot_*.wav` → `data/sad/normal/`
- `sad_whisper_pilot_*.wav` → `data/sad/whisper/`
- `angry_normal_pilot_*.wav` → `data/angry/normal/`
- `angry_loud_pilot_*.wav` → `data/angry/loud/`

---

## IMMEDIATE POST-RECORDING CHECKS
For each file:
- [ ] Duration is 3-6 seconds
- [ ] No clipping (peaks below 0 dB)
- [ ] No background noise dominates
- [ ] Emotion sounds natural (not theatrical)
- [ ] Whisper is clearly quieter than normal
- [ ] Loud is clearly stronger than normal (but not distorted)

---

## VALIDATION PIPELINE (Run After Recording)

### Step 1: Bootstrap Classification
```bash
python emotion_assisted_prelabeling.py --project-root . --data-dir data --min-confidence 0.65
```

### Step 2: Balance Gate Check
```bash
python check_dataset_balance.py
```

### Step 3: Real Mic KPI Validation
```bash
python emotion_real_mic_validation.py
```

---

## PILOT SUCCESS CRITERIA

### Must Pass:
- ✅ Sad recall ≥ 50% (at least 1 of 2 sad samples correctly classified)
- ✅ No severe misclassification (e.g., sad → happy, angry → happy)
- ✅ Whisper sample has energy band: `very_low` or `low`
- ✅ Loud sample has energy band: `high` or `normal` (elevated)
- ✅ No systematic preprocessing failures

### Red Flags (STOP if any occur):
- ❌ Both sad samples misclassified as happy/excited
- ❌ Whisper classified as `high` energy band
- ❌ Loud sample clipped or distorted
- ❌ All samples route to `review_required` (confidence too low)

---

## DECISION LOGIC

**IF pilot passes:**
→ Proceed with full 44-sample recording
→ Recording style and quality are validated
→ Preprocessing + model behavior is reasonable

**IF pilot fails:**
→ STOP full recording
→ Diagnose root cause:
  - Recording technique issue (too theatrical, wrong volume)
  - Mic positioning/gain issue
  - Energy band mapping issue
  - Confidence calibration too strict
→ Fix identified issue
→ Re-run pilot

---

## Expected Timeline
- Recording 8 samples: **6-8 minutes**
- Running validation pipeline: **2-3 minutes**
- Analyzing results: **2 minutes**
- Total pilot checkpoint: **~12 minutes**

---

**READY TO BEGIN PILOT RECORDING**

Record the 8 samples following the specifications above, then signal completion.
Validation pipeline will execute immediately.
