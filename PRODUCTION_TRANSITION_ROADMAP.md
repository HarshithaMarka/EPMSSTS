# EPMSSTS v2: Production Transition Roadmap & Implementation Checklist

**Status:** Deployment Planning Document  
**Timeline:** 12-16 weeks to production  
**Team:** 4-6 engineers (ML, backend, infra)  
**Target Launch:** Q3 2026  

---

## PHASE 1: FOUNDATION (Week 1-3)

### Week 1: Infrastructure & Environment Setup

**Objectives:**
- Provision GPU server
- Setup development environment
- Establish data pipeline

**Deliverables:**

- [ ] H100 GPU server provisioned (80GB HBM3)
  - [ ] Installed CUDA 12.x, cuDNN 9.x
  - [ ] Docker containers configured
  - [ ] Monitoring (Prometheus + Grafana)
  
- [ ] Development environment
  - [ ] Git repository for architecture code
  - [ ] Jupyter for experimentation
  - [ ] MLFlow or Weights & Biases for experiment tracking
  
- [ ] Data pipeline
  - [ ] Audio ingestion from production (anonymized)
  - [ ] Annotation infrastructure (Label Studio instance)
  - [ ] Training data versioning (DVC or similar)

**People:** 1 ML Engineer + 1 Platform Engineer

**Estimated Effort:** 40 hours

**Blockers:** GPU procurement (might have 4-6 week lead time, order immediately)

---

### Week 2: Emotion Module - Data Preparation & Model Baseline

**Objectives:**
- Annotate 500 training samples with valence/arousal
- Train baseline Wav2Vec2 + projection head
- Establish baseline metrics

**Tasks:**

1. **Data Annotation (with contractors)**
   - [ ] Prepare annotation interface in Label Studio
     - [ ] Emotion labels (7 categories)
     - [ ] Valence slider (-1 to +1)
     - [ ] Arousal slider (0 to 1)
     - [ ] Audio quality assessment
   - [ ] Recruit 3-4 native Telugu speakers as annotators
   - [ ] Create annotation guidelines document
   - [ ] Annotate 500 samples (distributed work: 150-200 per annotator)
   - [ ] Cross-validator (4th person) QA samples with >10% disagreement
   - [ ] Final dataset: 500 samples with gold labels + confidence

2. **Model Training**
   - [ ] Setup Wav2Vec2 fine-tuning pipeline
     - [ ] Load `facebook/wav2vec2-large-xlsr-53`
     - [ ] Create EmotionProjectionHead()
     - [ ] Implement multi-task loss (classification + regression + triplet)
     - [ ] Configure training hyperparameters
   - [ ] Train on 500 annotated samples
     - [ ] 80/10/10 split (400/50/50)
     - [ ] Batch size 32, 3 epochs, AdamW
     - [ ] Expected training time: 4-6 hours on H100
   - [ ] Evaluate:
     - [ ] Classification F1 score (target: >0.85)
     - [ ] Valence MAE (target: <0.15)
     - [ ] Arousal MAE (target: <0.12)
     - [ ] Triplet loss improvement (target: similarity increase >10%)

3. **Documentation**
   - [ ] Write [EMOTION_MODULE_TRAINING_REPORT.md](EMOTION_MODULE_TRAINING_REPORT.md)
     - [ ] Training curves (loss, metrics)
     - [ ] Confusion matrix (emotion classification)
     - [ ] Regression accuracy by emotion class
     - [ ] Error analysis (misclassified examples)

**People:** 1 ML Engineer (model), 1 Data Annotator (coordination)

**Estimated Effort:** 120 hours ML + 80 hours annotation coordination

**Success Criteria:**
- [ ] 500 annotated samples in database
- [ ] Trained emotion module saved to `models/emotion_v1.pth`
- [ ] Evaluation report written
- [ ] F1 score > 0.85, Valence MAE < 0.15

---

### Week 3: Dialect Module - Data Collection & Baseline Training

**Objectives:**
- Collect 300 Telugu audio samples with dialect annotations
- Train dialect embedding module
- Validate dialect preservation

**Tasks:**

