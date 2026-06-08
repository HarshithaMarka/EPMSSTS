from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, List

import numpy as np
import soundfile as sf

from epmssts.services.emotion.audio_emotion import AudioEmotionService
from epmssts.services.emotion.audio_preprocessing import get_emotion_preprocessor

EMOTIONS = ["neutral", "happy", "sad", "angry", "fearful"]

REQUIRED_FILES = [
    Path("data/happy/normal/happy_normal_real_01.wav"),
    Path("data/sad/normal/sad_normal_real_01.wav"),
    Path("data/angry/normal/angry_normal_real_01.wav"),
    Path("data/neutral/normal/neutral_normal_real_01.wav"),
]


def infer_expected_from_name(path: Path) -> str | None:
    stem = path.stem.lower()
    for emotion in ["happy", "sad", "angry", "neutral", "fearful", "excited"]:
        if emotion in stem.split("_"):
            return "happy" if emotion == "excited" else emotion
    return None


def to_mono_16k(audio: np.ndarray, sr: int) -> np.ndarray:
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)
    audio = audio.astype(np.float32)
    if sr == 16000:
        return audio
    target_len = int(len(audio) * (16000 / sr))
    if target_len <= 1:
        return np.zeros(1, dtype=np.float32)
    x_old = np.linspace(0, 1, len(audio), dtype=np.float32)
    x_new = np.linspace(0, 1, target_len, dtype=np.float32)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def energy_band_from_rms_db(rms_db: float) -> str:
    if rms_db < -35.0:
        return "very_low"
    if rms_db < -25.0:
        return "low"
    if rms_db < -15.0:
        return "normal"
    return "high"


def build_confusion(rows: List[Dict]) -> Dict[str, Dict[str, int]]:
    cm = {e: {p: 0 for p in EMOTIONS} for e in EMOTIONS}
    for row in rows:
        expected = row["expected"]
        predicted = row["predicted"]
        if expected in cm and predicted in cm[expected]:
            cm[expected][predicted] += 1
    return cm


def per_class_recall(rows: List[Dict]) -> Dict[str, float]:
    recall: Dict[str, float] = {}
    for emotion in EMOTIONS:
        total = sum(1 for r in rows if r["expected"] == emotion)
        correct = sum(1 for r in rows if r["expected"] == emotion and r["predicted"] == emotion)
        recall[emotion] = (correct / total) if total else 0.0
    return recall


def confidence_distribution(rows: List[Dict], bins: int = 10) -> Dict:
    confs = np.array([r["confidence"] for r in rows], dtype=np.float32)
    if confs.size == 0:
        return {"bin_edges": [], "counts": []}
    counts, edges = np.histogram(confs, bins=bins, range=(0.0, 1.0))
    return {"bin_edges": [float(x) for x in edges], "counts": [int(x) for x in counts]}


def stability_metric(rows: List[Dict]) -> float:
    if len(rows) < 2:
        return 1.0
    preds = [r["predicted"] for r in rows]
    flips = sum(1 for i in range(1, len(preds)) if preds[i] != preds[i - 1])
    return 1.0 - (flips / (len(preds) - 1))


def main() -> int:
    missing = [str(p) for p in REQUIRED_FILES if not p.exists()]
    if missing:
        print("MISSING_REQUIRED_REAL_FILES")
        for m in missing:
            print(f"  - {m}")
        return 1

    # Real-only staging folder for strict evaluation
    real_dir = Path("data_real_only")
    if real_dir.exists():
        shutil.rmtree(real_dir)
    real_dir.mkdir(parents=True, exist_ok=True)

    for src in REQUIRED_FILES:
        rel = src.relative_to("data")
        dst = real_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    preprocessor = get_emotion_preprocessor()
    classifier = AudioEmotionService()

    rows: List[Dict] = []
    for path in REQUIRED_FILES:
        audio, sr = sf.read(path)
        audio16 = to_mono_16k(audio, sr)
        _, metrics = preprocessor.preprocess_for_emotion(audio16, 16000)
        pred = classifier.predict(audio16, 16000)

        expected = infer_expected_from_name(path)
        if expected is None:
            continue

        row = {
            "file": str(path).replace("\\", "/"),
            "expected": expected,
            "predicted": pred.label,
            "confidence": float(pred.confidence),
            "energy_band": metrics.energy_band,
            "sample_rate": 16000,
            "channels": 1,
            "duration_sec": float(len(audio16) / 16000.0),
            "rms_db": float(metrics.raw_rms_db),
        }
        rows.append(row)

    cm = build_confusion(rows)
    recall = per_class_recall(rows)

    # Volume invariance not meaningful with one sample per utterance, keep as N/A sentinel
    volume_invariance = None

    report = {
        "num_samples": len(rows),
        "files": rows,
        "confusion_matrix": cm,
        "per_class_recall": recall,
        "sad_recall": recall.get("sad", 0.0),
        "volume_invariance": volume_invariance,
        "confidence_distribution": confidence_distribution(rows),
        "stability_metric": stability_metric(rows),
    }

    out = Path("outputs/validation_reports/real_only_batch_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("REAL_ONLY_VALIDATION_COMPLETE")
    print(f"REPORT={out.as_posix()}")
    for row in rows:
        print(
            f"FILE={row['file']} EXPECTED={row['expected']} PRED={row['predicted']} "
            f"CONF={row['confidence']:.4f} BAND={row['energy_band']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
