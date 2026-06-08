from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_step(command: list[str], name: str, timeout: int = 1800) -> tuple[bool, str]:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return False, f"{name} failed to execute: {exc}"

    if proc.returncode != 0:
        return False, f"{name} failed: {proc.stdout}\n{proc.stderr}"
    return True, proc.stdout


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    failures: list[str] = []

    ok, out = run_step([sys.executable, "ci_dialect_audit.py"], "Dialect leakage audit")
    if not ok:
        failures.append(out)
    else:
        audit = load_json(Path("DIALECT_CI_AUDIT_RESULTS.json"))
        if audit.get("speaker_leakage_detected", False):
            failures.append("Dialect leakage audit detected speaker leakage")

    ok, out = run_step([sys.executable, "emotion_fix_regression_tests.py"], "Emotion stability test")
    if not ok:
        failures.append(out)

    ok, out = run_step([sys.executable, "validate_acoustic_dialect_real_samples.py"], "Volume invariance test")
    if not ok:
        failures.append(out)
    else:
        vol = load_json(Path("DIALECT_VALIDATION_RESULTS.json"))
        if not vol.get("volume_stable", False):
            failures.append("Volume invariance test failed")

    calibration_labels = Path("data/calibration/calibration_labels.jsonl")
    if calibration_labels.exists():
        ok, out = run_step([sys.executable, "-c", "from pathlib import Path; from epmssts.services.production.calibration import ConfidenceCalibrator; c=ConfidenceCalibrator(Path('artifacts/calibration/temperature_scaling.json')); r=c.maybe_recompute_from_dataset(Path('data/calibration/calibration_labels.jsonl')); print(r.ece); import sys; sys.exit(0 if r.ece <= 0.08 else 1)"] , "Confidence calibration test")
        if not ok:
            failures.append("Confidence calibration ECE exceeded threshold (0.08)")
    else:
        failures.append("Confidence calibration labels missing at data/calibration/calibration_labels.jsonl")

    ok, out = run_step([sys.executable, "streaming_latency_smoke_test.py"], "Streaming latency test")
    if not ok:
        failures.append(out)
    else:
        stream_report = load_json(Path("STREAMING_LATENCY_REPORT.json"))
        if not stream_report.get("within_budget", False):
            failures.append("Streaming latency exceeded 2-second budget")

    report = {
        "failures": failures,
        "passed": len(failures) == 0,
    }
    Path("CI_PRODUCTION_GATE_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    if failures:
        print(json.dumps(report, indent=2))
        raise SystemExit(1)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