1. **Dialect Data Collection**
   - [ ] Setup data collection protocol
     - [ ] Standard 10 sentences covering phonetic range
     - [ ] Record from Andhra, Telangana, urban speakers
     - [ ] Quality: Quiet home environment (no heavy background noise)
   - [ ] Recruit 30+ speakers (10 per dialect category)
   - [ ] Collect 3 utterances per speaker = 90-100 samples per category = 300 total
   - [ ] Obtain consent & store anonymously
   - [ ] Store in FLAC format (lossless, 16kHz)

2. **Dialect Annotation**
   - [ ] Create annotation template
     - [ ] Primary dialect label (Andhra / Telangana / Standard)
     - [ ] Retroflex intensity (0-1 slider)
     - [ ] Nasalization level (0-1 slider)
     - [ ] Speech rate multiplier
     - [ ] Dialect mixture weights
   - [ ] Linguistics expert reviews & annotates
     - [ ] Or hire Telugu phonologist consultant (cost: ~$2k for 300 samples = $7/sample)
   - [ ] Quality control: Re-annotate 10% subset

3. **Feature Extraction Pipeline**
   - [ ] Implement extract_dialect_features() (MFCC, F0, spectral)
   - [ ] Test on 50 samples
   - [ ] Verify feature quality (no NaNs, stable ranges)
   - [ ] Create feature visualization dashboard

4. **Model Training**
   - [ ] Train DialectEmbeddingModule (BiLSTM + attention)
     - [ ] 70/15/15 split (210/45/45)
     - [ ] Batch size 16, 5 epochs
     - [ ] Expected training time: 2-3 hours on H100
   - [ ] Evaluate:
     - [ ] Classification accuracy (target: >0.80)
     - [ ] Retroflex intensity MAE (target: <0.15)
     - [ ] Nasalization MAE (target: <0.15)

**People:** 1 ML Engineer + 1 Linguistics Consultant (part-time)

**Estimated Effort:** 100 hours ML + 40 hours consultant + 20 hours data collection

**Success Criteria:**
- [ ] 300 dialect samples collected & annotated
- [ ] extract_dialect_features() implemented & tested
- [ ] Trained dialect module saved to `models/dialect_v1.pth`
- [ ] Classification accuracy > 0.80

---

## PHASE 2: INTEGRATION (Week 4-8)

### Week 4: Speaker Embedding & Module Integration

**Objectives:**
- Integrate ECAPA-TDNN speaker encoder
- Create SpeakerProfileManager
- Build orchestration layer combining all embeddings

**Tasks:**

1. **Speaker Encoder Integration**
   - [ ] Download `speechbrain/spk-ecapa-tdnn-superb`
   - [ ] Implement SpeakerEmbeddingExtractor class
     - [ ] extract() method with L2 normalization
     - [ ] compute_speaker_similarity()
     - [ ] _compute_quality_metrics()
   - [ ] Test on 50 diverse audio samples
     - [ ] Verify embedding norm ~1.0 after normalization
     - [ ] Check similarity matrix (same speaker > 0.9 similarity)

2. **Speaker Profile Management**
   - [ ] Design PostgreSQL schema for speaker_profiles
     - [ ] Column: embedding (pgvector, dimension 256)
     - [ ] Index: HNSW for fast similarity search
   - [ ] Implement SpeakerProfileManager
     - [ ] create_profile() with weighted averaging
     - [ ] store_profile() with pgvector backend
     - [ ] retrieve_profile()
     - [ ] compute_speaker_consistency()
   - [ ] Migration script: `CREATE EXTENSION vector;`

3. **Emotion + Dialect + Speaker Fusion**
   - [ ] Create OrchestrationV2 class
     ```python
     class OrchestrationV2:
         async def process_pipeline(self, audio_path, source_lang, target_lang):
             # Extract all embeddings in parallel
             emotion_emb = await emotion_service.extract(audio_path)
             dialect_emb = await dialect_service.extract(audio_path)
             speaker_emb = await speaker_service.extract(audio_path)
             
             # Compose style vector
             style_vector = self._compose_style_vector(
                 emotion_emb, dialect_emb, speaker_emb
             )
             
             return {
                 "emotion": emotion_emb,
                 "dialect": dialect_emb,
                 "speaker": speaker_emb,
                 "composed_style_vector": style_vector
             }
     ```
   - [ ] Unit tests for each component
   - [ ] Integration tests (end-to-end on sample audio)

