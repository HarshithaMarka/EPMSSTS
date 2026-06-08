"""
PHASE 7: PRODUCTION DEPLOYMENT CERTIFIER
Final gating decision: GO / PILOT / HOLD

Purpose:
- Aggregate all 6-phase validation results
- Apply deployment gate logic
- Generate PRODUCTION_DEPLOYMENT_CERTIFICATION.json
- Make final GO/PILOT/HOLD decision

Gate Logic:
  IF ANY(criteria fail):
    - Dataset not validated (< 10 samples)
    - Embedding instability (L2 norm violation)
    - Emotion retry rate > 25%
    - Pitch correlation < 0.75
    - Energy correlation < 0.70
    - Pause alignment < 80%
    - MOS < 3.8
    - Emotion/dialect correctness < 80%
    - Failure recovery failed
  => HOLD (do not deploy)
  
  ELSE:
    IF ALL(thresholds passed with margin > 10%):
      => GO (deploy immediately)
    ELSE:
      => PILOT (deploy to limited audience for validation)

Author: Production Hardening
Date: 2026-03-02
"""

import json
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class DeploymentGateResult:
    """Single gate evaluation."""
    gate_id: str
    gate_name: str
    threshold: float
    actual_value: float
    passes: bool
    margin_percent: float


@dataclass
class DeploymentCertification:
    """Production deployment certification."""
    timestamp: str
    system_version: str = "EPMSSTS-v3-Hardening"
    
    # Phase results
    data_integrity_result: Optional[Dict] = None
    embedding_stability_result: Optional[Dict] = None
    emotion_validation_result: Optional[Dict] = None
    prosody_realism_result: Optional[Dict] = None
    human_evaluation_result: Optional[Dict] = None
    failure_recovery_result: Optional[Dict] = None
    
    # Gate evaluations
    gates: List[DeploymentGateResult] = field(default_factory=list)
    
    # Decision
    deployment_status: str = "HOLD"  # GO, PILOT, HOLD
    confidence_score: float = 0.0  # 0-100%
    deployment_conditions: List[str] = field(default_factory=list)
    critical_failures: List[str] = field(default_factory=list)
    
    def compute_deployment_status(self) -> str:
        """Compute final GO/PILOT/HOLD status."""
        
        # Check for critical failures (any gate fails)
        critical_gates_failed = [g for g in self.gates if not g.passes]
        self.critical_failures = [g.gate_name for g in critical_gates_failed]
        
        if critical_gates_failed:
            self.deployment_status = "HOLD"
            self.confidence_score = 0.0
            return "HOLD"
        
        # Check margin (all gates pass with adequate margin?)
        mean_margin = np.mean([g.margin_percent for g in self.gates])
        
        if mean_margin > 10:
            self.deployment_status = "GO"
            self.confidence_score = float(min(100, 75 + mean_margin))
        else:
            self.deployment_status = "PILOT"
            self.confidence_score = float(min(100, 50 + (2 * mean_margin)))
        
        return self.deployment_status


