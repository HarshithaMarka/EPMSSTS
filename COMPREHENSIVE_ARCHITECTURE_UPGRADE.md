# EPMSSTS: Comprehensive Architecture Upgrade to Production-Grade Neural Conditioning

**Status:** Architecture Design Document  
**Target Scale:** 100,000 daily active users  
**SLA:** <5s non-streaming, streaming-ready architecture  
**Date:** March 2026  

---

## EXECUTIVE SUMMARY

### Current System State
- ✓ Functional microservice architecture
- ✓ Basic STT, emotion label, translation, TTS
- ✗ Rule-based prosody hacking
- ✗ Discrete emotion labels (not continuous)
- ✗ No speaker style preservation
- ✗ Categorical dialect handling
- ✗ No cross-lingual emotion validation
- ✗ Production SaaS: 20-30% confidence

### Target System State
- ✓ Continuous emotion representation (64-128d embeddings)
- ✓ Learned dialect conditioning vectors
- ✓ Speaker style embedding extraction & preservation
- ✓ Neural TTS with style conditioning (XTTS v2 or VITS-GST)
- ✓ Sentiment-aware translation
- ✓ Session-aware emotion memory
- ✓ Production SaaS: 80-90% confidence
- ✓ 100k DAU architecture with drift monitoring
- ✓ Backward compatible migration

### Key Architectural Decisions

| Component | Current | Upgrade | Rationale |
|-----------|---------|---------|-----------|
| **Emotion Model** | Wav2Vec2 classifier (K labels) | Wav2Vec2 + learned projection head (continuous embedding) | Preserves emotional nuance, enables conditioning |
| **Dialect System** | String labels | Learned embedding space from phoneme/pitch | Contextual conditioning, natural variation |
| **Speaker Style** | Not extracted | ECAPA-TDNN speaker encoder (256d) | Voice consistency, personalization |
| **Prosody** | Rule-based scaling | Neural TTS with style conditioning | Learned relationships, natural variation |
| **Orchestration** | Sequential, rule-driven | Vector composition (emotion + dialect + speaker) | Clean, learnable, modular |
| **Translation** | NLLB direct | NLLB + sentiment preservation layer | Emotional intensity maintained |
| **Session Memory** | None | EMA-smoothed emotion embedding | Prevents emotional flip-flop |
| **Monitoring** | Basic metrics | Drift detection, embedding entropy, style consistency | Production reliability |

---

## PART 1: EMOTION REPRESENTATION UPGRADE

### 1.1 Current State Problem

```python
# OLD: Discrete emotion classification
emotion_output = {
    "label": "sad",           # K categories
    "confidence": 0.86,
    "# Usage in TTS:
    "pitch_adjustment": -0.2,   # Hard-coded rule
    "speed_adjustment": 0.95,
    "energy_adjustment": 0.85
}
```

**Problems:**
- Only K discrete states (usually 5-7 emotions)
- Loses emotional nuance (e.g., "slightly sad" vs "deeply sad" → same rules)
- Rules don't generalize to new emotions or intensities
- No cross-lingual emotional representation
- Cannot blend emotions (tension + hope simultaneously)
- TTS has no gradient to learn prosody

### 1.2 Upgraded Architecture

#### Step 1: Extract Intermediate Embedding from Wav2Vec2

```
Input Audio (16kHz, mono)
    ↓
[Wav2Vec2 Encoder (Base)]
    ↓
Hidden states shape: (seq_len, 768)
    ↓
[Mean Pooling / Attention Pooling]
    ↓
audio_representation: (768,)    ← Key: Don't throw this away
```

#### Step 2: Train Emotion Projection Head

```
audio_representation (768)
    ↓
[Linear layer: 768 → 256]
    ↓
[LayerNorm + ReLU]
    ↓
[Linear layer: 256 → 128]      ← Emotion embedding dimension
    ↓
emotion_embedding: (128,)       ← Continuous representation

Parallel heads for auxiliary tasks:
    ↓ [Linear 128 → 1] → valence: float ∈ [-1, 1]
    ↓ [Linear 128 → 1] → arousal: float ∈ [0, 1]
    ↓ [Linear 128 → 1] → confidence: float ∈ [0, 1]
```

#### Step 3: Training Strategy

**Supervised Multi-Task Learning:**

1. **Task 1 - Emotion Classification (existing labels as targets)**
   - Map embedding through final classifier head
   - Standard CrossEntropyLoss
   - Trains embedding to capture discriminative features

2. **Task 2 - Valence Regression**
   - Annotate training set with valence scores ([-1, 1])
   - MSELoss on valence regression head
   - Captures emotional polarity

3. **Task 3 - Arousal Regression**
   - Annotate training set with arousal scores ([0, 1])
   - MSELoss on arousal regression head
   - Captures emotional intensity

4. **Task 4 - Triplet Loss on Embeddings** (optional but recommended)
   - Anchor: Example A (sad, low arousal)
   - Positive: Example A2 (sad, low arousal, different speaker)
   - Negative: Example B (happy, high arousal, same speaker)
   - Ensures semantic meaning in embedding space

**Loss Function:**

```python
loss = (
    α * cross_entropy_loss(classifier(emotion_embedding), label)
    + β * mse_loss(valence_head(emotion_embedding), valence_target)
    + γ * mse_loss(arousal_head(emotion_embedding), arousal_target)
    + δ * triplet_loss(emotion_embedding)
)
# Typical: α=1.0, β=0.5, γ=0.5, δ=0.3
```

#### Step 4: Output Format

```python
emotion_output = {
    # Continuous representation for TTS conditioning
    "embedding": np.array([...]),          # shape (128,), normalized
    
    # Interpretable axes (regression outputs)
    "valence": 0.35,                       # -1 (negative) to +1 (positive)
    "arousal": 0.78,                       # 0 (calm) to 1 (excited)
    
    # Confidence metrics
    "confidence": 0.92,                    # Overall confidence
    "embedding_entropy": 0.45,             # Distributional confidence
    
    # Auxiliary task outputs (for monitoring)
    "label_prediction": "sad",
    "label_logits": {
        "happy": 0.05,
        "sad": 0.82,
        "neutral": 0.08,
        "angry": 0.03,
        "surprised": 0.02
    }
}
```

### 1.3 Implementation Details

**Model Architecture (PyTorch):**

```python
class EmotionEmbeddingModule(nn.Module):
    def __init__(self, hidden_dim=768, embedding_dim=128, num_classes=7):
        super().__init__()
        # Shared embedding projection
        self.projection = nn.Sequential(
            nn.Linear(hidden_dim, 256),
            nn.LayerNorm(256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, embedding_dim),
            nn.LayerNorm(embedding_dim)  # L2 norm
        )
        
        # Task-specific heads
        self.classifier = nn.Linear(embedding_dim, num_classes)
        self.valence_head = nn.Linear(embedding_dim, 1)
        self.arousal_head = nn.Linear(embedding_dim, 1)
        
    def forward(self, audio_embedding):
        # audio_embedding: (batch, 768)
        emotion_embedding = self.projection(audio_embedding)  # (batch, 128)
        
        return {
            "embedding": emotion_embedding,
            "label_logits": self.classifier(emotion_embedding),
            "valence": torch.tanh(self.valence_head(emotion_embedding)),
            "arousal": torch.sigmoid(self.arousal_head(emotion_embedding))
        }
```

**Training Data Preparation:**

```python
# Annotation template for training dataset
training_example = {
    "audio_path": "speaker_001_sad_01.wav",
    "emotion_label": "sad",           # Original label
    "valence": -0.7,                  # -1: very negative, +1: very positive
    "arousal": 0.3,                   # 0: calm, 1: excited
    "emotion_intensity": 8,           # 1-10 scale (optional, for loss weighting)
    "notes": "Deep, melancholic sadness"
}
```

### 1.4 Integration with Orchestration

