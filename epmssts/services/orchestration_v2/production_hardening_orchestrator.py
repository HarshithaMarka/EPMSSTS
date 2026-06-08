"""
PRODUCTION HARDENING: 7-PHASE ORCHESTRATOR
Master pipeline coordinating all phases with hard gates

Phases:
1. Data Integrity Enforcement - Validate real mic audio
2. Embedding Stability Hardener - Enforce L2/boundaries
3. Adaptive Emotion Validator - Calibrate thresholds
4. Waveform Prosody Validator - F0/energy/pauses
5. Human Blind Test Framework - Real evaluator ratings
6. Failure Integrity Checker - Circuit breaker testing
7. Production Deployment Certifier - Final GO/PILOT/HOLD

Gate Logic:
- Phase 1 → Phase 2: >= 10 valid files REQUIRED
- Phase 2 → Phase 3: >= 95% embedding conformance REQUIRED
- Phase 3 → Phase 4: Retry rate <= 25% REQUIRED
- Phase 4 → Phase 5: Pitch >= 0.75, Energy >= 0.70, Pauses >= 80% REQUIRED
- Phase 5 → Phase 6: MOS >= 3.8, Emotion >= 80%, Dialect >= 80% REQUIRED
- Phase 6 → Phase 7: >= 90% recovery tests passed REQUIRED
- Phase 7: Compute final GO/PILOT/HOLD

Author: Production Hardening
Date: 2026-03-02
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class GateStatus(Enum):
    """Gate evaluation result."""
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


@dataclass
class PhaseGate:
    """Gate evaluation between phases."""
    phase_from: int
    phase_to: int
    criteria_name: str
    threshold: float
    actual_value: float
    status: GateStatus
    failure_reason: Optional[str] = None


class ProductionHardeningOrchestrator:
    """
    Master orchestrator for 7-phase production hardening.
    
    Manages:
    - Phase sequencing
    - Gate validation between phases
    - Report aggregation
    - Final deployment decision
    """
    
    PHASE_MODULES = {
        1: 'data_integrity_enforcer',
        2: 'embedding_stability_hardener',
        3: 'adaptive_emotion_validator',
        4: 'prosody_waveform_validator',
        5: 'human_blind_test_framework',
        6: 'failure_integrity_checker',
        7: 'production_deployment_certifier'
    }
    
    PHASE_NAMES = {
        1: 'Data Integrity Enforcement',
        2: 'Embedding Stability Hardener',
        3: 'Adaptive Emotion Validator',
        4: 'Waveform Prosody Validator',
        5: 'Human Blind Test Framework',
        6: 'Failure Integrity Checker',
        7: 'Production Deployment Certifier'
    }
    
    REPORT_FILES = {
        1: 'DATA_INTEGRITY_REPORT.json',
        2: 'EMBEDDING_STABILITY_REPORT.json',
        3: 'EMOTION_VALIDATION_REPORT.json',
        4: 'PROSODY_REALISM_REPORT.json',
        5: 'HUMAN_EVALUATION_REPORT.json',
        6: 'FAILURE_RECOVERY_REPORT.json',
        7: 'PRODUCTION_DEPLOYMENT_CERTIFICATION.json'
    }
    
    # Hard gates between phases
    PHASE_GATES = {
        (1, 2): {
            'criteria': 'Minimum Valid Samples',
            'threshold': 10,
            'field': 'valid_files',
            'comparison': '>='
        },
        (2, 3): {
            'criteria': 'Embedding Conformance Rate',
            'threshold': 0.95,
            'field': 'conformance_rate',
            'comparison': '>='
        },
        (3, 4): {
            'criteria': 'Emotion Validator Retry Rate',
            'threshold': 0.25,
            'field': 'retry_rate',
            'comparison': '<='
        },
        (4, 5): {
            'criteria': 'Prosody Thresholds',
            'threshold': 0.75,  # Minimum of pitch/energy/pauses
            'sub_fields': [
                ('pitch_correlation.mean', 0.75, '>='),
                ('energy_correlation.mean', 0.70, '>='),
                ('pause_alignment.mean', 0.80, '>=')
            ],
            'comparison': 'all'
        },
        (5, 6): {
            'criteria': 'Human Evaluation Thresholds',
            'threshold': 3.8,  # MOS
            'sub_fields': [
                ('aggregate_metrics.mean_mos', 3.8, '>='),
                ('aggregate_metrics.emotion_correctness', 0.80, '>='),
                ('aggregate_metrics.dialect_correctness', 0.80, '>=')
            ],
            'comparison': 'all'
        },
        (6, 7): {
            'criteria': 'Failure Recovery Pass Rate',
            'threshold': 0.90,
            'field': 'pass_rate',
            'comparison': '>='
        }
    }
    
    def __init__(self, output_dir: str = "outputs/production"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.phase_reports: Dict[int, Dict] = {}
        self.gates: List[PhaseGate] = []
        self.current_phase: int = 0
        self.execution_log: List[str] = []
    
    def log_execution(self, message: str) -> None:
        """Log execution event."""
        timestamp = datetime.now().isoformat()
        line = f"[{timestamp}] {message}"
        self.execution_log.append(line)
        logger.info(message)
    
    def load_phase_report(self, phase: int, report_file: str) -> Optional[Dict]:
        """Load report from completed phase."""
        
        try:
            report_path = self.output_dir / report_file
            if not report_path.exists():
                self.log_execution(f"⚠ Phase {phase} report not found: {report_file}")
                return None
            
            with open(report_path) as f:
                report = json.load(f)
            
            self.phase_reports[phase] = report
            self.log_execution(f"✓ Phase {phase} report loaded")
            
            return report
        
        except Exception as e:
            self.log_execution(f"✗ Failed to load phase {phase}: {str(e)}")
            return None
    
    def evaluate_gate(self, phase_from: int, phase_to: int, report: Dict) -> Tuple[GateStatus, Optional[str]]:
        """
        Evaluate gate between phases.
        
        Returns:
            (status, failure_reason)
        """
        
        gate_spec = self.PHASE_GATES.get((phase_from, phase_to))
        if not gate_spec:
            return (GateStatus.PASS, None)
        
        # Single criterion gate
        if 'field' in gate_spec and 'comparison' in gate_spec:
            field = gate_spec['field']
            threshold = gate_spec['threshold']
            comparison = gate_spec['comparison']
            
            # Navigate nested field
            value = self._get_nested_field(report, field)
            
            if value is None:
                failure_reason = f"Field '{field}' not found in report"
                return (GateStatus.FAIL, failure_reason)
            
            passed = self._compare(value, threshold, comparison)
            
            if not passed:
                failure_reason = f"{gate_spec['criteria']}: {value} {comparison} {threshold} FAILED"
            else:
                failure_reason = None
            
            status = GateStatus.PASS if passed else GateStatus.FAIL
        
        # Multiple criteria gate
        elif 'sub_fields' in gate_spec:
            failed_criteria = []
            
            for field, threshold, comparison in gate_spec['sub_fields']:
                value = self._get_nested_field(report, field)
                
                if value is None:
                    failed_criteria.append(f"Field '{field}' not found")
                    continue
                
                passed = self._compare(value, threshold, comparison)
                
                if not passed:
                    failed_criteria.append(f"{field}: {value} {comparison} {threshold}")
            
            if failed_criteria:
                status = GateStatus.FAIL
                failure_reason = "; ".join(failed_criteria)
            else:
                status = GateStatus.PASS
                failure_reason = None
        
        else:
            return (GateStatus.PASS, None)
        
        # Log gate result
        gate = PhaseGate(
            phase_from=phase_from,
            phase_to=phase_to,
            criteria_name=gate_spec['criteria'],
            threshold=gate_spec.get('threshold', 0),
            actual_value=value if 'value' in locals() else 0,
            status=status,
            failure_reason=failure_reason
        )
        self.gates.append(gate)
        
        return (status, failure_reason)
    
    @staticmethod
    def _get_nested_field(obj: Dict, field_path: str):
        """Get nested field from dict using dot notation."""
        parts = field_path.split('.')
        current = obj
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
            
            if current is None:
                return None
        
        return current
    
    @staticmethod
    def _compare(actual, threshold, comparison: str) -> bool:
        """Compare actual vs threshold."""
        if comparison == '>=':
            return actual >= threshold
        elif comparison == '<=':
            return actual <= threshold
        elif comparison == '>':
            return actual > threshold
        elif comparison == '<':
            return actual < threshold
        elif comparison == '==':
            return actual == threshold
        else:
            return True
    
    def run_hardening_pipeline(self,
                              test_audio_dir: str = "outputs/production",
                              skip_manual_phases: bool = False) -> Dict:
        """
        Run complete 7-phase hardening pipeline.
        
        Args:
            test_audio_dir: Directory with test audio files
            skip_manual_phases: Skip phases requiring manual input (Phase 5: human evaluation)
        
        Returns:
            Final orchestration report
        """
        
        self.log_execution("=" * 70)
        self.log_execution("EPMSSTS PRODUCTION HARDENING PIPELINE")
        self.log_execution("=" * 70)
        
        # Load all available reports
        for phase in range(1, 8):
            report_file = self.REPORT_FILES[phase]
            self.load_phase_report(phase, report_file)
        
        # Evaluate gates sequentially
        phase_order = [
            (1, 2),
            (2, 3),
            (3, 4),
            (4, 5),
            (5, 6),
            (6, 7)
        ]
        
        self.log_execution("\nEvaluating Phase Gates:")
        
        for phase_from, phase_to in phase_order:
            self.log_execution(f"\nGate: {self.PHASE_NAMES[phase_from]} → {self.PHASE_NAMES[phase_to]}")
            
            # Check if we have report from source phase
            if phase_from not in self.phase_reports:
                self.log_execution(f"  ⚠ Phase {phase_from} report not available, blocking...")
                gate_status = GateStatus.BLOCKED
            else:
                gate_status, failure_reason = self.evaluate_gate(
                    phase_from, phase_to,
                    self.phase_reports[phase_from]
                )
                
                if gate_status == GateStatus.PASS:
                    self.log_execution(f"  ✓ Gate PASSED")
                else:
                    self.log_execution(f"  ✗ Gate FAILED: {failure_reason}")
            
            # Stop pipeline if gate fails
            if gate_status != GateStatus.PASS:
                self.log_execution(f"\n🛑 Pipeline blocked at Phase {phase_from} → {phase_to}")
                break
        
        # Generate orchestration report
        orchestration_report = self._generate_orchestration_report()
        
        return orchestration_report
    
    def _generate_orchestration_report(self) -> Dict:
        """Generate final orchestration report."""
        
        report = {
            'timestamp': str(datetime.now()),
            'pipeline_name': 'EPMSSTS Production Hardening',
            'total_phases': 7,
            'phase_names': self.PHASE_NAMES,
            
            'execution_log': self.execution_log,
            
            'gates': [
                {
                    'from_phase': g.phase_from,
                    'to_phase': g.phase_to,
                    'criteria': g.criteria_name,
                    'status': g.status.value,
                    'failure_reason': g.failure_reason
                }
                for g in self.gates
            ],
            
            'phase_reports_loaded': {
                phase: (phase in self.phase_reports)
                for phase in range(1, 8)
            }
        }
        
        # Save orchestration report
        report_path = self.output_dir / "ORCHESTRATION_REPORT.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.log_execution(f"\n✓ Orchestration report saved: {report_path}")
        
        return report


# Example usage
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    orchestrator = ProductionHardeningOrchestrator(
        output_dir="outputs/production"
    )
    
    # Run pipeline
    report = orchestrator.run_hardening_pipeline(
        test_audio_dir="outputs/production",
        skip_manual_phases=True
    )
    
    logger.info("\n" + "=" * 70)
    logger.info("ORCHESTRATION COMPLETE")
    logger.info("=" * 70)
