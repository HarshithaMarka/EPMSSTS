"""
REAL-WORLD PILOT: EDGE CASE TESTER
Test system behavior under challenging real-world conditions

Purpose:
- Test low volume input
- Test slight background noise
- Test emotional whisper
- Test fast speech
- Test mild sarcasm
- Track emotion misclassification rate
- Track retry rate
- Track failure recovery success

Author: Production ML & Product Reliability Engineer
Date: 2026-03-02
"""

import json
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EdgeCaseType(Enum):
    """Types of edge cases."""
    LOW_VOLUME = "low_volume"
    BACKGROUND_NOISE = "background_noise"
    EMOTIONAL_WHISPER = "emotional_whisper"
    FAST_SPEECH = "fast_speech"
    MILD_SARCASM = "mild_sarcasm"


@dataclass
class EdgeCaseTest:
    """Single edge case test result."""
    test_id: str
    user_id: str
    edge_case_type: EdgeCaseType
    
    # Input characteristics
    input_audio_path: str
    expected_emotion: str
    expected_dialect: str
    
    # System response
    detected_emotion: str
    detected_dialect: str
    emotion_correct: bool
    dialect_correct: bool
    
    # Performance
    processing_time_ms: float
    retry_occurred: bool
    retry_count: int
    failure_recovered: bool
    
    # Errors
    error_occurred: bool = False
    error_message: Optional[str] = None
    stage: Optional[str] = None
    exception_type: Optional[str] = None
    timeout_breach: bool = False
    memory_spike: bool = False
    circuit_breaker_activation: bool = False
    retry_exhausted: bool = False
    silence_misclassification: bool = False
    async_cancellation: bool = False