```python
# In orchestration service
async def process_emotion(audio_path: str):
    # 1. Load audio
    audio = load_audio(audio_path)
    
    # 2. Extract Wav2Vec2 embedding
    with torch.no_grad():
        wav2vec_embedding = wav2vec2_model.extract_features(audio)[0]
        audio_representation = pool_features(wav2vec_embedding)  # (768,)
    
    # 3. Get emotion embedding and auxiliary outputs
    emotion_output = emotion_module(audio_representation.unsqueeze(0))
    
    # 4. Return compact representation
    return {
        "emotion_embedding": emotion_output["embedding"].cpu().numpy(),
        "valence": float(emotion_output["valence"].cpu()),
        "arousal": float(emotion_output["arousal"].cpu()),
        "confidence": compute_confidence(emotion_output["label_logits"]),
        "label": emotion_output["label_logits"].argmax(dim=1).item()
    }
```

---

## PART 2: DIALECT EMBEDDING CONDITIONING

### 2.1 Current State Problem

```python
# OLD: Categorical dialect detection
dialect_detection = {
    "dialect": "telangana",      # String label
    "confidence": 0.88,
    # Usage in TTS:
    "pitch_shift": 1.1,          # Hard-coded for Telangana
    "vowel_duration_adjust": 0.98
}
```

**Problems:**
- Only categorical outputs (3-5 dialect categories)
- No gradual variation between dialects
- Intra-dialect variation lost
- Rules don't capture phonetic subtlety
- Cannot represent dialect mixture (urban speaker with dialectal features)

### 2.2 Upgraded Architecture

#### Step 1: Speech Feature Extraction for Dialect Recognition

```
Input Audio
    ↓
[Preprocessing: Trimming, normalization]
    ↓
[Feature Extraction]
    ├─ MFCC (13 coefficients)
    ├─ Delta MFCC (velocity)
    ├─ Delta-delta MFCC (acceleration)
    ├─ Pitch contour (F0)
    ├─ Voice activity detection (VAD)
    └─ Speech rate (phones/sec)
    ↓
Feature matrix: (time_steps, feature_dim)

[Phonetic Level Analysis] (for Telugu-specific features)
    ├─ Create phoneme segmentation using ASR
    ├─ Extract phoneme durations
    ├─ Extract pitch trajectories per phoneme
    └─ Analyze retroflex characteristics (Telugu-specific)
    ↓
phoneme_features: dict {
    "retroflex_rate": 0.23,          # Andhra uses more retroflex sounds
    "vowel_nasalization": 0.15,       # Telangana more nasal
    "geminate_duration": 1.2          # Andhra longer geminate vowels
}
```

#### Step 2: Train Dialect Embedding Encoder

```
MFCC stack (time_steps, 39)
    ↓
[Temporal Encoder - BiLSTM or Transformer]
    ├─ Stack of 2-3 BiLSTM layers (384 hidden)
    └─ Or self-attention blocks
    ↓
(time_steps, 384)
    ↓
[Temporal Pooling]
    ├─ Mean pooling across time
    └─ Attention pooling (learn what features matter)
    ↓
(384,)
    ↓
[Dialect Projection Head]
    ├─ Linear 384 → 256
    ├─ ReLU + LayerNorm
    └─ Linear 256 → 64
    ↓
dialect_embedding: (64,)   ← Learned representation

Parallel output heads:
    ├─ Classifier (64 → num_dialects)  [Cross-entropy loss]
    ├─ Retroflex regression (64 → 1)   [MSE loss]
    ├─ Nasalization regression (64 → 1) [MSE loss]
    └─ Confidence head (64 → 1)        [Binary cross-entropy]
```

#### Step 3: Training Data Preparation

For Telugu, annotate with:

```python
dialect_annotation = {
    "audio_id": "telugu_001_andhra_young_female",
    "dialect": "andhra",                    # Primary category
    
    # Continuous characteristics
    "retroflex_intensity": 0.8,             # 0-1: how much retroflex sounds
    "nasalization_level": 0.3,              # 0-1: nasal quality
    "vowel_duration_style": "long",         # "short" / "medium" / "long"
    "geminate_duration_ratio": 1.3,         # vs standard
    
    # Speech rate characteristic
    "speech_rate_relative": 1.05,           # vs corpus mean
    
    # Additional context
    "speaker_origin": "Hyderabad",
    "age_group": "25-35",
    "formality_level": "casual_conversation",
    
    # For mixture scenarios
    "dialect_mixture": {
        "andhra": 0.7,
        "telangana": 0.2,
        "standard": 0.1
    }
}
```

#### Step 4: Loss Function

```python
loss = (
    α * cross_entropy(classifier(dialect_embedding), dialect_label)
    + β * mse_loss(retroflex_head(dialect_embedding), retroflex_target)
    + γ * mse_loss(nasalization_head(dialect_embedding), nasalization_target)
    + δ * triplet_loss(dialect_embedding, dialect_label)  # Same dialect = similar
)
```

#### Step 5: Output Format

```python
dialect_output = {
    # Continuous embedding for TTS conditioning
    "embedding": np.array([...]),           # shape (64,)
    
    # Interpretable phonetic dimensions
    "retroflex_intensity": 0.78,            # 0-1
    "nasalization_level": 0.32,            # 0-1
    "speech_rate_relative": 1.02,          # multiplier
    "vowel_duration_style": "medium",      # categorical
    
    # Label and confidence
    "primary_dialect": "andhra",
    "dialect_probabilities": {
        "andhra": 0.72,
        "telangana": 0.20,
        "standard": 0.08
    },
    "confidence": 0.88,
    
    # For dialect mixture representation (when confidence low)
    "mixture_weights": {
        "andhra": 0.72,
        "telangana": 0.20,
        "standard": 0.08
    }
}
```

### 2.3 Implementation Architecture

```python
class DialectEmbeddingModule(nn.Module):
    def __init__(self, feature_dim=39, embedding_dim=64, num_dialects=3):
        super().__init__()
        
        # Temporal encoder
        self.encoder = nn.Sequential(
            nn.LSTM(feature_dim, 384, num_layers=2, 
                    batch_first=True, bidirectional=True),
        )
        self.attention_pooling = nn.MultiheadAttention(
            embed_dim=768, num_heads=8, batch_first=True
        )
        
        # Embedding projection
        self.projection = nn.Sequential(
            nn.Linear(768, 256),
            nn.LayerNorm(256),
            nn.ReLU(),
            nn.Linear(256, embedding_dim),
            nn.LayerNorm(embedding_dim)
        )
        
        # Task heads
        self.dialect_classifier = nn.Linear(embedding_dim, num_dialects)
        self.retroflex_head = nn.Linear(embedding_dim, 1)
        self.nasalization_head = nn.Linear(embedding_dim, 1)
        self.confidence_head = nn.Linear(embedding_dim, 1)
        
    def forward(self, mfcc_features):
        # mfcc_features: (batch, time_steps, 39)
        
        lstm_out, _ = self.encoder(mfcc_features)  # (batch, T, 768)
        
        # Attention pooling
        attn_out, _ = self.attention_pooling(lstm_out, lstm_out, lstm_out)
        pooled = attn_out.mean(dim=1)              # (batch, 768)
        
        dialect_embedding = self.projection(pooled) # (batch, 64)
        
        return {
            "embedding": dialect_embedding,
            "classifier": self.dialect_classifier(dialect_embedding),
            "retroflex": torch.sigmoid(self.retroflex_head(dialect_embedding)),
            "nasalization": torch.sigmoid(self.nasalization_head(dialect_embedding)),
            "confidence": torch.sigmoid(self.confidence_head(dialect_embedding))
        }
```

---

## PART 3: SPEAKER STYLE PRESERVATION

### 3.1 Current State Problem

**Missing entirely.** Speaker characteristics (voice identity, rhythm, unique prosody) are lost between input and output audio.

### 3.2 Upgraded Architecture: Speaker Encoder Integration

#### Step 1: Choose Speaker Encoder Model

**Option A: ECAPA-TDNN (Recommended for Production)**
- Pre-trained on speaker verification tasks
- 256-dimensional speaker embedding
- Fast inference (~10ms)
- Proven in production systems
- Model: `speechbrain/spk-ecapa-tdnn-superb`
- License: Apache 2.0

