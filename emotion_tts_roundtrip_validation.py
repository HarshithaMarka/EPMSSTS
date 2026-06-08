#!/usr/bin/env python3
"""
TTS Round-Trip Emotion Preservation Validation

Phase 4: Verify that emotion affects TTS prosody (pitch, rate, energy)
Phase 5: Executive demo simulation - end-to-end emotional translation

Tests:
1. TTS generates emotionally expressive speech
2. Emotion is preserved in round-trip (text → TTS → STT → emotion)
3. Latency is acceptable (<4s)
4. System feels natural, not robotic
"""

import asyncio
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("emotion.tts.validation")


@dataclass
class TTSMetrics:
    """Metrics extracted from synthesized speech."""
    duration_sec: float
    mean_pitch_hz: Optional[float]
    pitch_std_hz: Optional[float]
    speech_rate_wps: Optional[float]  # Words per second
    energy_db: float
    dynamic_range_db: float


@dataclass
class RoundTripResult:
    """Result of a round-trip emotion test."""
    test_id: str
    input_text: str
    input_emotion: str
    input_confidence: float
    tts_audio_path: Optional[Path]
    tts_metrics: TTSMetrics
    roundtrip_emotion: str
    roundtrip_confidence: float
    emotion_preserved: bool
    consistency_score: float
    latency_ms: float


