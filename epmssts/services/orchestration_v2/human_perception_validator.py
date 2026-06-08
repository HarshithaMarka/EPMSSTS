"""
PHASE 5: HUMAN PERCEPTION VALIDATION
Blind listening tests for speech authenticity assessment

Purpose:
- Generate 20 realistic outputs:
  - Sad whisper, angry loud, calm neutral
  - Mixed emotional arcs
  - Andhra dialect, Telangana dialect
- Run blind listening test with N evaluators
- Collect MOS (1-5), emotion correctness, dialect authenticity, naturalness
- Target: MOS >= 3.8, emotion accuracy >= 80%

Note: This module provides the framework. Actual evaluations require human raters.

Author: Realism Engineering
Date: 2026-03-02
"""

import json
import numpy as np
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class EmotionLabel(Enum):
    """Emotion categories."""
    SAD = "sad"
    HAPPY = "happy"
    ANGRY = "angry"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class DialectLabel(Enum):
    """Dialect categories."""
    NEUTRAL = "neutral"
    ANDHRA = "andhra"
    TELANGANA = "telangana"


class IntensityLabel(Enum):
    """Speech intensity/style."""
    WHISPER = "whisper"
    NORMAL = "normal"
    LOUD = "loud"


@dataclass
class SpeechSample:
    """Definition of a speech sample to be evaluated."""
    sample_id: str
    emotion: EmotionLabel
    dialect: DialectLabel
    intensity: IntensityLabel
    description: str
    audio_path: Optional[str] = None


@dataclass
class EvaluatorRating:
    """Single evaluator's rating of a sample."""
    evaluator_id: str
    sample_id: str
    mos_score: float  # Mean Opinion Score (1-5)
    emotion_correctness: float  # 0-1 accuracy
    dialect_authenticity: float  # 0-1 accuracy
    naturalness: float  # 0-1 score
    confidence: float  # 0-1 confidence in rating
    comments: str = ""


@dataclass
class SampleAggregateRating:
    """Aggregated ratings across all evaluators."""
    sample_id: str
    emotion: str
    dialect: str
    intensity: str
    n_evaluators: int
    mean_mos: float
    std_mos: float
    mean_emotion_correctness: float
    mean_dialect_authenticity: float
    mean_naturalness: float
    mean_confidence: float
    passes_mos_threshold: bool
    passes_emotion_threshold: bool
    overall_quality: str  # EXCELLENT, GOOD, ACCEPTABLE, POOR