**Option B: Resemblyzer**
- 256-dimensional embeddings
- Good generalization across languages
- Slower (~50ms per inference)
- Model size: ~100MB

**Option C: ECAPA-TDNN Multilingual (Proposed for v2)**
- Handle multilingual speakers
- Future-proof for cross-language scenarios

**Recommendation:** ECAPA-TDNN (SpeechBrain)

#### Step 2: Speaker Embedding Extraction Pipeline

```
Input Audio
    ↓
[Audio Preprocessing]
    ├─ Resample to 16kHz
    ├─ Normalize volume (-20dBFS)
    └─ Trim silence (VAD)
    ↓
[Speaker Encoder (ECAPA-TDNN)]
    ├─ Input: 16kHz audio, variable length
    └─ Output: 256-dim vector
    ↓
speaker_embedding: (256,)

[Optional: Post-processing]
    ├─ L2 normalization (important!)
    ├─ Dimensionality reduction to 128 (for efficiency)
    └─ Quantization (int8 for storage)
    ↓
normalized_speaker_embedding: (128,) [after reduction]
```

#### Step 3: Speaker Embedding Quality Assurance

```python
speaker_quality = {
    "embedding_norm": float,              # Should be ~1.0 after L2 norm
    "speaker_consistency_score": float,   # For multi-turn: is this same speaker?
    "voicing_duration": float,            # % of audio with voice activity
    "embedding_confidence": float,        # Model confidence (from model metadata)
    "background_noise_level": float,      # For quality assessment
}

# Quality checks before using embedding
assert speaker_quality["embedding_norm"] > 0.95, "Embedding not normalized"
assert speaker_quality["voicing_duration"] > 0.3, "Insufficient speech content"
```

#### Step 4: Storage and Retrieval

```python
# Store speaker embeddings in efficient format
speaker_profile = {
    "speaker_id": "user_12345",
    
    # Raw embedding (can store multiple for consistency)
    "embeddings": [
        np.array([...]),  # From first utterance
        np.array([...]),  # From second utterance
        np.array([...])   # From third utterance
    ],
    
    # Aggregated profile (mean of embeddings)
    "profile_embedding": np.array([...]),  # shape (128,)
    
    # Metadata
    "embedding_model": "ecapa-tdnn-superb",
    "num_utterances": 3,
    "average_voicing_duration": 0.65,
    "embedding_variance": 0.12,            # How consistent are embeddings?
    
    # For verification
    "embedding_hash": "abc123...",         # For change detection
    "profile_created": "2024-01-15T10:30:00Z",
    "last_updated": "2024-01-15T10:30:00Z"
}
```

#### Step 5: Speaker Embedding Usage in TTS

```python
# At TTS synthesis time:
tts_input = {
    "text": translated_text,
    "language": "te",
    
    # Style conditioning vectors (all normalized to unit norm)
    "speaker_embedding": speaker_profile["profile_embedding"],   # (128,)
    "emotion_embedding": emotion_output["embedding"],            # (128,)
    "dialect_embedding": dialect_output["embedding"],            # (64,)
    
    # Speaker-specific parameters (learned from embedding)
    "target_speaker_id": "user_12345",     # For speaker-specific model if available
}

# TTS model processes: text + all three conditional embeddings
# Result: Speech in translated language, with original speaker characteristics
```

### 3.3 Implementation Details

```python
class SpeakerEmbeddingModule:
    def __init__(self, model_name="spk-ecapa-tdnn-superb"):
        from speechbrain.pretrained import SpeakerRecognition
        self.model = SpeakerRecognition.from_hparams(
            source=f"speechbrain/{model_name}",
            savedir="pretrained_models/"
        )
        
    def extract_speaker_embedding(self, audio_path: str) -> np.ndarray:
        """Extract 256-dim speaker embedding from audio."""
        embedding = self.model.encode_speaker(audio_path)
        # embedding shape: (256,)
        
        # L2 normalize
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
        
        # Optional: reduce to 128 dims for efficiency
        # (would require training a projection layer)
        
        return embedding
    
    def compute_speaker_similarity(self, 
                                   embedding1: np.ndarray,
                                   embedding2: np.ndarray) -> float:
        """Cosine similarity between two embeddings (0-1)."""
        similarity = np.dot(embedding1, embedding2)  # After L2 norm
        return float(np.clip(similarity, 0, 1))
    
    def create_speaker_profile(self, audio_paths: List[str]) -> dict:
        """Create aggregated speaker profile from multiple utterances."""
        embeddings = []
        for path in audio_paths:
            emb = self.extract_speaker_embedding(path)
            embeddings.append(emb)
        
        # Mean embedding
        profile_embedding = np.mean(embeddings, axis=0)
        profile_embedding /= (np.linalg.norm(profile_embedding) + 1e-8)
        
        # Variance (consistency measure)
        variance = np.var([
            self.compute_speaker_similarity(profile_embedding, emb)
            for emb in embeddings
        ])
        
        return {
            "profile_embedding": profile_embedding,
            "num_utterances": len(embeddings),
            "embedding_variance": float(variance),
            "individual_embeddings": embeddings
        }
```

---

## PART 4: NEURAL TTS WITH STYLE CONDITIONING

### 4.1 Current State Problem

```python
# OLD: Rule-based prosody
tts_output = synthesize_speech(
    text=translated_text,
    speaker_id="telugu_voice_01",
    pitch_adjustment=-0.2,      # Hard-coded based on emotion label
    speed_adjustment=0.95,
    energy_adjustment=0.85
)
# Result: Predictable, robotic, not personalized
```

**Problems:**
- No learned relationship between emotion and prosody
- No speaker personalization
- Cannot blend multiple style influences
- Predetermined outputs for each emotion
- No generalization to new speakers or dialects

### 4.2 Upgraded Architecture: XTTS v2 with Multiple Style Vectors

**Recommendation: Coqui XTTS v2**
- Already supports multi-speaker TTS
- Can be extended for style conditioning
- Reasonable GPU requirements (~6-8GB)
- Apache 2.0 license
- Native multi-lingual support

**Alternative: VITS2 with Global Style Tokens (GST)**
- More lightweight (~300MB model)
- Explicit style token learning
- Requires more training/fine-tuning work

#### Step 1: XTTS v2 Architecture Extension

```
Text Input
    ↓
[Text Encoder (based on GPT-2)]
    ├─ Tokenize and embed
    └─ Produce linguistic features
    ↓
(seq_len, 768)
    ↓
[STYLE CONDITIONING FUSION LAYER] ← NEW
    ├─ speaker_embedding: (128,)
    ├─ emotion_embedding: (128,)
    ├─ dialect_embedding: (64,)
    └─ speaker_consistency_weight: scalar
    ↓
    Fusion strategy:
    - Concatenate: [text_features, speaker, emotion, dialect]
    - Project to shared dimension
    - Add via learned attention
    ↓
conditioned_text_features: seq_len, fused_dim
    ↓
[Decoder - Conformer blocks]
    └─ Process fused features
    ↓
[Acoustic features decoder]
    └─ Produce mel-spectrogram with prosody
    ↓
[Vocoder (HiFiGAN)]
    └─ Convert spectrogram → waveform
    ↓
Output Audio (16kHz)
```

#### Step 2: Style Fusion Implementation