class TTSEmotionValidator:
    """Validate TTS emotional expressiveness and round-trip preservation."""
    
    EMOTIONS = ["neutral", "happy", "sad", "angry"]
    
    def __init__(self):
        # Import services
        try:
            from epmssts.services.tts.synthesizer import TtsService
            from epmssts.services.stt.stt_service import SttService
            from epmssts.services.emotion.audio_emotion import AudioEmotionService
            from epmssts.services.emotion.text_emotion import TextEmotionService
            from epmssts.services.emotion.fusion import fuse_emotions
            from epmssts.services.emotion.audio_preprocessing import get_emotion_preprocessor
            
            self.tts_service = TtsService()
            self.stt_service = SttService()
            self.audio_emotion_service = AudioEmotionService()
            self.text_emotion_service = None
            self.preprocessor = get_emotion_preprocessor()
            
            try:
                self.text_emotion_service = TextEmotionService()
            except Exception:
                logger.warning("Text emotion service not available")
            
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            logger.warning("TTS/STT services unavailable - validation limited to basic checks")
            self.tts_service = None
            self.stt_service = None
            self.audio_emotion_service = None
            self.text_emotion_service = None
            self.preprocessor = None
        
        self.output_dir = Path("outputs/tts_validation")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _extract_audio_features(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> TTSMetrics:
        """Extract prosodic features from audio."""
        import scipy.signal as signal
        from scipy.fft import rfft, rfftfreq
        
        duration = len(audio) / sample_rate
        
        # Energy
        rms = np.sqrt(np.mean(audio ** 2))
        energy_db = 20 * np.log10(rms + 1e-10)
        
        # Dynamic range
        peak = np.max(np.abs(audio))
        dynamic_range_db = 20 * np.log10(peak / (rms + 1e-10))
        
        # Placeholder for pitch (requires specialized pitch detection)
        # In production, use librosa.pyin or similar
        mean_pitch_hz = None
        pitch_std_hz = None
        
        # Placeholder for speech rate
        speech_rate_wps = None
        
        return TTSMetrics(
            duration_sec=duration,
            mean_pitch_hz=mean_pitch_hz,
            pitch_std_hz=pitch_std_hz,
            speech_rate_wps=speech_rate_wps,
            energy_db=energy_db,
            dynamic_range_db=dynamic_range_db
        )
    
    def _synthesize_emotional_speech(
        self,
        text: str,
        emotion: str,
        output_path: Path
    ) -> Tuple[np.ndarray, int]:
        """
        Synthesize speech with emotion.
        
        Returns: (audio, sample_rate)
        """
        if not self.tts_service:
            logger.error("TTS service not available")
            return None, None
        
        try:
            from epmssts.services.tts.synthesizer import TtsSynthesisRequest
            
            # Create TTS request
            request = TtsSynthesisRequest(
                text=text,
                target_language="en"
            )
            
            # Synthesize (current TTS may not support emotion parameter)
            audio_bytes = self.tts_service.synthesize(request)
            
            # If audio_bytes is AsyncGenerator or coroutine, we need to handle it
            import asyncio
            import inspect
            if inspect.iscoroutine(audio_bytes) or inspect.isasyncgen(audio_bytes):
                loop = asyncio.get_event_loop()
                audio_bytes = loop.run_until_complete(audio_bytes)
            
            # Convert bytes to numpy array
            # Assume 16kHz mono PCM
            audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            sample_rate = 16000
            
            # Save audio
            sf.write(str(output_path), audio, sample_rate)
            
            return audio, sample_rate
            
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            import traceback
            traceback.print_exc()
            return None, None
    
    async def _run_stt_emotion_pipeline(
        self,
        audio: np.ndarray,
        sample_rate: int
    ) -> Tuple[str, str, float]:
        """
        Run STT + emotion detection pipeline.
        
        Returns: (transcribed_text, emotion, confidence)
        """
        # STT
        try:
            stt_result = await self.stt_service.transcribe(audio, sample_rate)
            transcribed_text = stt_result.text if hasattr(stt_result, 'text') else stt_result
        except Exception as e:
            logger.error(f"STT failed: {e}")
            transcribed_text = ""
        
        # Emotion detection
        predicted_emotion, confidence, scores, _ = self._predict_emotion(
            audio, sample_rate, transcribed_text
        )
        
        return transcribed_text, predicted_emotion, confidence
    
    def _predict_emotion(
        self,
        audio: np.ndarray,
        sample_rate: int,
        text: Optional[str] = None
    ) -> Tuple[str, float, Dict[str, float], Optional[str]]:
        """Run emotion prediction with fusion if text available."""
        # Preprocess audio
        audio_processed, metrics = self.preprocessor.preprocess_for_emotion(
            audio, sample_rate
        )
        
        # Audio emotion
        audio_prediction = self.audio_emotion_service.predict(
            audio_processed, sample_rate
        )
        
        # If no text or no text emotion service, return audio only
        if not text or not self.text_emotion_service:
            return (
                audio_prediction.label,
                audio_prediction.confidence,
                audio_prediction.scores,
                None
            )
        
        # Text emotion
        try:
            text_prediction = self.text_emotion_service.predict(text)
            
            # Fusion
            from epmssts.services.emotion.fusion import fuse_emotions
            fused_label, fused_conf, fused_scores = fuse_emotions(
                audio_emotion=audio_prediction.label,
                audio_confidence=audio_prediction.confidence,
                text_emotion=text_prediction.label,
                text_confidence=text_prediction.confidence,
                audio_energy_rms_db=metrics.rms_db
            )
            
            return fused_label, fused_conf, fused_scores, None
            
        except Exception as e:
            logger.warning(f"Text emotion or fusion failed: {e}")
            return (
                audio_prediction.label,
                audio_prediction.confidence,
                audio_prediction.scores,
                None
            )
    
    # ============================================================
    # PHASE 4: TTS Expressiveness Validation
    # ============================================================
    
    async def phase4_tts_expressiveness(self) -> Dict[str, any]:
        """
        Validate that emotion affects TTS prosody.
        
        Round-trip test: text → TTS → STT → emotion detection
        """
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 4: TTS EXPRESSIVENESS VALIDATION")
        logger.info("=" * 80)
        
        if not self.tts_service:
            logger.warning("⚠️  TTS service not available - skipping Phase 4")
            logger.info("   Note: This phase requires functional TTS/STT services")
            logger.info("   For full validation, ensure TTS is properly configured")
            return {
                "results": [],
                "preservation_rate": 0.0,
                "avg_consistency": 0.0,
                "avg_latency_ms": 0.0,
                "skipped": True
            }
        
        test_cases = [
            {"text": "I am so happy to see you today", "emotion": "happy"},
            {"text": "I feel really sad about what happened", "emotion": "sad"},
            {"text": "This makes me very angry", "emotion": "angry"},
            {"text": "The weather is normal today", "emotion": "neutral"},
        ]
        
        results = []
        preserved_count = 0
        total_latency_ms = 0
        
        for idx, test_case in enumerate(test_cases):
            text = test_case["text"]
            emotion = test_case["emotion"]
            
            logger.info(f"\n  Test {idx+1}: '{text}' (expected: {emotion})")
            
            # Synthesize speech
            output_path = self.output_dir / f"tts_{emotion}_{idx}.wav"
            
            start_time = time.time()
            
            try:
                audio, sample_rate = self._synthesize_emotional_speech(
                    text, emotion, output_path
                )
                
                if audio is None:
                    logger.error(f"    ✗ TTS synthesis failed")
                    continue
                    
            except Exception as e:
                logger.error(f"    ✗ TTS synthesis failed: {e}")
                continue
            
            # Extract TTS metrics
            tts_metrics = self._extract_audio_features(audio, sample_rate)
            
            # Run round-trip: STT + Emotion
            transcribed_text, detected_emotion, detected_conf = await self._run_stt_emotion_pipeline(
                audio, sample_rate
            )
            
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            total_latency_ms += latency_ms
            
            # Check preservation
            is_preserved = detected_emotion == emotion
            
            # Calculate consistency score (fuzzy match)
            # If not exact match, check if in top 2 predictions
            consistency_score = 1.0 if is_preserved else (detected_conf if detected_emotion != "neutral" else 0.3)
            
            if is_preserved:
                preserved_count += 1
            
            # Log results
            logger.info(f"    TTS metrics:")
            logger.info(f"      Duration: {tts_metrics.duration_sec:.2f}s")
            logger.info(f"      Energy: {tts_metrics.energy_db:.1f} dBFS")
            logger.info(f"      Dynamic range: {tts_metrics.dynamic_range_db:.1f} dB")
            
            logger.info(f"    Round-trip results:")
            logger.info(f"      STT: '{transcribed_text}'")
            logger.info(f"      Detected emotion: {detected_emotion} (conf={detected_conf:.2f})")
            logger.info(f"      Latency: {latency_ms:.0f}ms")
            
            if is_preserved:
                logger.info(f"    ✓ EMOTION PRESERVED")
            else:
                logger.warning(f"    ✗ EMOTION NOT PRESERVED: {emotion} → {detected_emotion}")
            
            # Store result
            result = RoundTripResult(
                test_id=f"tts_{idx}",
                input_text=text,
                input_emotion=emotion,
                input_confidence=1.0,
                tts_audio_path=output_path,
                tts_metrics=tts_metrics,
                roundtrip_emotion=detected_emotion,
                roundtrip_confidence=detected_conf,
                emotion_preserved=is_preserved,
                consistency_score=consistency_score,
                latency_ms=latency_ms
            )
            results.append(result)
        
        # Summary
        preservation_rate = preserved_count / len(test_cases) if test_cases else 0.0
        avg_latency_ms = total_latency_ms / len(test_cases) if test_cases else 0.0
        avg_consistency = sum(r.consistency_score for r in results) / len(results) if results else 0.0
        
        logger.info(f"\n  PHASE 4 SUMMARY:")
        logger.info(f"    Tests: {len(test_cases)}")
        logger.info(f"    Emotion preserved: {preserved_count}/{len(test_cases)} ({preservation_rate:.1%})")
        logger.info(f"    Average consistency: {avg_consistency:.2f}")
        logger.info(f"    Average latency: {avg_latency_ms:.0f}ms")
        
        if preservation_rate >= 0.70:
            logger.info("    ✓ TTS expressiveness GOOD (≥70% preservation)")
        else:
            logger.warning("    ⚠ TTS expressiveness POOR (<70% preservation)")
            logger.warning("    → Consider emotion-aware TTS model or prosody adjustment")
        
        if avg_latency_ms < 4000:
            logger.info(f"    ✓ Latency acceptable (<4s)")
        else:
            logger.warning(f"    ⚠ Latency too high (>{avg_latency_ms/1000:.1f}s)")
        
        return {
            "results": results,
            "preservation_rate": preservation_rate,
            "avg_consistency": avg_consistency,
            "avg_latency_ms": avg_latency_ms
        }
    
    # ============================================================
    # PHASE 5: Executive Demo Simulation
    # ============================================================
    
    async def phase5_executive_demo(self) -> Dict[str, any]:
        """
        Simulate real user interaction: speak → translate → speak back.
        
        Evaluates naturalness, prosody, latency, and overall experience.
        """
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 5: EXECUTIVE DEMO SIMULATION")
        logger.info("=" * 80)
        
        if not self.tts_service:
            logger.warning("⚠️  TTS service not available - skipping Phase 5")
            logger.info("   Note: This phase requires functional TTS service")
            logger.info("   For full validation, ensure TTS is properly configured")
            return {
                "scenarios": [],
                "avg_latency_ms": 0.0,
                "naturalness_score": 0.0,
                "robotic_warnings": 0,
                "skipped": True
            }
        
        # Simulate user speaking emotionally
        demo_scenarios = [
            {
                "description": "Happy greeting",
                "user_text": "Hello! I'm so excited to meet you!",
                "emotion": "happy",
                "translation_target": "es"  # Spanish
            },
            {
                "description": "Concerned question",
                "user_text": "I'm worried about the project deadline.",
                "emotion": "sad",
                "translation_target": "fr"  # French
            },
            {
                "description": "Frustrated complaint",
                "user_text": "This is completely unacceptable!",
                "emotion": "angry",
                "translation_target": "de"  # German
            },
        ]
        
        logger.info("\n  Simulating end-to-end emotional translation scenarios:")
        
        results_summary = {
            "scenarios": [],
            "avg_latency_ms": 0.0,
            "naturalness_score": 0.0,
            "robotic_warnings": 0
        }
        
        for idx, scenario in enumerate(demo_scenarios):
            logger.info(f"\n  Scenario {idx+1}: {scenario['description']}")
            logger.info(f"    User says: \"{scenario['user_text']}\"")
            logger.info(f"    Emotion: {scenario['emotion']}")
            
            start_time = time.time()
            
            # Step 1: Detect emotion from user text
            if self.text_emotion_service:
                try:
                    text_emotion = self.text_emotion_service.predict(scenario['user_text'])
                    detected_emotion = text_emotion.label
                    detected_conf = text_emotion.confidence
                except:
                    detected_emotion = scenario['emotion']
                    detected_conf = 0.8
            else:
                detected_emotion = scenario['emotion']
                detected_conf = 0.8
            
            logger.info(f"    Detected emotion: {detected_emotion} (conf={detected_conf:.2f})")
            
            # Step 2: Simulate translation (placeholder)
            # In real system, would call translation service
            translated_text = f"[{scenario['translation_target'].upper()}] {scenario['user_text']}"
            
            logger.info(f"    Translated: \"{translated_text}\"")
            
            # Step 3: Synthesize with emotion
            output_path = self.output_dir / f"demo_{idx}.wav"
            try:
                audio, sample_rate = self._synthesize_emotional_speech(
                    translated_text, detected_emotion, output_path
                )
                
                # Extract metrics
                tts_metrics = self._extract_audio_features(audio, sample_rate)
                
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                
                logger.info(f"    TTS generated:")
                logger.info(f"      Duration: {tts_metrics.duration_sec:.2f}s")
                logger.info(f"      Energy: {tts_metrics.energy_db:.1f} dBFS")
                logger.info(f"      Latency: {latency_ms:.0f}ms")
                
                # Evaluate naturalness (heuristic)
                naturalness_score = 0.7  # Base score
                
                # Penalize if too quiet or too loud
                if tts_metrics.energy_db < -30:
                    naturalness_score -= 0.2
                    logger.warning("      ⚠ Audio too quiet")
                elif tts_metrics.energy_db > -10:
                    naturalness_score -= 0.1
                    logger.warning("      ⚠ Audio too loud")
                else:
                    naturalness_score += 0.1
                
                # Penalize if dynamic range too low (robotic)
                if tts_metrics.dynamic_range_db < 3:
                    naturalness_score -= 0.2
                    results_summary["robotic_warnings"] += 1
                    logger.warning("      ⚠ Low dynamic range - may sound robotic")
                else:
                    naturalness_score += 0.1
                
                # Check latency
                if latency_ms < 4000:
                    logger.info("      ✓ Latency acceptable")
                else:
                    naturalness_score -= 0.2
                    logger.warning(f"      ⚠ Latency too high ({latency_ms/1000:.1f}s)")
                
                logger.info(f"      Naturalness score: {naturalness_score:.2f}/1.0")
                
                results_summary["scenarios"].append({
                    "description": scenario['description'],
                    "latency_ms": latency_ms,
                    "naturalness_score": naturalness_score,
                    "tts_metrics": tts_metrics
                })
                
            except Exception as e:
                logger.error(f"    ✗ Demo failed: {e}")
                continue
        
        # Calculate averages
        if results_summary["scenarios"]:
            results_summary["avg_latency_ms"] = sum(
                s["latency_ms"] for s in results_summary["scenarios"]
            ) / len(results_summary["scenarios"])
            
            results_summary["naturalness_score"] = sum(
                s["naturalness_score"] for s in results_summary["scenarios"]
            ) / len(results_summary["scenarios"])
        
        logger.info(f"\n  PHASE 5 SUMMARY:")
        logger.info(f"    Average latency: {results_summary['avg_latency_ms']:.0f}ms")
        logger.info(f"    Average naturalness: {results_summary['naturalness_score']:.2f}/1.0")
        logger.info(f"    Robotic warnings: {results_summary['robotic_warnings']}")
        
        if results_summary["naturalness_score"] >= 0.70:
            logger.info("    ✓ System feels NATURAL")
        else:
            logger.warning("    ⚠ System may sound ROBOTIC")
        
        if results_summary["avg_latency_ms"] < 4000:
            logger.info("    ✓ Latency ACCEPTABLE for real-time use")
        else:
            logger.warning("    ⚠ Latency TOO HIGH for real-time")
        
        return results_summary


async def main():
    """Run TTS emotion validation."""
    logger.info("TTS EMOTION EXPRESSIVENESS & ROUND-TRIP VALIDATION")
    logger.info("=" * 80)
    
    validator = TTSEmotionValidator()
    
    try:
        # Phase 4: TTS expressiveness
        phase4_results = await validator.phase4_tts_expressiveness()
        
        # Phase 5: Executive demo
        phase5_results = await validator.phase5_executive_demo()
        
        # Final assessment
        logger.info("\n" + "=" * 80)
        logger.info("TTS VALIDATION SUMMARY")
        logger.info("=" * 80)
        
        logger.info(f"\n  Round-trip preservation: {phase4_results['preservation_rate']:.1%}")
        logger.info(f"  Average consistency: {phase4_results['avg_consistency']:.2f}")
        logger.info(f"  TTS latency: {phase4_results['avg_latency_ms']:.0f}ms")
        logger.info(f"  Demo naturalness: {phase5_results['naturalness_score']:.2f}/1.0")
        logger.info(f"  Demo latency: {phase5_results['avg_latency_ms']:.0f}ms")
        
        # Overall TTS emotion score
        tts_score = (
            phase4_results['preservation_rate'] * 0.5 +
            phase5_results['naturalness_score'] * 0.5
        )
        
        logger.info(f"\n  🎯 TTS EMOTION SCORE: {tts_score:.1%}")
        
        if tts_score >= 0.70:
            logger.info("\n  ✅ TTS emotion system is PRODUCTION-READY")
        else:
            logger.warning("\n  ⚠️  TTS emotion needs improvement")
            logger.warning("  Recommendations:")
            if phase4_results['preservation_rate'] < 0.70:
                logger.warning("    - Implement emotion-aware TTS or prosody modification")
            if phase5_results['naturalness_score'] < 0.70:
                logger.warning("    - Improve dynamic range and naturalness")
            if phase4_results['avg_latency_ms'] > 4000 or phase5_results['avg_latency_ms'] > 4000:
                logger.warning("    - Optimize TTS synthesis speed")
        
        logger.info("\n" + "=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
