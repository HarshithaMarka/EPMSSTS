"""
REAL-WORLD PILOT: STABILITY & DRIFT ANALYZER
Track speaker consistency and emotion stability across multi-turn conversations

Purpose:
- Compute speaker embedding similarity per turn
- Track minimum similarity (detect drift)
- Flag drift events (<0.85 cosine similarity)
- Log emotion flip events
- Generate PILOT_STABILITY_ANALYSIS.json

Author: Production ML & Product Reliability Engineer
Date: 2026-03-02
"""

import json
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class TurnStabilityMetrics:
    """Stability metrics for a single turn."""
    turn_id: int
    speaker_similarity: float  # Cosine similarity to previous turn
    emotion_same_as_previous: bool
    emotion_current: str
    emotion_previous: str


@dataclass
class ConversationStabilityAnalysis:
    """Stability analysis for a conversation session."""
    session_id: str
    user_id: str
    total_turns: int
    
    # Turn-by-turn metrics
    turn_metrics: List[TurnStabilityMetrics] = field(default_factory=list)
    
    # Aggregate stability
    mean_speaker_similarity: float = 0.0
    min_speaker_similarity: float = 1.0
    speaker_drift_events: int = 0  # Count of similarity <0.85
    
    emotion_flip_count: int = 0  # Emotion changes across turns
    emotion_stability_rate: float = 0.0  # % of turns with same emotion as previous
    
    stability_passes: bool = False