4. **API Updates**
   - [ ] Update /pipeline/process endpoint
     - [ ] Accept new input fields
     - [ ] Return new response format (with all embeddings)
     - [ ] Backward compatibility (old fields still present)
   - [ ] Create versioning (v1 = old, v2 = new)
   - [ ] OpenAPI documentation

**People:** 1 ML Engineer + 1 Backend Engineer

**Estimated Effort:** 100 hours ML + 80 hours backend

**Success Criteria:**
- [ ] Speaker embeddings created for 100+ test users
- [ ] PostgreSQL speaker profiles table functional
- [ ] OrchestrationV2 processes full pipeline
- [ ] API v2 endpoint returns new response format
- [ ] Backward compatibility maintained (v1 still works)

---

### Week 5-6: Translation & Sentiment Preservation

**Objectives:**
- Integrate NLLB-200 translation
- Implement sentiment preservation layer
- Test on Spanish→Telugu & English→Telugu

**Tasks:**

1. **Translation Service Setup**
   - [ ] Load NLLB-200-1.3B model
   - [ ] Create TranslationService class
     - [ ] translate() method
     - [ ] Multi-language support (ES→TE, EN→TE, etc.)
   - [ ] Benchmark latency (target: <500ms for 100 chars)
   - [ ] Setup caching for common phrases

2. **Sentiment Preservation Implementation**
   - [ ] Implement SentimentPreservingTranslator
     - [ ] _analyze_sentiment() using XLM-RoBERTa
     - [ ] _extract_emotion_keywords() per language
     - [ ] _translate_with_constraint() with retry logic
   - [ ] Create emotion lexicons for Spanish, English, Telugu
     - [ ] Manual curation OR
     - [ ] Auto-extract from existing lexicons (e.g., NRC)
   - [ ] Test on 100 examples
     - [ ] Measure sentiment preservation rate (target: >80% sentences preserve sentiment)
     - [ ] Measure latency increase from retry (expected: +200-300ms for 20% of cases)

3. **Integration with Orchestration**
   - [ ] Add translation step to OrchestrationV2
   - [ ] Chain: STT → Emotion → Dialect → Translation (with sentiment check) → TTS
   - [ ] Response includes sentiment_loss, sentiment_preserved flags

4. **Evaluation Dataset**
   - [ ] Create test set: 50 sentences in Spanish with varied emotional content
     - [ ] 15 positive emotional
     - [ ] 15 negative emotional
     - [ ] 10 neutral
     - [ ] 10 strongly emotional (exclamations, emphasis)
   - [ ] Manual verification: Do translated versions preserve emotion?
     - [ ] Annotator task: "Rate sentiment preservation 1-5"
     - [ ] Target: Average score > 4.0

**People:** 1 ML Engineer

**Estimated Effort:** 100 hours

**Success Criteria:**
- [ ] NLLB-200 integrated, latency <500ms
- [ ] Sentiment preservation rate > 80%
- [ ] Test set evaluation (average score > 4.0)
- [ ] Retry logic reduces sentiment loss by >30%

---

### Week 7: Session Emotion Memory & Orchestration Refinement

**Objectives:**
- Implement SessionEmotionMemory with EMA smoothing
- Support multi-turn conversations
- Refine orchestration error handling

**Tasks:**

1. **Session Memory Implementation**
   - [ ] Implement SessionEmotionMemory class
     - [ ] EMA update with configurable alpha (default 0.3)
     - [ ] track smoothed emotion across turns
     - [ ] compute_continuity_score()
     - [ ] get_emotion_trajectory()
   - [ ] Test on 10 simulated multi-turn conversations
     - [ ] Verify EMA smoothing (emotion changes gradually, not jerky)
     - [ ] Measure continuity improvement (target: ±0.10 change per sentence → ±0.03 with EMA)

2. **Session Management in Orchestration**
   - [ ] Add session_id parameter to pipeline
   - [ ] Create SessionManager for multi-turn state
   - [ ] Load/save session state (Redis or PostgreSQL)
   - [ ] Test conversation flow:
     - [ ] Turn 1: "I'm sad" → emotion = sad
     - [ ] Turn 2: "But getting better" → emotion smoothed from sad→neutral
     - [ ] Verify TTS prosody transitions smoothly