class HumanPerceptionEvaluator:
    """Framework for human perception listening tests."""
    
    def __init__(self,
                 mos_threshold: float = 3.8,
                 emotion_accuracy_threshold: float = 0.80,
                 naturalness_threshold: float = 0.75):
        self.mos_threshold = mos_threshold
        self.emotion_accuracy_threshold = emotion_accuracy_threshold
        self.naturalness_threshold = naturalness_threshold
        
        self.samples: List[SpeechSample] = []
        self.ratings: List[EvaluatorRating] = []
        self.aggregate_ratings: Dict[str, SampleAggregateRating] = {}
    
    def create_evaluation_set(self) -> List[SpeechSample]:
        """
        Create set of 20 samples for evaluation.
        
        Returns:
            List of 20 SpeechSample definitions
        """
        
        samples = [
            # Emotion + Intensity variations (3 x 3 = 9)
            SpeechSample(
                sample_id="S001",
                emotion=EmotionLabel.SAD,
                dialect=DialectLabel.NEUTRAL,
                intensity=IntensityLabel.WHISPER,
                description="Sad whisper - low energy, melancholic"
            ),
            SpeechSample(
                sample_id="S002",
                emotion=EmotionLabel.SAD,
                dialect=DialectLabel.NEUTRAL,
                intensity=IntensityLabel.NORMAL,
                description="Sad normal - downbeat tone"
            ),
            SpeechSample(
                sample_id="S003",
                emotion=EmotionLabel.SAD,
                dialect=DialectLabel.NEUTRAL,
                intensity=IntensityLabel.LOUD,
                description="Sad loud - shouted sadness (conflicted)"
            ),
            SpeechSample(
                sample_id="S004",
                emotion=EmotionLabel.HAPPY,
                dialect=DialectLabel.NEUTRAL,
                intensity=IntensityLabel.WHISPER,
                description="Happy whisper - soft joy"
            ),
            SpeechSample(
                sample_id="S005",
                emotion=EmotionLabel.HAPPY,
                dialect=DialectLabel.NEUTRAL,
                intensity=IntensityLabel.NORMAL,
                description="Happy normal - cheerful tone"
            ),
            SpeechSample(
                sample_id="S006",
                emotion=EmotionLabel.HAPPY,
                dialect=DialectLabel.NEUTRAL,
                intensity=IntensityLabel.LOUD,
                description="Happy loud - excited, energetic"
            ),
            SpeechSample(
                sample_id="S007",
                emotion=EmotionLabel.ANGRY,
                dialect=DialectLabel.NEUTRAL,
                intensity=IntensityLabel.WHISPER,
                description="Angry whisper - cold, menacing"
            ),
            SpeechSample(
                sample_id="S008",
                emotion=EmotionLabel.ANGRY,
                dialect=DialectLabel.NEUTRAL,
                intensity=IntensityLabel.NORMAL,
                description="Angry normal - frustrated"
            ),
            SpeechSample(
                sample_id="S009",
                emotion=EmotionLabel.ANGRY,
                dialect=DialectLabel.NEUTRAL,
                intensity=IntensityLabel.LOUD,
                description="Angry loud - shouting, aggressive"
            ),
            # Calm neutral (2)
            SpeechSample(
                sample_id="S010",
                emotion=EmotionLabel.NEUTRAL,
                dialect=DialectLabel.NEUTRAL,
                intensity=IntensityLabel.NORMAL,
                description="Calm neutral - natural conversational"
            ),
            SpeechSample(
                sample_id="S011",
                emotion=EmotionLabel.NEUTRAL,
                dialect=DialectLabel.NEUTRAL,
                intensity=IntensityLabel.NORMAL,
                description="Calm neutral - professional, detached"
            ),
            # Mixed emotional arcs (3)
            SpeechSample(
                sample_id="S012",
                emotion=EmotionLabel.MIXED,
                dialect=DialectLabel.NEUTRAL,
                intensity=IntensityLabel.NORMAL,
                description="Mixed - sadness transitioning to acceptance"
            ),
            SpeechSample(
                sample_id="S013",
                emotion=EmotionLabel.MIXED,
                dialect=DialectLabel.NEUTRAL,
                intensity=IntensityLabel.NORMAL,
                description="Mixed - anger cooling to negotiation"
            ),
            SpeechSample(
                sample_id="S014",
                emotion=EmotionLabel.MIXED,
                dialect=DialectLabel.NEUTRAL,
                intensity=IntensityLabel.NORMAL,
                description="Mixed - neutral to enthusiastic"
            ),
            # Dialect variations (6)
            SpeechSample(
                sample_id="S015",
                emotion=EmotionLabel.NEUTRAL,
                dialect=DialectLabel.ANDHRA,
                intensity=IntensityLabel.NORMAL,
                description="Andhra dialect - neutral content"
            ),
            SpeechSample(
                sample_id="S016",
                emotion=EmotionLabel.HAPPY,
                dialect=DialectLabel.ANDHRA,
                intensity=IntensityLabel.NORMAL,
                description="Andhra dialect - happy emotion"
            ),
            SpeechSample(
                sample_id="S017",
                emotion=EmotionLabel.NEUTRAL,
                dialect=DialectLabel.TELANGANA,
                intensity=IntensityLabel.NORMAL,
                description="Telangana dialect - neutral content"
            ),
            SpeechSample(
                sample_id="S018",
                emotion=EmotionLabel.HAPPY,
                dialect=DialectLabel.TELANGANA,
                intensity=IntensityLabel.NORMAL,
                description="Telangana dialect - happy emotion"
            ),
            # Challenging pairs (2)
            SpeechSample(
                sample_id="S019",
                emotion=EmotionLabel.HAPPY,
                dialect=DialectLabel.ANDHRA,
                intensity=IntensityLabel.LOUD,
                description="Challenging - Andhra + happy + loud"
            ),
            SpeechSample(
                sample_id="S020",
                emotion=EmotionLabel.SAD,
                dialect=DialectLabel.TELANGANA,
                intensity=IntensityLabel.WHISPER,
                description="Challenging - Telangana + sad + whisper"
            ),
        ]
        
        self.samples = samples
        return samples
    
    def add_evaluator_rating(self, rating: EvaluatorRating) -> None:
        """Add a single evaluator's rating."""
        self.ratings.append(rating)
    
    def add_ratings_batch(self, ratings: List[EvaluatorRating]) -> None:
        """Add multiple ratings at once."""
        self.ratings.extend(ratings)
    
    def aggregate_ratings(self) -> Dict[str, SampleAggregateRating]:
        """
        Aggregate ratings across evaluators.
        
        Returns:
            Dict mapping sample_id to SampleAggregateRating
        """
        
        # Group ratings by sample
        ratings_by_sample: Dict[str, List[EvaluatorRating]] = {}
        for rating in self.ratings:
            if rating.sample_id not in ratings_by_sample:
                ratings_by_sample[rating.sample_id] = []
            ratings_by_sample[rating.sample_id].append(rating)
        
        # Aggregate each sample
        for sample in self.samples:
            sample_ratings = ratings_by_sample.get(sample.sample_id, [])
            
            if not sample_ratings:
                logger.warning(f"No ratings for sample {sample.sample_id}")
                continue
            
            # Compute aggregates
            mos_scores = [r.mos_score for r in sample_ratings]
            emotion_scores = [r.emotion_correctness for r in sample_ratings]
            dialect_scores = [r.dialect_authenticity for r in sample_ratings]
            naturalness_scores = [r.naturalness for r in sample_ratings]
            confidence_scores = [r.confidence for r in sample_ratings]
            
            mean_mos = float(np.mean(mos_scores))
            std_mos = float(np.std(mos_scores))
            mean_emotion = float(np.mean(emotion_scores))
            mean_dialect = float(np.mean(dialect_scores))
            mean_naturalness = float(np.mean(naturalness_scores))
            mean_confidence = float(np.mean(confidence_scores))
            
            # Check thresholds
            passes_mos = mean_mos >= self.mos_threshold
            passes_emotion = mean_emotion >= self.emotion_accuracy_threshold
            
            # Quality classification
            if mean_mos >= 4.5:
                quality = "EXCELLENT"
            elif mean_mos >= 3.8:
                quality = "GOOD"
            elif mean_mos >= 3.0:
                quality = "ACCEPTABLE"
            else:
                quality = "POOR"
            
            aggregate = SampleAggregateRating(
                sample_id=sample.sample_id,
                emotion=sample.emotion.value,
                dialect=sample.dialect.value,
                intensity=sample.intensity.value,
                n_evaluators=len(sample_ratings),
                mean_mos=mean_mos,
                std_mos=std_mos,
                mean_emotion_correctness=mean_emotion,
                mean_dialect_authenticity=mean_dialect,
                mean_naturalness=mean_naturalness,
                mean_confidence=mean_confidence,
                passes_mos_threshold=passes_mos,
                passes_emotion_threshold=passes_emotion,
                overall_quality=quality
            )
            
            self.aggregate_ratings[sample.sample_id] = aggregate
        
        return self.aggregate_ratings
    
    def generate_human_eval_report(self, output_file: Optional[str] = None) -> Dict:
        """Generate HUMAN_EVAL_REPORT.json"""
        
        # Ensure aggregation done
        if not self.aggregate_ratings:
            self.aggregate_ratings()
        
        # Compute overall statistics
        if self.aggregate_ratings:
            mos_scores = [r.mean_mos for r in self.aggregate_ratings.values()]
            emotion_accuracy = [r.mean_emotion_correctness for r in self.aggregate_ratings.values()]
            dialect_authenticity = [r.mean_dialect_authenticity for r in self.aggregate_ratings.values()]
            naturalness = [r.mean_naturalness for r in self.aggregate_ratings.values()]
            
            passing_mos = sum(1 for r in self.aggregate_ratings.values() if r.passes_mos_threshold)
            passing_emotion = sum(1 for r in self.aggregate_ratings.values() if r.passes_emotion_threshold)
        else:
            mos_scores = emotion_accuracy = dialect_authenticity = naturalness = []
            passing_mos = passing_emotion = 0
        
        report = {
            'timestamp': str(np.datetime64('now')),
            'evaluation_framework': {
                'type': 'BLIND_LISTENING_TEST',
                'note': 'Framework ready for human evaluation. Synthetic ratings shown below for demonstration.',
                'mos_threshold': self.mos_threshold,
                'emotion_accuracy_threshold': self.emotion_accuracy_threshold,
                'naturalness_threshold': self.naturalness_threshold
            },
            'sample_set': {
                'total_samples': len(self.samples),
                'categories': {
                    'emotion_intensity_pairs': 9,
                    'calm_neutral': 2,
                    'mixed_emotional_arcs': 3,
                    'dialect_variations': 6,
                    'challenging_pairs': 2
                }
            },
            'evaluation_results': {
                'total_evaluators': len(set(r.evaluator_id for r in self.ratings)) if self.ratings else 0,
                'total_ratings': len(self.ratings),
                'samples_rated': len(self.aggregate_ratings),
                'mean_mos': float(np.mean(mos_scores)) if mos_scores else 0.0,
                'std_mos': float(np.std(mos_scores)) if mos_scores else 0.0,
                'samples_passing_mos': passing_mos,
                'mean_emotion_accuracy': float(np.mean(emotion_accuracy)) if emotion_accuracy else 0.0,
                'samples_passing_emotion': passing_emotion,
                'mean_dialect_authenticity': float(np.mean(dialect_authenticity)) if dialect_authenticity else 0.0,
                'mean_naturalness': float(np.mean(naturalness)) if naturalness else 0.0
            },
            'quality_distribution': {
                'EXCELLENT': sum(1 for r in self.aggregate_ratings.values() if r.overall_quality == 'EXCELLENT'),
                'GOOD': sum(1 for r in self.aggregate_ratings.values() if r.overall_quality == 'GOOD'),
                'ACCEPTABLE': sum(1 for r in self.aggregate_ratings.values() if r.overall_quality == 'ACCEPTABLE'),
                'POOR': sum(1 for r in self.aggregate_ratings.values() if r.overall_quality == 'POOR')
            },
            'target_metrics': {
                'mos_target': self.mos_threshold,
                'emotion_accuracy_target': self.emotion_accuracy_threshold,
                'mos_achieved': float(np.mean(mos_scores)) if mos_scores else 0.0,
                'emotion_accuracy_achieved': float(np.mean(emotion_accuracy)) if emotion_accuracy else 0.0,
                'deployment_ready': (
                    float(np.mean(mos_scores)) >= self.mos_threshold if mos_scores else False
                ) and (
                    float(np.mean(emotion_accuracy)) >= self.emotion_accuracy_threshold if emotion_accuracy else False
                )
            },
            'sample_ratings': [
                asdict(r) for r in self.aggregate_ratings.values()
            ]
        }
        
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"✓ Human eval report saved: {output_file}")
        
        return report


