"""
REAL-WORLD PILOT: USAGE LOGGER
Real-time logging during user interactions

Purpose:
- Log each speech-to-speech interaction
- Track multi-turn conversations
- Record emotion detection results
- Monitor retry occurrences
- Measure processing time

Author: Production ML & Product Reliability Engineer
Date: 2026-03-02
"""

import json
import numpy as np
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class InteractionLog:
    """Single interaction log entry."""
    interaction_id: str
    user_id: str
    timestamp: str
    
    # Audio
    input_audio_path: str
    output_audio_path: str
    
    # Processing
    emotion_detected: str
    emotion_confidence: float
    dialect_detected: str
    dialect_confidence: float
    
    # Performance
    processing_time_ms: float
    retry_occurred: bool
    retry_reason: Optional[str] = None
    
    # Error tracking
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
    failure_recovered: bool = False
    unhandled_exception: bool = False


@dataclass
class ConversationSession:
    """Multi-turn conversation session."""
    session_id: str
    user_id: str
    start_time: str
    end_time: Optional[str] = None
    
    turns: List[InteractionLog] = field(default_factory=list)
    total_turns: int = 0
    
    # Session-level tracking
    retries_total: int = 0
    errors_total: int = 0
    mean_processing_time_ms: float = 0.0
    
    session_complete: bool = False