3. **Error Handling & Fallbacks**
   - [ ] Implement CircuitBreakerV2 for each service
     - [ ] TTS failure → fallback to basic synthesis
     - [ ] Translation failure → return source language
     - [ ] Emotion extraction failure → use neutral emotion
   - [ ] Test failure scenarios:
     - [ ] Service down (circuit breaker opens)
     - [ ] Slow service (timeout handling)
     - [ ] Invalid input (graceful degradation)
   - [ ] Monitoring: Alert on circuit breaker opens

4. **Response Format Finalization**
   - [ ] Extended response with all new fields
   - [ ] Quality metrics (emotion_preservation, dialect_preservation, speaker_similarity)
   - [ ] Session context (emotion_continuity_score, session_emotion_summary)
   - [ ] Example response in updated API documentation

**People:** 1 ML Engineer + 1 Backend Engineer

**Estimated Effort:** 80 hours

**Success Criteria:**
- [ ] SessionEmotionMemory functional and tested
- [ ] Multi-turn conversation support working
- [ ] Circuit breaker fallbacks implemented
- [ ] Extended response format validated

---

### Week 8: XTTS v2 Integration (Pre-finetuning)

**Objectives:**
- Integrate XTTS v2 (without style conditioning yet)
- Setup fine-tuning infrastructure
- Create LoRA layers for style conditioning

**Tasks:**

1. **XTTS v2 Integration**
   - [ ] Download XTTS v2 model
   - [ ] Create synthesizer wrapper
     - [ ] Language mapping (te → "te")
     - [ ] Benchmark latency (expected: 800-1000ms)
   - [ ] Test synthesis on 50 sentences
     - [ ] Different languages (Telugu, English, Spanish)
     - [ ] Audio quality assessment

2. **GPU Memory Optimization**
   - [ ] Implement GPUResourceManager
     - [ ] Load base models (Wav2Vec2, Emotion, Dialect) at startup
     - [ ] Load/unload XTTS v2 on-demand
     - [ ] Monitor GPU memory usage
   - [ ] Benchmark memory with concurrent requests
     - [ ] Single request: ~6GB peak
     - [ ] Batch of 4: ~8GB peak (efficient!)

3. **Style Conditioning Fusion Layer**
   - [ ] Implement StyleConditioningFusion module (from COMPREHENSIVE_ARCHITECTURE_UPGRADE.md)
   - [ ] Mock style vectors and test fusion layer
   - [ ] Prepare for fine-tuning (next phase)

4. **Training Data Preparation for XTTS Fine-tuning**
   - [ ] Collect or license 50-100 hours of Telugu speech
     - [ ] Different speakers, emotions, dialects
     - [ ] Each with gold emotion/dialect/speaker embeddings
   - [ ] Organize in XTTS fine-tuning format
   - [ ] Create training config for LoRA fine-tuning

**People:** 1 ML Engineer + 1 Platform Engineer

**Estimated Effort:** 100 hours

**Success Criteria:**
- [ ] XTTS v2 integrated and tested
- [ ] Latency <1000ms consistently
- [ ] GPU memory stable (no leaks)
- [ ] Training data prepared for Phase 3

---

## PHASE 3: FINE-TUNING & VALIDATION (Week 9-12)

### Week 9-10: XTTS v2 LoRA Fine-tuning

**Objectives:**
- Fine-tune XTTS v2 with style conditioning
- Achieve emotion preservation in TTS output
- Create baseline evaluation metrics

**Tasks:**

1. **LoRA Configuration**
   - [ ] Install PEFT (Parameter-Efficient Fine-Tuning)
   - [ ] Configure LoRA for XTTS v2
     - [ ] Rank: 8-16
     - [ ] Target modules: Attention Q,V projections
     - [ ] Alpha: 16
   - [ ] Estimate tunable parameters (~1% of original)

2. **Training Pipeline**
   - [ ] Setup training loop with style vectors
   - [ ] Loss function: Reconstruction + style matching
   - [ ] Schedule: 3 epochs on 50-100 hours data
   - [ ] Expected duration: 2-3 weeks (continuous training on H100)
   - [ ] Checkpoints: Save every epoch