```python
class StyleConditioningFusion(nn.Module):
    """Fuse multiple style embeddings into acoustic features."""
    
    def __init__(self, text_feature_dim=768, 
                 speaker_dim=128, emotion_dim=128, dialect_dim=64,
                 fused_dim=768):
        super().__init__()
        
        # Project each style vector to a common dimension
        self.speaker_projection = nn.Linear(speaker_dim, fused_dim // 3)
        self.emotion_projection = nn.Linear(emotion_dim, fused_dim // 3)
        self.dialect_projection = nn.Linear(dialect_dim, fused_dim // 3)
        
        # Learned fusion weights
        self.fusion_gating = nn.Sequential(
            nn.Linear(fused_dim, fused_dim // 2),
            nn.ReLU(),
            nn.Linear(fused_dim // 2, 3),  # 3 gates for 3 styles
            nn.Softmax(dim=-1)
        )
        
        # Cross-modal attention (optional, for rich fusion)
        self.cross_attention = nn.MultiheadAttention(
            embed_dim=fused_dim, num_heads=8, batch_first=True
        )
        
    def forward(self, text_features, speaker_emb, emotion_emb, dialect_emb):
        # text_features: (batch, seq_len, 768)
        # speaker_emb: (batch, 128)
        # emotion_emb: (batch, 128)
        # dialect_emb: (batch, 64)
        
        batch_size = text_features.shape[0]
        seq_len = text_features.shape[1]
        
        # Project style embeddings
        speaker_proj = self.speaker_projection(speaker_emb)  # (batch, 256)
        emotion_proj = self.emotion_projection(emotion_emb)  # (batch, 256)
        dialect_proj = self.dialect_projection(dialect_emb)  # (batch, 256)
        
        # Concatenate style vectors
        style_vector = torch.cat(
            [speaker_proj, emotion_proj, dialect_proj], 
            dim=-1
        )  # (batch, 768)
        
        # Learn fusion weights
        fusion_weights = self.fusion_gating(style_vector)  # (batch, 3)
        
        # Expand style to sequence length
        style_features = torch.cat(
            [
                speaker_proj.unsqueeze(1).expand(-1, seq_len, -1),
                emotion_proj.unsqueeze(1).expand(-1, seq_len, -1),
                dialect_proj.unsqueeze(1).expand(-1, seq_len, -1)
            ],
            dim=-1
        )  # (batch, seq_len, 768)
        
        # Fuse with text features via residual + attention
        fused = text_features + style_features
        
        # Apply cross-modal attention for rich interaction
        attn_out, _ = self.cross_attention(
            fused, fused, fused
        )
        
        # Final combination
        combined = text_features + attn_out + style_features
        
        return combined  # (batch, seq_len, 768)
```

#### Step 3: Training / Fine-tuning Strategy

**Approach A: No Additional Training (Zero-shot Guidance)**
```python
# Use XTTS v2 as-is, implement style guidance at inference time
# "Guide" the acoustic decoder using style embeddings
# Minimal training, but less natural results
```

**Approach B: LoRA Fine-tuning (Recommended)**
```python
# Add Low-Rank Adaptation layers to XTTS v2
# Only train LoRA weights, freeze main model
# Training dataset: 500-1000 minutes of speech with style annotations
# GPU: 1x V100 / A100, ~1 week training

from peft import get_peft_model, LoraConfig

config = LoraConfig(
    r=8,  # LoRA rank
    lora_alpha=16,
    target_modules=["q_proj", "v_proj"],  # Attention layers
    lora_dropout=0.1,
    bias="none"
)

model = get_peft_model(xtts_model, config)
```

**Approach C: Full Fine-tuning (Best Quality, Expensive)**
```python
# Train entire XTTS v2 model with style conditioning
# Training dataset: 5000+ minutes diverse speaker/emotion/dialect data
# GPU: 8x A100, ~4 weeks training
# Suitable for >1M DAU systems
```

**Training Data Format:**

```python
training_example = {
    "audio_path": "telugu_speaker_001_sentence_02.wav",
    "transcript": "అలా చేయండి, ఇది చాలా ముఖ్యమైనది",  # Telugu
    "language": "te",
    "speaker_id": "telugu_speaker_001",
    "speaker_embedding": np.array([...]),        # (128,) from ECAPA-TDNN
    "emotion": "concerned",
    "emotion_embedding": np.array([...]),        # (128,)
    "emotion_valence": -0.2,
    "emotion_arousal": 0.7,
    "dialect": "telangana",
    "dialect_embedding": np.array([...]),        # (64,)
    "prosody_annotation": {
        "pitch_relative": 1.15,                  # Relative to speaker mean
        "energy_relative": 1.08,
        "speech_rate_relative": 0.98,
        "phoneme_durations": [...]               # Optional detailed annotation
    }
}
```

#### Step 4: Inference Pipeline

```python
class NeuralTTSOrchestrator:
    def __init__(self, model_path="xtts_v2_finetuned"):
        self.model = load_xtts_v2_model(model_path)
        self.fusion_layer = StyleConditioningFusion()
    
    async def synthesize_with_style(self,
                                   text: str,
                                   language: str,
                                   speaker_embedding: np.ndarray,
                                   emotion_embedding: np.ndarray,
                                   dialect_embedding: np.ndarray,
                                   target_emotion_intensity: float = 1.0) -> np.ndarray:
        """
        Synthesize speech with learned style conditioning.
        
        Args:
            text: Translated text to synthesize
            language: Output language code
            speaker_embedding: (128,) speaker vector from ECAPA-TDNN
            emotion_embedding: (128,) emotion vector
            dialect_embedding: (64,) dialect vector
            target_emotion_intensity: Scale emotion effect (0-2, default 1.0)
        
        Returns:
            audio: (samples,) synthesized speech
        """
        
        with torch.no_grad():
            # 1. Text encoding
            text_features = self.model.encode_text(text, language)
            
            # 2. Apply style conditioning
            style_conditioned = self.fusion_layer(
                text_features=text_features,
                speaker_emb=torch.tensor(speaker_embedding).unsqueeze(0),
                emotion_emb=torch.tensor(emotion_embedding).unsqueeze(0) * target_emotion_intensity,
                dialect_emb=torch.tensor(dialect_embedding).unsqueeze(0)
            )
            
            # 3. Acoustic decoding
            mel_spec = self.model.acoustic_decoder(style_conditioned)
            
            # 4. Vocoding
            audio = self.model.vocoder(mel_spec)
        
        return audio.cpu().numpy()
```

---

## PART 5: CROSS-LINGUAL EMOTION PRESERVATION

### 5.1 Problem Statement

Current system: Spanish "¡Qué triste!" → Telugu "చాలా విషాదం" (loses emotion intensity)

**Challenge:** Emotion is expressed through lexical choice, intensity markers, and prosody. Translation often normalizes the emotional content.

### 5.2 Sentiment-Aware Translation Architecture

```
Input Audio (Language A)
    ↓
[STT: Speech → Text A]
    ↓
[Emotion Recognition]
    ├─ emotion_embedding
    ├─ valence
    └─ arousal
    ↓
[Sentiment Analysis - Pre-translation]
    ├─ Input: Text A
    ├─ Model: BERT-multilingual or language-specific
    ├─ Output: sentiment_score_source ∈ [-1, 1]
    └─ Output: emotion_keywords [list of emotional expressions]
    ↓
[Translation Engine: Text A → Text B]
    ├─ Model: NLLB-200
    └─ Standard translation
    ├─ Output: Text B
    ↓
[Sentiment Analysis - Post-translation]
    ├─ Input: Text B
    ├─ Model: Same sentiment analyzer
    ├─ Output: sentiment_score_target
    └─ Output: emotion_keywords_translated
    ↓
[Emotion Preservation Check]
    sentiment_loss = |sentiment_score_source - sentiment_score_target|
    
    if sentiment_loss > THRESHOLD (e.g., 0.3):
        → Retry translation with emotion constraint
        → Or apply lexical substitution
        → Or adjust TTS emotion embedding
    ↓
[TTS - with Adjusted Emotion Conditioning]
    ├─ Use original emotion_embedding if above threshold is NOT exceeded
    └─ Or use modified emotion_embedding if adjustment needed
    ↓
Output Audio (Language B)
```

### 5.3 Implementation

