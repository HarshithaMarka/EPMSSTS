"""
Production Validation - Speech Pipeline (EPMSSTS)

Validates:
- Real speech output (not synthetic tones)
- Translation-to-TTS integrity
- Target language correctness
- Emotion prosody effects
- Stability under sequential and concurrent requests
"""

from __future__ import annotations

import asyncio
import io
import json
import math
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import soundfile as sf
from scipy import signal

from epmssts.api.pipeline import run_speech_to_speech
from epmssts.services.dialect.classifier import DialectClassifier
from epmssts.services.emotion.audio_emotion import AudioEmotionService
from epmssts.services.emotion.text_emotion import TextEmotionService
from epmssts.services.stt.transcriber import SpeechToTextService
from epmssts.services.translation.translator import TranslationService
from epmssts.services.tts.synthesizer import TtsService, TtsSynthesisRequest

OUTPUTS_DIR = Path(__file__).parent / "outputs"
REPORT_JSON = OUTPUTS_DIR / "PRODUCTION_VALIDATION_REPORT.json"
REPORT_MD = OUTPUTS_DIR / "PRODUCTION_VALIDATION_REPORT.md"


class TtsSpy:
    """Wraps TtsService to record the exact request being synthesized."""

    def __init__(self, inner: TtsService) -> None:
        self.inner = inner
        self.requests: List[Dict[str, Any]] = []

    def synthesize(self, request: TtsSynthesisRequest) -> bytes:
        voice_info = None
        if getattr(self.inner, "_pyttsx3", None) is not None:
            try:
                current_voice_id = self.inner._pyttsx3.getProperty("voice")
                voice_name = None
                for v in self.inner._pyttsx3.getProperty("voices"):
                    if v.id == current_voice_id:
                        voice_name = getattr(v, "name", None)
                        break
                voice_info = {
                    "voice_id": current_voice_id,
                    "voice_name": voice_name,
                }
            except Exception:
                voice_info = None

        self.requests.append(
            {
                "text": request.text,
                "language": request.language,
                "emotion": request.emotion,
                "voice": voice_info,
            }
        )
        return self.inner.synthesize(request)


