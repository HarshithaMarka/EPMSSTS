#!/usr/bin/env python3
"""Build CSV template for labeling real microphone recordings."""

from __future__ import annotations

import csv
from pathlib import Path

AUDIO_EXT = {".wav", ".mp3", ".flac", ".m4a"}


def main() -> int:
    root = Path(".")
    out = Path("outputs/validation_reports/real_mic_manifest_template.csv")
    out.parent.mkdir(parents=True, exist_ok=True)

    files = []
    for path in root.rglob("*"):
        if path.suffix.lower() in AUDIO_EXT and path.is_file():
            files.append(path)

    files = sorted(files)

    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["filename", "expected", "volume", "utterance_id"])
        writer.writeheader()
        for path in files:
            writer.writerow(
                {
                    "filename": path.name,
                    "expected": "",
                    "volume": "normal",
                    "utterance_id": path.stem,
                }
            )

    print(f"Template written: {out} | rows={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
