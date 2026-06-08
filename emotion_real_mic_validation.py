#!/usr/bin/env python3
"""
Real microphone emotion robustness validation.

Validates production behavior on real recordings only:
- Per-class recall
- Confusion matrix
- Volume invariance
- Emotion stability

Filename convention (recommended):
  <utterance_id>__<expected_emotion>__<volume>.wav
Examples:
  s01_line1__sad__whisper.wav
  s01_line1__sad__normal.wav
  s01_line1__sad__shout.wav

Fallback parsing:
- expected emotion inferred from filename tokens: happy/sad/angry/neutral/fearful/excited
- volume inferred from tokens: whisper/quiet/normal/loud/shout/noisy
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("emotion.real.validation")

EMOTIONS = ["neutral", "happy", "sad", "angry", "fearful"]
VOLUME_BUCKETS = ["whisper", "quiet", "normal", "loud", "shout", "noisy"]


@dataclass
class Sample:
    path: Path
    expected: str
    volume: str
    utterance_id: str


def infer_expected_and_volume(stem: str) -> Tuple[Optional[str], str, str]:
    parts = re.split(r"[_\-\s]+", stem.lower())

    expected = None
    for emo in ["happy", "sad", "angry", "neutral", "fearful", "excited"]:
        if emo in parts or f"__{emo}__" in stem.lower():
            expected = "happy" if emo == "excited" else emo
            break

    volume = "normal"
    for token in VOLUME_BUCKETS:
        if token in parts or f"__{token}" in stem.lower() or f"_{token}" in stem.lower():
            volume = token
            break

    # Try strict format: utterance__emotion__volume
    strict = stem.split("__")
    if len(strict) >= 3:
        utterance_id = strict[0]
        expected_strict = strict[1].lower()
        volume_strict = strict[2].lower()
        if expected_strict in EMOTIONS or expected_strict == "excited":
            expected = "happy" if expected_strict == "excited" else expected_strict
        if volume_strict in VOLUME_BUCKETS:
            volume = volume_strict
        return expected, volume, utterance_id

    # Fallback utterance id: remove obvious tokens
    utterance_id = stem.lower()
    for token in EMOTIONS + ["excited"] + VOLUME_BUCKETS:
        utterance_id = utterance_id.replace(f"_{token}", "")
        utterance_id = utterance_id.replace(f"-{token}", "")
    utterance_id = utterance_id.strip("_-") or stem.lower()

    return expected, volume, utterance_id


class RealMicValidator:
    def __init__(self, data_dir: Path, manifest_path: Optional[Path] = None):
        from epmssts.services.emotion.audio_emotion import AudioEmotionService
        from epmssts.services.emotion.audio_preprocessing import get_emotion_preprocessor

        self.data_dir = data_dir
        self.manifest_path = manifest_path
        self.service = AudioEmotionService()
        self.preprocessor = get_emotion_preprocessor()
        self.samples: List[Sample] = []
        self.results: List[Tuple[Sample, str, float, Dict[str, float]]] = []
        self.preprocessing_latencies_ms: List[float] = []

    def _load_manifest(self) -> Dict[str, Sample]:
        if self.manifest_path is None or not self.manifest_path.exists():
            return {}

        manifest: Dict[str, Sample] = {}
        with self.manifest_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                filename = (row.get("filename") or "").strip()
                expected = (row.get("expected") or "").strip().lower()
                volume = (row.get("volume") or "normal").strip().lower()
                utterance_id = (row.get("utterance_id") or Path(filename).stem).strip()
                if not filename or expected not in EMOTIONS:
                    continue
                manifest[filename.lower()] = Sample(
                    path=Path(filename),
                    expected=expected,
                    volume=volume if volume in VOLUME_BUCKETS else "normal",
                    utterance_id=utterance_id,
                )
        logger.info("Loaded manifest labels: %d", len(manifest))
        return manifest

    def load_samples(self) -> None:
        manifest = self._load_manifest()
        audio_files = sorted(list(self.data_dir.rglob("*.wav")) + list(self.data_dir.rglob("*.mp3")))
        if not audio_files:
            raise FileNotFoundError(f"No audio files found in {self.data_dir}")

        for path in audio_files:
            manifest_item = manifest.get(path.name.lower())
            if manifest_item is not None:
                self.samples.append(
                    Sample(
                        path=path,
                        expected=manifest_item.expected,
                        volume=manifest_item.volume,
                        utterance_id=manifest_item.utterance_id,
                    )
                )
                continue

            expected, volume, utt = infer_expected_and_volume(path.stem)
            if expected is None:
                logger.warning("Skipping unlabeled file: %s", path.name)
                continue
            self.samples.append(Sample(path=path, expected=expected, volume=volume, utterance_id=utt))

        if not self.samples:
            raise ValueError("No labeled files found. Use filename tokens or strict naming convention.")

    def _to_mono_16k(self, audio: np.ndarray, sr: int) -> np.ndarray:
        if audio.ndim == 2:
            audio = np.mean(audio, axis=1)
        audio = audio.astype(np.float32)
        if sr == 16000:
            return audio
        # Lightweight linear resampling
        target_len = int(len(audio) * (16000 / sr))
        if target_len <= 1:
            return np.zeros(1, dtype=np.float32)
        x_old = np.linspace(0, 1, len(audio), dtype=np.float32)
        x_new = np.linspace(0, 1, target_len, dtype=np.float32)
        return np.interp(x_new, x_old, audio).astype(np.float32)

    def run(self) -> None:
        for sample in self.samples:
            try:
                audio, sr = sf.read(sample.path)
                audio = self._to_mono_16k(audio, sr)

                t0 = time.perf_counter()
                _processed, metrics = self.preprocessor.preprocess_for_emotion(audio, 16000)
                t1 = time.perf_counter()
                self.preprocessing_latencies_ms.append((t1 - t0) * 1000.0)

                pred = self.service.predict(audio, 16000)
                self.results.append((sample, pred.label, pred.confidence, pred.scores))
            except Exception as exc:
                logger.error("Failed on %s: %s", sample.path.name, exc)

    def confidence_calibration_curve(self, num_bins: int = 10) -> Dict[str, List[float]]:
        if not self.results:
            return {"bin_centers": [], "avg_confidence": [], "empirical_accuracy": [], "counts": []}

        bins = np.linspace(0.0, 1.0, num_bins + 1)
        bucket_conf: List[List[float]] = [[] for _ in range(num_bins)]
        bucket_acc: List[List[float]] = [[] for _ in range(num_bins)]

        for sample, pred, conf, _ in self.results:
            idx = int(np.digitize([conf], bins, right=True)[0]) - 1
            idx = max(0, min(num_bins - 1, idx))
            bucket_conf[idx].append(conf)
            bucket_acc[idx].append(1.0 if pred == sample.expected else 0.0)

        centers = []
        avg_conf = []
        emp_acc = []
        counts = []
        for i in range(num_bins):
            centers.append(float((bins[i] + bins[i + 1]) / 2.0))
            counts.append(len(bucket_conf[i]))
            avg_conf.append(float(np.mean(bucket_conf[i])) if bucket_conf[i] else 0.0)
            emp_acc.append(float(np.mean(bucket_acc[i])) if bucket_acc[i] else 0.0)

        return {
            "bin_centers": centers,
            "avg_confidence": avg_conf,
            "empirical_accuracy": emp_acc,
            "counts": counts,
        }

    def silence_misclassification_rate(self) -> float:
        silent_like = 0
        non_neutral = 0
        for sample, pred, _conf, _scores in self.results:
            name = sample.path.stem.lower()
            if "silence" in name or "silent" in name:
                silent_like += 1
                if pred != "neutral":
                    non_neutral += 1
        if silent_like == 0:
            return 0.0
        return non_neutral / silent_like

    def confusion_and_recall(self) -> Tuple[Dict[str, Dict[str, int]], Dict[str, float]]:
        cm = {e: {p: 0 for p in EMOTIONS} for e in EMOTIONS}
        totals = Counter()
        correct = Counter()

        for sample, pred, _, _ in self.results:
            expected = sample.expected
            if expected not in EMOTIONS or pred not in EMOTIONS:
                continue
            cm[expected][pred] += 1
            totals[expected] += 1
            if expected == pred:
                correct[expected] += 1

        recall = {e: (correct[e] / totals[e] if totals[e] else 0.0) for e in EMOTIONS}
        return cm, recall

    def volume_invariance(self) -> float:
        by_utt = defaultdict(list)
        for sample, pred, _, _ in self.results:
            by_utt[sample.utterance_id].append((sample.volume, pred, sample.expected))

        if not by_utt:
            return 0.0

        scores = []
        for _, items in by_utt.items():
            if len(items) < 2:
                continue
            expected = items[0][2]
            correct = sum(1 for _, pred, _ in items if pred == expected)
            scores.append(correct / len(items))

        return float(np.mean(scores)) if scores else 0.0

    def stability_score(self) -> float:
        # Uses file order as sequence proxy
        if len(self.results) < 2:
            return 1.0
        preds = [pred for _, pred, _, _ in self.results]
        flips = sum(1 for i in range(1, len(preds)) if preds[i] != preds[i - 1])
        flip_rate = flips / (len(preds) - 1)
        return 1.0 - flip_rate

    def neutral_over_correction_rate(self) -> float:
        non_neutral = 0
        neutral_preds = 0
        for sample, pred, _, _ in self.results:
            if sample.expected != "neutral":
                non_neutral += 1
                if pred == "neutral":
                    neutral_preds += 1
        if non_neutral == 0:
            return 0.0
        return neutral_preds / non_neutral

    def summary(self) -> Dict:
        cm, recall = self.confusion_and_recall()
        invariance = self.volume_invariance()
        stability = self.stability_score()
        neutral_over = self.neutral_over_correction_rate()
        silence_misclass = self.silence_misclassification_rate()
        calibration_curve = self.confidence_calibration_curve()

        p50 = float(np.percentile(self.preprocessing_latencies_ms, 50)) if self.preprocessing_latencies_ms else 0.0
        p95 = float(np.percentile(self.preprocessing_latencies_ms, 95)) if self.preprocessing_latencies_ms else 0.0

        macro_recall = float(np.mean(list(recall.values())))
        sad_recall = recall.get("sad", 0.0)

        # Production score emphasizing requested KPIs
        production_score = np.mean([
            min(1.0, sad_recall / 0.65) if sad_recall > 0 else 0.0,
            min(1.0, invariance / 0.75) if invariance > 0 else 0.0,
            stability,
            macro_recall,
            1.0 - min(1.0, neutral_over),
        ])

        return {
            "num_samples": len(self.results),
            "confusion_matrix": cm,
            "per_class_recall": recall,
            "sad_recall": sad_recall,
            "volume_invariance": invariance,
            "emotion_stability": stability,
            "neutral_over_correction_rate": neutral_over,
            "silence_misclassification_rate": silence_misclass,
            "preprocessing_latency_ms": {
                "p50": p50,
                "p95": p95,
                "meets_lt_50ms": bool(p95 < 50.0),
            },
            "confidence_calibration_curve": calibration_curve,
            "production_score": float(production_score),
            "targets": {
                "sad_recall_target": 0.65,
                "volume_invariance_target": 0.75,
                "production_score_target": 0.75,
                "preprocessing_p95_lt_ms": 50.0,
            },
            "target_hit": {
                "sad_recall": bool(sad_recall >= 0.65),
                "volume_invariance": bool(invariance >= 0.75),
                "production_score": bool(production_score >= 0.75),
                "preprocessing_p95_lt_50ms": bool(p95 < 50.0),
                "silence_misclassification_zero": bool(silence_misclass == 0.0),
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate emotion robustness on real mic recordings")
    parser.add_argument("--data-dir", type=str, required=True, help="Directory containing real recordings")
    parser.add_argument("--manifest", type=str, default=None, help="Optional CSV labels: filename,expected,volume,utterance_id")
    parser.add_argument("--out", type=str, default="outputs/validation_reports/real_mic_validation.json")
    args = parser.parse_args()

    manifest_path = Path(args.manifest) if args.manifest else None
    validator = RealMicValidator(Path(args.data_dir), manifest_path=manifest_path)
    validator.load_samples()
    validator.run()
    report = validator.summary()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info("Samples used: %d", report["num_samples"])
    logger.info("Sad recall: %.2f", report["sad_recall"])
    logger.info("Volume invariance: %.2f", report["volume_invariance"])
    logger.info("Neutral over-correction rate: %.2f", report["neutral_over_correction_rate"])
    logger.info("Production score: %.2f", report["production_score"])

    if report["num_samples"] < 50:
        logger.warning("Only %d labeled samples found; target validation requires >= 50 real mic recordings.", report["num_samples"])
        return 1

    return 0 if all(report["target_hit"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