def _to_mono_float32(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    return audio.astype(np.float32)


def _resample_16k(audio: np.ndarray, sr: int) -> np.ndarray:
    if sr == 16000:
        return audio
    target_len = int(len(audio) * 16000 / sr)
    if target_len <= 0:
        return np.asarray([], dtype=np.float32)
    return signal.resample(audio, target_len).astype(np.float32)


def _waveform_stats(audio: np.ndarray, sr: int) -> Dict[str, float]:
    if audio.size == 0 or sr <= 0:
        return {
            "duration_sec": 0.0,
            "rms": 0.0,
            "peak": 0.0,
            "zcr": 0.0,
            "spectral_flatness": 1.0,
            "peak_ratio": 0.0,
        }

    duration = float(len(audio) / sr)
    rms = float(np.sqrt(np.mean(np.square(audio))))
    peak = float(np.max(np.abs(audio)))
    zcr = float(np.mean(audio[:-1] * audio[1:] < 0))

    # Spectral flatness and peak ratio to detect tone-like output
    fft = np.fft.rfft(audio)
    mag = np.abs(fft) + 1e-12
    spectral_flatness = float(np.exp(np.mean(np.log(mag))) / np.mean(mag))
    peak_ratio = float(np.max(mag) / np.mean(mag))

    return {
        "duration_sec": duration,
        "rms": rms,
        "peak": peak,
        "zcr": zcr,
        "spectral_flatness": spectral_flatness,
        "peak_ratio": peak_ratio,
    }


def _is_tone_like(stats: Dict[str, float]) -> bool:
    # Strong single-frequency energy and very low flatness suggests a tone.
    return stats["peak_ratio"] > 30.0 and stats["spectral_flatness"] < 0.05


def _contains_devanagari(text: str) -> bool:
    return any(0x0900 <= ord(ch) <= 0x097F for ch in text)


def _contains_telugu(text: str) -> bool:
    return any(0x0C00 <= ord(ch) <= 0x0C7F for ch in text)


def _detect_language_by_script(text: str, target_lang: str) -> bool:
    if target_lang == "hi":
        return _contains_devanagari(text)
    if target_lang == "te":
        return _contains_telugu(text)
    if target_lang == "en":
        return all(ord(ch) < 128 for ch in text if ch.isalpha())
    return False


def _load_audio_bytes(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(io.BytesIO(wav_bytes))
    return _to_mono_float32(audio), int(sr)


def _load_audio_file(path: Path) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(path)
    return _to_mono_float32(audio), int(sr)


def _round_trip_transcribe(stt: SpeechToTextService, audio: np.ndarray, sr: int) -> Dict[str, Any]:
    audio_16k = _resample_16k(audio, sr)
    if audio_16k.size == 0:
        return {"text": "", "language": "", "duration": 0.0}
    result = stt.transcribe(audio_16k, sample_rate=16000)
    return {"text": result.text, "language": result.language, "duration": result.duration}


def _get_memory_rss_mb() -> Optional[float]:
    try:
        import psutil

        process = psutil.Process(os.getpid())
        return float(process.memory_info().rss) / (1024 * 1024)
    except Exception:
        return None


async def _run_single_case(
    name: str,
    source_lang: str,
    target_lang: str,
    source_text: str,
    services: Dict[str, Any],
) -> Dict[str, Any]:
    generator_tts = services["generator_tts"]
    tts_spy = services["tts_spy"]
    stt = services["stt"]

    # Generate source speech (input audio)
    src_request = TtsSynthesisRequest(
        text=source_text,
        language=source_lang,
        emotion="neutral",
    )
    src_wav = generator_tts.synthesize(src_request)

    # Run pipeline
    result = await run_speech_to_speech(
        src_wav,
        target_lang=target_lang,
        stt_service=services["stt"],
        emotion_service=services["emotion"],
        dialect_classifier=services["dialect"],
        translation_service=services["translation"],
        tts_service=tts_spy,
        text_emotion_service=services["text_emotion"],
        outputs_dir=OUTPUTS_DIR,
        timeout_seconds=300.0,
    )

    # Load output audio
    out_audio, out_sr = _load_audio_file(result.audio_path)
    stats = _waveform_stats(out_audio, out_sr)
    tone_like = _is_tone_like(stats)
    size_bytes = int(result.audio_path.stat().st_size)

    # Round-trip STT
    rt = _round_trip_transcribe(stt, out_audio, out_sr)

    # TTS input verification
    tts_input = tts_spy.requests[-1] if tts_spy.requests else None
    tts_input_text = tts_input["text"] if tts_input else ""

    # Target language check (script + STT detection)
    script_ok = _detect_language_by_script(tts_input_text, target_lang)
    rt_lang = (rt.get("language") or "").lower()
    stt_lang_ok = rt_lang == target_lang

    return {
        "name": name,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "source_text": source_text,
        "session_id": result.session_id,
        "transcript": result.transcript,
        "translated_text": result.translated_text,
        "tts_input": tts_input,
        "audio_path": str(result.audio_path),
        "audio_size_bytes": size_bytes,
        "waveform_stats": stats,
        "tone_like": tone_like,
        "round_trip": rt,
        "checks": {
            "size_gt_20kb": size_bytes > 20_000,
            "duration_gt_1s": stats["duration_sec"] > 1.0,
            "speech_like": (stats["rms"] > 0.001 and stats["peak"] > 0.01),
            "not_tone_like": not tone_like,
            "round_trip_non_empty": len(rt.get("text", "").strip()) > 0,
            "tts_input_eq_translation": tts_input_text.strip() == result.translated_text.strip(),
            "tts_input_not_transcript": tts_input_text.strip() != result.transcript.strip(),
            "target_lang_script_ok": script_ok,
            "target_lang_stt_ok": stt_lang_ok,
        },
    }


def _emotion_prosody_test(tts: TtsService) -> Dict[str, Any]:
    text = "I am testing emotion prosody in the speech output"
    emotions = ["happy", "sad", "angry", "neutral"]

    samples: Dict[str, Dict[str, Any]] = {}
    for emotion in emotions:
        req = TtsSynthesisRequest(text=text, language="en", emotion=emotion)
        wav = tts.synthesize(req)
        audio, sr = _load_audio_bytes(wav)
        stats = _waveform_stats(audio, sr)
        samples[emotion] = {
            "size_bytes": len(wav),
            "duration_sec": stats["duration_sec"],
            "rms": stats["rms"],
            "peak": stats["peak"],
        }

    durations = [samples[e]["duration_sec"] for e in emotions]
    duration_range = float(max(durations) - min(durations))

    return {
        "samples": samples,
        "duration_range_sec": duration_range,
        "rate_variation_detected": duration_range >= 0.15,
        "pitch_variation_detected": False,  # pyttsx3 rate only; no pitch control in current implementation
    }


def _stability_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    success = [r for r in results if r.get("error") is None]
    failures = [r for r in results if r.get("error") is not None]
    return {
        "total": len(results),
        "success": len(success),
        "failures": len(failures),
        "errors": [r.get("error") for r in failures],
    }


async def main() -> Dict[str, Any]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    # Shared services (simulate production singleton services)
    stt = SpeechToTextService()
    emotion = AudioEmotionService()
    dialect = DialectClassifier()
    translation = TranslationService()
    text_emotion = TextEmotionService()  # optional; used when input is English

    # TTS service for pipeline (spy wrapped) and for input audio generation
    tts = TtsService()
    tts_spy = TtsSpy(tts)
    generator_tts = TtsService()

    services = {
        "stt": stt,
        "emotion": emotion,
        "dialect": dialect,
        "translation": translation,
        "text_emotion": text_emotion,
        "tts_spy": tts_spy,
        "generator_tts": generator_tts,
    }

    # Phase 1: Real Speech Verification (3 test inputs)
    test_cases = [
        {
            "name": "English_to_Hindi",
            "source_lang": "en",
            "target_lang": "hi",
            "source_text": "I want to eat Indian food today and I feel very happy.",
        },
        {
            "name": "Telugu_to_English",
            "source_lang": "te",
            "target_lang": "en",
            "source_text": "nenu ippudu telugu lo matladutunnanu, naaku sahayam kavali.",
        },
        {
            "name": "English_to_Telugu",
            "source_lang": "en",
            "target_lang": "te",
            "source_text": "I need directions to the nearest hospital, please.",
        },
    ]

    phase1_results = []
    for case in test_cases:
        result = await _run_single_case(
            case["name"],
            case["source_lang"],
            case["target_lang"],
            case["source_text"],
            services,
        )
        phase1_results.append(result)

    # Phase 4: Emotion Prosody Validation
    emotion_results = _emotion_prosody_test(tts)

    # Phase 5: Stability & Concurrency
    seq_results = []
    mem_before = _get_memory_rss_mb()
    for i in range(5):
        try:
            r = await _run_single_case(
                f"Sequential_{i+1}",
                "en",
                "hi",
                "Please translate this message into Hindi and read it aloud.",
                services,
            )
            r["error"] = None
            seq_results.append(r)
        except Exception as exc:
            seq_results.append({"error": str(exc)})

    async def _concurrent_task(idx: int) -> Dict[str, Any]:
        try:
            r = await _run_single_case(
                f"Concurrent_{idx}",
                "en",
                "hi",
                "This is a concurrency stability check for the speech pipeline.",
                services,
            )
            r["error"] = None
            return r
        except Exception as exc:
            return {"error": str(exc)}

    concurrent_results = await asyncio.gather(
        _concurrent_task(1), _concurrent_task(2), _concurrent_task(3)
    )
    mem_after = _get_memory_rss_mb()

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "engine": getattr(tts, "_engine_kind", "unknown"),
        "phase1_real_speech": phase1_results,
        "phase2_translation_integrity": [
            {
                "name": r["name"],
                "tts_input": (r.get("tts_input") or {}).get("text", ""),
                "translated_text": r.get("translated_text", ""),
                "transcript": r.get("transcript", ""),
                "tts_input_eq_translation": r["checks"]["tts_input_eq_translation"],
                "tts_input_not_transcript": r["checks"]["tts_input_not_transcript"],
            }
            for r in phase1_results
        ],
        "phase3_target_language": [
            {
                "name": r["name"],
                "target_lang": r["target_lang"],
                "tts_voice": (r.get("tts_input") or {}).get("voice", None),
                "script_ok": r["checks"]["target_lang_script_ok"],
                "stt_lang_ok": r["checks"]["target_lang_stt_ok"],
                "round_trip_lang": (r.get("round_trip") or {}).get("language", ""),
            }
            for r in phase1_results
        ],
        "phase4_emotion_prosody": emotion_results,
        "phase5_stability": {
            "sequential": _stability_summary(seq_results),
            "concurrent": _stability_summary(list(concurrent_results)),
            "memory_rss_mb_before": mem_before,
            "memory_rss_mb_after": mem_after,
            "memory_rss_mb_delta": (mem_after - mem_before) if mem_before and mem_after else None,
        },
    }

    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    # Write Markdown summary
    md_lines = [
        "# Production Validation Report",
        "",
        f"Timestamp: {report['timestamp']}",
        f"TTS Engine: {report['engine']}",
        "",
        "## Phase 1 - Real Speech Verification",
    ]
    for r in phase1_results:
        stats = r["waveform_stats"]
        md_lines.extend(
            [
                f"### {r['name']}",
                f"- Audio size: {r['audio_size_bytes']} bytes",
                f"- Duration: {stats['duration_sec']:.2f}s",
                f"- RMS: {stats['rms']:.6f}",
                f"- Peak: {stats['peak']:.4f}",
                f"- ZCR: {stats['zcr']:.4f}",
                f"- Spectral flatness: {stats['spectral_flatness']:.4f}",
                f"- Peak ratio: {stats['peak_ratio']:.2f}",
                f"- Tone-like detected: {r['tone_like']}",
                f"- Round-trip transcript: {r['round_trip']['text']}",
                "",
            ]
        )

    md_lines.extend(
        [
            "## Phase 2 - Translation-to-TTS Integrity",
            "",
        ]
    )
    for r in report["phase2_translation_integrity"]:
        md_lines.extend(
            [
                f"### {r['name']}",
                f"- TTS input == translated: {r['tts_input_eq_translation']}",
                f"- TTS input != transcript: {r['tts_input_not_transcript']}",
                f"- TTS input: {r['tts_input']}",
                "",
            ]
        )

    md_lines.extend(
        [
            "## Phase 3 - Target Language Confirmation",
            "",
        ]
    )
    for r in report["phase3_target_language"]:
        md_lines.extend(
            [
                f"### {r['name']}",
                f"- Target lang: {r['target_lang']}",
                f"- Script heuristic ok: {r['script_ok']}",
                f"- STT detected lang ok: {r['stt_lang_ok']}",
                f"- TTS voice: {r['tts_voice']}",
                "",
            ]
        )

    md_lines.extend(
        [
            "## Phase 4 - Emotion Prosody",
            "",
            f"- Duration range: {emotion_results['duration_range_sec']:.2f}s",
            f"- Rate variation detected: {emotion_results['rate_variation_detected']}",
            f"- Pitch variation detected: {emotion_results['pitch_variation_detected']}",
            "",
            "## Phase 5 - Stability & Concurrency",
            "",
            f"- Sequential: {report['phase5_stability']['sequential']}",
            f"- Concurrent: {report['phase5_stability']['concurrent']}",
            f"- Memory RSS before: {report['phase5_stability']['memory_rss_mb_before']}",
            f"- Memory RSS after: {report['phase5_stability']['memory_rss_mb_after']}",
            f"- Memory RSS delta: {report['phase5_stability']['memory_rss_mb_delta']}",
            "",
        ]
    )

    REPORT_MD.write_text("\n".join(md_lines), encoding="utf-8")

    return report


if __name__ == "__main__":
    try:
        results = asyncio.run(main())
        print(json.dumps(results, indent=2, ensure_ascii=False))
    except KeyboardInterrupt:
        print("Validation interrupted")
    except Exception as exc:
        print(f"Validation failed: {exc}")
        raise