class PilotEdgeCaseTester:
    """
    Test system robustness under challenging conditions.
    
    Requirements:
    - Handle low volume input
    - Handle slight background noise
    - Handle emotional whisper
    - Handle fast speech
    - Handle mild sarcasm
    - Track misclassification rates
    - Verify failure recovery
    """
    
    def __init__(self, output_dir: str = "outputs/pilot"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.edge_case_tests: List[EdgeCaseTest] = []
    
    def test_edge_case(self,
                      user_id: str,
                      edge_case_type: EdgeCaseType,
                      input_audio_path: str,
                      expected_emotion: str,
                      expected_dialect: str,
                      detected_emotion: str,
                      detected_dialect: str,
                      processing_time_ms: float,
                      retry_occurred: bool = False,
                      retry_count: int = 0,
                      failure_recovered: bool = True,
                      error_occurred: bool = False,
                      error_message: Optional[str] = None,
                      stage: Optional[str] = None,
                      exception_type: Optional[str] = None,
                      timeout_breach: bool = False,
                      memory_spike: bool = False,
                      circuit_breaker_activation: bool = False,
                      retry_exhausted: bool = False,
                      silence_misclassification: bool = False,
                      async_cancellation: bool = False) -> EdgeCaseTest:
        """Register an edge case test result."""
        
        test_id = f"edge_{edge_case_type.value}_{len(self.edge_case_tests):03d}"
        
        test = EdgeCaseTest(
            test_id=test_id,
            user_id=user_id,
            edge_case_type=edge_case_type,
            input_audio_path=input_audio_path,
            expected_emotion=expected_emotion,
            expected_dialect=expected_dialect,
            detected_emotion=detected_emotion,
            detected_dialect=detected_dialect,
            emotion_correct=(expected_emotion.lower() == detected_emotion.lower()),
            dialect_correct=(expected_dialect.lower() == detected_dialect.lower()),
            processing_time_ms=processing_time_ms,
            retry_occurred=retry_occurred,
            retry_count=retry_count,
            failure_recovered=failure_recovered,
            error_occurred=error_occurred,
            error_message=error_message,
            stage=stage,
            exception_type=exception_type,
            timeout_breach=timeout_breach,
            memory_spike=memory_spike,
            circuit_breaker_activation=circuit_breaker_activation,
            retry_exhausted=retry_exhausted,
            silence_misclassification=silence_misclassification,
            async_cancellation=async_cancellation
        )
        
        self.edge_case_tests.append(test)
        
        logger.info(f"✓ Edge case {test_id}: emotion {'✓' if test.emotion_correct else '✗'}, "
                   f"retries {retry_count}")
        
        return test
    
    def aggregate_by_edge_type(self, edge_type: EdgeCaseType) -> Dict:
        """Aggregate results for a specific edge case type."""
        
        tests = [t for t in self.edge_case_tests if t.edge_case_type == edge_type]
        
        if not tests:
            return {
                'edge_case_type': edge_type.value,
                'no_tests': True
            }
        
        emotion_correct = sum(1 for t in tests if t.emotion_correct)
        dialect_correct = sum(1 for t in tests if t.dialect_correct)
        retries = sum(t.retry_count for t in tests)
        errors = sum(1 for t in tests if t.error_occurred)
        recovery_success = sum(1 for t in tests if t.failure_recovered or not t.error_occurred)
        
        return {
            'edge_case_type': edge_type.value,
            'total_tests': len(tests),
            'emotion_accuracy': float(emotion_correct / len(tests)),
            'dialect_accuracy': float(dialect_correct / len(tests)),
            'total_retries': retries,
            'retry_rate': float(sum(1 for t in tests if t.retry_occurred) / len(tests)),
            'error_count': errors,
            'error_rate': float(errors / len(tests)),
            'recovery_success_rate': float(recovery_success / len(tests)),
            'mean_processing_time_ms': float(np.mean([t.processing_time_ms for t in tests]))
        }
    
    def generate_edge_case_report(self, output_file: Optional[str] = None) -> Dict:
        """Generate EDGE_CASE_REPORT.json"""
        
        if not self.edge_case_tests:
            return {'status': 'NO_TESTS', 'tests': []}
        
        # Aggregate by edge case type
        edge_type_summaries = {
            edge_type.value: self.aggregate_by_edge_type(edge_type)
            for edge_type in EdgeCaseType
        }
        
        # Overall aggregates
        emotion_correct = sum(1 for t in self.edge_case_tests if t.emotion_correct)
        retries = sum(t.retry_count for t in self.edge_case_tests)
        errors = sum(1 for t in self.edge_case_tests if t.error_occurred)
        recovery_success = sum(1 for t in self.edge_case_tests if t.failure_recovered or not t.error_occurred)
        
        report = {
            'timestamp': str(datetime.now()),
            
            'overall_metrics': {
                'total_edge_case_tests': len(self.edge_case_tests),
                'emotion_misclassification_rate': 1.0 - (emotion_correct / len(self.edge_case_tests)),
                'overall_retry_rate': float(sum(1 for t in self.edge_case_tests if t.retry_occurred) / len(self.edge_case_tests)),
                'overall_error_rate': float(errors / len(self.edge_case_tests)),
                'failure_recovery_success_rate': float(recovery_success / len(self.edge_case_tests))
            },
            
            'per_edge_type_results': edge_type_summaries,
            
            'edge_case_tests': [
                {
                    'test_id': t.test_id,
                    'user_id': t.user_id,
                    'edge_case_type': t.edge_case_type.value,
                    'expected_emotion': t.expected_emotion,
                    'detected_emotion': t.detected_emotion,
                    'emotion_correct': t.emotion_correct,
                    'expected_dialect': t.expected_dialect,
                    'detected_dialect': t.detected_dialect,
                    'dialect_correct': t.dialect_correct,
                    'processing_time_ms': float(t.processing_time_ms),
                    'retry_occurred': t.retry_occurred,
                    'retry_count': t.retry_count,
                    'failure_recovered': t.failure_recovered,
                    'error_occurred': t.error_occurred,
                    'error_message': t.error_message,
                    'stage': t.stage,
                    'exception_type': t.exception_type,
                    'timeout_breach': t.timeout_breach,
                    'memory_spike': t.memory_spike,
                    'circuit_breaker_activation': t.circuit_breaker_activation,
                    'retry_exhausted': t.retry_exhausted,
                    'silence_misclassification': t.silence_misclassification,
                    'async_cancellation': t.async_cancellation
                }
                for t in self.edge_case_tests
            ]
        }
        
        if output_file:
            output_path = self.output_dir / output_file
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"✓ Edge case report saved: {output_path}")
        
        return report


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    tester = PilotEdgeCaseTester(output_dir="outputs/pilot")
    
    logger.info("Simulating edge case testing...\n")
    
    np.random.seed(42)
    emotions = ['neutral', 'sad', 'happy', 'angry', 'whisper']
    dialects = ['neutral', 'andhra', 'telangana', 'mixed']
    
    # Test each edge case type
    edge_cases = [
        EdgeCaseType.LOW_VOLUME,
        EdgeCaseType.BACKGROUND_NOISE,
        EdgeCaseType.EMOTIONAL_WHISPER,
        EdgeCaseType.FAST_SPEECH,
        EdgeCaseType.MILD_SARCASM
    ]
    
    for edge_type in edge_cases:
        # 5-10 tests per edge case type
        num_tests = np.random.randint(5, 11)
        
        for test_idx in range(num_tests):
            user_id = f"user_{np.random.randint(0, 10):03d}"
            expected_emotion = np.random.choice(emotions)
            expected_dialect = np.random.choice(dialects)
            
            # Edge cases have higher error rates
            misclassification_prob = 0.25 if edge_type in [EdgeCaseType.FAST_SPEECH, EdgeCaseType.MILD_SARCASM] else 0.15
            
            detected_emotion = expected_emotion if np.random.rand() > misclassification_prob else np.random.choice(emotions)
            detected_dialect = expected_dialect if np.random.rand() > 0.10 else np.random.choice(dialects)
            
            processing_time = np.random.uniform(300, 2000)
            retry = np.random.rand() > 0.75
            retry_count = np.random.randint(1, 3) if retry else 0
            
            error = np.random.rand() > 0.95
            recovery = not error or np.random.rand() > 0.2
            
            tester.test_edge_case(
                user_id=user_id,
                edge_case_type=edge_type,
                input_audio_path=f"outputs/pilot/edge/{edge_type.value}_{test_idx}.wav",
                expected_emotion=expected_emotion,
                expected_dialect=expected_dialect,
                detected_emotion=detected_emotion,
                detected_dialect=detected_dialect,
                processing_time_ms=processing_time,
                retry_occurred=retry,
                retry_count=retry_count,
                failure_recovered=recovery,
                error_occurred=error,
                error_message="Timeout" if error else None
            )
    
    # Generate report
    report = tester.generate_edge_case_report("EDGE_CASE_REPORT.json")
    
    logger.info(f"\n✓ Edge case testing complete")
    logger.info(f"  Total tests: {report['overall_metrics']['total_edge_case_tests']}")
    logger.info(f"  Misclassification rate: {report['overall_metrics']['emotion_misclassification_rate']:.1%}")
    logger.info(f"  Retry rate: {report['overall_metrics']['overall_retry_rate']:.1%}")
    logger.info(f"  Recovery success: {report['overall_metrics']['failure_recovery_success_rate']:.1%}")
