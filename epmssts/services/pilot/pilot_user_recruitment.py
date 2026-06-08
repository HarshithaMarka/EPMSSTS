"""
REAL-WORLD PILOT: USER RECRUITMENT & MANAGEMENT
Track 10 independent beta users conducting real-world validation

Purpose:
- Register 10 diverse users (NOT internal team)
- Track diversity: mic quality, speaking style, emotional expressiveness
- Log participation status
- Ensure minimum interaction requirements met

Author: Production ML & Product Reliability Engineer
Date: 2026-03-02
"""

import json
import numpy as np
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MicQuality(Enum):
    """Microphone quality levels."""
    PROFESSIONAL = "professional"
    CONSUMER = "consumer"
    MOBILE = "mobile"
    BUDGET = "budget"


class SpeakingStyle(Enum):
    """Speaking style diversity."""
    CLEAR = "clear"
    FAST = "fast"
    SOFT = "soft"
    EXPRESSIVE = "expressive"
    MONOTONE = "monotone"


@dataclass
class UserProfile:
    """Beta user profile."""
    user_id: str
    name: str  # Anonymous ID in production
    
    # Diversity factors
    mic_quality: MicQuality
    speaking_style: SpeakingStyle
    emotional_expressiveness: str  # high, medium, low
    dialect_background: str  # neutral, andhra, telangana, mixed
    
    # Participation tracking
    interactions_completed: int = 0
    emotional_variations_covered: List[str] = field(default_factory=list)
    dialect_samples_provided: int = 0
    
    # Status
    registered_date: str = field(default_factory=lambda: str(datetime.now()))
    participation_complete: bool = False
    
    def check_requirements(self) -> bool:
        """Check if user met minimum participation requirements."""
        
        # Minimum 5 interactions
        if self.interactions_completed < 5:
            return False
        
        # Must cover at least 3 emotions
        if len(self.emotional_variations_covered) < 3:
            return False
        
        # At least one dialect sample (if applicable)
        if self.dialect_background != "neutral" and self.dialect_samples_provided < 1:
            return False
        
        return True


