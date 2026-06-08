"""
REAL-WORLD PILOT: INTEGRATION HARNESS
End-to-end demonstration of complete pilot validation workflow

Purpose:
- Demonstrate all 6 pilot phases working together
- Generate simulated pilot data for framework testing
- Validate orchestration flow
- Generate all required reports

NOTE: This harness uses SIMULATED data for testing the framework.
      For production, replace with REAL user interactions and feedback.

Author: Production ML & Product Reliability Engineer
Date: 2026-03-02
"""

import numpy as np
import logging
from pathlib import Path
from typing import List, Tuple

from pilot_user_recruitment import (
    PilotUserRecruitment, UserProfile, 
    MicQuality, SpeakingStyle
)
from pilot_usage_logger import PilotUsageLogger, InteractionLog
from pilot_human_feedback_collector import PilotHumanFeedbackCollector, UserFeedback
from pilot_stability_analyzer import PilotStabilityAnalyzer
from pilot_edge_case_tester import PilotEdgeCaseTester, EdgeCaseType
from pilot_orchestrator import RealWorldPilotOrchestrator
from reliability_stabilizer import ReliabilityStabilizer

logger = logging.getLogger(__name__)


class PilotIntegrationHarness:
    """
    Integration harness for complete pilot validation workflow.
    
    Generates simulated pilot data to test framework functionality.
    """
    
    def __init__(self, output_dir: str = "outputs/pilot"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize all components
        self.recruitment = PilotUserRecruitment(output_dir=str(self.output_dir))
        self.usage_logger = PilotUsageLogger(output_dir=str(self.output_dir))
        self.feedback_collector = PilotHumanFeedbackCollector(output_dir=str(self.output_dir))
        self.stability_analyzer = PilotStabilityAnalyzer(output_dir=str(self.output_dir))
        self.edge_case_tester = PilotEdgeCaseTester(output_dir=str(self.output_dir))
        self.reliability_stabilizer = ReliabilityStabilizer(stage_timeout_ms=900.0, max_concurrent_gpu_ops=2)
    
    def simulate_user_recruitment(self) -> List[str]:
        """Simulate recruiting 10 diverse users."""
        
        logger.info("\\n--- SIMULATING USER RECRUITMENT ---")
        
        users = [
            ("user_001", "Alice Kumar", MicQuality.PROFESSIONAL, SpeakingStyle.CLEAR, "high", "neutral"),
            ("user_002", "Raj Patel", MicQuality.CONSUMER, SpeakingStyle.FAST, "medium", "andhra"),
            ("user_003", "Priya Singh", MicQuality.MOBILE, SpeakingStyle.SOFT, "low", "telangana"),
            ("user_004", "Arjun Reddy", MicQuality.BUDGET, SpeakingStyle.EXPRESSIVE, "high", "mixed"),
            ("user_005", "Lakshmi Rao", MicQuality.CONSUMER, SpeakingStyle.MONOTONE, "medium", "andhra"),
            ("user_006", "Vikram Joshi", MicQuality.PROFESSIONAL, SpeakingStyle.CLEAR, "high", "neutral"),
            ("user_007", "Deepa Nair", MicQuality.MOBILE, SpeakingStyle.FAST, "medium", "telangana"),
            ("user_008", "Sanjay Mehta", MicQuality.BUDGET, SpeakingStyle.SOFT, "low", "mixed"),
            ("user_009", "Anita Sharma", MicQuality.CONSUMER, SpeakingStyle.EXPRESSIVE, "high", "andhra"),
            ("user_010", "Rohit Desai", MicQuality.PROFESSIONAL, SpeakingStyle.MONOTONE, "medium", "neutral"),
        ]
        
        user_ids = []
        for user_id, name, mic, speaking, emotion_level, dialect in users:
            self.recruitment.register_user(
                user_id=user_id,
                name=name,
                mic_quality=mic,
                speaking_style=speaking,
                emotional_expressiveness=emotion_level,
                dialect_background=dialect
            )
            user_ids.append(user_id)
            logger.info(f"✓ Registered {name} ({user_id})")
        
        # Simulate participation progress
        emotions = ["neutral", "happy", "sad", "angry", "excited", "calm"]
        
        for user_id in user_ids:
            # Each user does 5-8 interactions
            num_interactions = np.random.randint(5, 9)
            
            for i in range(num_interactions):
                emotion = np.random.choice(emotions)
                dialect_sample = (i == 0)  # First interaction includes dialect
                
                self.recruitment.update_user_progress(
                    user_id=user_id,
                    emotion=emotion,
                    dialect_sample=dialect_sample
                )
        
        logger.info(f"\\n✓ {len(user_ids)} users recruited with diverse profiles")
        
        return user_ids
    
    def simulate_user_interactions(self, user_ids: List[str]) -> List[Tuple[str, str]]:
        """Simulate user interactions and multi-turn conversations."""
        
        logger.info("\\n--- SIMULATING USER INTERACTIONS ---")
        
        emotions = ["neutral", "happy", "sad", "angry", "excited", "calm"]
        dialects = ["neutral", "andhra", "telangana", "mixed"]
        
        conversation_sessions = []
        
        for user_id in user_ids:
            # Start a multi-turn conversation (5-10 turns)
            num_turns = np.random.randint(5, 11)
            session_id = self.usage_logger.start_conversation_session(user_id)
            
            for turn in range(num_turns):
                emotion = np.random.choice(emotions)
                dialect = np.random.choice(dialects)
                
                # Simulate processing
                processing_time = np.random.randint(200, 800)
                retry = (np.random.random() < 0.1)  # 10% retry rate
                injected_fault = (np.random.random() < 0.05)

                def _worker():
                    if injected_fault:
                        raise TimeoutError("injected_timeout")
                    return {
                        "emotion_detected": emotion,
                        "dialect_detected": dialect,
                    }

                stabilized_output, diagnostics = self.reliability_stabilizer.stabilize_interaction(
                    stage="runtime_inference",
                    worker=_worker,
                    timeout_ms=900.0,
                )

                final_emotion = stabilized_output.get("emotion_detected", emotion)
                final_dialect = stabilized_output.get("dialect_detected", dialect)
                recovered = diagnostics.get("recovered_with_fallback", False)
                unhandled = False
                error = False
                
                self.usage_logger.log_interaction(
                    user_id=user_id,
                    session_id=session_id,
                    input_audio_path=f"inputs/{user_id}_turn_{turn:02d}.wav",
                    output_audio_path=f"outputs/{user_id}_turn_{turn:02d}_out.wav",
                    emotion_detected=final_emotion,
                    emotion_confidence=np.random.uniform(0.7, 0.99),
                    dialect_detected=final_dialect,
                    dialect_confidence=np.random.uniform(0.6, 0.95),
                    processing_time_ms=processing_time,
                    retry_occurred=retry or diagnostics.get("retry_exhausted", False),
                    retry_reason="watchdog_fallback" if recovered else ("low_confidence" if retry else None),
                    error_occurred=error,
                    error_message=None,
                    stage=diagnostics.get("stage"),
                    exception_type=diagnostics.get("exception_type"),
                    timeout_breach=diagnostics.get("timeout_breach", False),
                    memory_spike=diagnostics.get("memory_spike", False),
                    circuit_breaker_activation=diagnostics.get("circuit_breaker_activation", False),
                    retry_exhausted=diagnostics.get("retry_exhausted", False),
                    silence_misclassification=diagnostics.get("silence_misclassification", False),
                    async_cancellation=diagnostics.get("async_cancellation", False),
                    failure_recovered=recovered,
                    unhandled_exception=unhandled
                )
            
            self.usage_logger.end_conversation_session(session_id)
            conversation_sessions.append((user_id, session_id))
            
            logger.info(f"✓ {user_id}: {num_turns} turn conversation logged")
        
        logger.info(f"\\n✓ {len(conversation_sessions)} multi-turn conversations logged")
        
        return conversation_sessions
    
    def simulate_human_feedback(self, user_ids: List[str]) -> None:
        """Simulate human survey responses."""
        
        logger.info("\\n--- SIMULATING HUMAN FEEDBACK ---")
        
        emotions = ["neutral", "happy", "sad", "angry", "excited", "calm"]
        dialects = ["neutral", "andhra", "telangana", "mixed"]
        
        for user_id in user_ids:
            # Each user provides 3-5 feedback entries
            num_feedback = np.random.randint(3, 6)
            
            for i in range(num_feedback):
                # Simulate MOS score (3-5 range with slight variation)
                mos = np.random.choice([3, 4, 5], p=[0.2, 0.5, 0.3])
                
                # Emotion authenticity (80% correct)
                emotion_expected = np.random.choice(emotions)
                emotion_heard = emotion_expected if np.random.random() < 0.8 else np.random.choice(emotions)
                
                # Dialect authenticity (75% correct)
                dialect_expected = np.random.choice(dialects)
                dialect_heard = dialect_expected if np.random.random() < 0.75 else np.random.choice(dialects)
                
                # Speaker consistency (90% yes)
                speaker_consistent = (np.random.random() < 0.9)
                
                # Daily use acceptance (70% yes)
                daily_use = (np.random.random() < 0.7)
                
                # Comments
                comments = [
                    "Natural and expressive",
                    "Sometimes robotic on fast speech",
                    "Emotion feels authentic",
                    "Slight accent drift in long conversations",
                    "Would use for daily communication"
                ]
                comment = np.random.choice(comments)
                
                self.feedback_collector.collect_feedback(
                    user_id=user_id,
                    interaction_id=f"{user_id}_interaction_{i:02d}",
                    mos_score=mos,
                    emotion_expected=emotion_expected,
                    emotion_heard=emotion_heard,
                    dialect_expected=dialect_expected,
                    dialect_heard=dialect_heard,
                    speaker_consistent=speaker_consistent,
                    daily_use_acceptance=daily_use,
                    comments=comment
                )
            
            logger.info(f"✓ {user_id}: {num_feedback} feedback entries collected")
        
        logger.info(f"\\n✓ Human feedback collected from {len(user_ids)} users")
    
    def simulate_stability_analysis(self, conversation_sessions: List[Tuple[str, str]]) -> None:
        """Simulate speaker embedding stability analysis."""
        
        logger.info("\\n--- SIMULATING STABILITY ANALYSIS ---")
        
        emotions = ["neutral", "happy", "sad", "angry", "excited", "calm"]
        
        for user_id, session_id in conversation_sessions:
            # Simulate 5-10 turns
            num_turns = np.random.randint(5, 11)
            
            # Generate simulated speaker embeddings (512-dim)
            base_embedding = np.random.randn(512)
            base_embedding = base_embedding / np.linalg.norm(base_embedding)
            
            turn_embeddings = []
            turn_emotions = []
            
            for turn in range(num_turns):
                # Add slight noise to base embedding (simulates natural variation)
                noise = np.random.randn(512) * 0.1
                turn_embedding = base_embedding + noise
                turn_embedding = turn_embedding / np.linalg.norm(turn_embedding)
                
                turn_embeddings.append(turn_embedding.tolist())
                turn_emotions.append(np.random.choice(emotions))
            
            self.stability_analyzer.analyze_conversation(
                session_id=session_id,
                user_id=user_id,
                speaker_embeddings=turn_embeddings,
                emotions=turn_emotions
            )
            
            logger.info(f"✓ {user_id}: {num_turns} turn stability analyzed")
        
        logger.info(f"\\n✓ Stability analysis completed for {len(conversation_sessions)} sessions")
    
    def simulate_edge_case_testing(self, user_ids: List[str]) -> None:
        """Simulate edge case testing."""
        
        logger.info("\\n--- SIMULATING EDGE CASE TESTING ---")
        
        edge_types = list(EdgeCaseType)
        emotions = ["neutral", "happy", "sad", "angry", "excited", "calm"]
        dialects = ["neutral", "andhra", "telangana", "mixed"]
        
        for user_id in user_ids:
            # Test 2-3 edge cases per user
            num_edge_tests = np.random.randint(2, 4)
            
            for i in range(num_edge_tests):
                edge_type = np.random.choice(edge_types)
                
                # Edge cases have lower accuracy
                emotion_expected = np.random.choice(emotions)
                emotion_detected = emotion_expected if np.random.random() < 0.65 else np.random.choice(emotions)
                
                dialect_expected = np.random.choice(dialects)
                dialect_detected = dialect_expected if np.random.random() < 0.60 else np.random.choice(dialects)
                
                # Edge cases have higher retry rate
                retry = (np.random.random() < 0.25)
                
                # Simulate edge faults, then recover via reliability stabilizer
                injected_fault = (np.random.random() < 0.15)

                def _edge_worker():
                    if injected_fault:
                        raise RuntimeError("edge_case_processing_exception")
                    return {
                        "detected_emotion": emotion_detected,
                        "detected_dialect": dialect_detected,
                    }

                stabilized_output, diagnostics = self.reliability_stabilizer.stabilize_interaction(
                    stage=f"edge_case_{edge_type.value}",
                    worker=_edge_worker,
                    timeout_ms=900.0,
                )

                final_detected_emotion = stabilized_output.get("detected_emotion", emotion_detected)
                final_detected_dialect = stabilized_output.get("detected_dialect", dialect_detected)
                failure_recovered = diagnostics.get("recovered_with_fallback", False)
                error_occurred = False
                
                processing_time = np.random.randint(300, 1200)  # Longer processing
                
                self.edge_case_tester.test_edge_case(
                    user_id=user_id,
                    edge_case_type=edge_type,
                    input_audio_path=f"inputs/{user_id}_edge_{edge_type.value}_{i:02d}.wav",
                    expected_emotion=emotion_expected,
                    expected_dialect=dialect_expected,
                    detected_emotion=final_detected_emotion,
                    detected_dialect=final_detected_dialect,
                    processing_time_ms=processing_time,
                    retry_occurred=retry or diagnostics.get("retry_exhausted", False),
                    error_occurred=error_occurred,
                    failure_recovered=failure_recovered,
                    error_message=None,
                    stage=diagnostics.get("stage"),
                    exception_type=diagnostics.get("exception_type"),
                    timeout_breach=diagnostics.get("timeout_breach", False),
                    memory_spike=diagnostics.get("memory_spike", False),
                    circuit_breaker_activation=diagnostics.get("circuit_breaker_activation", False),
                    retry_exhausted=diagnostics.get("retry_exhausted", False),
                    silence_misclassification=diagnostics.get("silence_misclassification", False),
                    async_cancellation=diagnostics.get("async_cancellation", False)
                )
            
            logger.info(f"✓ {user_id}: {num_edge_tests} edge case tests completed")
        
        logger.info(f"\\n✓ Edge case testing completed for {len(user_ids)} users")
    
    def generate_all_reports(self) -> None:
        """Generate all pilot validation reports."""
        
        logger.info("\\n--- GENERATING PILOT REPORTS ---")
        
        # Report 1: User Registry
        self.recruitment.generate_user_registry_report(output_file="PILOT_USER_REGISTRY.json")
        logger.info("✓ PILOT_USER_REGISTRY.json")
        
        # Report 2: Usage Log
        self.usage_logger.generate_usage_log_report(output_file="PILOT_USAGE_LOG.json")
        logger.info("✓ PILOT_USAGE_LOG.json")
        
        # Report 3: Human Feedback
        self.feedback_collector.generate_human_feedback_report(output_file="PILOT_HUMAN_FEEDBACK.json")
        logger.info("✓ PILOT_HUMAN_FEEDBACK.json")
        
        # Report 4: Stability Analysis
        self.stability_analyzer.generate_stability_report(output_file="PILOT_STABILITY_ANALYSIS.json")
        logger.info("✓ PILOT_STABILITY_ANALYSIS.json")
        
        # Report 5: Edge Case Report
        self.edge_case_tester.generate_edge_case_report(output_file="EDGE_CASE_REPORT.json")
        logger.info("✓ EDGE_CASE_REPORT.json")
        
        logger.info("\\n✓ All pilot reports generated")
    
    def run_complete_integration_test(self) -> None:
        """Run complete end-to-end pilot integration test."""
        
        logger.info("="*70)
        logger.info("REAL-WORLD PILOT: INTEGRATION HARNESS")
        logger.info("="*70)
        logger.info("")
        logger.info("NOTE: This harness uses SIMULATED data for framework testing.")
        logger.info("      For production, replace with REAL user interactions.")
        logger.info("")
        
        # Step 1: User Recruitment
        user_ids = self.simulate_user_recruitment()
        
        # Step 2: User Interactions
        conversation_sessions = self.simulate_user_interactions(user_ids)
        
        # Step 3: Human Feedback
        self.simulate_human_feedback(user_ids)
        
        # Step 4: Stability Analysis
        self.simulate_stability_analysis(conversation_sessions)
        
        # Step 5: Edge Case Testing
        self.simulate_edge_case_testing(user_ids)
        
        # Step 6: Generate all reports
        self.generate_all_reports()
        
        # Step 7: Run orchestrator with generated data
        logger.info("\\n" + "="*70)
        logger.info("RUNNING PILOT ORCHESTRATION WITH GENERATED DATA")
        logger.info("="*70)
        
        orchestrator = RealWorldPilotOrchestrator(output_dir=str(self.output_dir))
        final_report = orchestrator.run_complete_pilot()
        
        logger.info("\\n" + "="*70)
        logger.info("INTEGRATION TEST COMPLETE")
        logger.info("="*70)
        logger.info("")
        logger.info("All pilot validation reports generated:")
        logger.info(f"  • {self.output_dir / 'PILOT_USER_REGISTRY.json'}")
        logger.info(f"  • {self.output_dir / 'PILOT_USAGE_LOG.json'}")
        logger.info(f"  • {self.output_dir / 'PILOT_HUMAN_FEEDBACK.json'}")
        logger.info(f"  • {self.output_dir / 'PILOT_STABILITY_ANALYSIS.json'}")
        logger.info(f"  • {self.output_dir / 'EDGE_CASE_REPORT.json'}")
        logger.info(f"  • {self.output_dir / 'REAL_WORLD_PILOT_REPORT.json'}")
        logger.info(f"  • {self.output_dir / 'PILOT_ORCHESTRATION_LOG.json'}")
        logger.info("")
        
        if final_report:
            decision = final_report.get('deployment_decision', {})
            logger.info(f"FINAL DEPLOYMENT DECISION: {decision.get('status', 'UNKNOWN')}")
            logger.info(f"CONFIDENCE: {decision.get('confidence_score', 0):.1f}%")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    harness = PilotIntegrationHarness(output_dir="outputs/pilot")
    harness.run_complete_integration_test()