class PilotStabilityAnalyzer:
    """
    Analyze speaker consistency and emotion stability across conversations.
    
    Requirements:
    - Speaker similarity ≥0.85 across turns
    - Track emotion flip events
    - Flag drift warnings
    """
    
    DRIFT_THRESHOLD = 0.85
    MIN_ACCEPTABLE_SIMILARITY = 0.85
    
    def __init__(self, output_dir: str = "outputs/pilot"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_analyses: List[ConversationStabilityAnalysis] = []
    
    def analyze_conversation(self,
                            session_id: str,
                            user_id: str,
                            speaker_embeddings: List[np.ndarray],
                            emotions: List[str]) -> ConversationStabilityAnalysis:
        """
        Analyze stability for a multi-turn conversation.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            speaker_embeddings: List of speaker embeddings per turn
            emotions: List of emotions per turn
        
        Returns:
            ConversationStabilityAnalysis
        """
        
        if len(speaker_embeddings) != len(emotions):
            raise ValueError("Embeddings and emotions must have same length")
        
        if len(speaker_embeddings) < 2:
            logger.warning(f"Session {session_id} has <2 turns, skipping analysis")
            return ConversationStabilityAnalysis(
                session_id=session_id,
                user_id=user_id,
                total_turns=len(speaker_embeddings)
            )
        
        analysis = ConversationStabilityAnalysis(
            session_id=session_id,
            user_id=user_id,
            total_turns=len(speaker_embeddings)
        )
        
        # Compute turn-by-turn metrics
        similarities = []
        emotion_flips = 0
        drift_events = 0
        
        for i in range(1, len(speaker_embeddings)):
            # Speaker similarity
            similarity = self._cosine_similarity(
                speaker_embeddings[i-1],
                speaker_embeddings[i]
            )
            similarities.append(similarity)
            
            # Drift check
            if similarity < self.DRIFT_THRESHOLD:
                drift_events += 1
            
            # Emotion flip
            emotion_same = (emotions[i] == emotions[i-1])
            if not emotion_same:
                emotion_flips += 1
            
            turn_metric = TurnStabilityMetrics(
                turn_id=i,
                speaker_similarity=similarity,
                emotion_same_as_previous=emotion_same,
                emotion_current=emotions[i],
                emotion_previous=emotions[i-1]
            )
            
            analysis.turn_metrics.append(turn_metric)
        
        # Aggregate stability
        analysis.mean_speaker_similarity = float(np.mean(similarities))
        analysis.min_speaker_similarity = float(np.min(similarities))
        analysis.speaker_drift_events = drift_events
        analysis.emotion_flip_count = emotion_flips
        analysis.emotion_stability_rate = 1.0 - (emotion_flips / (len(emotions) - 1))
        
        # Pass/fail
        analysis.stability_passes = (
            analysis.min_speaker_similarity >= self.MIN_ACCEPTABLE_SIMILARITY
        )
        
        self.session_analyses.append(analysis)
        
        logger.info(f"✓ Analyzed {session_id}: mean similarity {analysis.mean_speaker_similarity:.3f}, "
                   f"drift events {drift_events}")
        
        return analysis
    
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity."""
        a = np.asarray(a, dtype=np.float32)
        b = np.asarray(b, dtype=np.float32)
        
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)
        
        if a_norm < 1e-8 or b_norm < 1e-8:
            return 0.0
        
        similarity = np.dot(a, b) / (a_norm * b_norm)
        
        return float(np.clip(similarity, -1.0, 1.0))
    
    def generate_stability_report(self, output_file: Optional[str] = None) -> Dict:
        """Generate PILOT_STABILITY_ANALYSIS.json"""
        
        if not self.session_analyses:
            return {'status': 'NO_ANALYSES', 'sessions': []}
        
        # Aggregate across all sessions
        all_similarities = []
        all_drift_events = 0
        all_emotion_flips = 0
        sessions_passed = 0
        
        for analysis in self.session_analyses:
            if analysis.turn_metrics:
                all_similarities.extend([m.speaker_similarity for m in analysis.turn_metrics])
                all_drift_events += analysis.speaker_drift_events
                all_emotion_flips += analysis.emotion_flip_count
                
                if analysis.stability_passes:
                    sessions_passed += 1
        
        report = {
            'timestamp': str(datetime.now()),
            
            'aggregate_stability': {
                'total_sessions': len(self.session_analyses),
                'sessions_passed': sessions_passed,
                'pass_rate': float(sessions_passed / len(self.session_analyses)) if self.session_analyses else 0.0,
                'mean_speaker_similarity': float(np.mean(all_similarities)) if all_similarities else 0.0,
                'std_speaker_similarity': float(np.std(all_similarities)) if all_similarities else 0.0,
                'min_speaker_similarity': float(np.min(all_similarities)) if all_similarities else 0.0,
                'total_drift_events': all_drift_events,
                'drift_event_rate': float(all_drift_events / len(all_similarities)) if all_similarities else 0.0,
                'total_emotion_flips': all_emotion_flips
            },
            
            'stability_thresholds': {
                'drift_threshold': self.DRIFT_THRESHOLD,
                'min_acceptable_similarity': self.MIN_ACCEPTABLE_SIMILARITY
            },
            
            'per_session_analysis': [
                {
                    'session_id': a.session_id,
                    'user_id': a.user_id,
                    'total_turns': a.total_turns,
                    'mean_speaker_similarity': float(a.mean_speaker_similarity),
                    'min_speaker_similarity': float(a.min_speaker_similarity),
                    'speaker_drift_events': a.speaker_drift_events,
                    'emotion_flip_count': a.emotion_flip_count,
                    'emotion_stability_rate': float(a.emotion_stability_rate),
                    'stability_passes': a.stability_passes,
                    'turn_details': [
                        {
                            'turn_id': m.turn_id,
                            'speaker_similarity': float(m.speaker_similarity),
                            'emotion_current': m.emotion_current,
                            'emotion_previous': m.emotion_previous,
                            'emotion_same': m.emotion_same_as_previous
                        }
                        for m in a.turn_metrics
                    ]
                }
                for a in self.session_analyses
            ]
        }
        
        if output_file:
            output_path = self.output_dir / output_file
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"✓ Stability analysis saved: {output_path}")
        
        return report


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    analyzer = PilotStabilityAnalyzer(output_dir="outputs/pilot")
    
    logger.info("Simulating stability analysis...\n")
    
    # Simulate 10 conversation sessions
    np.random.seed(42)
    emotions = ['neutral', 'sad', 'happy', 'angry', 'whisper']
    
    for session_idx in range(10):
        session_id = f"session_{session_idx:03d}"
        user_id = f"user_{session_idx:03d}"
        
        # 5-8 turns per conversation
        num_turns = np.random.randint(5, 9)
        
        # Generate embeddings with realistic drift
        base_embedding = np.random.randn(256)
        base_embedding = base_embedding / np.linalg.norm(base_embedding)
        
        speaker_embeddings = [base_embedding]
        for _ in range(num_turns - 1):
            # Add small perturbation
            drift_amount = np.random.uniform(0.02, 0.08)
            new_embedding = base_embedding + np.random.randn(256) * drift_amount
            new_embedding = new_embedding / np.linalg.norm(new_embedding)
            speaker_embeddings.append(new_embedding)
        
        # Generate emotions with occasional flips
        session_emotions = [np.random.choice(emotions)]
        for _ in range(num_turns - 1):
            # 80% chance to keep same emotion
            if np.random.rand() > 0.20:
                session_emotions.append(session_emotions[-1])
            else:
                session_emotions.append(np.random.choice(emotions))
        
        analyzer.analyze_conversation(
            session_id=session_id,
            user_id=user_id,
            speaker_embeddings=speaker_embeddings,
            emotions=session_emotions
        )
    
    # Generate report
    report = analyzer.generate_stability_report("PILOT_STABILITY_ANALYSIS.json")
    
    logger.info(f"\n✓ Stability analysis complete")
    logger.info(f"  Mean similarity: {report['aggregate_stability']['mean_speaker_similarity']:.3f}")
    logger.info(f"  Drift events: {report['aggregate_stability']['total_drift_events']}")
    logger.info(f"  Pass rate: {report['aggregate_stability']['pass_rate']:.1%}")