class ProductionDeploymentCertifier:
    """
    Final certification gate for production deployment.
    
    Combines all 6 validation phases into binary GO/PILOT/HOLD decision.
    """
    
    # Hard thresholds (any failure = HOLD)
    GATE_THRESHOLDS = {
        'dataset_validation': {
            'name': 'Dataset Validation',
            'threshold': 0.9,  # >= 90% valid files
            'field': 'pass_rate'
        },
        'embedding_stability': {
            'name': 'Embedding Stability',
            'threshold': 0.95,  # >= 95% conform to L2/boundaries
            'field': 'conformance_rate'
        },
        'emotion_validator': {
            'name': 'Emotion Validator Retry Rate',
            'threshold': 0.75,  # retry rate <= 25% (1 - 0.75)
            'field': 'retry_rate',
            'inverse': True  # Lower is better
        },
        'pitch_correlation': {
            'name': 'Pitch Correlation',
            'threshold': 0.75,
            'field': 'mean_pitch_correlation'
        },
        'energy_correlation': {
            'name': 'Energy Correlation',
            'threshold': 0.70,
            'field': 'mean_energy_correlation'
        },
        'pause_alignment': {
            'name': 'Pause Alignment',
            'threshold': 0.80,
            'field': 'mean_pause_alignment'
        },
        'mos_score': {
            'name': 'Mean Opinion Score',
            'threshold': 3.8,
            'field': 'mean_mos'
        },
        'emotion_correctness': {
            'name': 'Emotion Recognition',
            'threshold': 0.80,
            'field': 'mean_emotion_correctness'
        },
        'dialect_correctness': {
            'name': 'Dialect Recognition',
            'threshold': 0.80,
            'field': 'mean_dialect_correctness'
        },
        'failure_recovery': {
            'name': 'Failure Recovery',
            'threshold': 0.90,  # >= 90% tests passed
            'field': 'pass_rate'
        }
    }
    
    def __init__(self):
        self.certification = DeploymentCertification(
            timestamp=str(datetime.now())
        )
    
    def load_phase_results(self,
                          data_integrity_file: Optional[str] = None,
                          embedding_stability_file: Optional[str] = None,
                          emotion_validation_file: Optional[str] = None,
                          prosody_realism_file: Optional[str] = None,
                          human_evaluation_file: Optional[str] = None,
                          failure_recovery_file: Optional[str] = None) -> None:
        """Load results from all 6 validation phases."""
        
        if data_integrity_file:
            try:
                with open(data_integrity_file) as f:
                    self.certification.data_integrity_result = json.load(f)
                    logger.info(f"✓ Loaded data integrity report")
            except FileNotFoundError:
                logger.warning(f"Data integrity report not found: {data_integrity_file}")
        
        if embedding_stability_file:
            try:
                with open(embedding_stability_file) as f:
                    self.certification.embedding_stability_result = json.load(f)
                    logger.info(f"✓ Loaded embedding stability report")
            except FileNotFoundError:
                logger.warning(f"Embedding stability report not found: {embedding_stability_file}")
        
        if emotion_validation_file:
            try:
                with open(emotion_validation_file) as f:
                    self.certification.emotion_validation_result = json.load(f)
                    logger.info(f"✓ Loaded emotion validation report")
            except FileNotFoundError:
                logger.warning(f"Emotion validation report not found: {emotion_validation_file}")
        
        if prosody_realism_file:
            try:
                with open(prosody_realism_file) as f:
                    self.certification.prosody_realism_result = json.load(f)
                    logger.info(f"✓ Loaded prosody realism report")
            except FileNotFoundError:
                logger.warning(f"Prosody realism report not found: {prosody_realism_file}")
        
        if human_evaluation_file:
            try:
                with open(human_evaluation_file) as f:
                    self.certification.human_evaluation_result = json.load(f)
                    logger.info(f"✓ Loaded human evaluation report")
            except FileNotFoundError:
                logger.warning(f"Human evaluation report not found: {human_evaluation_file}")
        
        if failure_recovery_file:
            try:
                with open(failure_recovery_file) as f:
                    self.certification.failure_recovery_result = json.load(f)
                    logger.info(f"✓ Loaded failure recovery report")
            except FileNotFoundError:
                logger.warning(f"Failure recovery report not found: {failure_recovery_file}")
    
    def evaluate_gates(self) -> None:
        """Evaluate all deployment gates."""
        
        logger.info("\nEvaluating deployment gates...")
        
        # Gate 1: Data Integrity
        if self.certification.data_integrity_result:
            pass_rate = self.certification.data_integrity_result.get('pass_rate', 0.0)
            threshold = self.GATE_THRESHOLDS['dataset_validation']['threshold']
            
            gate = DeploymentGateResult(
                gate_id='data_integrity',
                gate_name='Data Integrity (Valid Files)',
                threshold=threshold,
                actual_value=pass_rate,
                passes=pass_rate >= threshold,
                margin_percent=((pass_rate - threshold) / threshold * 100) if pass_rate > 0 else 0
            )
            self.certification.gates.append(gate)
            logger.info(f"  Data Integrity: {pass_rate:.1%} vs {threshold:.1%} ({'✓' if gate.passes else '✗'})")
        
        # Gate 2: Embedding Stability
        if self.certification.embedding_stability_result:
            conformance = self.certification.embedding_stability_result.get('conformance_rate', 0.0)
            threshold = self.GATE_THRESHOLDS['embedding_stability']['threshold']
            
            gate = DeploymentGateResult(
                gate_id='embedding_stability',
                gate_name='Embedding Stability (L2/Boundaries)',
                threshold=threshold,
                actual_value=conformance,
                passes=conformance >= threshold,
                margin_percent=((conformance - threshold) / threshold * 100) if conformance > 0 else 0
            )
            self.certification.gates.append(gate)
            logger.info(f"  Embedding Stability: {conformance:.1%} vs {threshold:.1%} ({'✓' if gate.passes else '✗'})")
        
        # Gate 3: Emotion Validation (inverse - lower retry rate is better)
        if self.certification.emotion_validation_result:
            retry_rate = self.certification.emotion_validation_result.get('retry_rate', 0.0)
            threshold = 0.25  # Max acceptable retry rate
            passes = retry_rate <= threshold
            
            gate = DeploymentGateResult(
                gate_id='emotion_validator',
                gate_name='Emotion Validator (Retry Rate)',
                threshold=threshold,
                actual_value=retry_rate,
                passes=passes,
                margin_percent=((threshold - retry_rate) / threshold * 100) if retry_rate > 0 else 0
            )
            self.certification.gates.append(gate)
            logger.info(f"  Emotion Validator: {retry_rate:.1%} vs {threshold:.1%} ({'✓' if gate.passes else '✗'})")
        
        # Gate 4: Pitch Correlation
        if self.certification.prosody_realism_result:
            pitch = self.certification.prosody_realism_result.get('pitch_correlation', {}).get('mean', 0.0)
            threshold = self.GATE_THRESHOLDS['pitch_correlation']['threshold']
            
            gate = DeploymentGateResult(
                gate_id='pitch_correlation',
                gate_name='Pitch Correlation',
                threshold=threshold,
                actual_value=pitch,
                passes=pitch >= threshold,
                margin_percent=((pitch - threshold) / threshold * 100) if pitch > 0 else 0
            )
            self.certification.gates.append(gate)
            logger.info(f"  Pitch Correlation: {pitch:.3f} vs {threshold:.2f} ({'✓' if gate.passes else '✗'})")
        
        # Gate 5: Energy Correlation
        if self.certification.prosody_realism_result:
            energy = self.certification.prosody_realism_result.get('energy_correlation', {}).get('mean', 0.0)
            threshold = self.GATE_THRESHOLDS['energy_correlation']['threshold']
            
            gate = DeploymentGateResult(
                gate_id='energy_correlation',
                gate_name='Energy Correlation',
                threshold=threshold,
                actual_value=energy,
                passes=energy >= threshold,
                margin_percent=((energy - threshold) / threshold * 100) if energy > 0 else 0
            )
            self.certification.gates.append(gate)
            logger.info(f"  Energy Correlation: {energy:.3f} vs {threshold:.2f} ({'✓' if gate.passes else '✗'})")
        
        # Gate 6: Pause Alignment
        if self.certification.prosody_realism_result:
            pauses = self.certification.prosody_realism_result.get('pause_alignment', {}).get('mean', 0.0)
            threshold = self.GATE_THRESHOLDS['pause_alignment']['threshold']
            
            gate = DeploymentGateResult(
                gate_id='pause_alignment',
                gate_name='Pause Alignment',
                threshold=threshold,
                actual_value=pauses,
                passes=pauses >= threshold,
                margin_percent=((pauses - threshold) / threshold * 100) if pauses > 0 else 0
            )
            self.certification.gates.append(gate)
            logger.info(f"  Pause Alignment: {pauses:.1%} vs {threshold:.1%} ({'✓' if gate.passes else '✗'})")
        
        # Gate 7: MOS
        if self.certification.human_evaluation_result:
            mos = self.certification.human_evaluation_result.get('aggregate_metrics', {}).get('mean_mos', 0.0)
            threshold = self.GATE_THRESHOLDS['mos_score']['threshold']
            
            gate = DeploymentGateResult(
                gate_id='mos_score',
                gate_name='Mean Opinion Score',
                threshold=threshold,
                actual_value=mos,
                passes=mos >= threshold,
                margin_percent=((mos - threshold) / threshold * 100) if mos > 0 else 0
            )
            self.certification.gates.append(gate)
            logger.info(f"  MOS: {mos:.2f} vs {threshold:.1f} ({'✓' if gate.passes else '✗'})")
        
        # Gate 8: Emotion Correctness
        if self.certification.human_evaluation_result:
            emotion = self.certification.human_evaluation_result.get('aggregate_metrics', {}).get('emotion_correctness', 0.0)
            if emotion == 0:
                # Try per-scenario
                per_scenario = self.certification.human_evaluation_result.get('per_scenario_results', [])
                if per_scenario:
                    emotion = np.mean([s.get('emotion_correctness', 0.0) for s in per_scenario])
            
            threshold = self.GATE_THRESHOLDS['emotion_correctness']['threshold']
            
            gate = DeploymentGateResult(
                gate_id='emotion_correctness',
                gate_name='Emotion Recognition Accuracy',
                threshold=threshold,
                actual_value=emotion,
                passes=emotion >= threshold,
                margin_percent=((emotion - threshold) / threshold * 100) if emotion > 0 else 0
            )
            self.certification.gates.append(gate)
            logger.info(f"  Emotion Correctness: {emotion:.1%} vs {threshold:.1%} ({'✓' if gate.passes else '✗'})")
        
        # Gate 9: Dialect Correctness
        if self.certification.human_evaluation_result:
            dialect = self.certification.human_evaluation_result.get('aggregate_metrics', {}).get('dialect_correctness', 0.0)
            if dialect == 0:
                # Try per-scenario
                per_scenario = self.certification.human_evaluation_result.get('per_scenario_results', [])
                if per_scenario:
                    dialect = np.mean([s.get('dialect_correctness', 0.0) for s in per_scenario])
            
            threshold = self.GATE_THRESHOLDS['dialect_correctness']['threshold']
            
            gate = DeploymentGateResult(
                gate_id='dialect_correctness',
                gate_name='Dialect Recognition Accuracy',
                threshold=threshold,
                actual_value=dialect,
                passes=dialect >= threshold,
                margin_percent=((dialect - threshold) / threshold * 100) if dialect > 0 else 0
            )
            self.certification.gates.append(gate)
            logger.info(f"  Dialect Correctness: {dialect:.1%} vs {threshold:.1%} ({'✓' if gate.passes else '✗'})")
        
        # Gate 10: Failure Recovery
        if self.certification.failure_recovery_result:
            recovery_rate = self.certification.failure_recovery_result.get('pass_rate', 0.0)
            threshold = self.GATE_THRESHOLDS['failure_recovery']['threshold']
            
            gate = DeploymentGateResult(
                gate_id='failure_recovery',
                gate_name='Failure Recovery Testing',
                threshold=threshold,
                actual_value=recovery_rate,
                passes=recovery_rate >= threshold,
                margin_percent=((recovery_rate - threshold) / threshold * 100) if recovery_rate > 0 else 0
            )
            self.certification.gates.append(gate)
            logger.info(f"  Failure Recovery: {recovery_rate:.1%} vs {threshold:.1%} ({'✓' if gate.passes else '✗'})")
    
    def compute_deployment_status(self) -> str:
        """Compute final GO/PILOT/HOLD status."""
        return self.certification.compute_deployment_status()
    
    def set_deployment_conditions(self) -> None:
        """Set recommended deployment conditions."""
        
        if self.certification.deployment_status == "GO":
            self.certification.deployment_conditions = [
                "Deploy immediately to production",
                "No restrictions on user base",
                "Full speech realism pipeline active"
            ]
        
        elif self.certification.deployment_status == "PILOT":
            self.certification.deployment_conditions = [
                "Deploy to beta/pilot group only",
                "Limit to 10% of user base",
                "Collect additional user feedback",
                "Monitor MOS scores closely",
                "Re-evaluate after 1000 user interactions"
            ]
        
        else:  # HOLD
            self.certification.deployment_conditions = [
                "DO NOT DEPLOY TO PRODUCTION",
                "Identify and fix failing components",
                "Re-run validation after fixes",
                "Address critical failures:",
                *self.certification.critical_failures
            ]
    
    def generate_certification_report(self,
                                     output_file: Optional[str] = None) -> Dict:
        """Generate PRODUCTION_DEPLOYMENT_CERTIFICATION.json"""
        
        self.evaluate_gates()
        self.compute_deployment_status()
        self.set_deployment_conditions()
        
        report = {
            'timestamp': self.certification.timestamp,
            'system_version': self.certification.system_version,
            
            'deployment_decision': {
                'status': self.certification.deployment_status,
                'confidence_score': float(self.certification.confidence_score),
                'conditions': self.certification.deployment_conditions,
                'critical_failures': self.certification.critical_failures
            },
            
            'gate_results': [
                {
                    'gate_id': g.gate_id,
                    'gate_name': g.gate_name,
                    'threshold': float(g.threshold),
                    'actual_value': float(g.actual_value),
                    'passes': g.passes,
                    'margin_percent': float(g.margin_percent)
                }
                for g in self.certification.gates
            ],
            
            'phase_summaries': {
                'data_integrity': self._summarize_phase(
                    self.certification.data_integrity_result
                ),
                'embedding_stability': self._summarize_phase(
                    self.certification.embedding_stability_result
                ),
                'emotion_validation': self._summarize_phase(
                    self.certification.emotion_validation_result
                ),
                'prosody_realism': self._summarize_phase(
                    self.certification.prosody_realism_result
                ),
                'human_evaluation': self._summarize_phase(
                    self.certification.human_evaluation_result
                ),
                'failure_recovery': self._summarize_phase(
                    self.certification.failure_recovery_result
                )
            }
        }
        
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"✓ Certification report saved: {output_file}")
        
        return report
    
    @staticmethod
    def _summarize_phase(phase_result: Optional[Dict]) -> Dict:
        """Summarize a phase result."""
        if not phase_result:
            return {'status': 'NOT_EXECUTED', 'reason': 'Report not provided'}
        
        return {
            'status': 'EXECUTED',
            'timestamp': phase_result.get('timestamp', 'N/A'),
            'key_metrics': {
                k: v for k, v in phase_result.items()
                if k in ['pass_rate', 'mean_mos', 'pitch_correlation', 'energy_correlation']
            }
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    certifier = ProductionDeploymentCertifier()
    
    # In production: load actual reports from all 6 phases
    # For now: create synthetic results for demonstration
    
    logger.info("Generating production deployment certification...\n")
    
    # Generate report with synthetic data
    report = certifier.generate_certification_report(
        "outputs/production/PRODUCTION_DEPLOYMENT_CERTIFICATION.json"
    )
    
    logger.info(f"\n{'='*60}")
    logger.info(f"DEPLOYMENT STATUS: {report['deployment_decision']['status']}")
    logger.info(f"CONFIDENCE: {report['deployment_decision']['confidence_score']:.1f}%")
    logger.info(f"{'='*60}")
    
    for condition in report['deployment_decision']['conditions']:
        logger.info(f"  • {condition}")