```python
class CrossLingualEmotionPreserver:
    
    def __init__(self):
        # Pre-trained multilingual sentiment models
        self.sentiment_pipeline = pipeline(
            "text-classification",
            model="cardiffnlp/twitter-xlm-roberta-base-sentiment"  # Multilingual
        )
        
        # Alternative: language-specific models for accuracy
        self.sentiment_models = {
            "en": pipeline("text-classification", model="distilbert-base-english-sentiment"),
            "es": pipeline("text-classification", model="dccuchile/bert-base-spanish-phf"),
            "te": pipeline("text-classification", model="kumaraditya303/telugu-emojis-bert"),
            # etc for other languages
        }
        
        self.translator = pipeline("translation_xx_to_yy", 
                                  model="facebook/nllb-200-1.3B")
        
        # Emotion intensity lexicon (language-specific)
        self.emotion_lexicons = load_emotion_lexicons()
    
    def compute_premotion_intensity(self, text: str, language: str) -> dict:
        """Compute emotional intensity of text before translation."""
        
        # Sentiment score
        sentiment = self.sentiment_models.get(language, self.sentiment_pipeline)(text)
        
        # Intensity markers count
        exclamation_count = text.count('!')
        caps_count = sum(1 for c in text if c.isupper())
        
        # Emotion keyword matching
        emotion_words = [
            word for word in text.split()
            if word.lower() in self.emotion_lexicons.get(language, {})
        ]
        
        return {
            "sentiment_score": float(sentiment[0]["score"]),
            "intensity_markers": exclamation_count + caps_count,
            "emotion_keywords": emotion_words,
            "intensity_estimate": (
                abs(float(sentiment[0]["score"]) - 0.5) * 2 +  # Normalize sentiment
                min(exclamation_count, 3) * 0.2 +                 # Cap at 3 exclamations
                min(len(emotion_words), 5) * 0.15                 # Cap at 5 emotion words
            )
        }
    
    def compute_postmotion_intensity(self, text: str, language: str) -> dict:
        """Compute emotional intensity after translation."""
        return self.compute_premotion_intensity(text, language)
    
    def translate_with_emotion_preservation(self, 
                                            text_source: str,
                                            language_source: str,
                                            language_target: str,
                                            original_emotion_embedding: np.ndarray,
                                            max_sentiment_loss: float = 0.3) -> dict:
        """
        Translate text while preserving emotional intensity.
        
        Returns:
            {
                "text_target": translated_text,
                "emotion_preserved": bool,
                "sentiment_loss": float,
                "emotion_embedding_adjusted": np.ndarray,
                "retry_count": int
            }
        """
        
        # Measure emotion before translation
        pre_emotion = self.compute_premotion_intensity(text_source, language_source)
        
        # Translate
        text_target = self.translator(text_source, src_lang=language_source, 
                                     tgt_lang=language_target)[0]["translation_text"]
        
        # Measure emotion after translation
        post_emotion = self.compute_postmotion_intensity(text_target, language_target)
        
        # Compute loss
        sentiment_loss = abs(pre_emotion["sentiment_score"] - post_emotion["sentiment_score"])
        intensity_loss = abs(pre_emotion["intensity_estimate"] - post_emotion["intensity_estimate"])
        
        emotion_preserved = sentiment_loss < max_sentiment_loss and intensity_loss < 0.25
        
        if not emotion_preserved:
            # Strategy 1: Retry with explicit emotion constraint
            logger.warning(f"Emotion not preserved (loss={sentiment_loss:.2f}), retrying with constraint")
            text_target = self._translate_with_emotion_constraint(
                text_source, language_source, language_target,
                pre_emotion["sentiment_score"]
            )
            
            # Re-measure
            post_emotion = self.compute_postmotion_intensity(text_target, language_target)
            sentiment_loss = abs(pre_emotion["sentiment_score"] - post_emotion["sentiment_score"])
            emotion_preserved = sentiment_loss < max_sentiment_loss
        
        # Strategy 2: Adjust TTS emotion embedding if still not preserved
        emotion_embedding_adjusted = original_emotion_embedding.copy()
        if not emotion_preserved:
            # Scale emotion embedding based on intensity change
            intensity_ratio = post_emotion["intensity_estimate"] / (
                pre_emotion["intensity_estimate"] + 1e-6
            )
            emotion_embedding_adjusted = original_emotion_embedding * intensity_ratio
        
        return {
            "text_target": text_target,
            "emotion_preserved": emotion_preserved and sentiment_loss < max_sentiment_loss,
            "sentiment_loss": float(sentiment_loss),
            "intensity_loss": float(intensity_loss),
            "emotion_embedding_adjusted": emotion_embedding_adjusted,
            "pre_emotion_score": pre_emotion["sentiment_score"],
            "post_emotion_score": post_emotion["sentiment_score"]
        }
    
    def _translate_with_emotion_constraint(self, text: str, 
                                          src_lang: str, tgt_lang: str,
                                          target_sentiment: float) -> str:
        """Retry translation with explicit emotion constraint via prompt engineering."""
        
        if target_sentiment < -0.3:
            emotion_note = "Keep the negative/sad/serious tone."
        elif target_sentiment > 0.3:
            emotion_note = "Keep the positive/happy/enthusiastic tone."
        else:
            emotion_note = "Keep the neutral tone."
        
        # Use translator with instruction
        prompt = f"{text} [Instruction: {emotion_note}]"
        
        result = self.translator(prompt, src_lang=src_lang, tgt_lang=tgt_lang)
        return result[0]["translation_text"].replace("[Instruction:", "").split("]")[0]
```

---

## PART 6: SESSION-AWARE EMOTION MEMORY

### 6.1 Problem Statement

**Speaker says sentence 1:** "I'm sad" → emotion_embedding = sad_vector
**Speaker says sentence 2:** (continues with same emotion) → emotion_embedding = slightly different position

**Without session memory:** Emotion flips every sentence, produces jerky prosody changes

**With session memory:** Smooth emotional trajectory across conversation

### 6.2 Implementation: Exponential Moving Average (EMA)

```python
class SessionEmotionMemory:
    
    def __init__(self, ema_alpha: float = 0.3):
        """
        Initialize session emotion memory.
        
        Args:
            ema_alpha: EMA smoothing factor (0.2-0.5 typical)
                - Lower = more smoothing (slower changes)
                - Higher = more responsive to new emotions
        """
        self.ema_alpha = ema_alpha
        self.session_emotion_embedding = None  # (128,)
        self.session_valence = None
        self.session_arousal = None
        self.turn_count = 0
        self.emotion_trajectory = []
    
    def update(self, 
               emotion_embedding: np.ndarray,
               valence: float,
               arousal: float) -> dict:
        """
        Update session emotion with new measurement.
        
        Args:
            emotion_embedding: (128,) new emotion vector from current sentence
            valence: float, new valence measurement
            arousal: float, new arousal measurement
        
        Returns:
            {
                "smoothed_embedding": (128,),
                "smoothed_valence": float,
                "smoothed_arousal": float,
                "emotion_continuity_score": float  # 0-1, higher = more continuous
            }
        """
        
        self.turn_count += 1
        
        # First measurement: initialize
        if self.session_emotion_embedding is None:
            self.session_emotion_embedding = emotion_embedding.copy()
            self.session_valence = valence
            self.session_arousal = arousal
            continuity = 1.0
        else:
            # EMA update
            self.session_emotion_embedding = (
                self.ema_alpha * emotion_embedding +
                (1 - self.ema_alpha) * self.session_emotion_embedding
            )
            
            self.session_valence = (
                self.ema_alpha * valence +
                (1 - self.ema_alpha) * self.session_valence
            )
            
            self.session_arousal = (
                self.ema_alpha * arousal +
                (1 - self.ema_alpha) * self.session_arousal
            )
            
            # Compute continuity score (cosine similarity)
            continuity = np.dot(emotion_embedding, self.session_emotion_embedding) / (
                np.linalg.norm(emotion_embedding) * np.linalg.norm(self.session_emotion_embedding) + 1e-8
            )
            continuity = float(np.clip(continuity, 0, 1))
        
        # Store trajectory for analysis
        self.emotion_trajectory.append({
            "turn": self.turn_count,
            "raw_embedding": emotion_embedding.copy(),
            "smoothed_embedding": self.session_emotion_embedding.copy(),
            "raw_valence": valence,
            "smoothed_valence": self.session_valence,
            "continuity_score": continuity
        })
        
        return {
            "smoothed_embedding": self.session_emotion_embedding.copy(),
            "smoothed_valence": float(self.session_valence),
            "smoothed_arousal": float(self.session_arousal),
            "emotion_continuity_score": continuity,
            "turn_count": self.turn_count
        }
    
    def reset(self):
        """Reset for new session."""
        self.session_emotion_embedding = None
        self.session_valence = None
        self.session_arousal = None
        self.turn_count = 0
        self.emotion_trajectory = []
    
    def get_emotion_trajectory(self) -> list:
        """Return full trajectory for analysis/monitoring."""
        return self.emotion_trajectory.copy()
    
    def get_session_summary(self) -> dict:
        """Get summary statistics for session."""
        if not self.emotion_trajectory:
            return {}
        
        trajectory = np.array([e["smoothed_valence"] for e in self.emotion_trajectory])
        continuity_scores = np.array([e["continuity_score"] for e in self.emotion_trajectory])
        
        return {
            "total_turns": self.turn_count,
            "mean_valence": float(np.mean(trajectory)),
            "mean_arousal": float(np.mean([e["smoothed_arousal"] for e in self.emotion_trajectory])),
            "valence_std": float(np.std(trajectory)),
            "mean_continuity": float(np.mean(continuity_scores)),
            "valence_trend": "increasing" if trajectory[-1] > trajectory[0] else "decreasing",
            "dominant_emotion": self._classify_dominant_emotion()
        }
    
    def _classify_dominant_emotion(self) -> str:
        """Classify overall session emotion from valence/arousal."""
        if not self.emotion_trajectory:
            return "neutral"
        
        mean_valence = np.mean([e["smoothed_valence"] for e in self.emotion_trajectory])
        mean_arousal = np.mean([e["smoothed_arousal"] for e in self.emotion_trajectory])
        
        if mean_valence < -0.3 and mean_arousal < 0.5:
            return "sad"
        elif mean_valence < -0.3 and mean_arousal >= 0.5:
            return "angry"
        elif mean_valence > 0.3 and mean_arousal >= 0.5:
            return "happy"
        elif mean_valence > 0.3 and mean_arousal < 0.5:
            return "content"
        else:
            return "neutral"
```