3. **Validation During Training**
   - [ ] Generate samples at end of each epoch
   - [ ] Evaluate:
     - [ ] Emotion preservation (embedding cosine similarity)
     - [ ] Prosody contour correlation (pitch, energy)
     - [ ] Naturalness (subjective listening test, 3 trained annotators)
   - [ ] Monitor metrics for overfitting
   - [ ] Early stopping if validation plateaus

4. **Evaluation Dataset Preparation**
   - [ ] Curate 20 test conversations
     - [ ] 5 with happy emotion
     - [ ] 5 with sad emotion
     - [ ] 5 with neutral emotion
     - [ ] 5 with mixed emotions
   - [ ] Include Andhra, Telangana, Standard dialect samples
   - [ ] Include diverse speakers (F/M, age ranges)

**People:** 1 ML Engineer

**Estimated Effort:** 160 hours (includes waiting for training)

**Success Criteria:**
- [ ] Fine-tuned model saved to `models/xtts_v2_lora_finetuned/`
- [ ] Training curves show convergence
- [ ] Validation metrics improve (emotion preservation >0.85, prosody correlation >0.80)
- [ ] 20-sample test set ready for human evaluation

---

### Week 11: Realism Evaluation Framework

**Objectives:**
- Implement comprehensive evaluation metrics
- Establish baseline for comparison
- Create human evaluation protocol

**Tasks:**

1. **Automated Metrics Implementation**
   - [ ] Implement emotion_preservation_score()
     - [ ] Embedding similarity + valence difference
   - [ ] Implement dialect_preservation_score()
     - [ ] Embedding similarity + phonetic features
   - [ ] Implement speaker_similarity_score()
     - [ ] Speaker embedding similarity + prosody correlation
   - [ ] Implement prosody_contour_similarity()
     - [ ] Pitch correlation, energy correlation
   - [ ] Create evaluation pipeline that runs on all validation samples
   
2. **Metrics Dashboard**
   - [ ] Create Jupyter notebook for visualizations
     - [ ] Metric distributions per emotion/dialect/speaker
     - [ ] Scatter plots showing relationships
     - [ ] Trend lines over time (as model improves)
   - [ ] Export as [REALISM_EVALUATION_REPORT.md](REALISM_EVALUATION_REPORT.md)

