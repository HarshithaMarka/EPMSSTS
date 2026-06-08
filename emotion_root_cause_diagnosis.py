"""
Emotion Model Root Cause Diagnosis

Comprehensive diagnostic tool to identify why the emotion model
is producing "sad" for nearly all inputs.

This script performs systematic analysis of:
1. Raw model logits and probabilities
2. Label mapping verification
3. Data normalization effects
4. Feature variance analysis
5. Model configuration
6. Class imbalance indicators
7. Post-processing logic
8. Controlled test cases
"""

import sys
import json
import numpy as np
import torch
from pathlib import Path
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from epmssts.services.emotion.audio_emotion import AudioEmotionService, EMOTIONS


class EmotionDiagnostics:
    """Comprehensive emotion model diagnostics"""
    
    def __init__(self):
        self.service = AudioEmotionService()
        self.report = {
            "raw_logits_issue": False,
            "label_mapping_issue": False,
            "normalization_issue": False,
            "feature_collapse": False,
            "fusion_bias": False,
            "class_imbalance": False,
            "postprocessing_override": False,
            "root_cause": None,
            "recommended_fix": None,
            "detailed_findings": {}
        }
    
    def run_full_diagnosis(self):
        """Execute complete diagnostic suite"""
        print("=" * 80)
        print("EMOTION MODEL ROOT CAUSE DIAGNOSIS")
        print("=" * 80)
        print()
        
        # Step 1: Verify raw model output
        print("🔎 STEP 1 — VERIFY RAW MODEL OUTPUT")
        print("-" * 80)
        self.check_raw_model_output()
        print()
        
        # Step 2: Verify label mapping
        print("🔎 STEP 2 — VERIFY LABEL MAPPING")
        print("-" * 80)
        self.check_label_mapping()
        print()
        
        # Step 3: Check data normalization
        print("🔎 STEP 3 — CHECK DATA NORMALIZATION")
        print("-" * 80)
        self.check_normalization()
        print()
        
        # Step 4: Check feature variance
        print("🔎 STEP 4 — CHECK FEATURE VARIANCE")
        print("-" * 80)
        self.check_feature_variance()
        print()
        
        # Step 5: Check model mode
        print("🔎 STEP 5 — CHECK MODEL MODE")
        print("-" * 80)
        self.check_model_mode()
        print()
        
        # Step 6: Check class imbalance
        print("🔎 STEP 6 — CHECK CLASS IMBALANCE")
        print("-" * 80)
        self.check_class_imbalance()
        print()
        
        # Step 7: Check post-processing logic
        print("🔎 STEP 8 — CHECK THRESHOLD LOGIC")
        print("-" * 80)
        self.check_postprocessing_logic()
        print()
        
        # Step 9: Run controlled tests
        print("🔎 STEP 9 — RUN CONTROL TEST")
        print("-" * 80)
        self.run_controlled_tests()
        print()
        
        # Generate final report
        print("🔎 STEP 10 — DIAGNOSTIC REPORT")
        print("=" * 80)
        self.generate_report()
        
        return self.report
    
    def check_raw_model_output(self):
        """Step 1: Verify raw logits and probabilities"""
        print("Testing 10 different synthetic audio inputs...")
        print()
        
        test_cases = [
            ("Happy - High pitch, high energy", self.generate_happy_audio()),
            ("Angry - High energy, harsh", self.generate_angry_audio()),
            ("Neutral - Flat tone", self.generate_neutral_audio()),
            ("Sad - Low energy, low pitch", self.generate_sad_audio()),
            ("Loud - High amplitude", self.generate_loud_audio()),
            ("Whisper - Low amplitude", self.generate_whisper_audio()),
            ("Very high pitch", self.generate_high_pitch_audio()),
            ("Very low pitch", self.generate_low_pitch_audio()),
            ("Noisy", self.generate_noisy_audio()),
            ("Monotone", self.generate_monotone_audio()),
        ]
        
        all_outputs = []
        
        for i, (desc, audio) in enumerate(test_cases, 1):
            print(f"\nTest {i}: {desc}")
            print("-" * 60)
            
            # Get raw model outputs
            output = self.get_raw_model_output(audio)
            all_outputs.append(output)
            
            print(f"  Logits:       {self.format_array(output['logits'])}")
            print(f"  Probs:        {self.format_probs(output['raw_probabilities'])}")
            print(f"  Predicted:    {output['predicted_label']} (index: {output['predicted_index']})")
            print(f"  Confidence:   {output['confidence']:.4f}")
            print(f"  Final result: {output['final_label']} @ {output['final_confidence']:.4f}")
        
        # Analyze patterns
        print("\n" + "=" * 60)
        print("ANALYSIS:")
        print("-" * 60)
        
        # Check if logits are nearly identical
        logits_array = np.array([o['logits'] for o in all_outputs])
        logits_std = np.std(logits_array, axis=0)
        print(f"Logits std dev across inputs: {self.format_array(logits_std)}")
        
        if np.max(logits_std) < 0.5:
            print("⚠️  WARNING: Logits have very low variance - model may not be learning")
            self.report['raw_logits_issue'] = True
        
        # Check if one class is always highest
        predicted_labels = [o['predicted_label'] for o in all_outputs]
        label_counts = {label: predicted_labels.count(label) for label in set(predicted_labels)}
        print(f"\nPrediction distribution: {label_counts}")
        
        max_count = max(label_counts.values())
        if max_count >= 8:  # 80% or more
            dominant_label = [k for k, v in label_counts.items() if v == max_count][0]
            print(f"⚠️  WARNING: '{dominant_label}' predicted {max_count}/10 times (collapsed distribution)")
            self.report['raw_logits_issue'] = True
        
        # Check final results after post-processing
        final_labels = [o['final_label'] for o in all_outputs]
        final_counts = {label: final_labels.count(label) for label in set(final_labels)}
        print(f"Final distribution:      {final_counts}")
        
        if final_counts.get('sad', 0) >= 8:
            print(f"🚨 CRITICAL: 'sad' appears {final_counts['sad']}/10 times in final output")
            print("   This confirms the production issue!")
        
        self.report['detailed_findings']['raw_outputs'] = all_outputs
    
    def check_label_mapping(self):
        """Step 2: Verify label mapping is correct"""
        print("Checking model label configuration...")
        print()
        
        model = self.service._model
        
        if model is None:
            print("❌ Model not loaded")
            return
        
        # Get model's id2label mapping
        id2label = self.service._model_id2label
        label2emotion = self.service._label2emotion
        
        print(f"Model config id2label: {id2label}")
        print(f"Label to emotion map:  {label2emotion}")
        print(f"Target emotions:       {EMOTIONS}")
        print()
        
        # Verify mapping
        print("Mapping verification:")
        for idx, label in id2label.items():
            emotion = label2emotion.get(label, "UNMAPPED")
            print(f"  Index {idx} → '{label}' → '{emotion}'")
            
            # Check for issues
            if idx == 0 and emotion == "sad":
                print(f"    ⚠️  Index 0 maps to 'sad' - could cause bias if model defaults to 0")
        
        # Check if label order matches model training
        print("\n🔍 Checking if labels might be misaligned...")
        if 2 in id2label and id2label[2].lower() in ['sad', 'sad']:
            print("  ℹ️  'sad' is at index 2 in this model")
        if 0 in id2label and id2label[0].lower() == 'neu':
            print("  ℹ️  'neutral' is at index 0")
        
        self.report['detailed_findings']['label_mapping'] = {
            'id2label': id2label,
            'label2emotion': label2emotion
        }
    
    def check_normalization(self):
        """Step 3: Check data normalization effects"""
        print("Testing audio normalization impact...")
        print()
        
        # Create audio with different energy levels
        base_audio = self.generate_happy_audio()
        
        test_variants = [
            ("Original", base_audio),
            ("10x quieter", base_audio * 0.1),
            ("100x quieter", base_audio * 0.01),
            ("10x louder", np.clip(base_audio * 10, -1, 1)),
            ("Half amplitude", base_audio * 0.5),
        ]
        
        print("Testing same audio at different volumes:")
        print("-" * 60)
        
        results = []
        for desc, audio in test_variants:
            rms = np.sqrt(np.mean(np.square(audio)))
            rms_db = 20 * np.log10(rms + 1e-10)
            
            # Get features before and after preprocessing
            if self.service._preprocessor:
                audio_proc, metrics = self.service._preprocessor.preprocess_for_emotion(audio, 16000)
                rms_after = np.sqrt(np.mean(np.square(audio_proc)))
                rms_db_after = 20 * np.log10(rms_after + 1e-10)
            else:
                audio_proc = audio
                rms_db_after = rms_db
                metrics = None
            
            output = self.get_raw_model_output(audio)
            
            print(f"\n{desc}:")
            print(f"  RMS before: {rms_db:.2f} dB")
            if metrics:
                print(f"  RMS after:  {rms_db_after:.2f} dB (energy_band: {metrics.energy_band})")
            print(f"  Predicted:  {output['predicted_label']} @ {output['confidence']:.3f}")
            print(f"  Final:      {output['final_label']} @ {output['final_confidence']:.3f}")
            
            results.append({
                'desc': desc,
                'rms_before': rms_db,
                'rms_after': rms_db_after,
                'predicted': output['predicted_label'],
                'final': output['final_label']
            })
        
        # Check if all normalized to same distribution
        final_labels = [r['final'] for r in results]
        if len(set(final_labels)) == 1:
            print(f"\n⚠️  All variants produced same emotion: '{final_labels[0]}'")
            print("   Normalization may be destroying emotional variation")
            self.report['normalization_issue'] = True
        else:
            print(f"\n✓ Normalization preserves some variation")
        
        self.report['detailed_findings']['normalization'] = results
    
    def check_feature_variance(self):
        """Step 4: Check feature variance across emotions"""
        print("Computing feature embeddings for different emotions...")
        print()
        
        test_cases = [
            ("Happy", self.generate_happy_audio()),
            ("Angry", self.generate_angry_audio()),
            ("Neutral", self.generate_neutral_audio()),
            ("Sad", self.generate_sad_audio()),
            ("Loud", self.generate_loud_audio()),
        ]
        
        # Extract features before final classifier
        embeddings = []
        
        for desc, audio in test_cases:
            # Get model features
            if self.service._extractor and self.service._model:
                inputs = self.service._extractor(
                    audio, sampling_rate=16000, return_tensors="pt"
                )
                inputs = {k: v.to(self.service._device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    # Get hidden states (features before classifier)
                    outputs = self.service._model(**inputs, output_hidden_states=True)
                    # Use last hidden state as embedding
                    embedding = outputs.hidden_states[-1].mean(dim=1).cpu().numpy()[0]
                
                embeddings.append((desc, embedding))
                print(f"{desc:10s}: embedding shape {embedding.shape}, mean={np.mean(embedding):.4f}, std={np.std(embedding):.4f}")
        
        # Compute cosine similarities
        print("\nCosine similarities between embeddings:")
        print("-" * 60)
        
        for i in range(len(embeddings)):
            for j in range(i+1, len(embeddings)):
                desc1, emb1 = embeddings[i]
                desc2, emb2 = embeddings[j]
                
                # Cosine similarity
                similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
                print(f"  {desc1:10s} vs {desc2:10s}: {similarity:.4f}")
                
                if similarity > 0.95:
                    print(f"    ⚠️  Very high similarity - features may be collapsed")
                    self.report['feature_collapse'] = True
        
        self.report['detailed_findings']['feature_analysis'] = {
            'embeddings_computed': len(embeddings)
        }
    
    def check_model_mode(self):
        """Step 5: Verify model is in eval mode"""
        print("Checking model configuration...")
        print()
        
        model = self.service._model
        
        if model is None:
            print("❌ Model not loaded")
            return
        
        is_training = model.training
        print(f"Model training mode: {is_training}")
        
        if is_training:
            print("⚠️  WARNING: Model is in training mode! Should be eval()")
            self.report['detailed_findings']['model_mode_issue'] = True
        else:
            print("✓ Model is in eval mode")
        
        # Check device
        device = next(model.parameters()).device
        print(f"Model device:        {device}")
        print(f"Service device:      {self.service._device}")
        
        # Check if model has expected architecture
        print(f"\nModel type:          {type(model).__name__}")
        print(f"Number of labels:    {model.config.num_labels}")
        
        self.report['detailed_findings']['model_config'] = {
            'training_mode': is_training,
            'device': str(device),
            'num_labels': model.config.num_labels
        }
    
    def check_class_imbalance(self):
        """Step 6: Check for class imbalance indicators"""
        print("Checking model for class imbalance indicators...")
        print()
        
        model = self.service._model
        
        if model is None:
            print("❌ Model not loaded")
            return
        
        # Get final layer weights and biases
        classifier = model.classifier
        
        print(f"Classifier layer: {classifier}")
        
        # Get weights and biases
        weight = classifier.weight.detach().cpu().numpy()
        bias = classifier.bias.detach().cpu().numpy()
        
        print(f"\nClassifier weight shape: {weight.shape}")
        print(f"Classifier bias shape:   {bias.shape}")
        print()
        
        # Print bias values per class
        print("Final layer biases:")
        id2label = self.service._model_id2label
        
        for idx in range(len(bias)):
            label = id2label.get(idx, f"class_{idx}")
            emotion = self.service._label2emotion.get(label, label)
            print(f"  {emotion:10s} (idx {idx}): bias = {bias[idx]:.4f}")
        
        # Check for large bias differences
        bias_range = np.max(bias) - np.min(bias)
        print(f"\nBias range: {bias_range:.4f}")
        
        if bias_range > 2.0:
            max_idx = np.argmax(bias)
            max_label = id2label.get(max_idx, f"class_{max_idx}")
            max_emotion = self.service._label2emotion.get(max_label, max_label)
            print(f"⚠️  Large bias range detected")
            print(f"   Class '{max_emotion}' has highest bias ({bias[max_idx]:.4f})")
            print(f"   This may indicate training imbalance")
            self.report['class_imbalance'] = True
        
        # Check weight magnitudes
        print("\nWeight magnitudes (L2 norm) per class:")
        for idx in range(weight.shape[0]):
            label = id2label.get(idx, f"class_{idx}")
            emotion = self.service._label2emotion.get(label, label)
            magnitude = np.linalg.norm(weight[idx])
            print(f"  {emotion:10s}: {magnitude:.4f}")
        
        self.report['detailed_findings']['class_weights'] = {
            'biases': {self.service._label2emotion.get(id2label.get(i, f"class_{i}"), f"class_{i}"): float(b) 
                      for i, b in enumerate(bias)},
            'weight_shapes': str(weight.shape)
        }
    
    def check_postprocessing_logic(self):
        """Step 8: Check for post-processing overrides"""
        print("Analyzing post-processing logic...")
        print()
        
        # Read the audio_emotion.py source to check for overrides
        source_file = Path(__file__).parent / "epmssts" / "services" / "emotion" / "audio_emotion.py"
        
        if not source_file.exists():
            print("⚠️  Cannot locate source file")
            return
        
        with open(source_file, 'r') as f:
            source = f.read()
        
        # Look for suspicious patterns
        suspicious_patterns = [
            'override',
            'force',
            'if.*confidence.*<.*threshold',
            'if.*energy.*low.*sad',
            'label.*=.*"sad"',
            'return.*"sad"',
        ]
        
        print("Checking for hard-coded overrides...")
        found_issues = []
        
        for pattern in suspicious_patterns:
            if pattern in source.lower():
                print(f"  ⚠️  Found pattern: '{pattern}'")
                found_issues.append(pattern)
        
        # Check for confidence scaling
        if '_apply_confidence_scaling' in source:
            print("\n✓ Found _apply_confidence_scaling method")
            print("  This method modifies emotion scores based on audio metrics")
            print("  Checking if it's biasing toward 'sad'...")
            
            # Look for sad-specific scaling
            if 'scaled["sad"]' in source or "scaled['sad']" in source:
                print("  ⚠️  Method explicitly modifies 'sad' confidence")
                print("  This could be causing the bias if logic is incorrect")
                found_issues.append('sad confidence scaling')
        
        if found_issues:
            print(f"\n⚠️  Found {len(found_issues)} potential post-processing issues")
            self.report['postprocessing_override'] = True
        else:
            print("\n✓ No obvious hard-coded overrides found")
        
        self.report['detailed_findings']['postprocessing_checks'] = found_issues
    
    def run_controlled_tests(self):
        """Step 9: Run controlled synthetic tests"""
        print("Running controlled synthetic audio tests...")
        print()
        
        test_cases = [
            ("High pitch + high energy (should be happy)", 
             self.generate_synthetic_emotion(freq=600, amp=0.5, modulation=0.2)),
            ("High energy + harsh tone (should be angry)", 
             self.generate_synthetic_emotion(freq=300, amp=0.7, modulation=0.4)),
            ("Flat tone (should be neutral)", 
             self.generate_synthetic_emotion(freq=200, amp=0.3, modulation=0.0)),
            ("Low energy + low pitch (should be sad)", 
             self.generate_synthetic_emotion(freq=150, amp=0.2, modulation=0.05)),
        ]
        
        results = []
        for desc, audio in test_cases:
            prediction = self.service.predict(audio, 16000)
            results.append({
                'desc': desc,
                'predicted': prediction.label,
                'confidence': prediction.confidence,
                'scores': prediction.scores
            })
            
            print(f"\n{desc}:")
            print(f"  Predicted: {prediction.label} @ {prediction.confidence:.3f}")
            print(f"  Scores: {self.format_probs(prediction.scores)}")
        
        # Check if model differentiates
        predicted_labels = [r['predicted'] for r in results]
        unique_labels = len(set(predicted_labels))
        
        print(f"\n{'='*60}")
        print(f"Model predicted {unique_labels} different emotion(s)")
        
        if unique_labels == 1:
            print(f"⚠️  WARNING: Model outputs same emotion '{predicted_labels[0]}' for all inputs")
            print("   Model is NOT learning to differentiate emotions")
            self.report['feature_collapse'] = True
        elif unique_labels == 2:
            print("⚠️  WARNING: Model only differentiates 2 emotions (limited discrimination)")
        else:
            print("✓ Model shows some differentiation")
        
        self.report['detailed_findings']['controlled_tests'] = results
    
    def generate_report(self):
        """Generate final diagnostic report"""
        print("\n" + "=" * 80)
        print("DIAGNOSTIC REPORT")
        print("=" * 80)
        print()
        
        # Analyze findings
        issues_found = []
        
        if self.report['raw_logits_issue']:
            issues_found.append("Raw logits show collapsed distribution")
        if self.report['label_mapping_issue']:
            issues_found.append("Label mapping misconfiguration")
        if self.report['normalization_issue']:
            issues_found.append("Normalization destroying emotional variation")
        if self.report['feature_collapse']:
            issues_found.append("Feature embeddings are too similar")
        if self.report['class_imbalance']:
            issues_found.append("Model biases suggest class imbalance in training")
        if self.report['postprocessing_override']:
            issues_found.append("Post-processing logic may be forcing 'sad'")
        
        print("ISSUES DETECTED:")
        if issues_found:
            for issue in issues_found:
                print(f"  ❌ {issue}")
        else:
            print("  ✓ No critical issues detected")
        
        print()
        
        # Determine root cause
        if self.report['postprocessing_override']:
            self.report['root_cause'] = (
                "Post-processing confidence scaling logic is incorrectly biasing toward 'sad'. "
                "The _apply_confidence_scaling method modifies sad confidence based on audio metrics, "
                "and the logic appears to be increasing sad scores inappropriately."
            )
            self.report['recommended_fix'] = (
                "Review and fix _apply_confidence_scaling logic in audio_emotion.py. "
                "The method should preserve model predictions unless there's strong evidence "
                "of misclassification. Consider removing or reducing sad-specific adjustments."
            )
        elif self.report['feature_collapse']:
            self.report['root_cause'] = (
                "Model feature embeddings are too similar across different emotions. "
                "The model is not learning discriminative features for emotion classification."
            )
            self.report['recommended_fix'] = (
                "Model needs retraining with better data augmentation or different architecture. "
                "Current model may have been trained on imbalanced or low-quality data."
            )
        elif self.report['class_imbalance']:
            self.report['root_cause'] = (
                "Model has high bias toward one class, likely due to training data imbalance. "
                "The final layer biases show significant class preference."
            )
            self.report['recommended_fix'] = (
                "Retrain model with class-balanced data or apply post-training bias correction."
            )
        elif self.report['normalization_issue']:
            self.report['root_cause'] = (
                "Audio normalization is collapsing all inputs to similar distributions, "
                "making it impossible for the model to differentiate emotions."
            )
            self.report['recommended_fix'] = (
                "Adjust normalization strategy to preserve emotional characteristics. "
                "Consider using percentile normalization or energy-preserving methods."
            )
        else:
            self.report['root_cause'] = "Unable to determine definitive root cause from available diagnostics."
            self.report['recommended_fix'] = "Requires deeper investigation with actual production audio samples."
        
        print("ROOT CAUSE:")
        print(f"  {self.report['root_cause']}")
        print()
        
        print("RECOMMENDED FIX:")
        print(f"  {self.report['recommended_fix']}")
        print()
        
        # Save detailed report
        report_file = Path(__file__).parent / "emotion_diagnosis_report.json"
        with open(report_file, 'w') as f:
            # Convert numpy types to python types for JSON serialization
            json.dump(self.report, f, indent=2, default=str)
        
        print(f"Detailed report saved to: {report_file}")
        print()
        
        return self.report
    
    # Helper methods for generating synthetic audio
    
    def generate_happy_audio(self) -> np.ndarray:
        """Generate synthetic happy-sounding audio"""
        duration = 1.0
        sr = 16000
        t = np.linspace(0, duration, int(sr * duration))
        
        # High pitch with modulation (cheerful)
        freq = 300
        audio = np.sin(2 * np.pi * freq * t)
        # Add vibrato
        vibrato = 0.1 * np.sin(2 * np.pi * 5 * t)
        audio = audio * (1 + vibrato)
        audio = audio * 0.5
        
        return audio.astype(np.float32)
    
    def generate_angry_audio(self) -> np.ndarray:
        """Generate synthetic angry-sounding audio"""
        duration = 1.0
        sr = 16000
        t = np.linspace(0, duration, int(sr * duration))
        
        # Mid-low pitch with harsh harmonics
        freq = 200
        audio = np.sin(2 * np.pi * freq * t)
        # Add harsh harmonics
        audio += 0.3 * np.sin(2 * np.pi * freq * 2 * t)
        audio += 0.2 * np.sin(2 * np.pi * freq * 3 * t)
        # High energy
        audio = audio * 0.7
        
        return audio.astype(np.float32)
    
    def generate_neutral_audio(self) -> np.ndarray:
        """Generate synthetic neutral-sounding audio"""
        duration = 1.0
        sr = 16000
        t = np.linspace(0, duration, int(sr * duration))
        
        # Flat, monotone
        freq = 220
        audio = np.sin(2 * np.pi * freq * t)
        audio = audio * 0.4
        
        return audio.astype(np.float32)
    
    def generate_sad_audio(self) -> np.ndarray:
        """Generate synthetic sad-sounding audio"""
        duration = 1.0
        sr = 16000
        t = np.linspace(0, duration, int(sr * duration))
        
        # Low pitch, low energy, descending
        freq_start = 180
        freq_end = 150
        freq = freq_start + (freq_end - freq_start) * t / duration
        audio = np.sin(2 * np.pi * freq * t)
        # Low energy
        audio = audio * 0.2
        
        return audio.astype(np.float32)
    
    def generate_loud_audio(self) -> np.ndarray:
        """Generate loud audio"""
        duration = 1.0
        sr = 16000
        t = np.linspace(0, duration, int(sr * duration))
        
        freq = 250
        audio = np.sin(2 * np.pi * freq * t)
        audio = audio * 0.9
        
        return audio.astype(np.float32)
    
    def generate_whisper_audio(self) -> np.ndarray:
        """Generate whisper-like audio"""
        duration = 1.0
        sr = 16000
        t = np.linspace(0, duration, int(sr * duration))
        
        # Very low amplitude
        freq = 250
        audio = np.sin(2 * np.pi * freq * t)
        audio = audio * 0.05
        
        return audio.astype(np.float32)
    
    def generate_high_pitch_audio(self) -> np.ndarray:
        """Generate very high pitch audio"""
        duration = 1.0
        sr = 16000
        t = np.linspace(0, duration, int(sr * duration))
        
        freq = 800
        audio = np.sin(2 * np.pi * freq * t)
        audio = audio * 0.4
        
        return audio.astype(np.float32)
    
    def generate_low_pitch_audio(self) -> np.ndarray:
        """Generate very low pitch audio"""
        duration = 1.0
        sr = 16000
        t = np.linspace(0, duration, int(sr * duration))
        
        freq = 100
        audio = np.sin(2 * np.pi * freq * t)
        audio = audio * 0.4
        
        return audio.astype(np.float32)
    
    def generate_noisy_audio(self) -> np.ndarray:
        """Generate noisy audio"""
        duration = 1.0
        sr = 16000
        
        # White noise
        audio = np.random.randn(int(sr * duration)) * 0.1
        
        # Add some tonal component
        t = np.linspace(0, duration, int(sr * duration))
        audio += 0.3 * np.sin(2 * np.pi * 200 * t)
        
        return audio.astype(np.float32)
    
    def generate_monotone_audio(self) -> np.ndarray:
        """Generate perfectly monotone audio"""
        duration = 1.0
        sr = 16000
        t = np.linspace(0, duration, int(sr * duration))
        
        freq = 200
        audio = np.sin(2 * np.pi * freq * t)
        audio = audio * 0.3
        
        return audio.astype(np.float32)
    
    def generate_synthetic_emotion(self, freq: float, amp: float, modulation: float) -> np.ndarray:
        """Generate synthetic audio with specified characteristics"""
        duration = 1.0
        sr = 16000
        t = np.linspace(0, duration, int(sr * duration))
        
        audio = np.sin(2 * np.pi * freq * t)
        
        if modulation > 0:
            mod = modulation * np.sin(2 * np.pi * 4 * t)
            audio = audio * (1 + mod)
        
        audio = audio * amp
        
        return audio.astype(np.float32)
    
    def get_raw_model_output(self, audio: np.ndarray) -> Dict:
        """Get raw model output including logits"""
        sr = 16000
        
        # Preprocess if available
        if self.service._preprocessor:
            audio_proc, metrics = self.service._preprocessor.preprocess_for_emotion(audio, sr)
        else:
            audio_proc = audio
            metrics = None
        
        # Get model inputs
        inputs = self.service._extractor(
            audio_proc, sampling_rate=sr, return_tensors="pt"
        )
        inputs = {k: v.to(self.service._device) for k, v in inputs.items()}
        
        # Get raw logits
        with torch.no_grad():
            logits = self.service._model(**inputs).logits
        
        logits_np = logits.cpu().numpy()[0]
        
        # Softmax
        probs = torch.nn.functional.softmax(logits, dim=-1)[0].cpu().numpy()
        
        # Get predicted index and label
        predicted_idx = int(np.argmax(probs))
        raw_label = self.service._model_id2label[predicted_idx]
        predicted_label = self.service._label2emotion.get(raw_label, raw_label)
        confidence = float(probs[predicted_idx])
        
        # Map to canonical emotions
        canonical_scores = {e: 0.0 for e in EMOTIONS}
        for idx, prob in enumerate(probs):
            raw_label = self.service._model_id2label[int(idx)]
            emotion = self.service._label2emotion.get(raw_label, "neutral")
            canonical_scores[emotion] += float(prob)
        
        # Get final prediction after post-processing
        final_pred = self.service.predict(audio, sr)
        
        return {
            'logits': logits_np.tolist(),
            'raw_probabilities': {self.service._model_id2label[i]: float(p) for i, p in enumerate(probs)},
            'predicted_index': predicted_idx,
            'predicted_label': predicted_label,
            'confidence': confidence,
            'canonical_scores': canonical_scores,
            'final_label': final_pred.label,
            'final_confidence': final_pred.confidence,
            'final_scores': final_pred.scores,
            'audio_metrics': metrics.to_dict() if metrics else None
        }
    
    @staticmethod
    def format_array(arr):
        """Format numpy array for display"""
        if isinstance(arr, (list, tuple)):
            arr = np.array(arr)
        return '[' + ', '.join([f'{x:.3f}' for x in arr]) + ']'
    
    @staticmethod
    def format_probs(probs_dict):
        """Format probability dictionary for display"""
        return '{' + ', '.join([f'{k}: {v:.3f}' for k, v in probs_dict.items()]) + '}'


def main():
    """Run full diagnostic suite"""
    diagnostics = EmotionDiagnostics()
    report = diagnostics.run_full_diagnosis()
    
    print()
    print("=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)
    
    return report


if __name__ == "__main__":
    main()