---

## PART 7: UPDATED MICROSERVICE INTERFACES

### 7.1 Pipeline Service Input

**OLD:**
```json
POST /pipeline/process
{
    "audio_path": "user_audio.wav",
    "user_id": "user_12345"
}
```

**NEW:**
```json
POST /pipeline/process
{
    "audio_path": "user_audio.wav",
    "user_id": "user_12345",
    
    "source_language": "es",
    "target_language": "te",
    
    "_options": {
        "preserve_speaker_style": true,
        "emotion_conditioning": true,
        "dialect_conditioning": true,
        "session_smoothing": true,
        "session_id": "conversation_session_001",
        
        "advanced_options": {
            "emotion_intensity_scaling": 1.0,  # 0-2, scale emotion effect
            "max_emotion_preservation_loss": 0.3,  # For translation
            "enable_realtime_streaming": false,
            "tts_quality_level": "high"  # "low" / "medium" / "high"
        }
    }
}
```

### 7.2 Pipeline Service Output

**OLD:**
```json
{
    "output_audio_path": "output_12345.wav",
    "emotion": "sad",
    "confidence": 0.86,
    "latency_ms": 2340
}
```

**NEW:**
```json
{
    "output_audio_path": "output_12345.wav",
    
    "emotion": {
        "embedding": [0.12, -0.34, ...],     // (128,)
        "valence": -0.7,                     // -1 to +1
        "arousal": 0.3,                      // 0 to 1
        "confidence": 0.92,
        "label": "sad"                       // For backward compatibility
    },
    
    "dialect": {
        "embedding": [0.23, 0.45, ...],      // (64,)
        "primary": "andhra",
        "confidence": 0.88,
        "characteristics": {
            "retroflex_intensity": 0.78,
            "nasalization_level": 0.32,
            "speech_rate_relative": 1.02
        }
    },
    
    "speaker_style": {
        "speaker_embedding": [0.12, -0.34, ...],  // (128,)
        "speaker_consistency": 0.92,
        "speaker_id": "speaker_profile_xyz"
    },
    
    "translation": {
        "source_text": "¿Qué triste!",
        "target_text": "చాలా విషాదం!",
        "emotion_preserved": true,
        "sentiment_loss": 0.15
    },
    
    "stage_latencies_ms": {
        "audio_preprocessing": 45,
        "stt": 620,
        "emotion_extraction": 78,
        "dialect_extraction": 156,
        "speaker_extraction": 34,
        "translation": 234,
        "tts_synthesis": 892,
        "total": 2059
    },
    
    "session_context": {
        "session_id": "conversation_session_001",
        "turn_number": 3,
        "emotion_continuity_score": 0.89,
        "session_emotion_summary": {
            "trend": "increasing_positive",
            "dominant_emotion": "content"
        }
    },
    
    "quality_metrics": {
        "emotion_preservation_score": 0.94,
        "prosody_naturalness_score": 0.87,
        "speaker_similarity_score": 0.91,
        "overall_realism_score": 0.91
    }
}
```

### 7.3 Emotion Service

```python
# Service: emotion-extraction-service
POST /emotion/extract
{
    "audio_path": "input.wav"
}

Response:
{
    "embedding": [...],                 # (128,)
    "valence": float,                   # [-1, 1]
    "arousal": float,                   # [0, 1]
    "confidence": float,                # [0, 1]
    "label": str,
    "auxiliary": {
        "intensity_level": "high",
        "emotional_shift": false,        # Compared to last turn
        "expected_tts_pitch_multiplier": 1.15  # For debugging
    }
}
```

### 7.4 Dialect Service

```python
# Service: dialect-profiling-service
POST /dialect/profile
{
    "audio_path": "input.wav"
}

Response:
{
    "embedding": [...],                 # (64,)
    "primary_dialect": str,
    "confidence": float,
    "characteristics": {
        "retroflex_intensity": float,
        "nasalization_level": float,
        "speech_rate_relative": float,
        "vowel_duration_style": str
    },
    "dialect_mixture": {
        "andhra": float,
        "telangana": float,
        "standard": float
    }
}
```

### 7.5 Speaker Styling Service

```python
# Service: speaker-styling-service
POST /speaker/profile
{
    "audio_path": "input.wav"
}

Response:
{
    "embedding": [...],                 # (128,) normalized
    "speaker_consistency": float,       # vs stored profile
    "voicing_duration_pct": float,
    "background_noise_level": float,
    "quality_metrics": {
        "snr_db": float,
        "artifact_score": float
    }
}

# Create/update stored profile
POST /speaker/profile/create
{
    "user_id": "user_12345",
    "audio_paths": ["utt_001.wav", "utt_002.wav", "utt_003.wav"],
    "store_location": "user_profiles/"
}

Response:
{
    "profile_id": "sp_user_12345_v1",
    "num_utterances": 3,
    "profile_embedding": [...]        # (128,) aggregated
    "profile_variance": float,        # How consistent?
}
```

### 7.6 TTS Synthesis Service

```python
# Service: tts-synthesis-service
POST /tts/synthesize
{
    "text": "చాలా విషాదం",
    "language": "te",
    
    "conditioning": {
        "speaker_embedding": [...],         # (128,)
        "emotion_embedding": [...],         # (128,)
        "dialect_embedding": [...],         # (64,)
        "emotion_intensity_scale": 1.0
    }
}

Response:
{
    "audio": base64_encoded_wav,
    "duration_ms": float,
    "latency_ms": 892,
    "quality_metrics": {
        "prosody_score": float,
        "naturalness_score": float,
        "speaker_consistency_score": float
    }
}
```

---

## PART 8: PRODUCTION ENGINEERING

### 8.1 GPU Resource Requirements

**System:** 100k DAU

**Inference Server Configuration:**

