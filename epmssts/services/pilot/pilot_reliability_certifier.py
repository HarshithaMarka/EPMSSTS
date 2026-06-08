"""
PHASE 4: RELIABILITY HARD GATE CERTIFIER

Runs 500 continuous interactions after reliability patch and emits:
- RELIABILITY_CERTIFICATION.json

Hard criteria:
- 0 crashes
- 0 unhandled exceptions
- 0 silent returns
- 0 hanging requests
- 0 circuit breaker deadlocks
"""

import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from reliability_stabilizer import ReliabilityStabilizer


class ReliabilityHardGateCertifier:
    def __init__(self, output_dir: str = "outputs/pilot"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.stabilizer = ReliabilityStabilizer(stage_timeout_ms=900.0, max_concurrent_gpu_ops=2)

    def _simulate_worker(self) -> Dict[str, Any]:
        # Simulated stage workload with potential reliability hazards
        latency_ms = random.randint(120, 980)
        time.sleep(latency_ms / 100000.0)

        fault_draw = random.random()
        if fault_draw < 0.01:
            raise TimeoutError("Synthetic timeout trigger")
        if fault_draw < 0.013:
            raise MemoryError("Synthetic memory spike")
        if fault_draw < 0.016:
            raise RuntimeError("Synthetic model inference exception")

        return {
            "emotion_detected": random.choice(["neutral", "happy", "sad", "angry", "excited", "calm"]),
            "dialect_detected": random.choice(["neutral", "andhra", "telangana", "mixed"]),
            "confidence": round(random.uniform(0.78, 0.98), 4),
            "simulated_latency_ms": latency_ms,
        }

    def run(self, interactions: int = 500, output_file: str = "RELIABILITY_CERTIFICATION.json") -> Dict[str, Any]:
        crash_count = 0
        unhandled_exception_count = 0
        silent_return_count = 0
        hanging_request_count = 0
        circuit_breaker_deadlock_count = 0

        samples: List[Dict[str, Any]] = []

        for idx in range(interactions):
            stage_name = f"interaction_stage_{idx:04d}"

            try:
                output, diagnostics = self.stabilizer.stabilize_interaction(
                    stage=stage_name,
                    worker=self._simulate_worker,
                    timeout_ms=900.0,
                )

                # Hard-gate metrics
                if not output:
                    silent_return_count += 1
                if diagnostics.get("latency_ms", 0.0) > 900.0 and not diagnostics.get("recovered_with_fallback", False):
                    hanging_request_count += 1
                if diagnostics.get("circuit_breaker_activation", False) and not diagnostics.get("recovered_with_fallback", False):
                    circuit_breaker_deadlock_count += 1

                if idx < 20:
                    samples.append(
                        {
                            "interaction_index": idx,
                            "output_fallback": bool(output.get("fallback", False)) if isinstance(output, dict) else False,
                            "diagnostics": diagnostics,
                        }
                    )

            except Exception:
                crash_count += 1
                unhandled_exception_count += 1

        criteria = {
            "zero_crashes": crash_count == 0,
            "zero_unhandled_exceptions": unhandled_exception_count == 0,
            "zero_silent_returns": silent_return_count == 0,
            "zero_hanging_requests": hanging_request_count == 0,
            "zero_circuit_breaker_deadlocks": circuit_breaker_deadlock_count == 0,
        }

        deployment_status = "GO" if all(criteria.values()) else "HOLD"

        report = {
            "timestamp": str(datetime.now()),
            "interactions_simulated": interactions,
            "results": {
                "crash_count": crash_count,
                "unhandled_exception_count": unhandled_exception_count,
                "silent_return_count": silent_return_count,
                "hanging_request_count": hanging_request_count,
                "circuit_breaker_deadlock_count": circuit_breaker_deadlock_count,
            },
            "hard_gate_criteria": criteria,
            "deployment_status": deployment_status,
            "failure_tolerance": "0%",
            "sample_diagnostics": samples,
        }

        output_path = self.output_dir / output_file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        return report


if __name__ == "__main__":
    certifier = ReliabilityHardGateCertifier(output_dir="outputs/pilot")
    result = certifier.run(interactions=500, output_file="RELIABILITY_CERTIFICATION.json")
    print(
        f"Generated: outputs/pilot/RELIABILITY_CERTIFICATION.json | "
        f"status={result['deployment_status']}"
    )
