# STRICT RECORDING EXECUTION CHECKLIST
## Emotion Validation Dataset — 44 Recordings

---

## PRE-RECORDING SETUP (Complete ONCE before session)

### Environment Preparation
- [ ] Close all windows (external noise isolation)
- [ ] Turn off fan, AC, heating systems
- [ ] Silence phone notifications
- [ ] Close all background apps (no keyboard/mouse clicks)
- [ ] Use same room for all 44 recordings (acoustic consistency)

### Equipment Setup
- [ ] Use SAME microphone for entire session
- [ ] Position mic **15-20 cm** from mouth
- [ ] Angle mic **15-30° off-axis** (reduce plosives)
- [ ] Verify mic stand is stable (no handling noise)
- [ ] Test that recording software is set to:
  - Format: WAV
  - Sample rate: 16000 Hz
  - Channels: Mono
  - Bit depth: 16-bit minimum

### Input Level Calibration
- [ ] Record 5-second test in "normal" volume
- [ ] Verify peak level stays between -12 dB and -6 dB
- [ ] Verify NO red clipping indicators
- [ ] Adjust input gain if needed
- [ ] Lock gain setting for entire session

### Baseline RMS Check
- [ ] Record "normal" baseline sample
- [ ] Measure RMS (should be around -20 to -18 dBFS)
- [ ] This is your "normal" volume reference
- [ ] Do NOT change mic position or gain during session

---

## PER-RECORDING EXECUTION (Repeat for EACH of 44 files)

### Step 1: File Naming
- [ ] Determine emotion + volume for this recording
- [ ] Name file: `{emotion}_{volume}_{index}.wav`
  - Example: `sad_whisper_001.wav`
- [ ] Prepare to save directly to: `data/{emotion}/{volume}/`

### Step 2: Mental Preparation (15 seconds)
- [ ] Read selected sentence
- [ ] Visualize natural context for this emotion
- [ ] **Do NOT exaggerate or act theatrically**
- [ ] Think of real-life situation that evokes this emotion
- [ ] Take natural breath

### Step 3: Record
- [ ] Press record
- [ ] Wait 0.3 seconds (avoid start click)
- [ ] Speak sentence with natural emotion
- [ ] Duration: **3-6 seconds only**
- [ ] Stop recording immediately after sentence ends
- [ ] **No trailing silence**

### Step 4: Immediate Quality Check (Do NOT skip)
- [ ] Play back recording
- [ ] Verify **no clipping** (visual waveform check)
- [ ] Verify **no background noise** dominates speech
- [ ] Verify **duration is 3-6 seconds**
- [ ] Verify **emotion sounds natural, not theatrical**
- [ ] If ANY check fails → DELETE and re-record immediately

### Step 5: RMS Verification
For volume consistency across session:
- [ ] Whisper recordings: RMS should be ~6-10 dB LOWER than baseline
- [ ] Normal recordings: RMS should match baseline (±2 dB)
- [ ] Loud recordings: RMS should be ~6-10 dB HIGHER than baseline
- [ ] If outside range → re-record with volume adjustment

### Step 6: Save & Log
- [ ] Save file with correct name in correct folder
- [ ] Mark completed in tracking matrix
- [ ] Move to next recording

---

## EMOTION-SPECIFIC EXECUTION GUIDANCE

### Happy (10 recordings: 2 whisper, 7 normal, 1 loud)
**Natural Context**: Good news, pleasant surprise, satisfaction
**Vocal Characteristics**:
- Slight upward pitch at sentence end
- Natural smile voice (lips slightly wider)
- Moderate energy increase (not euphoric)
- Slightly faster tempo than neutral

**Avoid**: Laughing, giggling, excessive brightness

**Sample Sentences**:
1. "I just got the job I wanted."
2. "This is the best day I've had."
3. "That made me really happy."
4. "Everything worked out perfectly."
5. "I'm so glad this happened."
6. "This feels really good."
7. "I couldn't be happier about it."
8. "What a wonderful surprise."
9. "This is exactly what I hoped for."
10. "I'm really pleased with this."

---