```
Hardware:
- Compute Node: 1x NVIDIA H100 (80GB HBM3)
- Memory Node: 768GB DRAM (for model caching)
- Storage: 2x 4TB NVMe for sorted indices, embeddings cache

Model Sizes:
- Wav2Vec2-large: 1.3GB (loaded once)
- Emotion module: 0.5GB
- Dialect module: 0.8GB
- Speaker encoder (ECAPA-TDNN): 0.2GB
- XTTS v2 (finetuned): 4.2GB
- NLLB-200 (1.3B params): 5.6GB
- Total: ~13.6GB

Batch Processing Configuration:
- Batch size for non-lat-critical: 32
- Batch size for real-time: 8
- Concurrent sessions: 64 (4s avg latency, 256s = 4.3 min per session)

Throughput Estimate:
- STT: 480 requests/min (8 concurrent * 60s / 1s latency)
- Emotion extraction: 600 requests/min
- TTS: 180 requests/min (slower stage, 892ms per request)
- Bottleneck: TTS synthesis
```

**Deployment Architecture:**

```
Load Balancer (nginx)
    ↓
[STT Inference Server] (1x GPU, 8 concurrent, batch-32)
    ↓ Queuing: Ultra-fast, 10-50ms wait
[Orchestration + Routing Layer]
    ├─ [Emotion Service] (0.5 GPU share, batched)
    ├─ [Dialect Service] (0.5 GPU share, batched)
    └─ [Speaker Service] (CPU-based, minimal GPU)
    ↓ Queuing: Fast, 50-200ms wait
[Translation Service]
    ├─ NLLB inference (1x GPU core)
    └─ Sentiment checking (CPU, PyTorch CPU inference)
    ↓ Queuing: Moderate, 200-500ms wait
[TTS Synthesis Server] (2x GPU)
    ├─ XTTS v2 + vocoding
    └─ Batch size: 8, with priority queue (realtime users first)
    ↓ Queuing: Highest latency, 500ms-2s wait
[Output Storage] (S3 / GCS)
```

### 8.2 Monitoring & Drift Detection

```python
class ProductionMonitoringDashboard:
    
    def __init__(self):
        self.metrics_collector = PrometheusCollector()
        self.drift_detector = DriftDetector()
    
    def register_metrics(self):
        """Register all metrics with Prometheus."""
        
        # Latency SLI
        self.latency_p99 = Histogram('epmssts_latency_ms',
                                    'End-to-end latency',
                                    buckets=[100, 500, 1000, 2000, 5000])
        
        # Emotion distribution
        self.emotion_distribution = Gauge('epmssts_emotion_valence_mean',
                                         'Mean valence in session window')
        self.emotion_entropy = Gauge('epmssts_emotion_embedding_entropy',
                                    'Entropy of emotion embeddings')
        
        # Dialect distribution
        self.dialect_distribution = Counter('epmssts_dialect_primary_count',
                                           'Count of each dialect',
                                           labelnames=['dialect'])
        
        # Speaker consistency
        self.speaker_consistency = Histogram('epmssts_speaker_consistency_score',
                                            'Speaker embedding consistency',
                                            buckets=[0.7, 0.8, 0.85, 0.9, 0.95])
        
        # Emotion preservation in translation
        self.sentiment_loss = Histogram('epmssts_sentiment_loss',
                                       'Emotion loss in translation',
                                       buckets=[0.1, 0.2, 0.3, 0.4, 0.5])
        
        # GPU utilization
        self.gpu_memory = Gauge('epmssts_gpu_memory_mb',
                               'GPU memory used (MB)')
        self.gpu_util = Gauge('epmssts_gpu_utilization_pct',
                             'GPU utilization percentage')
        
        # Circuit breaker states
        self.circuit_breaker_state = Gauge('epmssts_circuit_breaker_state',
                                          'Circuit breaker open/closed',
                                          labelnames=['service'])
    
    def detect_drift(self, recent_window_size: int = 1000):
        """
        Detect distributional drift in embeddings and metrics.
        """
        
        recent_emotions = self.metrics_collector.get_recent_metrics(
            'emotion_embedding', recent_window_size
        )
        historical_emotions = self.metrics_collector.get_historical_baseline(
            'emotion_embedding', days=30
        )
        
        # KL divergence test
        kl_div = scipy.spatial.distance.jensenshannon(
            np.histogram(np.mean(recent_emotions, axis=1), bins=20)[0],
            np.histogram(np.mean(historical_emotions, axis=1), bins=20)[0]
        )
        
        if kl_div > DRIFT_THRESHOLD:
            self.alert("EMOTION_DISTRIBUTION_DRIFT", {
                "kl_divergence": float(kl_div),
                "recent_mean": float(np.mean(recent_emotions)),
                "historical_mean": float(np.mean(historical_emotions))
            })
        
        # Similar checks for dialect distribution, speaker consistency, etc.
```

### 8.3 Circuit Breaker & Fallback Strategy

```python
class RobustOrchestration:
    
    def __init__(self):
        self.circuit_breakers = {
            "tts_synthesis": CircuitBreaker(failure_threshold=5, timeout_sec=30),
            "translation": CircuitBreaker(failure_threshold=10, timeout_sec=60),
            "emotion_extraction": CircuitBreaker(failure_threshold=3, timeout_sec=15)
        }
        self.fallback_strategies = {}
    
    async def process_with_fallbacks(self, request: PipelineRequest):
        """Process with multi-level fallback strategy."""
        
        try:
            # Primary path
            emotion = await self.circuit_breakers["emotion_extraction"].call(
                self.emotion_service.extract, request.audio_path
            )
        except CircuitBreakerOpen:
            # Fallback 1: Use cached emotion from same speaker
            emotion = await self._fallback_emotion_from_cache(request.user_id)
            if emotion is None:
                # Fallback 2: Use neutral emotion
                emotion = self._create_neutral_emotion()
        
        try:
            translation = await self.circuit_breakers["translation"].call(
                self.translation_service.translate, request.text
            )
        except CircuitBreakerOpen:
            # Fallback: Return source language (no translation)
            translation = request.text
            target_language = request.source_language
        
        try:
            audio = await self.circuit_breakers["tts_synthesis"].call(
                self.tts_service.synthesize, translation, emotion
            )
        except CircuitBreakerOpen:
            # Fallback: Use lower-quality, cached TTS
            audio = await self._lowquality_tts_fallback(
                translation, emotion
            )
        
        return audio response
    
    async def _fallback_emotion_from_cache(self, user_id: str):
        """Get last known emotion for this user."""
        return self.user_emotion_cache.get(user_id)
    
    def _create_neutral_emotion(self):
        """Create neutral emotion embedding."""
        return {
            "embedding": np.zeros(128),
            "valence": 0.0,
            "arousal": 0.5,
            "confidence": 0.1,
            "fallback": True
        }
```

---

## PART 9: VALIDATION & REALISM EVALUATION

### 9.1 New Evaluation Metrics

**A. Emotion Preservation Score**

```python
def emotion_preservation_score(
    source_emotion_embedding: np.ndarray,
    target_emotion_embedding: np.ndarray,
    source_valence: float,
    target_valence: float
) -> float:
    """
    Measure how well emotion is preserved through pipeline.
    
    Scale: 0-1, where 1 = perfect preservation
    """
    
    # 1. Embedding cosine similarity
    embed_sim = np.dot(source_emotion_embedding, target_emotion_embedding) / (
        np.linalg.norm(source_emotion_embedding) * 
        np.linalg.norm(target_emotion_embedding) + 1e-8
    )
    embed_score = np.clip((embed_sim + 1) / 2, 0, 1)  # Normalize to [0, 1]
    
    # 2. Valence trajectory preservation
    valence_diff = abs(source_valence - target_valence)
    valence_score = max(0, 1 - valence_diff / 2)  # Max diff = 2 (from -1 to +1)
    
    # Combined score (weighted)
    return 0.6 * embed_score + 0.4 * valence_score
```

**B. Dialect Preservation Score**

```python
def dialect_preservation_score(
    source_dialect_embedding: np.ndarray,
    source_phonetic_features: dict,  # retroflex_rate, etc.
    output_speech_analysis: dict     # Same features extracted from output
) -> float:
    """
    Measure preservation of dialect characteristics in synthesized speech.
    """
    
    # 1. Embedding similarity
    embed_sim = np.dot(source_dialect_embedding, 
                      output_speech_analysis["dialect_embedding"]) / (
        np.linalg.norm(source_dialect_embedding) + 1e-8
    )
    embed_score = np.clip((embed_sim + 1) / 2, 0, 1)
    
    # 2. Phonetic feature preservation
    phonetic_scores = []
    for feature in ["retroflex_intensity", "nasalization_level", "speech_rate_relative"]:
        source_val = source_phonetic_features.get(feature, 0)
        output_val = output_speech_analysis.get(feature, 0)
        diff = abs(source_val - output_val)
        score = max(0, 1 - diff)
        phonetic_scores.append(score)
    
    phonetic_score = np.mean(phonetic_scores)
    
    # Combined
    return 0.5 * embed_score + 0.5 * phonetic_score
```

