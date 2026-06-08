#!/usr/bin/env python3
"""
Comprehensive Emotion Detection Diagnostic & Validation Script

This script validates the emotion detection fixes for live microphone input.
It tests:

1. Audio preprocessing with RMS normalization
2. Energy-based calibration (prevents "sad" bias on low-energy audio)
3. Silence detection and filtering
4. Emotion fusion logic with adaptive weighting
5. Override rules for low-confidence predictions

Run with:
    python emotion_diagnostics.py --verbose
    python emotion_diagnostics.py --test-audio sample.wav
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
)
logger = logging.getLogger("emotion.diagnostics")


def test_preprocessing_pipeline():
    """Test the audio preprocessing with RMS normalization."""
    from epmssts.services.emotion.audio_preprocessing import (
        EmotionAudioPreprocessor,
    )

    logger.info("\n" + "=" * 80)
    logger.info("TEST 1: AUDIO PREPROCESSING WITH RMS NORMALIZATION")
    logger.info("=" * 80)

    preprocessor = EmotionAudioPreprocessor()

    # Test case 1: Normal speech-like audio
    logger.info("\nTest Case 1.1: Normal Speech-like Audio")
    normal_audio = np.random.normal(0, 0.05, 16000)  # 1 second @ 16kHz
    processed, metrics = preprocessor.preprocess_for_emotion(
        normal_audio, sample_rate=16000
    )

    logger.info(f"  Input RMS (before): {np.sqrt(np.mean(normal_audio**2)):.6f}")
    logger.info(f"  Output RMS (dBFS): {metrics.rms_db:.2f} (target: -20 dBFS)")
    logger.info(f"  Energy Level: {metrics.energy_level}")
    logger.info(f"  Dynamic Range: {metrics.dynamic_range:.2f} dB")
    logger.info(f"  Spectral Centroid: {metrics.spectral_centroid:.1f} Hz")
    logger.info(
        f"  ✓ RMS normalized within 2 dB of target: "
        f"{abs(metrics.rms_db - (-20.0)) <= 2.0}"
    )

    # Test case 2: Quiet audio (low energy) - THIS WOULD CAUSE "SAD" BIAS
    logger.info("\nTest Case 1.2: Low-Energy Audio (Micro Gain Problem)")
    quiet_audio = np.random.normal(0, 0.001, 16000)  # 10x quieter
    processed_quiet, metrics_quiet = preprocessor.preprocess_for_emotion(
        quiet_audio, sample_rate=16000
    )

    logger.info(
        f"  Input RMS (before): {np.sqrt(np.mean(quiet_audio**2)):.6f} (too quiet)"
    )
    logger.info(f"  Output RMS (dBFS): {metrics_quiet.rms_db:.2f}")
    logger.info(f"  Energy Level: {metrics_quiet.energy_level}")
    logger.warning(
        f"  ⚠ This audio would be normalized, but should trigger "
        f"'low_energy_sad_bias' override in inference"
    )

    # Test case 3: Very quiet audio (near-silent)
    logger.info("\nTest Case 1.3: Very Quiet Audio (Near-Silent)")
    silent_audio = np.random.normal(0, 1e-5, 16000)
    processed_silent, metrics_silent = preprocessor.preprocess_for_emotion(
        silent_audio, sample_rate=16000
    )

    logger.info(f"  Input RMS (before): {np.sqrt(np.mean(silent_audio**2)):.9f}")
    logger.info(f"  Output RMS (dBFS): {metrics_silent.rms_db:.2f}")
    logger.info(f"  Energy Level: {metrics_silent.energy_level}")


def test_energy_based_calibration():
    """Test energy-based override rules to prevent "sad" bias."""
    from epmssts.services.emotion.audio_preprocessing import (
        EmotionAudioPreprocessor,
    )

    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: ENERGY-BASED CALIBRATION & SAD BIAS PREVENTION")
    logger.info("=" * 80)

    preprocessor = EmotionAudioPreprocessor()

    # Test the override logic
    test_cases = [
        {
            "name": "Normal energy + high confidence happy",
            "rms_db": -20.0,
            "confidence": 0.85,
            "emotion": "happy",
            "expect_override": False,
        },
        {
            "name": "Low energy + low confidence sad",
            "rms_db": -45.0,
            "confidence": 0.55,
            "emotion": "sad",
            "expect_override": True,
            "reason_contains": "low_energy_sad_bias",
        },
        {
            "name": "Very low energy (below floor)",
            "rms_db": -65.0,
            "confidence": 0.9,
            "emotion": "angry",
            "expect_override": True,
            "reason_contains": "energy_floor",
        },
        {
            "name": "Quiet but confident prediction",
            "rms_db": -38.0,
            "confidence": 0.8,
            "emotion": "neutral",
            "expect_override": False,
        },
        {
            "name": "Quiet + low confidence + sad (typical bias)",
            "rms_db": -40.0,
            "confidence": 0.6,
            "emotion": "sad",
            "expect_override": True,
            "reason_contains": "low_energy_sad_bias",
        },
    ]

    for test_case in test_cases:
        logger.info(f"\n  {test_case['name']}")
        should_override, reason = preprocessor.should_override_to_neutral(
            rms_db=test_case["rms_db"],
            confidence=test_case["confidence"],
            predicted_emotion=test_case["emotion"],
        )

        expected = test_case["expect_override"]
        passed = should_override == expected

        logger.info(
            f"    RMS: {test_case['rms_db']} dBFS | "
            f"Confidence: {test_case['confidence']} | "
            f"Emotion: {test_case['emotion']}"
        )
        logger.info(f"    Override? {should_override} (expected: {expected})")
        if reason:
            logger.info(f"    Reason: {reason}")

        if passed:
            logger.info(f"    ✓ PASS")
        else:
            logger.error(f"    ✗ FAIL: Expected override={expected}, got {should_override}")

        # Check reason contains expected string if provided
        if "reason_contains" in test_case and should_override:
            if test_case["reason_contains"] in reason:
                logger.info(f"    ✓ Reason matches")
            else:
                logger.error(
                    f"    ✗ Reason mismatch: expected '{test_case['reason_contains']}' "
                    f"in '{reason}'"
                )


def test_fusion_logic():
    """Test adaptive emotion fusion with confidence weighting."""
    from epmssts.services.emotion.audio_emotion import EmotionPrediction
    from epmssts.services.emotion.fusion import fuse_emotions

    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: ADAPTIVE EMOTION FUSION LOGIC")
    logger.info("=" * 80)

    test_cases = [
        {
            "name": "Audio only (no text)",
            "audio": ("happy", 0.85, {"happy": 0.85, "neutral": 0.10, "sad": 0.05, "angry": 0.0, "fearful": 0.0}),
            "text": None,
            "audio_energy": None,
            "expect_label": "happy",
        },
        {
            "name": "Low audio confidence + high text confidence",
            "audio": ("sad", 0.35, {"sad": 0.35, "neutral": 0.30, "happy": 0.20, "angry": 0.10, "fearful": 0.05}),
            "text": ("happy", 0.80, {"happy": 0.80, "neutral": 0.10, "sad": 0.10, "angry": 0.0, "fearful": 0.0}),
            "audio_energy": None,
            "expect_label": "happy",
        },
        {
            "name": "Both confident, different emotions (weighted avg)",
            "audio": ("angry", 0.70, {"angry": 0.70, "happy": 0.20, "sad": 0.10, "neutral": 0.0, "fearful": 0.0}),
            "text": ("happy", 0.65, {"happy": 0.65, "sad": 0.20, "neutral": 0.15, "angry": 0.0, "fearful": 0.0}),
            "audio_energy": -20.0,
            "expect_label": None,  # Will be weighted average
        },
        {
            "name": "Low audio energy + low confidence → neutral",
            "audio": ("sad", 0.40, {"sad": 0.40, "neutral": 0.35, "happy": 0.25, "angry": 0.0, "fearful": 0.0}),
            "text": None,
            "audio_energy": -50.0,
            "expect_label": "neutral",
        },
    ]

    for test_case in test_cases:
        logger.info(f"\n  {test_case['name']}")

        audio_label, audio_conf, audio_scores = test_case["audio"]
        audio_pred = EmotionPrediction(
            label=audio_label,
            confidence=audio_conf,
            scores=audio_scores,
        )

        if test_case["text"]:
            text_label, text_conf, text_scores = test_case["text"]
            text_pred = EmotionPrediction(
                label=text_label,
                confidence=text_conf,
                scores=text_scores,
            )
        else:
            text_pred = None

        try:
            result = fuse_emotions(
                audio_pred,
                text_pred,
                audio_energy_rms_db=test_case["audio_energy"],
            )

            logger.info(
                f"    Result: {result.label} (confidence: {result.confidence:.2f})"
            )

            if test_case["expect_label"]:
                if result.label == test_case["expect_label"]:
                    logger.info(f"    ✓ PASS")
                else:
                    logger.error(
                        f"    ✗ FAIL: Expected {test_case['expect_label']}, "
                        f"got {result.label}"
                    )
            else:
                logger.info(f"    (weighted result, no exact expectation)")

        except Exception as e:
            logger.error(f"    ✗ FAIL: {e}")


def test_silence_handling():
    """Test silence detection and neutral fallback."""
    from epmssts.services.emotion.audio_emotion import AudioEmotionService

    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: SILENCE DETECTION & NEUTRAL FALLBACK")
    logger.info("=" * 80)

    logger.info("\n  Creating AudioEmotionService...")
    try:
        service = AudioEmotionService()

        # Test silence detection
        test_audios = [
            ("Silent (RMS=1e-8)", np.zeros(16000), 1e-8),
            ("Very quiet (RMS=2e-5)", np.random.normal(0, 2e-5, 16000), 2e-5),
            ("Quiet (RMS=1e-4)", np.random.normal(0, 1e-4, 16000), 1e-4),
            ("Normal (RMS=0.05)", np.random.normal(0, 0.05, 16000), 0.05),
        ]

        for name, audio, _ in test_audios:
            is_silent = service.is_silent(audio)
            rms = np.sqrt(np.mean(audio**2))
            logger.info(f"    {name}: is_silent={is_silent} (RMS={rms:.9f})")
            logger.info(f"        Threshold: {AudioEmotionService.is_silent.__doc__}")

    except Exception as e:
        logger.error(f"  ✗ Could not initialize emotion service: {e}")


def test_real_audio_file(audio_file: Path):
    """Test on a real audio file if provided."""
    import soundfile as sf

    from epmssts.services.emotion.audio_emotion import AudioEmotionService
    from epmssts.services.emotion.audio_preprocessing import (
        get_emotion_preprocessor,
    )
    from epmssts.services.stt.audio_handler import preprocess_audio_bytes

    logger.info("\n" + "=" * 80)
    logger.info(f"TEST 5: REAL AUDIO FILE: {audio_file}")
    logger.info("=" * 80)

    if not audio_file.exists():
        logger.error(f"  ✗ File not found: {audio_file}")
        return

    try:
        logger.info(f"  Loading audio from {audio_file}...")
        audio_data, sr = sf.read(audio_file)

        logger.info(f"  Original: sample_rate={sr}, shape={audio_data.shape}")

        # Preprocess
        preprocessor = get_emotion_preprocessor()
        processed, metrics = preprocessor.preprocess_for_emotion(audio_data, sr)

        logger.info(f"\n  PREPROCESSING METRICS:")
        logger.info(f"    Energy Level: {metrics.energy_level}")
        logger.info(f"    RMS (dBFS): {metrics.rms_db:.2f}")
        logger.info(f"    Peak (dBFS): {metrics.peak_db:.2f}")
        logger.info(f"    Spectral Centroid: {metrics.spectral_centroid:.1f} Hz")
        logger.info(f"    Dynamic Range: {metrics.dynamic_range:.2f} dB")
        logger.info(f"    Crest Factor: {metrics.crest_factor:.2f}")

        # Run emotion detection
        logger.info(f"\n  Running emotion detection...")
        service = AudioEmotionService()
        if service._model_available:
            result = service.predict(processed, 16000)
            logger.info(f"\n  EMOTION PREDICTION:")
            logger.info(f"    Label: {result.label}")
            logger.info(f"    Confidence: {result.confidence:.4f}")
            logger.info(f"    Scores:")
            for emotion, score in sorted(
                result.scores.items(), key=lambda x: x[1], reverse=True
            ):
                logger.info(f"      {emotion}: {score:.4f}")
        else:
            logger.warning("  ⚠ Emotion model not available")

    except Exception as e:
        logger.error(f"  ✗ Error processing audio: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all diagnostic tests."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Emotion Detection Diagnostic Suite"
    )
    parser.add_argument(
        "--test-audio",
        type=Path,
        help="Path to an audio file to test with",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("EMOTION DETECTION DIAGNOSTIC SUITE")
    logger.info("=" * 80)
    logger.info(
        "This suite validates fixes for the 'sad' bias in live microphone recordings."
    )

    try:
        test_preprocessing_pipeline()
        test_energy_based_calibration()
        test_fusion_logic()
        test_silence_handling()

        if args.test_audio:
            test_real_audio_file(args.test_audio)

        logger.info("\n" + "=" * 80)
        logger.info("DIAGNOSTIC SUITE COMPLETE")
        logger.info("=" * 80)
        return 0

    except Exception as e:
        logger.error(f"\n✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