### Sad (10 recordings: 1 whisper, 7 normal, 2 loud)
**Natural Context**: Disappointment, loss, fatigue, melancholy
**Vocal Characteristics**:
- Slower tempo (10-20% slower than neutral)
- Lower average pitch
- Reduced energy and volume
- Natural breath softness
- Downward pitch movement at sentence end

**Avoid**: Crying, sobbing, whimpering, extreme despair

**Sample Sentences**:
1. "I miss you more than I can say."
2. "I feel really tired today."
3. "This is harder than I thought."
4. "I wish things were different."
5. "I don't know what to do anymore."
6. "Everything feels heavy right now."
7. "I'm just feeling really low."
8. "It's been a rough day."
9. "I can't stop thinking about it."
10. "Nothing seems to help."

---

### Angry (7 recordings: 0 whisper, 4 normal, 3 loud)
**Natural Context**: Frustration, injustice, boundary violation
**Vocal Characteristics**:
- Slight vocal tension (NOT shouting)
- Higher energy than neutral
- Faster tempo
- Sharper consonant articulation
- Controlled intensity

**Avoid**: Screaming, yelling, rage, aggression

**Sample Sentences**:
1. "This is completely unacceptable."
2. "I can't believe this happened again."
3. "You need to stop doing that."
4. "This is not what we agreed on."
5. "I'm really upset about this."
6. "That was not okay."
7. "I've had enough of this."

---

### Neutral (7 recordings: 1 whisper, 6 normal, 0 loud)
**Natural Context**: Factual statements, informational speech
**Vocal Characteristics**:
- Flat affect (minimal pitch variation)
- Steady tempo (not slow, not fast)
- Normal conversational volume
- No emotional coloring

**Avoid**: Boredom, sarcasm, disinterest tone

**Sample Sentences**:
1. "The meeting starts at nine."
2. "The package arrived yesterday."
3. "I placed the file on the table."
4. "Please open the next page."
5. "The report is due on Friday."
6. "I'll be there in ten minutes."
7. "The temperature is twenty degrees."

---

### Excited (10 recordings: 2 whisper, 7 normal, 1 loud)
**Natural Context**: Anticipation, positive surprise, enthusiasm
**Vocal Characteristics**:
- Higher tempo (10-20% faster than neutral)
- Brighter tone (higher formants)
- Slightly elevated energy
- Wider pitch range movement
- Quick onset

**Avoid**: Hyperactivity, manic energy, screaming

**Sample Sentences**:
1. "We're going on a trip tomorrow!"
2. "I can't wait to see it!"
3. "This is going to be amazing!"
4. "Did you hear the news?"
5. "I just found out something incredible!"
6. "This is exactly what I wanted!"
7. "I'm so ready for this!"
8. "We finally get to do it!"
9. "I've been waiting for this moment!"
10. "This is going to be so much fun!"

---

## VOLUME DIFFERENTIATION EXECUTION

### Whisper Recordings (6 total)
**Target RMS**: -30 to -26 dBFS (6-10 dB below normal baseline)
**Execution**:
- Move slightly CLOSER to mic (12-15 cm)
- Speak with reduced intensity
- Maintain clear articulation (still intelligible)
- Avoid excessive breath noise
- Check: should be clearly quieter but NOT breathy noise

### Normal Recordings (31 total)
**Target RMS**: -22 to -18 dBFS (baseline reference)
**Execution**:
- Standard mic distance (15-20 cm)
- Conversational speaking voice
- Natural projection
- Check: matches calibration baseline

### Loud Recordings (7 total)
**Target RMS**: -16 to -12 dBFS (6-10 dB above normal baseline)
**Execution**:
- Move slightly FARTHER from mic (20-25 cm)
- Strong vocal projection (NOT shouting)
- Increased intensity without tension
- Avoid clipping at all costs
- Check: louder but NO distortion

---

## SESSION MANAGEMENT

### Batch Recording Strategy (Recommended)
Record in batches to maintain acoustic consistency:
- Batch 1: All "normal" volume (31 recordings) — 25 minutes
- Batch 2: All "whisper" volume (6 recordings) — 6 minutes
- Batch 3: All "loud" volume (7 recordings) — 7 minutes
- 5-minute breaks between batches

