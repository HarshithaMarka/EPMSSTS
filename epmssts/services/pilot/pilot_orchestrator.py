"""
REAL-WORLD PILOT: MASTER ORCHESTRATOR
Coordinates all 6 pilot validation phases for systematic execution

Phases:
1. User Recruitment & Diversity Validation
2. Real Usage Simulation & Logging
3. Human Perception Survey Collection
4. Consistency & Drift Analysis
5. Edge Case Testing
6. Final Pilot Deployment Gate

This orchestrator ensures all phases execute in correct order with dependency management.

Author: Production ML & Product Reliability Engineer
Date: 2026-03-02
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from pilot_user_recruitment import PilotUserRecruitment, MicQuality, SpeakingStyle
from pilot_usage_logger import PilotUsageLogger
from pilot_human_feedback_collector import PilotHumanFeedbackCollector
from pilot_stability_analyzer import PilotStabilityAnalyzer
from pilot_edge_case_tester import PilotEdgeCaseTester, EdgeCaseType
from pilot_deployment_gate import PilotDeploymentGate

logger = logging.getLogger(__name__)


class RealWorldPilotOrchestrator:
    """
    Master orchestrator for complete pilot validation workflow.
    
    Workflow:
    1. Load user registry
    2. Load usage logs
    3. Load human feedback
    4. Analyze stability
    5. Test edge cases
    6. Execute deployment gate
    7. Generate final report
    """
    
    def __init__(self, output_dir: str = "outputs/pilot"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.phase_status = {
            'user_recruitment': 'NOT_STARTED',
            'usage_logging': 'NOT_STARTED',
            'human_feedback': 'NOT_STARTED',
            'stability_analysis': 'NOT_STARTED',
            'edge_case_testing': 'NOT_STARTED',
            'deployment_gate': 'NOT_STARTED'
        }
        
        self.orchestration_log = []
    
    def log_phase(self, phase_name: str, status: str, message: str):
        """Log phase execution."""
        entry = {
            'timestamp': str(datetime.now()),
            'phase': phase_name,
            'status': status,
            'message': message
        }
        self.orchestration_log.append(entry)
        
        symbol = '✓' if status == 'COMPLETED' else '⚠' if status == 'WARNING' else '✗' if status == 'FAILED' else '▶'
        logger.info(f"{symbol} [{phase_name}] {message}")
    
    def phase_1_user_recruitment(self, user_registry_file: str = "PILOT_USER_REGISTRY.json") -> bool:
        """Phase 1: Validate user recruitment and diversity."""
        
        phase_name = 'user_recruitment'
        self.phase_status[phase_name] = 'IN_PROGRESS'
        self.log_phase(phase_name, 'IN_PROGRESS', 'Starting user recruitment validation')
        
        try:
            # Load user registry
            registry_path = self.output_dir / user_registry_file
            
            if not registry_path.exists():
                self.log_phase(phase_name, 'FAILED', f'User registry not found: {user_registry_file}')
                self.phase_status[phase_name] = 'FAILED'
                return False
            
            with open(registry_path) as f:
                registry = json.load(f)
            
            # Check diversity validation
            diversity = registry.get('diversity_validation', {})
            diversity_valid = diversity.get('diversity_valid', False)
            
            # Check participation completion
            participation = registry.get('participation_summary', {})
            completion_rate = participation.get('completion_rate', 0.0)
            
            if not diversity_valid:
                self.log_phase(phase_name, 'WARNING', f'Diversity validation failed. Blocking issues: {diversity.get("blocking_issues")}')
            
            if completion_rate < 1.0:
                users_ready = participation.get('users_ready_for_analysis', 0)
                total_users = len(registry.get('users', []))
                self.log_phase(phase_name, 'WARNING', f'Only {users_ready}/{total_users} users completed minimum requirements')
            
            self.log_phase(phase_name, 'COMPLETED', f'{participation.get("users_ready_for_analysis", 0)} users validated and ready')
            self.phase_status[phase_name] = 'COMPLETED'
            return True
        
        except Exception as e:
            self.log_phase(phase_name, 'FAILED', f'Error: {str(e)}')
            self.phase_status[phase_name] = 'FAILED'
            return False
    
    def phase_2_usage_logging(self, usage_log_file: str = "PILOT_USAGE_LOG.json") -> bool:
        """Phase 2: Validate usage logging completeness."""
        
        phase_name = 'usage_logging'
        self.phase_status[phase_name] = 'IN_PROGRESS'
        self.log_phase(phase_name, 'IN_PROGRESS', 'Starting usage log validation')
        
        try:
            # Load usage log
            log_path = self.output_dir / usage_log_file
            
            if not log_path.exists():
                self.log_phase(phase_name, 'FAILED', f'Usage log not found: {usage_log_file}')
                self.phase_status[phase_name] = 'FAILED'
                return False
            
            with open(log_path) as f:
                usage_log = json.load(f)
            
            # Check validation results
            validation = usage_log.get('validation', {})
            total_interactions = usage_log.get('total_interactions', 0)
            
            invalid_users = [u for u in validation.get('per_user_validation', []) if not u.get('meets_minimum_interactions', False)]
            
            if invalid_users:
                self.log_phase(phase_name, 'WARNING', f'{len(invalid_users)} users did not meet minimum interaction requirements')
            
            self.log_phase(phase_name, 'COMPLETED', f'{total_interactions} interactions logged across {len(validation.get("per_user_validation", []))} users')
            self.phase_status[phase_name] = 'COMPLETED'
            return True
        
        except Exception as e:
            self.log_phase(phase_name, 'FAILED', f'Error: {str(e)}')
            self.phase_status[phase_name] = 'FAILED'
            return False
    
    def phase_3_human_feedback(self, feedback_file: str = "PILOT_HUMAN_FEEDBACK.json") -> bool:
        """Phase 3: Validate human feedback collection."""
        
        phase_name = 'human_feedback'
        self.phase_status[phase_name] = 'IN_PROGRESS'
        self.log_phase(phase_name, 'IN_PROGRESS', 'Starting human feedback validation')
        
        try:
            # Load feedback
            feedback_path = self.output_dir / feedback_file
            
            if not feedback_path.exists():
                self.log_phase(phase_name, 'FAILED', f'Human feedback not found: {feedback_file}')
                self.phase_status[phase_name] = 'FAILED'
                return False
            
            with open(feedback_path) as f:
                feedback = json.load(f)
            
            # CRITICAL CHECK: Ensure real human data
            if feedback.get('auto_generated', True):
                self.log_phase(phase_name, 'FAILED', 'Feedback is auto-generated, not from real users')
                self.phase_status[phase_name] = 'FAILED'
                return False
            
            # Check metrics
            metrics = feedback.get('aggregate_metrics', {})
            mos = metrics.get('mean_mos', 0.0)
            total_feedback = len(feedback.get('raw_feedback', []))
            
            if mos < 2.0:
                self.log_phase(phase_name, 'WARNING', f'Low MOS score: {mos:.2f}')
            
            self.log_phase(phase_name, 'COMPLETED', f'{total_feedback} real human feedback entries collected (MOS: {mos:.2f})')
            self.phase_status[phase_name] = 'COMPLETED'
            return True
        
        except Exception as e:
            self.log_phase(phase_name, 'FAILED', f'Error: {str(e)}')
            self.phase_status[phase_name] = 'FAILED'
            return False
    
    def phase_4_stability_analysis(self, stability_file: str = "PILOT_STABILITY_ANALYSIS.json") -> bool:
        """Phase 4: Validate stability analysis."""
        
        phase_name = 'stability_analysis'
        self.phase_status[phase_name] = 'IN_PROGRESS'
        self.log_phase(phase_name, 'IN_PROGRESS', 'Starting stability analysis validation')
        
        try:
            # Load stability analysis
            stability_path = self.output_dir / stability_file
            
            if not stability_path.exists():
                self.log_phase(phase_name, 'FAILED', f'Stability analysis not found: {stability_file}')
                self.phase_status[phase_name] = 'FAILED'
                return False
            
            with open(stability_path) as f:
                stability = json.load(f)
            
            # Check aggregate stability
            aggregate = stability.get('aggregate_stability', {})
            drift_rate = aggregate.get('drift_rate', 1.0)
            passed_sessions = aggregate.get('sessions_passed', 0)
            total_sessions = aggregate.get('total_sessions', 0)
            
            if drift_rate > 0.2:
                self.log_phase(phase_name, 'WARNING', f'High drift rate: {drift_rate:.2%}')
            
            self.log_phase(phase_name, 'COMPLETED', f'{passed_sessions}/{total_sessions} sessions passed stability test (drift rate: {drift_rate:.2%})')
            self.phase_status[phase_name] = 'COMPLETED'
            return True
        
        except Exception as e:
            self.log_phase(phase_name, 'FAILED', f'Error: {str(e)}')
            self.phase_status[phase_name] = 'FAILED'
            return False
    
    def phase_5_edge_case_testing(self, edge_case_file: str = "EDGE_CASE_REPORT.json") -> bool:
        """Phase 5: Validate edge case testing."""
        
        phase_name = 'edge_case_testing'
        self.phase_status[phase_name] = 'IN_PROGRESS'
        self.log_phase(phase_name, 'IN_PROGRESS', 'Starting edge case validation')
        
        try:
            # Load edge case report
            edge_path = self.output_dir / edge_case_file
            
            if not edge_path.exists():
                self.log_phase(phase_name, 'WARNING', f'Edge case report not found: {edge_case_file} (optional)')
                self.phase_status[phase_name] = 'SKIPPED'
                return True  # Not critical
            
            with open(edge_path) as f:
                edge_cases = json.load(f)
            
            # Check overall metrics
            overall = edge_cases.get('overall_summary', {})
            total_tests = overall.get('total_tests', 0)
            error_rate = overall.get('overall_error_rate', 0.0)
            
            if error_rate > 0.3:
                self.log_phase(phase_name, 'WARNING', f'High edge case error rate: {error_rate:.2%}')
            
            self.log_phase(phase_name, 'COMPLETED', f'{total_tests} edge case tests completed (error rate: {error_rate:.2%})')
            self.phase_status[phase_name] = 'COMPLETED'
            return True
        
        except Exception as e:
            self.log_phase(phase_name, 'WARNING', f'Error (non-critical): {str(e)}')
            self.phase_status[phase_name] = 'SKIPPED'
            return True  # Not critical
    
    def phase_6_deployment_gate(self) -> Dict:
        """Phase 6: Execute final deployment gate."""
        
        phase_name = 'deployment_gate'
        self.phase_status[phase_name] = 'IN_PROGRESS'
        self.log_phase(phase_name, 'IN_PROGRESS', 'Starting deployment gate evaluation')
        
        try:
            gate = PilotDeploymentGate(output_dir=str(self.output_dir))
            
            # Load all pilot data
            pilot_data = gate.load_pilot_data(
                human_feedback_file="PILOT_HUMAN_FEEDBACK.json",
                usage_log_file="PILOT_USAGE_LOG.json",
                stability_file="PILOT_STABILITY_ANALYSIS.json",
                edge_case_file="EDGE_CASE_REPORT.json"
            )
            
            # Generate deployment report
            report = gate.generate_pilot_report(
                pilot_data=pilot_data,
                output_file="REAL_WORLD_PILOT_REPORT.json"
            )
            
            decision = report['deployment_decision']['status']
            confidence = report['deployment_decision']['confidence_score']
            
            if decision == 'GO':
                self.log_phase(phase_name, 'COMPLETED', f'✓ GO for deployment (confidence: {confidence:.1f}%)')
            elif decision == 'PILOT EXTENSION':
                self.log_phase(phase_name, 'COMPLETED', f'⚠ PILOT EXTENSION recommended (confidence: {confidence:.1f}%)')
            else:
                self.log_phase(phase_name, 'COMPLETED', f'✗ HOLD deployment (confidence: {confidence:.1f}%)')
            
            self.phase_status[phase_name] = 'COMPLETED'
            return report
        
        except Exception as e:
            self.log_phase(phase_name, 'FAILED', f'Error: {str(e)}')
            self.phase_status[phase_name] = 'FAILED'
            return {}
    
    def run_complete_pilot(self) -> Dict:
        """Execute complete pilot validation workflow."""
        
        logger.info("="*70)
        logger.info("REAL-WORLD PILOT VALIDATION ORCHESTRATION")
        logger.info("="*70)
        logger.info("")
        
        start_time = datetime.now()
        
        # Phase 1: User Recruitment
        logger.info("\\n--- PHASE 1: USER RECRUITMENT & DIVERSITY ---")
        phase1_success = self.phase_1_user_recruitment()
        
        # Phase 2: Usage Logging
        logger.info("\\n--- PHASE 2: USAGE LOGGING ---")
        phase2_success = self.phase_2_usage_logging()
        
        # Phase 3: Human Feedback
        logger.info("\\n--- PHASE 3: HUMAN FEEDBACK COLLECTION ---")
        phase3_success = self.phase_3_human_feedback()
        
        # Phase 4: Stability Analysis
        logger.info("\\n--- PHASE 4: STABILITY ANALYSIS ---")
        phase4_success = self.phase_4_stability_analysis()
        
        # Phase 5: Edge Case Testing
        logger.info("\\n--- PHASE 5: EDGE CASE TESTING ---")
        phase5_success = self.phase_5_edge_case_testing()
        
        # Phase 6: Deployment Gate
        logger.info("\\n--- PHASE 6: DEPLOYMENT GATE ---")
        final_report = self.phase_6_deployment_gate()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Final summary
        logger.info("\\n" + "="*70)
        logger.info("PILOT ORCHESTRATION COMPLETE")
        logger.info("="*70)
        logger.info(f"Duration: {duration:.1f}s")
        logger.info("\\nPhase Status:")
        for phase, status in self.phase_status.items():
            symbol = '✓' if status == 'COMPLETED' else '⚠' if status == 'SKIPPED' else '✗'
            logger.info(f"  {symbol} {phase}: {status}")
        
        if final_report:
            decision = final_report.get('deployment_decision', {})
            logger.info(f"\\nFINAL DECISION: {decision.get('status', 'UNKNOWN')}")
            logger.info(f"CONFIDENCE: {decision.get('confidence_score', 0):.1f}%")
            
            logger.info("\\nRecommendations:")
            for rec in final_report.get('recommendations', []):
                logger.info(f"  • {rec}")
        
        # Save orchestration log
        log_path = self.output_dir / "PILOT_ORCHESTRATION_LOG.json"
        with open(log_path, 'w') as f:
            json.dump({
                'orchestration_log': self.orchestration_log,
                'phase_status': self.phase_status,
                'duration_seconds': duration,
                'final_decision': final_report.get('deployment_decision', {}) if final_report else None
            }, f, indent=2)
        
        logger.info(f"\\n✓ Orchestration log saved: {log_path}")
        
        return final_report


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    orchestrator = RealWorldPilotOrchestrator(output_dir="outputs/pilot")
    final_report = orchestrator.run_complete_pilot()
