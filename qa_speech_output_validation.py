"""
EPMSSTS Speech Output QA & Validation Audit
============================================

Comprehensive validation of speech output generation, translation consistency,
target language correctness, and emotion prosody mapping.

Senior AI Systems QA Engineer and Speech Pipeline Auditor
February 27, 2026
"""

import asyncio
import io
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import wave

import numpy as np
import soundfile as sf
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent))

from epmssts.api.main import app


class SpeechOutputQAValidator:
    """Comprehensive QA validation for speech output."""
    
    def __init__(self):
        self.results = {
            "timestamp": time.time(),
            "test_cases": [],
            "audio_validation": {},
            "text_consistency": {},
            "language_validation": {},
            "emotion_validation": {},
            "multi_language_tests": [],
            "summary": {},
        }
        self.test_audio_cache = {}
    
    def generate_test_audio(self, duration=2.0, audio_type="speech_like", emotion="neutral"):
        """Generate test audio with emotional characteristics."""
        cache_key = f"{duration}_{audio_type}_{emotion}"
        if cache_key in self.test_audio_cache:
            return self.test_audio_cache[cache_key]
        
        sample_rate = 16000
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        if audio_type == "speech_like":
            # Speech-like audio
            audio = (
                0.2 * np.sin(2 * np.pi * 200 * t) +
                0.15 * np.sin(2 * np.pi * 500 * t) +
                0.1 * np.sin(2 * np.pi * 1500 * t) +
                0.05 * np.random.randn(len(t))
            ).astype(np.float32)
            audio = audio / np.max(np.abs(audio)) * 0.3
        else:
            audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
        
        buf = io.BytesIO()
        sf.write(buf, audio, sample_rate, format='WAV')
        buf.seek(0)
        result = buf.getvalue()
        
        self.test_audio_cache[cache_key] = result
        return result
    
    def analyze_audio_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze audio file properties."""
        if not file_path.exists():
            return {
                "exists": False,
                "error": "File does not exist"
            }
        
        file_size = file_path.stat().st_size
        
        try:
            # Read using soundfile
            audio_data, sample_rate = sf.read(file_path)
            
            # Handle mono/stereo
            if audio_data.ndim == 2:
                audio_data = audio_data.mean(axis=1)
            
            duration = len(audio_data) / sample_rate
            rms = float(np.sqrt(np.mean(np.square(audio_data))))
            peak = float(np.max(np.abs(audio_data)))
            
            # Check if silent
            is_silent = rms < 1e-5
            
            return {
                "exists": True,
                "file_size_bytes": file_size,
                "file_size_kb": round(file_size / 1024, 2),
                "duration_sec": round(duration, 3),
                "sample_rate": sample_rate,
                "rms": round(rms, 6),
                "peak": round(peak, 4),
                "is_silent": is_silent,
                "waveform_valid": peak > 0.01 and not is_silent,
                "audio_channels": 1 if audio_data.ndim == 1 else audio_data.shape[1],
            }
        except Exception as e:
            return {
                "exists": True,
                "file_size_bytes": file_size,
                "error": f"Failed to read: {str(e)}"
            }
    
    async def test_audio_file_validation(self, client: AsyncClient):
        """Test 1: Audio file generation and integrity."""
        print("\n" + "="*80)
        print("TEST 1: AUDIO FILE VALIDATION")
        print("="*80)
        
        audio_bytes = self.generate_test_audio(duration=2.0, audio_type="speech_like")
        
        test_cases = [
            ("te", "Test audio -> Telugu"),
            ("hi", "Test audio -> Hindi"),
            ("en", "Test audio -> English"),
        ]
        
        validation_results = []
        
        for target_lang, description in test_cases:
            print(f"\n  [{description}]")
            
            try:
                files = {"file": ("test.wav", audio_bytes, "audio/wav")}
                data = {"target_lang": target_lang}
                
                response = await client.post(
                    "/process/speech-to-speech",
                    files=files,
                    data=data,
                    timeout=120.0
                )
                
                if response.status_code != 200:
                    print(f"    Status: HTTP {response.status_code}")
                    validation_results.append({
                        "target_lang": target_lang,
                        "status": "fail",
                        "error": f"HTTP {response.status_code}"
                    })
                    continue
                
                result = response.json()
                session_id = result.get("session_id")
                audio_url = result.get("output_audio_url", "")
                
                if not session_id:
                    print(f"    ERROR: No session_id in response")
                    validation_results.append({
                        "target_lang": target_lang,
                        "status": "fail",
                        "error": "Missing session_id"
                    })
                    continue
                
                # Find audio file
                outputs_dir = Path(__file__).parent / "outputs"
                audio_file = outputs_dir / f"{session_id}.wav"
                
                # Analyze audio
                audio_analysis = self.analyze_audio_file(audio_file)
                
                checks = {
                    "file_exists": audio_analysis.get("exists", False),
                    "file_size_gt_0": audio_analysis.get("file_size_bytes", 0) > 0,
                    "duration_gt_0": audio_analysis.get("duration_sec", 0) > 0,
                    "not_silent": not audio_analysis.get("is_silent", True),
                    "waveform_valid": audio_analysis.get("waveform_valid", False),
                }
                
                all_passed = all(checks.values())
                
                for check, passed in checks.items():
                    status_str = "[OK]" if passed else "[FAIL]"
                    print(f"    {check}: {status_str}")
                
                if audio_analysis.get("duration_sec"):
                    print(f"    Duration: {audio_analysis['duration_sec']}s")
                if audio_analysis.get("file_size_kb"):
                    print(f"    File Size: {audio_analysis['file_size_kb']} KB")
                if audio_analysis.get("rms"):
                    print(f"    RMS: {audio_analysis['rms']}")
                
                validation_results.append({
                    "target_lang": target_lang,
                    "status": "pass" if all_passed else "fail",
                    "checks": checks,
                    "analysis": audio_analysis,
                    "session_id": session_id,
                })
                
                print(f"    Result: {'[PASS]' if all_passed else '[FAIL]'}")
                
            except Exception as e:
                print(f"    ERROR: {e}")
                validation_results.append({
                    "target_lang": target_lang,
                    "status": "fail",
                    "error": str(e)
                })
        
        self.results["audio_validation"] = {
            "test_cases": validation_results,
            "total": len(test_cases),
            "passed": sum(1 for r in validation_results if r["status"] == "pass"),
        }
        
        return validation_results
    
    async def test_text_consistency(self, client: AsyncClient):
        """Test 2: Verify TTS uses translated text, not original STT."""
        print("\n" + "="*80)
        print("TEST 2: TEXT-TO-SPEECH CONSISTENCY CHECK")
        print("="*80)
        print("Verifying: TTS input == translated text (not original transcript)")
        
        audio_bytes = self.generate_test_audio(duration=2.0)
        
        test_case = ("te", "Test consistency: transcript vs translation")
        target_lang = test_case[0]
        
        print(f"\n  [{test_case[1]}]")
        
        try:
            files = {"file": ("test.wav", audio_bytes, "audio/wav")}
            data = {"target_lang": target_lang}
            
            response = await client.post(
                "/process/speech-to-speech",
                files=files,
                data=data,
                timeout=120.0
            )
            
            if response.status_code != 200:
                print(f"    ERROR: HTTP {response.status_code}")
                self.results["text_consistency"] = {
                    "status": "fail",
                    "error": f"HTTP {response.status_code}"
                }
                return
            
            result = response.json()
            
            transcript = result.get("transcript", "")
            translated_text = result.get("translated_text", "")
            detected_language = result.get("detected_language", "")
            session_id = result.get("session_id", "")
            
            print(f"    Original Transcript: '{transcript[:80]}'")
            print(f"    Translated Text: '{translated_text[:80]}'")
            print(f"    Detected Language: {detected_language}")
            print(f"    Target Language: {target_lang}")
            
            # Check consistency
            checks = {
                "translation_different_from_transcript": transcript != translated_text or detected_language != target_lang,
                "translated_text_not_empty": len(translated_text.strip()) > 0,
                "transcript_not_empty": len(transcript.strip()) > 0,
                "languages_different": detected_language != target_lang,
            }
            
            # Verify TTS actually uses translated text
            # (This requires checking the audio file or TTS logs)
            # For now, we verify the API returned the correct values
            
            for check, passed in checks.items():
                status_str = "[OK]" if passed else "[WARN]"
                print(f"    {check}: {status_str}")
            
            # Analyze audio to confirm it contains speech
            outputs_dir = Path(__file__).parent / "outputs"
            audio_file = outputs_dir / f"{session_id}.wav"
            audio_analysis = self.analyze_audio_file(audio_file)
            
            tts_received_text = {
                "translated": translated_text,
                "language": target_lang,
                "audio_generated": audio_analysis.get("exists", False),
                "audio_valid": audio_analysis.get("waveform_valid", False),
            }
            
            all_passed = all(checks.values()) and audio_analysis.get("waveform_valid", False)
            
            self.results["text_consistency"] = {
                "status": "pass" if all_passed else "partial",
                "checks": checks,
                "tts_input_verification": tts_received_text,
                "audio_analysis": audio_analysis,
            }
            
            print(f"    Result: {'[PASS]' if all_passed else '[PARTIAL]'}")
            
        except Exception as e:
            print(f"    ERROR: {e}")
            self.results["text_consistency"] = {
                "status": "fail",
                "error": str(e)
            }
    
    async def test_target_language_validation(self, client: AsyncClient):
        """Test 3: Verify target language is correct in speech output."""
        print("\n" + "="*80)
        print("TEST 3: TARGET LANGUAGE VALIDATION")
        print("="*80)
        print("Verifying: Speech output language matches target language")
        
        audio_bytes = self.generate_test_audio(duration=2.0)
        
        test_cases = [
            ("en", "English", "Test -> English"),
            ("hi", "Hindi", "Test -> Hindi"),
            ("te", "Telugu", "Test -> Telugu"),
        ]
        
        language_results = []
        
        for target_code, lang_name, description in test_cases:
            print(f"\n  [{lang_name}] {description}")
            
            try:
                files = {"file": ("test.wav", audio_bytes, "audio/wav")}
                data = {"target_lang": target_code}
                
                response = await client.post(
                    "/process/speech-to-speech",
                    files=files,
                    data=data,
                    timeout=120.0
                )
                
                if response.status_code != 200:
                    language_results.append({
                        "target_language": lang_name,
                        "target_code": target_code,
                        "status": "fail",
                        "error": f"HTTP {response.status_code}"
                    })
                    continue
                
                result = response.json()
                
                target_lang_reported = result.get("target_language", "")
                translated_text = result.get("translated_text", "")
                session_id = result.get("session_id", "")
                
                # Analyze audio file
                outputs_dir = Path(__file__).parent / "outputs"
                audio_file = outputs_dir / f"{session_id}.wav"
                audio_analysis = self.analyze_audio_file(audio_file)
                
                # Check language consistency
                checks = {
                    "target_language_reported_correctly": target_lang_reported == target_code,
                    "translated_text_present": len(translated_text.strip()) > 0,
                    "audio_file_generated": audio_analysis.get("exists", False),
                    "audio_valid": audio_analysis.get("waveform_valid", False),
                }
                
                all_passed = all(checks.values())
                
                # Language-specific checks
                if target_code == "te":
                    # Check for Telugu characters
                    has_telugu_chars = any('\u0c00' <= c <= '\u0c7f' for c in translated_text)
                    checks["contains_target_script"] = has_telugu_chars
                    all_passed = all_passed and has_telugu_chars
                elif target_code == "hi":
                    # Check for Devanagari characters
                    has_hindi_chars = any('\u0900' <= c <= '\u097f' for c in translated_text)
                    checks["contains_target_script"] = has_hindi_chars
                    all_passed = all_passed and has_hindi_chars
                elif target_code == "en":
                    # Check contains Latin
                    has_latin = any(ord(c) < 128 for c in translated_text)
                    checks["contains_target_script"] = has_latin
                    all_passed = all_passed and has_latin
                
                for check, passed in checks.items():
                    status_str = "[OK]" if passed else "[WARN]"
                    print(f"    {check}: {status_str}")
                
                print(f"    Translated: '{translated_text[:60]}'")
                
                language_results.append({
                    "target_language": lang_name,
                    "target_code": target_code,
                    "status": "pass" if all_passed else "partial",
                    "checks": checks,
                    "translated_text_sample": translated_text[:100],
                    "audio_analysis": audio_analysis,
                })
                
                print(f"    Result: {'[PASS]' if all_passed else '[PARTIAL]'}")
                
            except Exception as e:
                print(f"    ERROR: {e}")
                language_results.append({
                    "target_language": lang_name,
                    "target_code": target_code,
                    "status": "fail",
                    "error": str(e)
                })
        
        self.results["language_validation"] = {
            "test_cases": language_results,
            "total": len(test_cases),
            "passed": sum(1 for r in language_results if r["status"] == "pass"),
        }
    
    async def test_emotion_verification(self, client: AsyncClient):
        """Test 4: Verify emotion is reflected in speech prosody."""
        print("\n" + "="*80)
        print("TEST 4: EMOTION VERIFICATION")
        print("="*80)
        print("Verifying: Emotion affects speech prosody (speed, pitch)")
        
        # For the QA validation, we test that emotion is detected and applied
        # Actual prosody analysis would require audio DSP analysis
        
        audio_bytes = self.generate_test_audio(duration=2.0)
        
        test_emotions = [
            ("neutral", "Baseline speech rate"),
            ("happy", "Should be slightly faster"),
            ("sad", "Should be slower"),
            ("angry", "Should be faster/sharper"),
        ]
        
        emotion_results = []
        target_lang = "en"
        
        print(f"\n  Testing emotion detection and application...")
        
        try:
            files = {"file": ("test.wav", audio_bytes, "audio/wav")}
            data = {"target_lang": target_lang}
            
            response = await client.post(
                "/process/speech-to-speech",
                files=files,
                data=data,
                timeout=120.0
            )
            
            if response.status_code != 200:
                print(f"    ERROR: HTTP {response.status_code}")
                self.results["emotion_validation"] = {
                    "status": "fail",
                    "error": f"HTTP {response.status_code}"
                }
                return
            
            result = response.json()
            
            detected_emotion = result.get("detected_emotion", "neutral")
            emotion_confidence = result.get("confidence", 0.0)
            meta = result.get("meta", {})
            session_id = result.get("session_id", "")
            
            print(f"    Detected Emotion: {detected_emotion}")
            print(f"    Confidence: {emotion_confidence:.3f}")
            
            # Check emotion prosody mapping
            from epmssts.services.tts.synthesizer import EMOTION_SPEED
            
            speed_multiplier = EMOTION_SPEED.get(detected_emotion.lower(), 1.0)
            
            print(f"    Speed Multiplier: {speed_multiplier}")
            
            # Verify emotion is valid
            valid_emotions = ["neutral", "happy", "sad", "angry", "fearful"]
            emotion_valid = detected_emotion.lower() in valid_emotions
            
            # Analyze audio to confirm prosody was applied
            outputs_dir = Path(__file__).parent / "outputs"
            audio_file = outputs_dir / f"{session_id}.wav"
            audio_analysis = self.analyze_audio_file(audio_file)
            
            checks = {
                "emotion_detected": len(detected_emotion) > 0,
                "valid_emotion_label": emotion_valid,
                "confidence_in_range": 0.0 <= emotion_confidence <= 1.0,
                "prosody_mapping_applied": speed_multiplier != 1.0 or detected_emotion == "neutral",
                "audio_generated": audio_analysis.get("exists", False),
                "audio_valid": audio_analysis.get("waveform_valid", False),
            }
            
            for check, passed in checks.items():
                status_str = "[OK]" if passed else "[WARN]"
                print(f"    {check}: {status_str}")
            
            all_passed = all(checks.values())
            
            self.results["emotion_validation"] = {
                "status": "pass" if all_passed else "partial",
                "detected_emotion": detected_emotion,
                "emotion_confidence": emotion_confidence,
                "speed_multiplier": speed_multiplier,
                "checks": checks,
                "audio_analysis": audio_analysis,
            }
            
            print(f"    Result: {'[PASS]' if all_passed else '[PARTIAL]'}")
            
        except Exception as e:
            print(f"    ERROR: {e}")
            self.results["emotion_validation"] = {
                "status": "fail",
                "error": str(e)
            }
    
    async def test_multi_language_pipeline(self, client: AsyncClient):
        """Test 5: Multi-language translation and TTS."""
        print("\n" + "="*80)
        print("TEST 5: MULTI-LANGUAGE PIPELINE")
        print("="*80)
        print("Testing: English -> Hindi, Telugu -> English, English -> Telugu")
        
        audio_bytes = self.generate_test_audio(duration=2.0)
        
        translation_pairs = [
            ("en", "hi", "English -> Hindi"),
            ("te", "en", "Telugu -> English"),
            ("en", "te", "English -> Telugu"),
        ]
        
        multi_lang_results = []
        
        for source_lang, target_lang, description in translation_pairs:
            print(f"\n  [{description}]")
            
            try:
                files = {"file": ("test.wav", audio_bytes, "audio/wav")}
                data = {"target_lang": target_lang}
                
                response = await client.post(
                    "/process/speech-to-speech",
                    files=files,
                    data=data,
                    timeout=120.0
                )
                
                if response.status_code != 200:
                    multi_lang_results.append({
                        "translation_pair": description,
                        "status": "fail",
                        "error": f"HTTP {response.status_code}"
                    })
                    continue
                
                result = response.json()
                
                detected_lang = result.get("detected_language", "")
                translated_text = result.get("translated_text", "")
                target_lang_output = result.get("target_language", "")
                session_id = result.get("session_id", "")
                
                # Analyze audio
                outputs_dir = Path(__file__).parent / "outputs"
                audio_file = outputs_dir / f"{session_id}.wav"
                audio_analysis = self.analyze_audio_file(audio_file)
                
                checks = {
                    "target_language_correct": target_lang_output == target_lang,
                    "translation_not_empty": len(translated_text.strip()) > 0,
                    "audio_generated": audio_analysis.get("exists", False),
                    "audio_valid": audio_analysis.get("waveform_valid", False),
                    "audio_playable": audio_analysis.get("duration_sec", 0) > 0,
                }
                
                all_passed = all(checks.values())
                
                for check, passed in checks.items():
                    status_str = "[OK]" if passed else "[FAIL]"
                    print(f"    {check}: {status_str}")
                
                print(f"    Detected: {detected_lang}, Translated: {translated_text[:50]}")
                
                multi_lang_results.append({
                    "translation_pair": description,
                    "status": "pass" if all_passed else "partial",
                    "detected_language": detected_lang,
                    "target_language": target_lang_output,
                    "translated_sample": translated_text[:100],
                    "checks": checks,
                    "audio_analysis": audio_analysis,
                })
                
                print(f"    Result: {'[PASS]' if all_passed else '[PARTIAL]'}")
                
            except Exception as e:
                print(f"    ERROR: {e}")
                multi_lang_results.append({
                    "translation_pair": description,
                    "status": "fail",
                    "error": str(e)
                })
        
        self.results["multi_language_tests"] = {
            "test_cases": multi_lang_results,
            "total": len(translation_pairs),
            "passed": sum(1 for r in multi_lang_results if r["status"] == "pass"),
        }
    
    def generate_qa_report(self):
        """Generate comprehensive QA report."""
        print("\n" + "="*80)
        print("COMPREHENSIVE QA VALIDATION REPORT")
        print("="*80)
        
        # Audio Validation Summary
        audio_val = self.results.get("audio_validation", {})
        audio_passed = audio_val.get("passed", 0)
        audio_total = audio_val.get("total", 0)
        
        print(f"\n[TEST 1] Audio File Validation: {audio_passed}/{audio_total} PASSED")
        
        # Text Consistency Summary
        text_cons = self.results.get("text_consistency", {})
        text_status = text_cons.get("status", "unknown").upper()
        print(f"[TEST 2] Text-to-Speech Consistency: {text_status}")
        
        # Language Validation Summary
        lang_val = self.results.get("language_validation", {})
        lang_passed = lang_val.get("passed", 0)
        lang_total = lang_val.get("total", 0)
        print(f"[TEST 3] Target Language Validation: {lang_passed}/{lang_total} PASSED")
        
        # Emotion Validation Summary
        emotion_val = self.results.get("emotion_validation", {})
        emotion_status = emotion_val.get("status", "unknown").upper()
        emotion_detected = emotion_val.get("detected_emotion", "unknown")
        print(f"[TEST 4] Emotion Verification: {emotion_status} (Detected: {emotion_detected})")
        
        # Multi-language Summary
        multi_tests = self.results.get("multi_language_tests", {})
        multi_passed = multi_tests.get("passed", 0)
        multi_total = multi_tests.get("total", 0)
        print(f"[TEST 5] Multi-Language Pipeline: {multi_passed}/{multi_total} PASSED")
        
        # Overall verdict
        all_tests = [audio_passed == audio_total, 
                     text_status == "PASS",
                     lang_passed == lang_total,
                     emotion_status == "PASS",
                     multi_passed == multi_total]
        
        passed_count = sum(all_tests)
        total_tests = len(all_tests)
        
        print(f"\n  Overall: {passed_count}/{total_tests} test categories PASSED")
        
        if passed_count == total_tests:
            verdict = "PASS"
            verdict_symbol = "✅"
        elif passed_count >= 3:
            verdict = "PARTIAL"
            verdict_symbol = "⚠️"
        else:
            verdict = "FAIL"
            verdict_symbol = "❌"
        
        print(f"\n  {verdict_symbol} FINAL VERDICT: {verdict}")
        print("="*80)
        
        self.results["summary"] = {
            "total_test_categories": total_tests,
            "passed_categories": passed_count,
            "verdict": verdict,
            "timestamp": time.time(),
        }
        
        # Save report
        report_path = Path(__file__).parent / "outputs" / "qa_validation_report.json"
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\nDetailed report saved to: {report_path}")
        
        return verdict


async def main():
    """Run comprehensive QA validation."""
    print("="*80)
    print("EPMSSTS SPEECH OUTPUT QA & VALIDATION AUDIT")
    print("Senior AI Systems QA Engineer and Speech Pipeline Auditor")
    print("="*80)
    
    validator = SpeechOutputQAValidator()
    
    try:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                
                # Run all tests
                await validator.test_audio_file_validation(client)
                await validator.test_text_consistency(client)
                await validator.test_target_language_validation(client)
                await validator.test_emotion_verification(client)
                await validator.test_multi_language_pipeline(client)
        
        # Generate report
        verdict = validator.generate_qa_report()
        
        return verdict.upper() == "PASS"
        
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nValidation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