### Fatigue Management
- Take 2-minute break every 12 recordings
- Hydrate (water only, no caffeine/sugar)
- Rest voice between batches
- If voice feels strained → stop and resume later

### Real-Time Quality Dashboard
Keep paper checklist visible:
```
Happy:    □□ (W)  □□□□□□□ (N)  □ (L)     [10 total]
Sad:      □ (W)   □□□□□□□ (N)  □□ (L)    [10 total]
Angry:            □□□□ (N)     □□□ (L)   [7 total]
Neutral:  □ (W)   □□□□□□ (N)              [7 total]
Excited:  □□ (W)  □□□□□□□ (N)  □ (L)     [10 total]
```
Mark checkbox only AFTER quality check passes.

---

## POST-RECORDING VALIDATION PROTOCOL

### Immediate Checks (Per File)
1. Waveform Visual Inspection
   - [ ] No clipping (peaks below 0 dB)
   - [ ] No dead silence > 0.5 seconds
   - [ ] Clean onset (no click/pop)
   - [ ] Clean ending (no trailing noise)

2. Audio Playback Check
   - [ ] Speech is intelligible
   - [ ] Emotion sounds natural
   - [ ] Volume matches intent (whisper/normal/loud)
   - [ ] No background noise artifacts

3. Duration Check
   - [ ] Between 3-6 seconds
   - [ ] No long pauses mid-sentence

### Batch Validation (After Each Emotion Set)
- [ ] Listen to all recordings of same emotion
- [ ] Verify consistent acoustic environment
- [ ] Verify emotional consistency (not drift)
- [ ] Verify volume spread is audible

### Final Session Validation
After all 44 recordings:
- [ ] Total file count = 44
- [ ] All files named correctly
- [ ] All files in correct folders
- [ ] All files are WAV, 16kHz, mono
- [ ] Quick spot-check random 5 files for quality

---

## AUTHENTICITY VERIFICATION CHECKLIST

For natural emotion validation, each recording should pass:
- [ ] Could this be spoken in real conversation? (YES required)
- [ ] Does emotion feel genuine, not acted? (YES required)
- [ ] Would you speak this way to a real person? (YES required)
- [ ] Is prosody natural, not exaggerated? (YES required)
- [ ] If played to stranger, would emotion be clear? (YES required)

**If ANY answer is NO → re-record that file immediately**

---

## TROUBLESHOOTING GUIDE

### Problem: Recordings sound theatrical
**Solution**: 
- Think of real memory, not acting
- Record as if speaking to real person
- Reduce energy by 30%
- Re-calibrate emotional intensity

### Problem: Volume inconsistency within same level
**Solution**:
- Check mic position hasn't shifted
- Verify gain hasn't changed
- Use baseline RMS as reference
- Re-record outliers

### Problem: Background noise appearing
**Solution**:
- Stop session immediately
- Identify noise source
- Eliminate source
- Re-record affected files

### Problem: Voice fatigue
**Solution**:
- Stop recording immediately
- Hydrate
- Rest 15-30 minutes
- Resume only when voice feels normal

---

## SUCCESS CRITERIA

Session is complete when:
- [ ] 44 files recorded and saved
- [ ] All files pass quality checks
- [ ] All files in correct folders with correct names
- [ ] Reviewer sheet ready for label confirmation
- [ ] Bootstrap script ready to run

**Target: Complete 44 recordings in under 45 minutes with breaks**

---

## NEXT STEPS (After Recording Session)

1. Run bootstrap classifier:
   ```
   python emotion_assisted_prelabeling.py --project-root . --data-dir data --min-confidence 0.65
   ```

2. Review and confirm labels:
   - Open `outputs/validation_reports/reviewer_sheet.csv`
   - Fill `reviewer_label` column for new 44 rows
   - Correct any misclassifications

3. Run balance gate:
   ```
   python check_dataset_balance.py
   ```
   Expected: PASSED

4. Run full KPI validation:
   ```
   python emotion_real_mic_validation.py
   ```
   Target KPIs:
   - Sad recall ≥ 65%
   - Volume invariance ≥ 75%
   - Production score ≥ 75%

---

**REMEMBER**: This dataset validates production emotion detection. Quality and realism are more important than speed.
