#!/usr/bin/env python3
"""
Dataset balance gate for real emotion recordings.

Pass conditions:
- >= 50 reviewed samples
- >= 10 per emotion for: happy, sad, angry, neutral, excited
- >= 3 per volume: whisper, normal, loud
- >= 5 genuine sad
- >= 5 genuine angry

Input should be reviewer sheet CSV where `reviewer_label` is filled.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List

REQUIRED_EMOTIONS = ["happy", "sad", "angry", "neutral", "excited"]
REQUIRED_VOLUMES = ["whisper", "normal", "loud"]


def normalize_label(value: str) -> str:
    v = (value or "").strip().lower()
    if v in {"joy", "happiness"}:
        return "happy"
    if v in {"excite", "excitement"}:
        return "excited"
    return v


def normalize_volume(value: str) -> str:
    v = (value or "").strip().lower()
    if v in {"quiet", "low", "soft"}:
        return "whisper"
    if v in {"high", "shout"}:
        return "loud"
    if v in REQUIRED_VOLUMES:
        return v
    return "normal"


def evaluate_balance(rows: List[Dict[str, str]]) -> Dict[str, object]:
    reviewed = [r for r in rows if (r.get("reviewer_label") or "").strip()]

    emotion_counts = Counter(normalize_label(r.get("reviewer_label", "")) for r in reviewed)
    volume_counts = Counter(normalize_volume(r.get("volume", "")) for r in reviewed)

    total_ok = len(reviewed) >= 50
    emotion_ok = all(emotion_counts[e] >= 10 for e in REQUIRED_EMOTIONS)
    volume_ok = all(volume_counts[v] >= 3 for v in REQUIRED_VOLUMES)
    sad_ok = emotion_counts["sad"] >= 5
    angry_ok = emotion_counts["angry"] >= 5

    passed = total_ok and emotion_ok and volume_ok and sad_ok and angry_ok

    deficits = {
        "total_missing": max(0, 50 - len(reviewed)),
        "emotion_missing": {e: max(0, 10 - emotion_counts[e]) for e in REQUIRED_EMOTIONS},
        "volume_missing": {v: max(0, 3 - volume_counts[v]) for v in REQUIRED_VOLUMES},
        "sad_missing": max(0, 5 - emotion_counts["sad"]),
        "angry_missing": max(0, 5 - emotion_counts["angry"]),
    }

    return {
        "passed": passed,
        "reviewed_count": len(reviewed),
        "emotion_counts": dict(emotion_counts),
        "volume_counts": dict(volume_counts),
        "checks": {
            "total_50_plus": total_ok,
            "per_emotion_10_plus": emotion_ok,
            "per_volume_3_plus": volume_ok,
            "genuine_sad_5_plus": sad_ok,
            "genuine_angry_5_plus": angry_ok,
        },
        "deficits": deficits,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check real-dataset balance gates")
    parser.add_argument(
        "--reviewer-csv",
        type=str,
        default="outputs/validation_reports/reviewer_sheet.csv",
        help="Reviewer sheet CSV path",
    )
    parser.add_argument(
        "--out-json",
        type=str,
        default="outputs/validation_reports/dataset_balance_report.json",
        help="Output JSON report path",
    )
    args = parser.parse_args()

    reviewer_path = Path(args.reviewer_csv)
    if not reviewer_path.exists():
        raise FileNotFoundError(f"Reviewer sheet not found: {reviewer_path}")

    with reviewer_path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    report = evaluate_balance(rows)

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
