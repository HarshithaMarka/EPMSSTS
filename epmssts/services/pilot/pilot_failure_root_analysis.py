"""
PHASE 1 + PHASE 2: FAILURE ROOT ANALYSIS

Inputs:
- REAL_WORLD_PILOT_REPORT.json
- PILOT_USAGE_LOG.json
- EDGE_CASE_REPORT.json

Outputs:
- FAILURE_ROOT_ANALYSIS.json

This module extracts all failure events, classifies root cause category,
and computes category percentages, mean latency before crash, and reproducibility.
"""

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional


CATEGORIES = [
    "Timeout breach",
    "Memory exhaustion",
    "Race condition",
    "Model inference exception",
    "Audio preprocessing crash",
    "Orchestrator mis-synchronization",
    "Circuit breaker false positive",
    "Unhandled edge input",
]


@dataclass
class FailureEvent:
    event_id: str
    source_report: str
    stage: str
    exception_type: str
    timeout_or_crash: str
    memory_spike: bool
    circuit_breaker_activation: bool
    retry_exhausted: bool
    silence_misclassification: bool
    async_cancellation: bool
    processing_time_ms: float
    category: str
    reproducibility_signature: str


class FailureRootAnalyzer:
    def __init__(self, output_dir: str = "outputs/pilot"):
        self.output_dir = Path(output_dir)

    def _load_json(self, file_name: str) -> Dict[str, Any]:
        with open(self.output_dir / file_name, "r", encoding="utf-8") as f:
            return json.load(f)

    def _classify_usage_event(self, interaction: Dict[str, Any]) -> str:
        retry = bool(interaction.get("retry_occurred", False))
        latency = float(interaction.get("processing_time_ms", 0.0))

        if retry and latency >= 700:
            return "Timeout breach"
        if retry:
            return "Orchestrator mis-synchronization"
        if latency >= 900:
            return "Model inference exception"
        return "Model inference exception"

    def _classify_edge_event(self, edge_event: Dict[str, Any]) -> str:
        edge_type = str(edge_event.get("edge_case_type", ""))
        retry = bool(edge_event.get("retry_occurred", False))
        latency = float(edge_event.get("processing_time_ms", 0.0))

        if edge_type in {"low_volume", "background_noise", "emotional_whisper", "fast_speech", "mild_sarcasm"}:
            if latency >= 900:
                return "Timeout breach"
            if retry:
                return "Orchestrator mis-synchronization"
            return "Unhandled edge input"

        return "Unhandled edge input"

    def extract_failures(self) -> Dict[str, Any]:
        pilot_report = self._load_json("REAL_WORLD_PILOT_REPORT.json")
        usage_log = self._load_json("PILOT_USAGE_LOG.json")
        edge_report = self._load_json("EDGE_CASE_REPORT.json")

        failure_events: List[FailureEvent] = []

        # From usage interactions
        for interaction in usage_log.get("interaction_log", []):
            if not interaction.get("error_occurred", False):
                continue

            category = self._classify_usage_event(interaction)
            signature = f"usage::{interaction.get('user_id','unknown')}::{category}"

            failure_events.append(
                FailureEvent(
                    event_id=str(interaction.get("interaction_id", "unknown_usage_failure")),
                    source_report="PILOT_USAGE_LOG.json",
                    stage="runtime_inference",
                    exception_type="UnknownRuntimeException",
                    timeout_or_crash="crash",
                    memory_spike=False,
                    circuit_breaker_activation=False,
                    retry_exhausted=bool(interaction.get("retry_occurred", False)),
                    silence_misclassification=False,
                    async_cancellation=False,
                    processing_time_ms=float(interaction.get("processing_time_ms", 0.0)),
                    category=category,
                    reproducibility_signature=signature,
                )
            )

        # From edge-case tests
        for edge_event in edge_report.get("edge_case_tests", []):
            if not edge_event.get("error_occurred", False):
                continue

            edge_type = str(edge_event.get("edge_case_type", "unknown"))
            category = self._classify_edge_event(edge_event)
            signature = f"edge::{edge_type}::{category}"

            failure_events.append(
                FailureEvent(
                    event_id=str(edge_event.get("test_id", "unknown_edge_failure")),
                    source_report="EDGE_CASE_REPORT.json",
                    stage=f"edge_case_{edge_type}",
                    exception_type="EdgeCaseProcessingException",
                    timeout_or_crash="crash",
                    memory_spike=False,
                    circuit_breaker_activation=False,
                    retry_exhausted=bool(edge_event.get("retry_occurred", False)),
                    silence_misclassification=not bool(edge_event.get("emotion_correct", True)),
                    async_cancellation=False,
                    processing_time_ms=float(edge_event.get("processing_time_ms", 0.0)),
                    category=category,
                    reproducibility_signature=signature,
                )
            )

        category_counter = Counter(event.category for event in failure_events)
        total_failures = len(failure_events)

        category_percentages = {
            category: (float(category_counter.get(category, 0)) / total_failures * 100.0 if total_failures > 0 else 0.0)
            for category in CATEGORIES
        }

        latencies = [event.processing_time_ms for event in failure_events]
        mean_latency_before_crash = float(mean(latencies)) if latencies else 0.0

        signature_counter = Counter(event.reproducibility_signature for event in failure_events)
        reproducible_count = sum(count for count in signature_counter.values() if count > 1)
        reproducibility_rate = float(reproducible_count / total_failures) if total_failures > 0 else 0.0

        output = {
            "timestamp": str(datetime.now()),
            "source_reports": {
                "pilot_report": "REAL_WORLD_PILOT_REPORT.json",
                "usage_log": "PILOT_USAGE_LOG.json",
                "edge_case_report": "EDGE_CASE_REPORT.json",
            },
            "pilot_failure_rate": float(pilot_report.get("key_metrics", {}).get("failure_rate", 0.0)),
            "total_failures_extracted": total_failures,
            "failure_events": [event.__dict__ for event in failure_events],
            "phase_2_categorization": {
                "category_percentages": category_percentages,
                "mean_latency_before_crash_ms": mean_latency_before_crash,
                "reproducibility_rate": reproducibility_rate,
            },
            "notes": [
                "Current pilot reports do not include typed exception metadata; classification uses deterministic heuristics from available fields.",
                "Instrumentation patch adds explicit per-failure metadata for future runs.",
            ],
        }

        return output

    def run(self, output_file: str = "FAILURE_ROOT_ANALYSIS.json") -> Dict[str, Any]:
        result = self.extract_failures()
        out_path = self.output_dir / output_file
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        return result


if __name__ == "__main__":
    analyzer = FailureRootAnalyzer(output_dir="outputs/pilot")
    report = analyzer.run(output_file="FAILURE_ROOT_ANALYSIS.json")
    print(f"Generated: outputs/pilot/FAILURE_ROOT_ANALYSIS.json | failures={report['total_failures_extracted']}")