**C. Speaker Similarity Score**

```python
def speaker_similarity_score(
    source_speaker_embedding: np.ndarray,
    output_speaker_embedding: np.ndarray,
    source_prosody: dict,
    output_prosody: dict
) -> float:
    """
    Measure how well speaker identity is preserved.
    """
    
    # 1. Speaker embedding cosine similarity
    speaker_sim = np.dot(source_speaker_embedding, output_speaker_embedding) / (
        np.linalg.norm(source_speaker_embedding) * 
        np.linalg.norm(output_speaker_embedding) + 1e-8
    )
    speaker_embed_score = np.clip((speaker_sim + 1) / 2, 0, 1)
    
    # 2. Prosody similarity (pitch, duration, energy)
    prosody_metrics = ["fundamental_frequency_mean", "speech_rate", "energy_rms"]
    prosody_scores = []
    
    for metric in prosody_metrics:
        source_val = source_prosody.get(metric, 0)
        output_val = output_prosody.get(metric, 0)
        # Normalize by source value for relative comparison
        if source_val > 0:
            relative_diff = abs(output_val - source_val) / source_val
            score = max(0, 1 - relative_diff)
        else:
            score = 1.0
        prosody_scores.append(score)
    
    prosody_score = np.mean(prosody_scores)
    
    # Combined
    return 0.4 * speaker_embed_score + 0.6 * prosody_score
```

**D. Prosody Contour Similarity**

```python
def prosody_contour_similarity(
    source_f0_contour: np.ndarray,  # Pitch trajectory
    output_f0_contour: np.ndarray,
    source_energy_contour: np.ndarray,
    output_energy_contour: np.ndarray
) -> float:
    """
    Measure similarity of pitch and energy trajectories.
    Useful for detecting if prosody is learned or still rule-based.
    """
    # Normalize both to [0, 1] scale within each signal
    source_f0_norm = (source_f0_contour - source_f0_contour.min()) / (
        source_f0_contour.max() - source_f0_contour.min() + 1e-8
    )
    output_f0_norm = (output_f0_contour - output_f0_contour.min()) / (
        output_f0_contour.max() - output_f0_contour.min() + 1e-8
    )
    
    # Interpolate to same length
    if len(source_f0_norm) != len(output_f0_norm):
        output_f0_norm = np.interp(
            np.linspace(0, 1, len(source_f0_norm)),
            np.linspace(0, 1, len(output_f0_norm)),
            output_f0_norm
        )
    
    # Compute Pearson correlation
    f0_correlation = np.corrcoef(source_f0_norm, output_f0_norm)[0, 1]
    f0_score = np.clip((f0_correlation + 1) / 2, 0, 1)  # Normalize to [0, 1]
    
    # Same for energy
    source_energy_norm = (source_energy_contour - source_energy_contour.min()) / (
        source_energy_contour.max() - source_energy_contour.min() + 1e-8
    )
    output_energy_norm = (output_energy_contour - output_energy_contour.min()) / (
        output_energy_contour.max() - output_energy_contour.min() + 1e-8
    )
    
    if len(source_energy_norm) != len(output_energy_norm):
        output_energy_norm = np.interp(
            np.linspace(0, 1, len(source_energy_norm)),
            np.linspace(0, 1, len(output_energy_norm)),
            output_energy_norm
        )
    
    energy_correlation = np.corrcoef(source_energy_norm, output_energy_norm)[0, 1]
    energy_score = np.clip((energy_correlation + 1) / 2, 0, 1)
    
    # Combined
    return 0.5 * f0_score + 0.5 * energy_score
```

---

## PART 10: MIGRATION ROADMAP

### Phase 1: Emergency (Week 1-2)
- [ ] Extract Wav2Vec2 embeddings from existing STT service
- [ ] Train emotion projection head on 500 training samples
- [ ] Implement continuous emotion output (parallel with old labels)
- [ ] No TTS changes yet

**Risk:** New emotion dimension coexists with old system, creates confusion

### Phase 2: Core Upgrade (Month 1)
- [ ] Implement dialect embedding module
- [ ] Integrate speaker encoder (ECAPA-TDNN)
- [ ] Add session emotion memory
- [ ] Implement translation sentiment preservation
- [ ] Update orchestration to compose style vectors

**Risk:** Orchestration becomes complex, needs careful testing

### Phase 3: TTS Integration (Month 2)
- [ ] Integrate XTTS v2 with style conditioning
- [ ] LoRA fine-tuning on 1000 samples with annotations
- [ ] Gradual rollout (5% traffic → 25% → 50%)
- [ ] A/B testing against old TTS

**Risk:** TTS quality may regress initially, requires monitoring

### Phase 4: Production Hardening (Month 3)
- [ ] Implement full monitoring & drift detection
- [ ] Add circuit breakers and fallback strategies
- [ ] Scale GPU infrastructure
- [ ] 100% traffic migration

**Risk:** Latency may exceed SLA, needs optimization

### Phase 5: Validation & Evaluation (Ongoing)
- [ ] Run REALISM_EVALUATION_REPORT weekly
- [ ] Collect MOS (Mean Opinion Score) from users
- [ ] Monitor emotion distribution, dialect distribution, speaker consistency drift

**Risk:** Metrics may not correlate with user satisfaction

### Backward Compatibility Strategy

```python
# All responses include both old and new formats

response = {
    # Old format (for compatibility)
    "emotion": "sad",                    # Keep old label
    "confidence": 0.86,
    "output_audio_path": "...",
    
    # New format (with additional fields)
    "emotion_extended": {
        "embedding": [...],
        "valence": -0.7,
        "arousal": 0.3,
        "confidence": 0.92,
        "label": "sad"                   # Repeated for clarity
    },
    
    # Feature flags for client behavior
    "features": {
        "uses_new_emotion_model": true,
        "uses_neural_tts": true,
        "dialect_conditioning_enabled": true
    }
}

# Clients can ignore new fields until ready to migrate
```

---

## SUMMARY TABLE: System Transformation

| Aspect | Current (v1) | Upgraded (v2) | Benefit |
|--------|-------------|---------------|---------|
| **Emotion** | 5-7 labels | 128d embedding + valence/arousal | Nuanced, blendable, learnable |
| **Dialect** | String label | 64d embedding + phonetic features | Contextual, gradualistic |
| **Speaker** | Lost | ECAPA-TDNN (128d) | Personalization, consistency |
| **Prosody** | Rule-based (hardcoded multipliers) | Learned neural TTS | Natural, variable |
| **Translation** | NLLB direct | NLLB + sentiment preservation | Emotion-aware |
| **Session** | None | EMA-smoothed emotion | Conversational continuity |
| **SLA** | <5s | <5s (same target, achieved through optimization) | No regression |
| **Monitoring** | Basic latency | Drift detection, embedding entropy, style consistency | Production-ready |
| **User Experience** | Rule-based, robotic | Neural, personalized, emotionally authentic | 80-90% production readiness |

---

## NEXT STEPS

1. **Review architecture decisions** - Validate Model choices
2. **Estimate training dataset size** - Prepare annotations for 500-5000 samples
3. **Plan GPU procurement** - 1x H100 + infrastructure
4. **Begin Phase 1 implementation** - Extract embeddings, train emotion head
5. **Setup evaluation framework** - REALISM_EVALUATION_REPORT automation

---

**Document Status:** Architecture Design Complete  
**Recommended Action:** Proceed to Phase 1 implementation  
**Estimated Timeline:** 12-16 weeks to full production  
**Team Size:** 4-6 engineers (ML, backend, infra)  
