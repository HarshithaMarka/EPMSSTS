#!/usr/bin/env python3
"""
Assisted pre-labeling and dataset bootstrap pipeline for real microphone recordings.

Features:
- Recursively scans project for audio files while excluding generated/env folders.
- Runs emotion pre-classification and extracts confidence + signal metrics.
- Auto-buckets high-confidence files into data/{emotion}/{volume}/ via copy only.
- Sends low-confidence or capped-emotion files to data/review_required/.
- Prevents duplication by checking existing hashes in data/.
- Emits prelabels CSV, reviewer sheet CSV, and bootstrap JSON report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

import numpy as np
import soundfile as sf

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("emotion.prelabel")

AUDIO_EXT = {".wav", ".mp3", ".flac", ".m4a"}
SCAN_EXCLUDE_DIRS = {"outputs", "node_modules", "data", ".git", "__pycache__"}
REQUIRED_EMOTIONS = ["happy", "sad", "angry", "neutral", "excited"]
MAX_PER_EMOTION = 15
MAX_SKEW_GAP = 5


@dataclass
class PrelabelRow:
    filename: str
    filepath: str
    predicted: str
    confidence: float
    rms: float
    centroid: float
    pitch_mean: float
    pitch_var: float
    band: str
    volume: str
    emotion_folder: str
    utterance_id: str
    assigned_to: str
    decision: str


def infer_volume_from_path(path: Path) -> str:
    tokens = set(part.lower() for part in path.parts)
    for vol in ["whisper", "normal", "loud", "quiet", "shout", "noisy"]:
        if vol in tokens or vol in path.stem.lower():
            return vol
    return "normal"


def map_energy_band_to_volume(band: str) -> str:
    mapping = {
        "very_low": "whisper",
        "low": "normal",
        "normal": "normal",
        "high": "loud",
    }
    return mapping.get((band or "").lower(), "normal")


def infer_emotion_folder(path: Path) -> str:
    tokens = [p.lower() for p in path.parts]
    for emo in ["happy", "sad", "angry", "neutral", "excited", "fearful"]:
        if emo in tokens:
            return "happy" if emo == "excited" else emo
    return "unknown"


def infer_utterance_id(path: Path) -> str:
    stem = path.stem.lower()
    for token in ["happy", "sad", "angry", "neutral", "excited", "fearful", "whisper", "normal", "loud", "quiet", "shout", "noisy"]:
        stem = stem.replace(f"_{token}", "")
        stem = stem.replace(f"-{token}", "")
    return stem.strip("_-") or path.stem


class AssistedPrelabeler:
    def __init__(self, project_root: Path, data_dir: Path, min_confidence: float, dry_run: bool):
        from epmssts.services.emotion.audio_emotion import AudioEmotionService
        from epmssts.services.emotion.audio_preprocessing import get_emotion_preprocessor

        self.project_root = project_root
        self.data_dir = data_dir
        self.min_confidence = min_confidence
        self.dry_run = dry_run
        self.emotion_service = AudioEmotionService()
        self.preprocessor = get_emotion_preprocessor()
        self.review_dir = self.data_dir / "review_required"
        self.existing_hashes = self._collect_existing_dataset_hashes()
        self.current_emotion_counts = self._collect_existing_emotion_counts()

    @staticmethod
    def _to_mono_16k(audio: np.ndarray, sr: int) -> np.ndarray:
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

    def _is_excluded(self, path: Path) -> bool:
        lowered = [part.lower() for part in path.parts]
        for part in lowered:
            if part in SCAN_EXCLUDE_DIRS or part.startswith("venv"):
                return True
        return False

    def _hash_file(self, path: Path) -> str:
        hasher = hashlib.sha1()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    def _collect_existing_dataset_hashes(self) -> Set[str]:
        hashes: Set[str] = set()
        if not self.data_dir.exists():
            return hashes

        for p in self.data_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in AUDIO_EXT:
                try:
                    hashes.add(self._hash_file(p))
                except Exception as exc:
                    logger.warning("Could not hash existing file %s: %s", p, exc)
        return hashes

    def _collect_existing_emotion_counts(self) -> Counter:
        counts = Counter()
        if not self.data_dir.exists():
            return counts

        for emotion in REQUIRED_EMOTIONS:
            emotion_dir = self.data_dir / emotion
            if not emotion_dir.exists():
                continue
            for p in emotion_dir.rglob("*"):
                if p.is_file() and p.suffix.lower() in AUDIO_EXT:
                    counts[emotion] += 1
        return counts

    def gather_files(self) -> List[Path]:
        files = []
        for p in self.project_root.rglob("*"):
            if self._is_excluded(p):
                continue
            if p.is_file() and p.suffix.lower() in AUDIO_EXT:
                files.append(p)
        return sorted(files)

    def _ensure_unique_destination(self, target_dir: Path, base_name: str, suffix: str) -> Path:
        candidate = target_dir / f"{base_name}{suffix}"
        if not candidate.exists():
            return candidate

        index = 1
        while True:
            candidate = target_dir / f"{base_name}_{index:03d}{suffix}"
            if not candidate.exists():
                return candidate
            index += 1

    def _safe_copy(self, source: Path, target: Path) -> None:
        if self.dry_run:
            logger.info("[DRY-RUN] copy %s -> %s", source, target)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    def _make_confidence_histogram(self, confidences: List[float]) -> Dict[str, int]:
        bins = {
            "0.00-0.20": 0,
            "0.20-0.40": 0,
            "0.40-0.60": 0,
            "0.60-0.80": 0,
            "0.80-1.00": 0,
        }
        for value in confidences:
            if value < 0.2:
                bins["0.00-0.20"] += 1
            elif value < 0.4:
                bins["0.20-0.40"] += 1
            elif value < 0.6:
                bins["0.40-0.60"] += 1
            elif value < 0.8:
                bins["0.60-0.80"] += 1
            else:
                bins["0.80-1.00"] += 1
        return bins

    def run(self) -> Dict[str, object]:
        rows: List[PrelabelRow] = []
        files = self.gather_files()
        logger.info("Found %d audio files under project root %s", len(files), self.project_root)

        for item in files:
            logger.info("Discovered audio file: %s", item)

        auto_assigned = 0
        review_required = 0
        skipped_duplicate = 0
        skipped_due_to_emotion_cap = 0
        skipped_due_to_skew = 0
        emotion_distribution = Counter()
        volume_distribution = Counter()
        confidences: List[float] = []

        for path in files:
            try:
                audio, sr = sf.read(path)
                audio = self._to_mono_16k(audio, sr)

                _, metrics = self.preprocessor.preprocess_for_emotion(audio, 16000)
                prediction = self.emotion_service.predict(audio, 16000)
                predicted = prediction.label
                confidence = float(prediction.confidence)
                band = metrics.energy_band
                mapped_volume = map_energy_band_to_volume(band)

                confidences.append(confidence)

                source_hash = self._hash_file(path)
                if source_hash in self.existing_hashes:
                    decision = "skipped_duplicate"
                    destination = ""
                    skipped_duplicate += 1
                    logger.info("Skipping duplicate content already present in data/: %s", path)
                else:
                    allow_auto_assign = confidence >= self.min_confidence
                    emotion_capped = self.current_emotion_counts[predicted] >= MAX_PER_EMOTION
                    min_count = min(self.current_emotion_counts[e] for e in REQUIRED_EMOTIONS)
                    would_skew = (self.current_emotion_counts[predicted] + 1) > (min_count + MAX_SKEW_GAP)

                    if allow_auto_assign and not emotion_capped and not would_skew and predicted in REQUIRED_EMOTIONS:
                        destination_dir = self.data_dir / predicted / mapped_volume
                        emotion_distribution[predicted] += 1
                        volume_distribution[mapped_volume] += 1
                        auto_assigned += 1
                        self.current_emotion_counts[predicted] += 1
                        decision = "auto_assigned"
                    else:
                        destination_dir = self.review_dir
                        review_required += 1
                        decision = "review_required"
                        if emotion_capped:
                            skipped_due_to_emotion_cap += 1
                            logger.info(
                                "Emotion cap reached for %s (%d), routing to review: %s",
                                predicted,
                                self.current_emotion_counts[predicted],
                                path,
                            )
                        if would_skew and predicted in REQUIRED_EMOTIONS:
                            skipped_due_to_skew += 1
                            logger.info(
                                "Skew guard routed %s to review (count=%d, min=%d, gap=%d): %s",
                                predicted,
                                self.current_emotion_counts[predicted],
                                min_count,
                                MAX_SKEW_GAP,
                                path,
                            )

                    target = self._ensure_unique_destination(destination_dir, path.stem, path.suffix)
                    destination = str(target.as_posix())
                    self._safe_copy(path, target)
                    self.existing_hashes.add(source_hash)
                    logger.info("%s: %s -> %s", decision, path, target)

                rows.append(
                    PrelabelRow(
                        filename=path.name,
                        filepath=str(path.as_posix()),
                        predicted=predicted,
                        confidence=confidence,
                        rms=float(metrics.raw_rms_db),
                        centroid=float(metrics.spectral_centroid),
                        pitch_mean=float(metrics.pitch_mean),
                        pitch_var=float(metrics.pitch_variance),
                        band=band,
                        volume=mapped_volume,
                        emotion_folder=infer_emotion_folder(path),
                        utterance_id=infer_utterance_id(path),
                        assigned_to=destination,
                        decision=decision,
                    )
                )
            except Exception as exc:
                logger.error("Failed prelabel for %s: %s", path.name, exc)

        logger.info("Generated %d prelabels", len(rows))
        return {
            "rows": rows,
            "report": {
                "total_files_scanned": len(files),
                "files_auto_assigned": auto_assigned,
                "files_requiring_review": review_required,
                "files_skipped_duplicate": skipped_duplicate,
                "files_routed_due_to_emotion_cap": skipped_due_to_emotion_cap,
                "files_routed_due_to_skew_guard": skipped_due_to_skew,
                "emotion_distribution": dict(emotion_distribution),
                "volume_distribution": dict(volume_distribution),
                "confidence_histogram": self._make_confidence_histogram(confidences),
                "min_confidence": self.min_confidence,
                "max_per_emotion": MAX_PER_EMOTION,
                "max_skew_gap": MAX_SKEW_GAP,
                "dry_run": self.dry_run,
            },
        }


def write_prelabels(rows: List[PrelabelRow], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "filename",
                "filepath",
                "predicted",
                "confidence",
                "rms",
                "centroid",
                "pitch_mean",
                "pitch_var",
                "band",
                "volume",
                "emotion_folder",
                "utterance_id",
                "assigned_to",
                "decision",
            ],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "filename": r.filename,
                    "filepath": r.filepath,
                    "predicted": r.predicted,
                    "confidence": f"{r.confidence:.6f}",
                    "rms": f"{r.rms:.4f}",
                    "centroid": f"{r.centroid:.2f}",
                    "pitch_mean": f"{r.pitch_mean:.2f}",
                    "pitch_var": f"{r.pitch_var:.2f}",
                    "band": r.band,
                    "volume": r.volume,
                    "emotion_folder": r.emotion_folder,
                    "utterance_id": r.utterance_id,
                    "assigned_to": r.assigned_to,
                    "decision": r.decision,
                }
            )


def write_reviewer_sheet(rows: List[PrelabelRow], out_csv: Path, min_confidence: float) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "filename",
                "filepath",
                "predicted",
                "confidence",
                "suggested_label",
                "reviewer_label",
                "notes",
                "volume",
                "emotion_folder",
                "utterance_id",
            ],
        )
        writer.writeheader()
        for r in rows:
            suggested = r.predicted if r.confidence >= min_confidence else ""
            writer.writerow(
                {
                    "filename": r.filename,
                    "filepath": r.filepath,
                    "predicted": r.predicted,
                    "confidence": f"{r.confidence:.6f}",
                    "suggested_label": suggested,
                    "reviewer_label": "",
                    "notes": "",
                    "volume": r.volume,
                    "emotion_folder": r.emotion_folder,
                    "utterance_id": r.utterance_id,
                }
            )


def write_bootstrap_report(report: Dict[str, object], out_json: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Assisted pre-labeling for real mic recordings")
    parser.add_argument("--project-root", type=str, default=".", help="Project root to scan recursively")
    parser.add_argument("--data-dir", type=str, default="data", help="Root data directory")
    parser.add_argument(
        "--prelabels-out",
        type=str,
        default="outputs/validation_reports/prelabels.csv",
        help="Output prelabels CSV",
    )
    parser.add_argument(
        "--review-out",
        type=str,
        default="outputs/validation_reports/reviewer_sheet.csv",
        help="Output reviewer sheet CSV",
    )
    parser.add_argument(
        "--bootstrap-report-out",
        type=str,
        default="outputs/validation_reports/bootstrap_report.json",
        help="Output bootstrap report JSON",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.65,
        help="Minimum confidence for auto-assignment into emotion buckets",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate copy operations without writing files",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    data_dir = Path(args.data_dir).resolve()
    labeler = AssistedPrelabeler(project_root=project_root, data_dir=data_dir, min_confidence=args.min_confidence, dry_run=args.dry_run)
    run_output = labeler.run()
    rows = run_output["rows"]
    report = run_output["report"]

    write_prelabels(rows, Path(args.prelabels_out))
    write_reviewer_sheet(rows, Path(args.review_out), min_confidence=args.min_confidence)
    write_bootstrap_report(report, Path(args.bootstrap_report_out))

    logger.info("Prelabels saved: %s", args.prelabels_out)
    logger.info("Reviewer sheet saved: %s", args.review_out)
    logger.info("Bootstrap report saved: %s", args.bootstrap_report_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
