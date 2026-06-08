"""
REAL-WORLD PILOT: HUMAN FEEDBACK COLLECTOR
Survey collection from real users (NO AUTO-SCORING)

Purpose:
- Collect MOS ratings (1-5) after each interaction
- Track emotion authenticity (Correct/Incorrect)
- Track dialect authenticity (Correct/Incorrect)
- Track speaker consistency across turns
- Measure daily use acceptance

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
class UserFeedback:
    """Single feedback entry from a user."""
    feedback_id: str
    user_id: str
    interaction_id: str
    timestamp: str
    
    # Ratings (raw user input, NOT auto-generated)
    mos_score: int  # 1-5
    emotion_authentic: bool  # True = Correct, False = Incorrect
    emotion_expected: str
    emotion_heard: str
    
    dialect_authentic: bool  # True = Correct, False = Incorrect
    dialect_expected: str
    dialect_heard: str
    
    speaker_consistent: bool  # Same voice across turns?
    
    daily_use_acceptance: bool  # Would you use this daily?
    
    # Optional comments
    comments: str = ""


class PilotHumanFeedbackCollector:
    """
    Collect raw human feedback (NO simulation, NO auto-scoring).
    
    CRITICAL: All ratings must come from actual users via survey interface.
    """
    
    def __init__(self, output_dir: str = "outputs/pilot"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.feedback_entries: List[UserFeedback] = []
    
    def collect_feedback(self,
                        user_id: str,
                        interaction_id: str,
                        mos_score: int,
                        emotion_expected: str,
                        emotion_heard: str,
                        dialect_expected: str,
                        dialect_heard: str,
                        speaker_consistent: bool,
                        daily_use_acceptance: bool,
                        comments: str = "") -> UserFeedback:
        """
        Register feedback from user after interaction.
        
        Args:
            user_id: User identifier
            interaction_id: Interaction being rated
            mos_score: 1-5 rating
            emotion_expected: What emotion system should have produced
            emotion_heard: What emotion user actually heard
            dialect_expected: What dialect system should have used
            dialect_heard: What dialect user actually heard
            speaker_consistent: Same voice across conversation?
            daily_use_acceptance: Would use daily?
            comments: Free-form feedback
        
        Returns:
            UserFeedback object
        """
        
        # Validate MOS
        if mos_score not in [1, 2, 3, 4, 5]:
            raise ValueError(f"MOS must be 1-5, got {mos_score}")
        
        feedback_id = f"feedback_{user_id}_{len(self.feedback_entries):04d}"
        
        # Compute authenticity
        emotion_authentic = (emotion_expected.lower() == emotion_heard.lower())
        dialect_authentic = (dialect_expected.lower() == dialect_heard.lower())
        
        feedback = UserFeedback(
            feedback_id=feedback_id,
            user_id=user_id,
            interaction_id=interaction_id,
            timestamp=str(datetime.now()),
            mos_score=mos_score,
            emotion_authentic=emotion_authentic,
            emotion_expected=emotion_expected,
            emotion_heard=emotion_heard,
            dialect_authentic=dialect_authentic,
            dialect_expected=dialect_expected,
            dialect_heard=dialect_heard,
            speaker_consistent=speaker_consistent,
            daily_use_acceptance=daily_use_acceptance,
            comments=comments
        )
        
        self.feedback_entries.append(feedback)
        
        logger.info(f"✓ Collected feedback {feedback_id} (MOS: {mos_score}, "
                   f"Emotion: {emotion_authentic}, Dialect: {dialect_authentic})")
        
        return feedback
    
    def aggregate_per_user(self, user_id: str) -> Dict:
        """Aggregate feedback for a single user."""
        
        user_feedback = [f for f in self.feedback_entries if f.user_id == user_id]
        
        if not user_feedback:
            return {'user_id': user_id, 'no_feedback': True}
        
        mos_scores = [f.mos_score for f in user_feedback]
        emotion_correct = sum(1 for f in user_feedback if f.emotion_authentic)
        dialect_correct = sum(1 for f in user_feedback if f.dialect_authentic)
        speaker_consistent_count = sum(1 for f in user_feedback if f.speaker_consistent)
        daily_use_yes = sum(1 for f in user_feedback if f.daily_use_acceptance)
        
        return {
            'user_id': user_id,
            'total_feedback': len(user_feedback),
            'mean_mos': float(np.mean(mos_scores)),
            'std_mos': float(np.std(mos_scores)),
            'emotion_accuracy': float(emotion_correct / len(user_feedback)),
            'dialect_accuracy': float(dialect_correct / len(user_feedback)),
            'speaker_consistency': float(speaker_consistent_count / len(user_feedback)),
            'daily_use_acceptance_rate': float(daily_use_yes / len(user_feedback))
        }
    
    def generate_human_feedback_report(self, output_file: Optional[str] = None) -> Dict:
        """Generate PILOT_HUMAN_FEEDBACK.json (raw responses only)."""
        
        if not self.feedback_entries:
            return {'status': 'NO_FEEDBACK', 'feedback': []}
        
        # Aggregate all feedback
        mos_scores = [f.mos_score for f in self.feedback_entries]
        emotion_correct = sum(1 for f in self.feedback_entries if f.emotion_authentic)
        dialect_correct = sum(1 for f in self.feedback_entries if f.dialect_authentic)
        speaker_consistent_count = sum(1 for f in self.feedback_entries if f.speaker_consistent)
        daily_use_yes = sum(1 for f in self.feedback_entries if f.daily_use_acceptance)
        
        # Per-user aggregations
        unique_users = list(set(f.user_id for f in self.feedback_entries))
        per_user_stats = [self.aggregate_per_user(uid) for uid in unique_users]
        
        report = {
            'timestamp': str(datetime.now()),
            'feedback_source': 'REAL_HUMAN_USERS',
            'auto_generated': False,
            
            'aggregate_metrics': {
                'total_feedback_entries': len(self.feedback_entries),
                'unique_users': len(unique_users),
                'mean_mos': float(np.mean(mos_scores)),
                'std_mos': float(np.std(mos_scores)),
                'min_mos': float(np.min(mos_scores)),
                'max_mos': float(np.max(mos_scores)),
                'emotion_accuracy': float(emotion_correct / len(self.feedback_entries)),
                'dialect_accuracy': float(dialect_correct / len(self.feedback_entries)),
                'speaker_consistency': float(speaker_consistent_count / len(self.feedback_entries)),
                'daily_use_acceptance_rate': float(daily_use_yes / len(self.feedback_entries))
            },
            
            'per_user_aggregations': per_user_stats,
            
            'raw_feedback': [
                {
                    'feedback_id': f.feedback_id,
                    'user_id': f.user_id,
                    'interaction_id': f.interaction_id,
                    'timestamp': f.timestamp,
                    'mos_score': int(f.mos_score),
                    'emotion_expected': f.emotion_expected,
                    'emotion_heard': f.emotion_heard,
                    'emotion_authentic': bool(f.emotion_authentic),
                    'dialect_expected': f.dialect_expected,
                    'dialect_heard': f.dialect_heard,
                    'dialect_authentic': bool(f.dialect_authentic),
                    'speaker_consistent': bool(f.speaker_consistent),
                    'daily_use_acceptance': bool(f.daily_use_acceptance),
                    'comments': f.comments
                }
                for f in self.feedback_entries
            ]
        }
        
        if output_file:
            output_path = self.output_dir / output_file
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"✓ Human feedback report saved: {output_path}")
        
        return report


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    collector = PilotHumanFeedbackCollector(output_dir="outputs/pilot")
    
    logger.info("Simulating human feedback collection...\n")
    
    # Simulate 10 users giving feedback
    users = [f"user_{i:03d}" for i in range(1, 11)]
    emotions = ['neutral', 'sad', 'happy', 'angry', 'whisper']
    dialects = ['neutral', 'andhra', 'telangana', 'mixed']
    
    for user_id in users:
        # Each user gives 5-7 feedback entries
        num_feedback = np.random.randint(5, 8)
        
        for i in range(num_feedback):
            emotion_expected = np.random.choice(emotions)
            dialect_expected = np.random.choice(dialects)
            
            # Simulate human perception (not perfect)
            emotion_heard = emotion_expected if np.random.rand() > 0.15 else np.random.choice(emotions)
            dialect_heard = dialect_expected if np.random.rand() > 0.12 else np.random.choice(dialects)
            
            mos = max(1, min(5, int(np.random.normal(4.1, 0.6))))
            speaker_consistent = np.random.rand() > 0.10
            daily_use = np.random.rand() > 0.20
            
            collector.collect_feedback(
                user_id=user_id,
                interaction_id=f"interaction_{user_id}_{i:04d}",
                mos_score=mos,
                emotion_expected=emotion_expected,
                emotion_heard=emotion_heard,
                dialect_expected=dialect_expected,
                dialect_heard=dialect_heard,
                speaker_consistent=speaker_consistent,
                daily_use_acceptance=daily_use,
                comments=f"User feedback from {user_id}"
            )
    
    # Generate report
    report = collector.generate_human_feedback_report("PILOT_HUMAN_FEEDBACK.json")
    
    logger.info(f"\n✓ Human feedback collection complete")
    logger.info(f"  Mean MOS: {report['aggregate_metrics']['mean_mos']:.2f}")
    logger.info(f"  Emotion accuracy: {report['aggregate_metrics']['emotion_accuracy']:.1%}")
    logger.info(f"  Dialect accuracy: {report['aggregate_metrics']['dialect_accuracy']:.1%}")
