# Dataset Completion Playbook (44 New Recordings)

## Current Accepted Baseline
- reviewed_count: 6
- accepted emotions: neutral=3, angry=3
- accepted volumes: normal=6

## Required to Pass Gate
- Total additional recordings needed: **44**
- Emotion deficits:
  - happy: 10
  - sad: 10
  - angry: 7
  - neutral: 7
  - excited: 10
- Volume deficits:
  - whisper: 3
  - loud: 3
  - normal: 0 (already satisfied)

## Optimized Recording Matrix (Emotion × Volume)
This matrix collects exactly 44 while distributing whisper/loud across multiple emotions.

| Emotion | Whisper | Normal | Loud | Total |
|---|---:|---:|---:|---:|
| Happy   | 2 | 7 | 1 | 10 |
| Sad     | 1 | 7 | 2 | 10 |
| Angry   | 0 | 4 | 3 | 7  |
| Neutral | 1 | 6 | 0 | 7  |
| Excited | 2 | 7 | 1 | 10 |
| **Total** | **6** | **31** | **7** | **44** |

This exceeds minimum volume constraints (whisper>=3, loud>=3) and keeps emotion targets exact.

## Quick Recording Checklist
Record each item as a unique file and place under matching bucket:
- `data/happy/{whisper,normal,loud}` → 10 new files (2W,7N,1L)
- `data/sad/{whisper,normal,loud}` → 10 new files (1W,7N,2L)
- `data/angry/{normal,loud}` → 7 new files (0W,4N,3L)
- `data/neutral/{whisper,normal}` → 7 new files (1W,6N,0L)
- `data/excited/{whisper,normal,loud}` → 10 new files (2W,7N,1L)

## Controlled Recording Protocol (under 45 minutes)
### Session Target
- 44 clips in 45 minutes
- Average pace: ~55-60 seconds per clip including naming and quick retake checks

### Per-clip Requirements
- Duration: **3-6 seconds**
- Language: consistent with production use-case
- Single speaker only
- One clear emotional intent per clip

### Mic Guidance
- Distance: **12-18 cm** from mouth
- Angle: **15-30° off-axis** to reduce plosives
- Environment: quiet room, fan/AC minimized
- Keep input level below clipping (no red peaks)

### Volume Instructions
- Whisper: low intensity, breathy, still intelligible
- Normal: conversational tone
- Loud: strong projection, no clipping/distortion

### Vocal Style Instructions by Emotion
- Happy: brighter tone, faster tempo, smiling articulation
- Sad: lower energy, softer onset, slower tempo, downward intonation
- Angry: tense tone, sharper consonants, controlled force
- Neutral: flat affect, steady tempo, minimal pitch variation
- Excited: high energy, faster speech, wider pitch movement

### Short Prompt Sentences (rotate to avoid lexical bias)
Use 2-3 per emotion and vary wording/order.

- Happy:
  1. "Today feels really good."
  2. "I am glad this worked out."
  3. "That made me smile."

- Sad:
  1. "I feel low right now."
  2. "This is hard for me."
  3. "I wish things were better."

- Angry:
  1. "This is not acceptable."
  2. "I am really upset about this."
  3. "Stop doing that now."

- Neutral:
  1. "The meeting starts at nine."
  2. "I placed the file on the table."
  3. "Please open the next page."

- Excited:
  1. "This is amazing news!"
  2. "I cannot wait to begin."
  3. "That was incredible!"

## Naming Convention
- Suggested: `<emotion>_<volume>_<index>.wav`
- Example: `sad_loud_003.wav`

## Post-Recording Validation Runbook
1. Bootstrap/classify/copy + refresh reports:
   - `python emotion_assisted_prelabeling.py --project-root . --data-dir data --min-confidence 0.65`
2. Review labels:
   - Open `outputs/validation_reports/reviewer_sheet.csv`
   - Fill `reviewer_label` for all new rows
3. Balance gate:
   - `python check_dataset_balance.py`
4. Real KPI validation:
   - `python emotion_real_mic_validation.py`

## Success Targets
- Sad recall >= 65%
- Volume invariance >= 75%
- Production score >= 75%
- Gate verdict: PASSED