class PilotUserRecruitment:
    """
    Manage pilot user recruitment and diversity validation.
    
    Requirements:
    - 10 independent users (not developers)
    - Diverse mic quality
    - Diverse speaking styles
    - Diverse emotional expressiveness
    """
    
    REQUIRED_USERS = 10
    MIN_INTERACTIONS_PER_USER = 5
    MIN_EMOTIONS_PER_USER = 3
    
    def __init__(self, output_dir: str = "outputs/pilot"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.users: Dict[str, UserProfile] = {}
    
    def register_user(self,
                     user_id: str,
                     name: str,
                     mic_quality: MicQuality,
                     speaking_style: SpeakingStyle,
                     emotional_expressiveness: str,
                     dialect_background: str) -> UserProfile:
        """Register a new pilot user."""
        
        if user_id in self.users:
            logger.warning(f"User {user_id} already registered")
            return self.users[user_id]
        
        user = UserProfile(
            user_id=user_id,
            name=name,
            mic_quality=mic_quality,
            speaking_style=speaking_style,
            emotional_expressiveness=emotional_expressiveness,
            dialect_background=dialect_background
        )
        
        self.users[user_id] = user
        logger.info(f"✓ Registered user {user_id}: {speaking_style.value}, {mic_quality.value}")
        
        return user
    
    def update_user_progress(self,
                            user_id: str,
                            emotion: Optional[str] = None,
                            dialect_sample: bool = False) -> None:
        """Update user participation progress."""
        
        if user_id not in self.users:
            logger.error(f"User {user_id} not registered")
            return
        
        user = self.users[user_id]
        user.interactions_completed += 1
        
        if emotion and emotion not in user.emotional_variations_covered:
            user.emotional_variations_covered.append(emotion)
        
        if dialect_sample:
            user.dialect_samples_provided += 1
        
        # Check if requirements met
        user.participation_complete = user.check_requirements()
        
        logger.info(f"User {user_id}: {user.interactions_completed} interactions, "
                   f"{len(user.emotional_variations_covered)} emotions")
    
    def validate_diversity(self) -> Dict[str, any]:
        """Validate user pool diversity."""
        
        if len(self.users) < self.REQUIRED_USERS:
            return {
                'sufficient_users': False,
                'reason': f'Only {len(self.users)} users (need {self.REQUIRED_USERS})'
            }
        
        # Check mic quality diversity
        mic_types = [u.mic_quality.value for u in self.users.values()]
        unique_mics = len(set(mic_types))
        
        # Check speaking style diversity
        speaking_styles = [u.speaking_style.value for u in self.users.values()]
        unique_styles = len(set(speaking_styles))
        
        # Check emotional expressiveness
        emotional_levels = [u.emotional_expressiveness for u in self.users.values()]
        unique_emotional = len(set(emotional_levels))
        
        diversity = {
            'sufficient_users': True,
            'total_users': len(self.users),
            'mic_quality_types': unique_mics,
            'speaking_style_types': unique_styles,
            'emotional_expressiveness_types': unique_emotional,
            'diversity_score': (unique_mics + unique_styles + unique_emotional) / 9.0,  # Max 3+3+3
            'sufficient_diversity': unique_mics >= 2 and unique_styles >= 3
        }
        
        return diversity
    
    def check_participation_completion(self) -> Dict[str, any]:
        """Check if all users completed minimum requirements."""
        
        completed_users = [u for u in self.users.values() if u.participation_complete]
        
        return {
            'total_users': len(self.users),
            'completed_users': len(completed_users),
            'completion_rate': len(completed_users) / len(self.users) if self.users else 0.0,
            'ready_for_analysis': len(completed_users) >= self.REQUIRED_USERS
        }
    
    def generate_user_registry_report(self, output_file: Optional[str] = None) -> Dict:
        """Generate user recruitment report."""
        
        diversity = self.validate_diversity()
        completion = self.check_participation_completion()
        
        report = {
            'timestamp': str(datetime.now()),
            'recruitment_status': {
                'target_users': self.REQUIRED_USERS,
                'registered_users': len(self.users),
                'completed_users': completion['completed_users'],
                'completion_rate': float(completion['completion_rate'])
            },
            
            'diversity_validation': diversity,
            
            'user_profiles': [
                {
                    'user_id': u.user_id,
                    'mic_quality': u.mic_quality.value,
                    'speaking_style': u.speaking_style.value,
                    'emotional_expressiveness': u.emotional_expressiveness,
                    'dialect_background': u.dialect_background,
                    'interactions_completed': u.interactions_completed,
                    'emotions_covered': u.emotional_variations_covered,
                    'dialect_samples': u.dialect_samples_provided,
                    'requirements_met': u.participation_complete
                }
                for u in self.users.values()
            ],
            
            'participation_requirements': {
                'min_interactions': self.MIN_INTERACTIONS_PER_USER,
                'min_emotions': self.MIN_EMOTIONS_PER_USER,
                'dialect_sample': 'required_if_applicable'
            },
            
            'pilot_readiness': {
                'ready_for_analysis': completion['ready_for_analysis'],
                'blocking_issues': []
            }
        }
        
        # Check for blocking issues
        if not diversity['sufficient_users']:
            report['pilot_readiness']['blocking_issues'].append(
                f"Only {len(self.users)} users (need {self.REQUIRED_USERS})"
            )
        
        if not diversity['sufficient_diversity']:
            report['pilot_readiness']['blocking_issues'].append(
                "Insufficient diversity (need ≥2 mic types, ≥3 speaking styles)"
            )
        
        if not completion['ready_for_analysis']:
            report['pilot_readiness']['blocking_issues'].append(
                f"Only {completion['completed_users']} users completed requirements"
            )
        
        if output_file:
            output_path = self.output_dir / output_file
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"✓ User registry report saved: {output_path}")
        
        return report


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    recruitment = PilotUserRecruitment(output_dir="outputs/pilot")
    
    # Example: Register 10 diverse users
    logger.info("Registering pilot users...\n")
    
    users_config = [
        ("user_001", "Alice", MicQuality.PROFESSIONAL, SpeakingStyle.CLEAR, "high", "neutral"),
        ("user_002", "Bob", MicQuality.CONSUMER, SpeakingStyle.FAST, "medium", "andhra"),
        ("user_003", "Carol", MicQuality.MOBILE, SpeakingStyle.SOFT, "high", "telangana"),
        ("user_004", "Dave", MicQuality.BUDGET, SpeakingStyle.EXPRESSIVE, "low", "neutral"),
        ("user_005", "Eve", MicQuality.CONSUMER, SpeakingStyle.MONOTONE, "medium", "mixed"),
        ("user_006", "Frank", MicQuality.PROFESSIONAL, SpeakingStyle.CLEAR, "high", "andhra"),
        ("user_007", "Grace", MicQuality.MOBILE, SpeakingStyle.FAST, "medium", "neutral"),
        ("user_008", "Henry", MicQuality.CONSUMER, SpeakingStyle.SOFT, "low", "telangana"),
        ("user_009", "Iris", MicQuality.BUDGET, SpeakingStyle.EXPRESSIVE, "high", "neutral"),
        ("user_010", "Jack", MicQuality.CONSUMER, SpeakingStyle.CLEAR, "medium", "mixed")
    ]
    
    for uid, name, mic, style, emotion, dialect in users_config:
        recruitment.register_user(uid, name, mic, style, emotion, dialect)
    
    # Simulate participation
    logger.info("\nSimulating user participation...")
    emotions = ['neutral', 'sad', 'happy', 'angry', 'whisper']
    
    for user_id in recruitment.users.keys():
        # Simulate 5+ interactions
        num_interactions = np.random.randint(5, 8)
        
        for _ in range(num_interactions):
            emotion = np.random.choice(emotions)
            dialect_sample = np.random.rand() > 0.7
            
            recruitment.update_user_progress(user_id, emotion, dialect_sample)
    
    # Generate report
    logger.info("\nGenerating user registry report...")
    report = recruitment.generate_user_registry_report("PILOT_USER_REGISTRY.json")
    
    logger.info(f"\n✓ Pilot user recruitment complete")
    logger.info(f"  Registered: {report['recruitment_status']['registered_users']} users")
    logger.info(f"  Completed: {report['recruitment_status']['completed_users']} users")
    logger.info(f"  Ready: {report['pilot_readiness']['ready_for_analysis']}")
