"""
REAL-WORLD PILOT: DEPLOYMENT GATE
Final GO / PILOT EXTENSION / HOLD decision based on real user data

Purpose:
- Aggregate metrics from all pilot phases
- Apply deployment gate logic
- Generate REAL_WORLD_PILOT_REPORT.json with final decision

Gate Logic:
  IF:
    MOS >= 3.8 AND
    Emotion accuracy >= 80% AND
    Dialect accuracy >= 80% AND
    Speaker consistency >= 85% AND
    Retry rate <= 20% AND
    No crash events
  THEN: deployment_status = "GO"
  
  ELSE IF metrics close but not meeting threshold:
    deployment_status = "PILOT EXTENSION"
  
  ELSE:
    deployment_status = "HOLD"

Author: Production ML & Product Reliability Engineer
Date: 2026-03-02
"""

import json
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class DeploymentCriteria:
    """Individual deployment criterion."""
    criterion_name: str
    threshold: float
    actual_value: float
    passes: bool
    margin_percent: float
    
    def __str__(self):
        status = "✓" if self.passes else "✗"
        return f"{status} {self.criterion_name}: {self.actual_value:.2f} (threshold: {self.threshold:.2f}, margin: {self.margin_percent:+.1f}%)"


class PilotDeploymentGate:
    """
    Final deployment decision gate for pilot validation.
    
    Deployment Thresholds:
    - MOS >= 3.8
    - Emotion accuracy >= 80%
    - Dialect accuracy >= 80%
    - Speaker consistency >= 85%
    - Retry rate <= 20%
    - Failure rate = 0% (no crashes)
    """
    
    # Hard thresholds
    THRESHOLD_MOS = 3.8
    THRESHOLD_EMOTION_ACCURACY = 0.80
    THRESHOLD_DIALECT_ACCURACY = 0.80
    THRESHOLD_SPEAKER_CONSISTENCY = 0.85
    THRESHOLD_RETRY_RATE = 0.20  # Maximum acceptable
    THRESHOLD_FAILURE_RATE = 0.0  # Zero tolerance for crashes
    
    # Margin for PILOT EXTENSION (within 10% of threshold)
    EXTENSION_MARGIN = 0.10
    
    def __init__(self, output_dir: str = "outputs/pilot"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.criteria: List[DeploymentCriteria] = []
        self.deployment_status: str = "HOLD"
        self.confidence_score: float = 0.0
        self.blocking_issues: List[str] = []
    
    def load_pilot_data(self,
                       human_feedback_file: str,
                       usage_log_file: str,
                       stability_file: str,
                       edge_case_file: Optional[str] = None) -> Dict:
        """Load all pilot validation data."""
        
        pilot_data = {}
        
        # Load human feedback
        try:
            with open(self.output_dir / human_feedback_file) as f:
                pilot_data['human_feedback'] = json.load(f)
            logger.info(f"✓ Loaded {human_feedback_file}")
        except FileNotFoundError:
            logger.error(f"✗ Human feedback not found: {human_feedback_file}")
            pilot_data['human_feedback'] = None
        
        # Load usage log
        try:
            with open(self.output_dir / usage_log_file) as f:
                pilot_data['usage_log'] = json.load(f)
            logger.info(f"✓ Loaded {usage_log_file}")
        except FileNotFoundError:
            logger.error(f"✗ Usage log not found: {usage_log_file}")
            pilot_data['usage_log'] = None
        
        # Load stability analysis
        try:
            with open(self.output_dir / stability_file) as f:
                pilot_data['stability'] = json.load(f)
            logger.info(f"✓ Loaded {stability_file}")
        except FileNotFoundError:
            logger.error(f"✗ Stability analysis not found: {stability_file}")
            pilot_data['stability'] = None
        
        # Load edge case report (optional)
        if edge_case_file:
            try:
                with open(self.output_dir / edge_case_file) as f:
                    pilot_data['edge_cases'] = json.load(f)
                logger.info(f"✓ Loaded {edge_case_file}")
            except FileNotFoundError:
                logger.warning(f"⚠ Edge case report not found: {edge_case_file}")
                pilot_data['edge_cases'] = None
        
        return pilot_data
    
    def evaluate_criteria(self, pilot_data: Dict) -> None:
        """Evaluate all deployment criteria."""
        
        logger.info("Evaluating deployment criteria...")
        
        # Check data availability
        if not pilot_data.get('human_feedback'):
            self.blocking_issues.append("Human feedback data not available")
            return
        
        if not pilot_data.get('usage_log'):
            self.blocking_issues.append("Usage log data not available")
            return
        
        if not pilot_data.get('stability'):
            self.blocking_issues.append("Stability analysis data not available")
            return
        
        human_metrics = pilot_data['human_feedback'].get('aggregate_metrics', {})
        usage_metrics = pilot_data['usage_log'].get('quality_metrics', {})
        stability_metrics = pilot_data['stability'].get('aggregate_stability', {})
        
        # Criterion 1: MOS
        mos = human_metrics.get('mean_mos', 0.0)
        mos_criterion = DeploymentCriteria(
            criterion_name="Mean Opinion Score",
            threshold=self.THRESHOLD_MOS,
            actual_value=mos,
            passes=(mos >= self.THRESHOLD_MOS),
            margin_percent=((mos - self.THRESHOLD_MOS) / self.THRESHOLD_MOS * 100) if mos > 0 else -100
        )
        self.criteria.append(mos_criterion)
        logger.info(str(mos_criterion))
        
        # Criterion 2: Emotion Accuracy
        emotion_acc = human_metrics.get('emotion_accuracy', 0.0)
        emotion_criterion = DeploymentCriteria(
            criterion_name="Emotion Accuracy",
            threshold=self.THRESHOLD_EMOTION_ACCURACY,
            actual_value=emotion_acc,
            passes=(emotion_acc >= self.THRESHOLD_EMOTION_ACCURACY),
            margin_percent=((emotion_acc - self.THRESHOLD_EMOTION_ACCURACY) / self.THRESHOLD_EMOTION_ACCURACY * 100) if emotion_acc > 0 else -100
        )
        self.criteria.append(emotion_criterion)
        logger.info(str(emotion_criterion))
        
        # Criterion 3: Dialect Accuracy
        dialect_acc = human_metrics.get('dialect_accuracy', 0.0)
        dialect_criterion = DeploymentCriteria(
            criterion_name="Dialect Accuracy",
            threshold=self.THRESHOLD_DIALECT_ACCURACY,
            actual_value=dialect_acc,
            passes=(dialect_acc >= self.THRESHOLD_DIALECT_ACCURACY),
            margin_percent=((dialect_acc - self.THRESHOLD_DIALECT_ACCURACY) / self.THRESHOLD_DIALECT_ACCURACY * 100) if dialect_acc > 0 else -100
        )
        self.criteria.append(dialect_criterion)
        logger.info(str(dialect_criterion))
        
        # Criterion 4: Speaker Consistency
        speaker_consistency = human_metrics.get('speaker_consistency', 0.0)
        speaker_criterion = DeploymentCriteria(
            criterion_name="Speaker Consistency",
            threshold=self.THRESHOLD_SPEAKER_CONSISTENCY,
            actual_value=speaker_consistency,
            passes=(speaker_consistency >= self.THRESHOLD_SPEAKER_CONSISTENCY),
            margin_percent=((speaker_consistency - self.THRESHOLD_SPEAKER_CONSISTENCY) / self.THRESHOLD_SPEAKER_CONSISTENCY * 100) if speaker_consistency > 0 else -100
        )
        self.criteria.append(speaker_criterion)
        logger.info(str(speaker_criterion))
        
        # Criterion 5: Retry Rate (lower is better)
        retry_rate = usage_metrics.get('retry_rate', 1.0)
        retry_criterion = DeploymentCriteria(
            criterion_name="Retry Rate",
            threshold=self.THRESHOLD_RETRY_RATE,
            actual_value=retry_rate,
            passes=(retry_rate <= self.THRESHOLD_RETRY_RATE),
            margin_percent=((self.THRESHOLD_RETRY_RATE - retry_rate) / self.THRESHOLD_RETRY_RATE * 100) if retry_rate < 1 else -100
        )
        self.criteria.append(retry_criterion)
        logger.info(str(retry_criterion))
        
        # Criterion 6: Failure Rate (zero tolerance)
        error_rate = usage_metrics.get('error_rate', 0.0)
        failure_criterion = DeploymentCriteria(
            criterion_name="Failure Rate",
            threshold=self.THRESHOLD_FAILURE_RATE,
            actual_value=error_rate,
            passes=(error_rate <= self.THRESHOLD_FAILURE_RATE),
            margin_percent=0.0 if error_rate == 0 else -100
        )
        self.criteria.append(failure_criterion)
        logger.info(str(failure_criterion))
    
    def compute_deployment_status(self) -> str:
        """Compute final GO / PILOT EXTENSION / HOLD decision."""
        
        if self.blocking_issues:
            self.deployment_status = "HOLD"
            self.confidence_score = 0.0
            logger.warning("HOLD: Blocking issues detected")
            for issue in self.blocking_issues:
                logger.warning(f"  - {issue}")
            return "HOLD"
        
        # Check for failures
        failed_criteria = [c for c in self.criteria if not c.passes]
        
        if not failed_criteria:
            # All criteria passed - check margin for GO vs PILOT EXTENSION
            margins = [c.margin_percent for c in self.criteria]
            mean_margin = np.mean(margins)
            
            if mean_margin > 10.0:
                self.deployment_status = "GO"
                self.confidence_score = float(min(100, 80 + mean_margin))
                logger.info(f"GO: All criteria passed with strong margin ({mean_margin:.1f}%)")
            else:
                self.deployment_status = "PILOT EXTENSION"
                self.confidence_score = float(min(100, 60 + (2 * mean_margin)))
                logger.info(f"PILOT EXTENSION: All criteria passed but margins low ({mean_margin:.1f}%)")
        
        else:
            # Check if close to threshold (within EXTENSION_MARGIN)
            close_failures = [c for c in failed_criteria if abs(c.margin_percent) < (self.EXTENSION_MARGIN * 100)]
            
            if close_failures and len(failed_criteria) <= 2:
                self.deployment_status = "PILOT EXTENSION"
                self.confidence_score = 50.0
                logger.warning(f"PILOT EXTENSION: {len(failed_criteria)} criteria failed but close to threshold")
            else:
                self.deployment_status = "HOLD"
                self.confidence_score = 0.0
                logger.warning(f"HOLD: {len(failed_criteria)} criteria failed")
            
            for criterion in failed_criteria:
                logger.warning(f"  - {criterion.criterion_name}: {criterion.actual_value:.2f} < {criterion.threshold:.2f}")
        
        return self.deployment_status
    
    def generate_pilot_report(self,
                             pilot_data: Dict,
                             output_file: Optional[str] = None) -> Dict:
        """Generate REAL_WORLD_PILOT_REPORT.json."""
        
        self.evaluate_criteria(pilot_data)
        self.compute_deployment_status()
        
        # Extract key metrics
        human_metrics = pilot_data.get('human_feedback', {}).get('aggregate_metrics', {})
        usage_metrics = pilot_data.get('usage_log', {}).get('quality_metrics', {})
        
        report = {
            'timestamp': str(datetime.now()),
            'pilot_type': 'REAL_WORLD_USER_VALIDATION',
            'data_source': 'REAL_HUMAN_USERS',
            
            'deployment_decision': {
                'status': self.deployment_status,
                'confidence_score': float(self.confidence_score),
                'blocking_issues': self.blocking_issues
            },
            
            'key_metrics': {
                'mean_mos': float(human_metrics.get('mean_mos', 0.0)),
                'emotion_accuracy': float(human_metrics.get('emotion_accuracy', 0.0)),
                'dialect_accuracy': float(human_metrics.get('dialect_accuracy', 0.0)),
                'speaker_consistency': float(human_metrics.get('speaker_consistency', 0.0)),
                'retry_rate': float(usage_metrics.get('retry_rate', 0.0)),
                'failure_rate': float(usage_metrics.get('error_rate', 0.0)),
                'user_daily_use_acceptance': float(human_metrics.get('daily_use_acceptance_rate', 0.0))
            },
            
            'deployment_criteria': [
                {
                    'criterion': c.criterion_name,
                    'threshold': float(c.threshold),
                    'actual': float(c.actual_value),
                    'passes': c.passes,
                    'margin_percent': float(c.margin_percent)
                }
                for c in self.criteria
            ],
            
            'deployment_thresholds': {
                'mos_minimum': self.THRESHOLD_MOS,
                'emotion_accuracy_minimum': self.THRESHOLD_EMOTION_ACCURACY,
                'dialect_accuracy_minimum': self.THRESHOLD_DIALECT_ACCURACY,
                'speaker_consistency_minimum': self.THRESHOLD_SPEAKER_CONSISTENCY,
                'retry_rate_maximum': self.THRESHOLD_RETRY_RATE,
                'failure_rate_maximum': self.THRESHOLD_FAILURE_RATE
            },
            
            'recommendations': self._generate_recommendations()
        }
        
        if output_file:
            output_path = self.output_dir / output_file
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Pilot report saved: {output_path}")
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate deployment recommendations."""
        
        recommendations = []
        
        if self.deployment_status == "GO":
            recommendations.append("System approved for public deployment")
            recommendations.append("No restrictions on user base")
            recommendations.append("Continue monitoring user feedback")
        
        elif self.deployment_status == "PILOT EXTENSION":
            recommendations.append("Extend pilot with additional users")
            recommendations.append("Target 20+ users for next phase")
            recommendations.append("Focus on improving weak criteria")
            
            # Identify weak areas
            weak_criteria = [c for c in self.criteria if c.margin_percent < 5.0]
            for criterion in weak_criteria:
                recommendations.append(f"Improve {criterion.criterion_name} (currently {criterion.actual_value:.2f})")
        
        else:  # HOLD
            recommendations.append("DO NOT DEPLOY to production")
            recommendations.append("Address critical failures")
            recommendations.append("Re-run pilot after fixes")
            
            # List failures
            failed = [c for c in self.criteria if not c.passes]
            for criterion in failed:
                recommendations.append(f"Fix {criterion.criterion_name}: {criterion.actual_value:.2f} < {criterion.threshold:.2f}")
        
        return recommendations


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    gate = PilotDeploymentGate(output_dir="outputs/pilot")
    
    logger.info("Loading pilot validation data...")
    
    # Load all pilot data
    pilot_data = gate.load_pilot_data(
        human_feedback_file="PILOT_HUMAN_FEEDBACK.json",
        usage_log_file="PILOT_USAGE_LOG.json",
        stability_file="PILOT_STABILITY_ANALYSIS.json",
        edge_case_file="EDGE_CASE_REPORT.json"
    )
    
    # Generate final deployment report
    report = gate.generate_pilot_report(
        pilot_data=pilot_data,
        output_file="REAL_WORLD_PILOT_REPORT.json"
    )
    
    logger.info(f"{'='*70}")
    logger.info(f"DEPLOYMENT DECISION: {report['deployment_decision']['status']}")
    logger.info(f"CONFIDENCE: {report['deployment_decision']['confidence_score']:.1f}%")
    logger.info(f"{'='*70}")
    
    logger.info("Key Metrics:")
    for key, value in report['key_metrics'].items():
        logger.info(f"  {key}: {value:.2f}")
    
    logger.info("Recommendations:")
    for rec in report['recommendations']:
        logger.info(f"  • {rec}")