class ListeningTestSimulator:
    """
    Simulates evaluator ratings for testing purposes.
    NOTE: In production, real human evaluators would provide these ratings.
    """
    
    @staticmethod
    def simulate_evaluations(
        samples: List[SpeechSample],
        n_evaluators: int = 5,
        quality_level: str = "GOOD"
    ) -> List[EvaluatorRating]:
        """
        Generate simulated evaluator ratings.
        
        Args:
            samples: List of samples to evaluate
            n_evaluators: Number of simulated evaluators
            quality_level: "EXCELLENT", "GOOD", "ACCEPTABLE", or "POOR"
            
        Returns:
            List of simulated EvaluatorRating objects
        """
        
        # Quality distribution parameters
        quality_params = {
            'EXCELLENT': {'mos_mean': 4.7, 'mos_std': 0.2, 'emotion_mean': 0.95},
            'GOOD': {'mos_mean': 4.0, 'mos_std': 0.4, 'emotion_mean': 0.85},
            'ACCEPTABLE': {'mos_mean': 3.3, 'mos_std': 0.5, 'emotion_mean': 0.72},
            'POOR': {'mos_mean': 2.5, 'mos_std': 0.6, 'emotion_mean': 0.55}
        }
        
        params = quality_params.get(quality_level, quality_params['ACCEPTABLE'])
        
        ratings = []
        for sample in samples:
            for eval_idx in range(n_evaluators):
                # Generate ratings with some variance
                mos = np.clip(
                    np.random.normal(params['mos_mean'], params['mos_std']),
                    1.0, 5.0
                )
                
                # Emotion correctness varies by actual emotion complexity
                if sample.emotion == EmotionLabel.MIXED:
                    emotion_base = params['emotion_mean'] - 0.15
                else:
                    emotion_base = params['emotion_mean']
                
                emotion_correctness = np.clip(
                    emotion_base + np.random.normal(0, 0.1),
                    0.0, 1.0
                )
                
                # Dialect authenticity
                if sample.dialect != DialectLabel.NEUTRAL:
                    dialect_score = np.clip(
                        emotion_correctness - 0.05 + np.random.normal(0, 0.1),
                        0.0, 1.0
                    )
                else:
                    dialect_score = 0.95
                
                naturalness = np.clip(
                    mos / 5.0 + np.random.normal(0, 0.1),
                    0.0, 1.0
                )
                
                rating = EvaluatorRating(
                    evaluator_id=f"EVL_{eval_idx:02d}",
                    sample_id=sample.sample_id,
                    mos_score=float(mos),
                    emotion_correctness=float(emotion_correctness),
                    dialect_authenticity=float(dialect_score),
                    naturalness=float(naturalness),
                    confidence=0.85
                )
                
                ratings.append(rating)
        
        return ratings


# Example usage
if __name__ == "__main__":
    evaluator = HumanPerceptionEvaluator()
    
    # Create evaluation set
    samples = evaluator.create_evaluation_set()
    print(f"✓ Created evaluation set with {len(samples)} samples")
    
    # Simulate ratings (for demo purposes)
    print("\n  Generating simulated evaluations (demo only)...")
    simulated_ratings = ListeningTestSimulator.simulate_evaluations(
        samples,
        n_evaluators=5,
        quality_level='GOOD'
    )
    
    evaluator.add_ratings_batch(simulated_ratings)
    
    # Aggregate and report
    evaluator.aggregate_ratings()
    report = evaluator.generate_human_eval_report(
        "outputs/v3_realism/HUMAN_EVAL_REPORT.json"
    )
    
    print(f"✓ Human evaluation report generated")
    print(f"  Mean MOS: {report['evaluation_results']['mean_mos']:.2f} (target: {report['target_metrics']['mos_target']})")
    print(f"  Emotion accuracy: {report['evaluation_results']['mean_emotion_accuracy']:.1%} (target: {80}%)")
    print(f"  Deployment ready: {report['target_metrics']['deployment_ready']}")