3. **Human Evaluation Protocol**
   - [ ] Create MOS (Mean Opinion Score) evaluation form
     - [ ] Prosody naturalness (1-5)
     - [ ] Emotion expressiveness (1-5)
     - [ ] Dialect authenticity (1-5)
     - [ ] Overall quality (1-5)
   - [ ] Recruit 5 native Telugu speakers as evaluators
   - [ ] Each evaluates all 20 test samples
   - [ ] Calculate inter-rater agreement (Fleiss' Kappa)
   - [ ] Target Kappa > 0.60 (substantial agreement)

4. **Baseline Comparison**
   - [ ] Run evaluation on old TTS output (rule-based prosody)
   - [ ] Document old metrics for comparison
   - [ ] Measure improvement: "v2 is X% better than v1"

**People:** 1 ML Engineer + 2 Human Evaluators

**Estimated Effort:** 120 hours

**Success Criteria:**
- [ ] All 5 automated metrics implemented
- [ ] Evaluation dashboard created
- [ ] Human evaluation completed (inter-rater Kappa >0.60)
- [ ] Improvement over baseline documented (target: >15% improvement)

---

### Week 12: Production Hardening & Monitoring

**Objectives:**
- Implement Prometheus metrics
- Setup drift detection
- Create runbook for operations

**Tasks:**

1. **Prometheus Metrics**
   - [ ] Register all metrics
     - [ ] Latency SLI (p99)
     - [ ] Emotion distribution
     - [ ] Dialect distribution
     - [ ] Speaker consistency
     - [ ] Sentiment preservation
     - [ ] GPU utilization
     - [ ] Circuit breaker states
   - [ ] Setup Grafana dashboards
     - [ ] Real-time monitoring
     - [ ] Historical trends
     - [ ] Alerts configuration

2. **Drift Detection**
   - [ ] Implement DriftDetector class
     - [ ] KL divergence for emotion/dialect distributions
     - [ ] Embedding entropy monitoring
     - [ ] Prosody contour anomaly detection
   - [ ] Setup alerts
     - [ ] Email notification on drift
     - [ ] Dashboard highlighting anomalies
   - [ ] Test on simulated drift scenarios

3. **Operations Runbook**
   - [ ] Create [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md)
     - [ ] System architecture diagram
     - [ ] Health check procedures
     - [ ] Troubleshooting guide
     - [ ] Rollback procedures
     - [ ] On-call escalation

4. **Load Testing**
   - [ ] Use k6 or vegeta for load testing
     - [ ] Target: 100 req/sec (simulating 100k DAU / 86400 sec)
     - [ ] Measure p50, p95, p99 latency
     - [ ] Verify error rate <0.1%
   - [ ] Document results

**People:** 1 Platform Engineer

**Estimated Effort:** 80 hours

**Success Criteria:**
- [ ] All Prometheus metrics emitting data
- [ ] Grafana dashboards live
- [ ] Drift detection alerts working
- [ ] Runbook written & reviewed
- [ ] Load test shows <5s p99 latency at 100 req/sec

---

## PHASE 4: DEPLOYMENT & ROLLOUT (Week 13-16)

### Week 13: Staging Deployment

**Objectives:**
- Deploy to staging environment
- Run smoke tests & integration tests
- Get stakeholder sign-off

**Tasks:**

1. **Staging Infrastructure**
   - [ ] Mirror production setup in staging
   - [ ] Deploy with Docker containers
   - [ ] Full logging + monitoring

2. **Test Suite**
   - [ ] Unit tests (all components)
   - [ ] Integration tests (full pipelines)
   - [ ] API contract tests (backward compatibility)
   - [ ] Load tests (at 100 DAU level)
   - [ ] Soak test (run for 24 hours, monitor memory leaks)

3. **Stakeholder Testing**
   - [ ] Demo to product team
   - [ ] Demo to QA team
   - [ ] Gather feedback
   - [ ] Fix critical issues found

4. **Documentation**
   - [ ] Update API documentation
   - [ ] Create deployment guide
   - [ ] Create user guide (if applicable)

**People:** 2 Engineers (ML + Platform)

**Estimated Effort:** 100 hours

**Success Criteria:**
- [ ] All tests passing
- [ ] Stakeholder sign-off obtained
- [ ] No critical bugs found in staging
- [ ] Memory stable over 24-hour soak test

---

### Week 14: Canary Deployment (5% Traffic)

**Objectives:**
- Route 5% of production traffic to v2
- Monitor for issues
- Validate metrics in production

**Tasks:**

1. **Deployment**
   - [ ] Deploy v2 to production
   - [ ] Configure traffic split: 95% v1 → 5% v2
   - [ ] Setup comparison logging (v1 vs v2 output for same inputs)

2. **Monitoring (24 hours)**
   - [ ] Check latency (p99 <5s)
   - [ ] Check error rate (<0.1%)
   - [ ] Check GPU memory stability
   - [ ] Compare metrics (emotion scores, sentiment preservation)
   - [ ] Monitor circuit breaker events

3. **User Feedback Collection**
   - [ ] Survey users on v2 quality (5% sample)
   - [ ] Collect audio clips for QA analysis
   - [ ] Address critical issues immediately

4. **Decision Point**
   - [ ] If metrics good: proceed to 25%
   - [ ] If issues found: rollback & debug

**People:** 1 Engineer on-call + 1 monitoring

**Estimated Effort:** 40 hours (intense, but brief)

**Success Criteria:**
- [ ] Latency p99 <5.5s (within SLA + margin)
- [ ] Error rate <0.5%
- [ ] No OOM errors
- [ ] User feedback neutral or positive

---

### Week 15: Progressive Rollout (25% → 50% → 75%)

**Objectives:**
- Gradually increase traffic split
- Maintain stability
- Prepare for full rollout

**Tasks:**

1. **Day 1: 25% Traffic**
   - [ ] Monitor for 24 hours
   - [ ] Verify metrics stable
   - [ ] Address any issues

2. **Day 2: 50% Traffic**
   - [ ] Monitor for 24 hours
   - [ ] Check metric changes (emotion distribution, sentiment preservation)
   - [ ] Verify no regression

3. **Day 3: 75% Traffic**
   - [ ] Monitor for 24 hours
   - [ ] Final checklist before 100%
   - [ ] Prepare rollback plan

**People:** 1 Engineer on-call + 1 monitoring

**Estimated Effort:** 40 hours

**Success Criteria:**
- [ ] All latency/stability metrics maintained
- [ ] No escalating error patterns
- [ ] User sentiment tracking positive

---

### Week 16: Full Rollout & Post-Launch Monitoring

**Objectives:**
- Complete migration to v2
- Maintain stability
- Start optimization phase

**Tasks:**

1. **100% Traffic Migration**
   - [ ] Route all traffic to v2
   - [ ] Keep v1 available for 1 week (quick rollback)

2. **Intensive Monitoring (1 week)**
   - [ ] Daily check-ins (30 min)
   - [ ] Review all metrics
   - [ ] Investigation of anomalies
   - [ ] Performance profiling

3. **User Feedback Collection**
   - [ ] In-app survey: "Quality of outputs?"
   - [ ] Target: 80%+ "Good" or "Excellent" feedback
   - [ ] Analyze any complaints

4. **Post Launch Checklist**
   - [ ] Sign-off from stakeholders
   - [ ] v1 code archived (can remove)
   - [ ] Operations team trained
   - [ ] SRE playbooks updated

**People:** 2 Engineers + Operations

**Estimated Effort:** 60 hours

**Success Criteria:**
- [ ] 100% traffic on v2 stable for 24 hours
- [ ] Metrics all green (latency, errors, memory)
- [ ] User satisfaction >80%
- [ ] Operations team confident in running system

---

## RESOURCE ALLOCATION SUMMARY

| Role | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Total |
|------|---------|---------|---------|---------|--------|
| **ML Engineer (Lead)** | 120h | 200h | 160h | 40h | 520h |
| **Backend Engineer** | 40h | 160h | 0h | 100h | 300h |
| **Platform Engineer** | 40h | 100h | 80h | 60h | 280h |
| **Data Annotation/Coordination** | 80h | 20h | 0h | 0h | 100h |
| **Linguistics Consultant** | 0h | 40h | 0h | 0h | 40h |
| **Human Evaluators** | 0h | 0h | 40h | 0h | 40h |
| **Total Person-Months** | 1.0 | 2.0 | 1.0 | 1.0 | **5.0** |

**Budget Estimate:**
- Engineering: 5 person-months × $20k/month = $100k
- Infrastructure (H100 rental): 4 months × $10k/month = $40k
- Data annotation: 100h × $25/h = $2.5k
- Consultant: 40h × $75/h = $3k
- Evaluation: 40h × $25/h = $1k
- **Total: ~$146.5k**

---

## RISK MITIGATION

### High Risk: XTTS v2 Fine-tuning Not Converging

**Mitigation:**
- [ ] Start with LoRA (low-rank) instead of full fine-tuning
- [ ] Use pre-trained checkpoints from Coqui
- [ ] Fallback: Use VITS2 instead (more stable, lighter weight)
- [ ] Mitigation effort: 2-person-weeks delay

### High Risk: Emotion Preservation Loss in Translation

**Mitigation:**
- [ ] Implement sentiment-aware back-translation
- [ ] Use stronger sentiment models (fine-tuned on Telugu)
- [ ] Fallback: Warn user if sentiment loss > 0.3
- [ ] Mitigation effort: 1-person-week

### Medium Risk: GPU Memory Leak

**Mitigation:**
- [ ] Implement strict model lifecycle (load/unload)
- [ ] Monitor GPU memory hourly
- [ ] Full model restart daily (if needed)
- [ ] Mitigation effort: Pre-implemented in Week 8

### Medium Risk: Latency SLA Violation

**Mitigation:**
- [ ] Aggressive batching (batch size 32 for STT/emotion)
- [ ] Model quantization (FP16 where possible)
- [ ] Fallback: Return v1 TTS if v2 takes >4s
- [ ] Mitigation effort: Pre-designed in architecture

---

## SUCCESS METRICS (12-week target)

| Metric | v1 Baseline | v2 Target | Definition |
|--------|------------|-----------|-----------|
| **Emotion Preservation** | N/A | >0.85 | Cosine similarity + valence preservation |
| **Dialect Preservation** | N/A | >0.80 | Embedding similarity + phonetic features |
| **Speaker Similarity** | N/A | >0.88 | Speaker embedding cosine similarity |
| **Prosody Correlation** | N/A | >0.80 | Pitch & energy contour correlation |
| **Latency p99** | varies | <5000ms | End-to-end, including TTS |
| **Sentiment Preservation** | N/A | >80% | % sentences maintain polarity |
| **User Rating (MOS)** | 3.2/5 | >4.1/5 | Mean opinion score |
| **Uptime** | 99.5% | 99.8% | Availability SLA |
| **Error Rate** | 0.8% | <0.3% | Failed requests / total |

---

## DELIVERABLES CHECKLIST

### Code & Models
- [ ] `emotion_module_v1.pth` - Trained emotion extraction model
- [ ] `dialect_module_v1.pth` - Trained dialect embedding model
- [ ] `xtts_v2_lora_finetuned/` - XTTS v2 with style conditioning LoRA
- [ ] `orchestration_v2.py` - Complete orchestration service
- [ ] `speaker_profile_manager.py` - Speaker embedding system
- [ ] `sentiment_preserving_translator.py` - Emotion-aware translation
- [ ] `session_emotion_memory.py` - Multi-turn emotion smoothing

### Documentation
- [ ] `COMPREHENSIVE_ARCHITECTURE_UPGRADE.md` ✓ (already created)
- [ ] `DETAILED_COMPONENT_SPECIFICATIONS.md` ✓ (already created)
- [ ] `EMOTION_MODULE_TRAINING_REPORT.md` (Week 2)
- [ ] `SENTIMENT_PRESERVATION_EVALUATION.md` (Week 5-6)
- [ ] `REALISM_EVALUATION_REPORT.md` (Week 11)
- [ ] `OPERATIONS_RUNBOOK.md` (Week 12)
- [ ] `API_v2_SPECIFICATION.md` (Updated Week 4)

### Infrastructure
- [ ] H100 GPU server configured
- [ ] PostgreSQL with pgvector extension
- [ ] Redis for caching
- [ ] Prometheus + Grafana monitoring
- [ ] Docker deployment images

### Validation
- [ ] 500 emotion-annotated samples dataset
- [ ] 300 dialect-annotated samples dataset
- [ ] 50+ hours Telugu speech (XTTS fine-tuning)
- [ ] 20 test conversations (human evaluation)
- [ ] Load test results (100 req/sec, <5s p99)

---

## NEXT IMMEDIATE ACTIONS (This Week)

1. **Order H100 Server** (lead time: 4-6 weeks)
   - Allocate budget
   - Coordinate with infrastructure team
   - Setup delivery & installation

2. **Recruit Annotation Team** (immediate)
   - Find 3-4 Telugu speakers (annotators)
   - Find 1 linguistics consultant
   - Prepare contracts

3. **Finalize Architecture Review** (this week)
   - Present to engineering leadership
   - Get buy-in on 16-week timeline
   - Assign team members

4. **Setup Repository** (this week)
   - Create code repository structure
   - Setup MLFlow tracking
   - Prepare development environment Docker

5. **Data Preparation** (concurrent, weeks 1-2)
   - Setup Label Studio instance
   - Prepare annotation guidelines
   - Download & license datasets

---

## GLOSSARY

- **DAU** - Daily Active Users (target: 100k)
- **SLA** - Service Level Agreement (<5 seconds latency target)
- **XTTS v2** - Coqui Text-to-Speech v2, multilingual
- **VITS** - Variational Inference Text-to-Speech
- **GST** - Global Style Tokens (prosody representation)
- **LoRA** - Low-Rank Adaptation (efficient fine-tuning)
- **ECAPA-TDNN** - Time Delay Neural Network for speaker verification
- **MFCC** - Mel-Frequency Cepstral Coefficients
- **MOS** - Mean Opinion Score (human evaluation metric)
- **EMA** - Exponential Moving Average
- **pgvector** - PostgreSQL extension for vector similarity search
- **Kappa** - Inter-rater agreement metric (Fleiss' Kappa)

---

## Document Status

**Created:** March 2026  
**Version:** 1.0  
**Status:** Ready for implementation  
**Next Update:** After Phase 1 completion  

**Approval Required From:**
- [ ] Engineering Lead
- [ ] ML Lead  
- [ ] Platform Lead
- [ ] Product Lead