class PilotUsageLogger:
    """
    Log all user interactions during pilot.
    
    Requirements:
    - Minimum 5 interactions per user
    - At least one 5+ turn conversation per user
    - Natural speech (no scripts)
    """
    
    MIN_INTERACTIONS_PER_USER = 5
    MIN_TURNS_PER_CONVERSATION = 5
    
    def __init__(self, output_dir: str = "outputs/pilot"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.interactions: List[InteractionLog] = []
        self.sessions: Dict[str, ConversationSession] = {}
        
        self.user_interaction_counts: Dict[str, int] = {}
    
    def start_conversation_session(self, user_id: str) -> str:
        """Start a new conversation session."""
        
        session_id = f"session_{user_id}_{len(self.sessions):03d}"
        
        session = ConversationSession(
            session_id=session_id,
            user_id=user_id,
            start_time=str(datetime.now())
        )
        
        self.sessions[session_id] = session
        
        logger.info(f"✓ Started session {session_id} for user {user_id}")
        
        return session_id
    
    def log_interaction(self,
                       user_id: str,
                       input_audio_path: str,
                       output_audio_path: str,
                       emotion_detected: str,
                       emotion_confidence: float,
                       dialect_detected: str,
                       dialect_confidence: float,
                       processing_time_ms: float,
                       retry_occurred: bool = False,
                       retry_reason: Optional[str] = None,
                       error_occurred: bool = False,
                       error_message: Optional[str] = None,
                       stage: Optional[str] = None,
                       exception_type: Optional[str] = None,
                       timeout_breach: bool = False,
                       memory_spike: bool = False,
                       circuit_breaker_activation: bool = False,
                       retry_exhausted: bool = False,
                       silence_misclassification: bool = False,
                       async_cancellation: bool = False,
                       failure_recovered: bool = False,
                       unhandled_exception: bool = False,
                       session_id: Optional[str] = None) -> InteractionLog:
        """Log a single interaction."""
        
        interaction_id = f"interaction_{user_id}_{len(self.interactions):04d}"
        
        interaction = InteractionLog(
            interaction_id=interaction_id,
            user_id=user_id,
            timestamp=str(datetime.now()),
            input_audio_path=input_audio_path,
            output_audio_path=output_audio_path,
            emotion_detected=emotion_detected,
            emotion_confidence=emotion_confidence,
            dialect_detected=dialect_detected,
            dialect_confidence=dialect_confidence,
            processing_time_ms=processing_time_ms,
            retry_occurred=retry_occurred,
            retry_reason=retry_reason,
            error_occurred=error_occurred,
            error_message=error_message,
            stage=stage,
            exception_type=exception_type,
            timeout_breach=timeout_breach,
            memory_spike=memory_spike,
            circuit_breaker_activation=circuit_breaker_activation,
            retry_exhausted=retry_exhausted,
            silence_misclassification=silence_misclassification,
            async_cancellation=async_cancellation,
            failure_recovered=failure_recovered,
            unhandled_exception=unhandled_exception
        )
        
        self.interactions.append(interaction)
        
        # Update user count
        if user_id not in self.user_interaction_counts:
            self.user_interaction_counts[user_id] = 0
        self.user_interaction_counts[user_id] += 1
        
        # Add to session if applicable
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            session.turns.append(interaction)
            session.total_turns += 1
            
            if retry_occurred:
                session.retries_total += 1
            if error_occurred:
                session.errors_total += 1
        
        logger.info(f"✓ Logged interaction {interaction_id} (emotion: {emotion_detected}, "
                   f"processing: {processing_time_ms:.0f}ms)")
        
        return interaction
    
    def end_conversation_session(self, session_id: str) -> None:
        """End a conversation session."""
        
        if session_id not in self.sessions:
            logger.error(f"Session {session_id} not found")
            return
        
        session = self.sessions[session_id]
        session.end_time = str(datetime.now())
        session.session_complete = True
        
        # Compute session statistics
        if session.turns:
            processing_times = [t.processing_time_ms for t in session.turns]
            session.mean_processing_time_ms = float(np.mean(processing_times))
        
        logger.info(f"✓ Ended session {session_id} ({session.total_turns} turns)")
    
    def validate_user_requirements(self, user_id: str) -> Dict:
        """Check if user met minimum interaction requirements."""
        
        user_interactions = [i for i in self.interactions if i.user_id == user_id]
        user_sessions = [s for s in self.sessions.values() if s.user_id == user_id]
        
        # Check for 5+ turn conversations
        long_conversations = [s for s in user_sessions if s.total_turns >= self.MIN_TURNS_PER_CONVERSATION]
        
        return {
            'user_id': user_id,
            'total_interactions': len(user_interactions),
            'meets_min_interactions': len(user_interactions) >= self.MIN_INTERACTIONS_PER_USER,
            'conversation_sessions': len(user_sessions),
            'long_conversations': len(long_conversations),
            'has_long_conversation': len(long_conversations) >= 1,
            'requirements_met': (
                len(user_interactions) >= self.MIN_INTERACTIONS_PER_USER and
                len(long_conversations) >= 1
            )
        }
    
    def generate_usage_log_report(self, output_file: Optional[str] = None) -> Dict:
        """Generate PILOT_USAGE_LOG.json"""
        
        # Per-user validation
        user_validations = {}
        for user_id in self.user_interaction_counts.keys():
            user_validations[user_id] = self.validate_user_requirements(user_id)
        
        # Aggregate statistics
        processing_times = [i.processing_time_ms for i in self.interactions]
        retry_count = sum(1 for i in self.interactions if i.retry_occurred)
        error_count = sum(1 for i in self.interactions if i.error_occurred)
        
        report = {
            'timestamp': str(datetime.now()),
            
            'interactions_summary': {
                'total_interactions': len(self.interactions),
                'unique_users': len(self.user_interaction_counts),
                'total_sessions': len(self.sessions),
                'mean_processing_time_ms': float(np.mean(processing_times)) if processing_times else 0.0,
                'std_processing_time_ms': float(np.std(processing_times)) if processing_times else 0.0,
                'max_processing_time_ms': float(np.max(processing_times)) if processing_times else 0.0
            },
            
            'quality_metrics': {
                'retry_occurrences': retry_count,
                'retry_rate': float(retry_count / len(self.interactions)) if self.interactions else 0.0,
                'error_occurrences': error_count,
                'error_rate': float(error_count / len(self.interactions)) if self.interactions else 0.0
            },
            
            'per_user_validation': user_validations,
            
            'conversation_sessions': [
                {
                    'session_id': s.session_id,
                    'user_id': s.user_id,
                    'total_turns': s.total_turns,
                    'retries': s.retries_total,
                    'errors': s.errors_total,
                    'mean_processing_time_ms': float(s.mean_processing_time_ms),
                    'complete': s.session_complete
                }
                for s in self.sessions.values()
            ],
            
            'interaction_log': [
                {
                    'interaction_id': i.interaction_id,
                    'user_id': i.user_id,
                    'timestamp': i.timestamp,
                    'emotion_detected': i.emotion_detected,
                    'emotion_confidence': float(i.emotion_confidence),
                    'dialect_detected': i.dialect_detected,
                    'dialect_confidence': float(i.dialect_confidence),
                    'processing_time_ms': float(i.processing_time_ms),
                    'retry_occurred': i.retry_occurred,
                    'retry_reason': i.retry_reason,
                    'error_occurred': i.error_occurred,
                    'error_message': i.error_message,
                    'stage': i.stage,
                    'exception_type': i.exception_type,
                    'timeout_breach': i.timeout_breach,
                    'memory_spike': i.memory_spike,
                    'circuit_breaker_activation': i.circuit_breaker_activation,
                    'retry_exhausted': i.retry_exhausted,
                    'silence_misclassification': i.silence_misclassification,
                    'async_cancellation': i.async_cancellation,
                    'failure_recovered': i.failure_recovered,
                    'unhandled_exception': i.unhandled_exception
                }
                for i in self.interactions
            ]
        }
        
        if output_file:
            output_path = self.output_dir / output_file
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"✓ Usage log saved: {output_path}")
        
        return report


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    usage_logger = PilotUsageLogger(output_dir="outputs/pilot")
    
    logger.info("Simulating pilot usage...\n")
    
    # Simulate 10 users with varying interactions
    users = [f"user_{i:03d}" for i in range(1, 11)]
    emotions = ['neutral', 'sad', 'happy', 'angry', 'whisper']
    dialects = ['neutral', 'andhra', 'telangana', 'mixed']
    
    for user_id in users:
        # Each user has 5-7 interactions
        num_interactions = np.random.randint(5, 8)
        
        # At least one long conversation
        session_id = usage_logger.start_conversation_session(user_id)
        
        for turn in range(6):  # 6-turn conversation
            emotion = np.random.choice(emotions)
            dialect = np.random.choice(dialects)
            processing_time = np.random.uniform(200, 1500)
            retry = np.random.rand() > 0.9
            
            usage_logger.log_interaction(
                user_id=user_id,
                input_audio_path=f"outputs/pilot/audio/{user_id}_input_{turn}.wav",
                output_audio_path=f"outputs/pilot/audio/{user_id}_output_{turn}.wav",
                emotion_detected=emotion,
                emotion_confidence=np.random.uniform(0.7, 0.95),
                dialect_detected=dialect,
                dialect_confidence=np.random.uniform(0.65, 0.92),
                processing_time_ms=processing_time,
                retry_occurred=retry,
                retry_reason="emotion_low_confidence" if retry else None,
                session_id=session_id
            )
        
        usage_logger.end_conversation_session(session_id)
    
    # Generate report
    report = usage_logger.generate_usage_log_report("PILOT_USAGE_LOG.json")
    
    logger.info(f"\n✓ Usage logging complete")
    logger.info(f"  Total interactions: {report['interactions_summary']['total_interactions']}")
    logger.info(f"  Retry rate: {report['quality_metrics']['retry_rate']:.1%}")
