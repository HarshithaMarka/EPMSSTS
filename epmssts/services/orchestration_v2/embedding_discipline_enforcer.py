"""
PHASE 2: EMBEDDING DISCIPLINE ENFORCER
Strict enforcement of embedding standards for production realism

Purpose:
- L2 normalization on all embeddings
- Fixed dimensional boundaries: emotion [0-1], speaker [2-255]
- EMA smoothing ONLY on emotion dims
- Re-anchor speaker if similarity <0.85
- Log drift per turn

Author: Realism Engineering
Date: 2026-03-02
"""

import json
import numpy as np
from dataclasses import dataclass, field
from typing import Tuple, Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class EmbeddingSnapshot:
    """Snapshot of embedding state at a turn."""
    turn_id: int
    full_embedding: np.ndarray  # [256]
    emotion_subspace: np.ndarray  # [2]
    speaker_subspace: np.ndarray  # [254]
    is_l2_normalized: bool
    l2_norm: float


@dataclass
class DriftMetrics:
    """Drift metrics for embedding stability."""
    turn_id: int
    emotion_drift: float
    speaker_drift: float
    speaker_consistency: float
    l2_normalization_status: str
    re_anchor_triggered: bool
    remarks: str = ""


class EmbeddingDisciplineEnforcer:
    """Strict embedding enforcement."""
    
    def __init__(self, 
                 emotion_dims: Tuple[int, int] = (0, 1),
                 speaker_dims: Tuple[int, int] = (2, 255),
                 ema_alpha: float = 0.3,
                 reanchor_threshold: float = 0.85):
        """
        Args:
            emotion_dims: start, end indices for emotion (inclusive)
            speaker_dims: start, end indices for speaker (inclusive)
            ema_alpha: EMA smoothing factor for emotion
            reanchor_threshold: cosine similarity below which to re-anchor
        """
        self.emotion_dims = emotion_dims
        self.speaker_dims = speaker_dims
        self.ema_alpha = ema_alpha
        self.reanchor_threshold = reanchor_threshold
        
        self.baseline_embedding = None
        self.current_emotion = None
        self.current_speaker = None
        self.turn_history: List[EmbeddingSnapshot] = []
        self.drift_history: List[DriftMetrics] = []
    
    def enforce_l2_normalization(self, embedding: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Enforce L2 normalization on embedding.
        
        Returns:
            normalized_embedding: [256]
            l2_norm: norm before normalization
        """
        l2_norm = np.linalg.norm(embedding, ord=2)
        
        if l2_norm < 1e-8:
            # Degenerate embedding, return small random vector
            logger.warning(f"Embedding has zero norm, returning random vector")
            normalized = np.random.randn(len(embedding)) * 1e-3
            return normalized, l2_norm
        
        normalized = embedding / l2_norm
        
        # Verify normalization
        actual_norm = np.linalg.norm(normalized, ord=2)
        if not np.isclose(actual_norm, 1.0, atol=1e-5):
            logger.warning(f"L2 normalization failed: norm={actual_norm}")
        
        return normalized, l2_norm
    
    def split_embedding(self, embedding: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Split embedding into emotion and speaker subspaces.
        
        Returns:
            emotion_subspace: [2] normalized
            speaker_subspace: [254] normalized
        """
        emotion_start, emotion_end = self.emotion_dims
        speaker_start, speaker_end = self.speaker_dims
        
        emotion = embedding[emotion_start:emotion_end+1].copy()
        speaker = embedding[speaker_start:speaker_end+1].copy()
        
        # Normalize emotion subspace
        emotion_norm = np.linalg.norm(emotion, ord=2)
        if emotion_norm > 1e-8:
            emotion = emotion / emotion_norm
        
        # Normalize speaker subspace
        speaker_norm = np.linalg.norm(speaker, ord=2)
        if speaker_norm > 1e-8:
            speaker = speaker / speaker_norm
        
        return emotion, speaker
    
    def reconstruct_embedding(self, 
                             emotion: np.ndarray,
                             speaker: np.ndarray) -> np.ndarray:
        """Reconstruct full 256d embedding from subspaces."""
        embedding = np.zeros(256)
        
        emotion_start, emotion_end = self.emotion_dims
        speaker_start, speaker_end = self.speaker_dims
        
        embedding[emotion_start:emotion_end+1] = emotion
        embedding[speaker_start:speaker_end+1] = speaker
        
        # L2 normalize the reconstructed embedding
        embedding_normalized, _ = self.enforce_l2_normalization(embedding)
        
        return embedding_normalized
    
    def initialize_baseline(self, embedding: np.ndarray) -> None:
        """Initialize baseline embedding for drift comparison."""
        embedding_normalized, _ = self.enforce_l2_normalization(embedding)
        
        self.baseline_embedding = embedding_normalized
        emotion, speaker = self.split_embedding(embedding_normalized)
        
        self.current_emotion = emotion.copy()
        self.current_speaker = speaker.copy()
        
        logger.info(f"Baseline initialized: emotion_norm={np.linalg.norm(emotion):.4f}, "
                   f"speaker_norm={np.linalg.norm(speaker):.4f}")
    
    def process_turn(self, embedding: np.ndarray, turn_id: int) -> DriftMetrics:
        """
        Process embedding for a single turn.
        
        Enforces:
        - L2 normalization
        - Splits into emotion/speaker
        - Applies EMA only to emotion
        - Detects speaker drift and re-anchors if needed
        
        Returns:
            DriftMetrics
        """
        if self.baseline_embedding is None:
            self.initialize_baseline(embedding)
        
        # 1. Enforce L2 normalization
        embedding_normalized, l2_norm = self.enforce_l2_normalization(embedding)
        l2_status = "OK" if np.isclose(l2_norm, 1.0, atol=0.1) else "DENORMALIZED"
        
        # 2. Split into subspaces
        new_emotion, new_speaker = self.split_embedding(embedding_normalized)
        
        # 3. Apply EMA ONLY to emotion dimension
        # Emotion subspace: smooth with EMA
        self.current_emotion = (
            self.ema_alpha * new_emotion +
            (1 - self.ema_alpha) * self.current_emotion
        )
        
        # 4. Detect speaker drift
        speaker_similarity = np.dot(new_speaker, self.current_speaker)
        speaker_similarity = np.clip(speaker_similarity, -1.0, 1.0)
        
        # 5. Re-anchor if drift exceeds threshold
        reanchor_triggered = False
        if speaker_similarity < self.reanchor_threshold:
            reanchor_triggered = True
            # Re-anchor to baseline speaker component
            _, baseline_speaker = self.split_embedding(self.baseline_embedding)
            self.current_speaker = baseline_speaker.copy()
            logger.warning(f"Turn {turn_id}: Speaker re-anchorred (similarity={speaker_similarity:.4f})")
        else:
            # Gradually adapt speaker (very slowly)
            self.current_speaker = (
                0.05 * new_speaker +  # Small adaptation
                0.95 * self.current_speaker
            )
        
        # 6. Reconstruct with EMA-smoothed emotion and (possibly re-anchored) speaker
        embedding_disciplined = self.reconstruct_embedding(
            self.current_emotion,
            self.current_speaker
        )
        
        # 7. Compute drift metrics
        emotion_drift = np.linalg.norm(new_emotion - self.current_emotion)
        speaker_drift = 1.0 - speaker_similarity  # Distance metric
        
        # Store snapshot
        snapshot = EmbeddingSnapshot(
            turn_id=turn_id,
            full_embedding=embedding_disciplined,
            emotion_subspace=self.current_emotion.copy(),
            speaker_subspace=self.current_speaker.copy(),
            is_l2_normalized=l2_status == "OK",
            l2_norm=float(l2_norm)
        )
        self.turn_history.append(snapshot)
        
        # Create drift metrics
        metrics = DriftMetrics(
            turn_id=turn_id,
            emotion_drift=float(emotion_drift),
            speaker_drift=float(speaker_drift),
            speaker_consistency=float(speaker_similarity),
            l2_normalization_status=l2_status,
            re_anchor_triggered=reanchor_triggered,
            remarks=f"Reanchor: {reanchor_triggered}" if reanchor_triggered else "Stable"
        )
        self.drift_history.append(metrics)
        
        return metrics
    
    def process_sequence(self, embeddings: np.ndarray) -> List[DriftMetrics]:
        """
        Process sequence of embeddings (conversation turn sequence).
        
        Args:
            embeddings: [n_turns, 256]
            
        Returns:
            List of DriftMetrics
        """
        metrics_list = []
        
        for turn_id, emb in enumerate(embeddings):
            metrics = self.process_turn(emb, turn_id)
            metrics_list.append(metrics)
        
        return metrics_list
    
    def get_stability_report(self) -> Dict:
        """Generate comprehensive stability report."""
        if not self.drift_history:
            return {'status': 'NO_DATA'}
        
        # Aggregate metrics
        emotion_drifts = [m.emotion_drift for m in self.drift_history]
        speaker_drifts = [m.speaker_drift for m in self.drift_history]
        speaker_consistency = [m.speaker_consistency for m in self.drift_history]
        reanchor_count = sum(1 for m in self.drift_history if m.re_anchor_triggered)
        
        # L2 normalization check
        l2_compliant = all(s.is_l2_normalized for s in self.turn_history)
        
        # Dimensional boundaries check
        dim_compliant = all(
            0 <= np.max(np.abs(s.emotion_subspace)) <= 1.0 and
            0 <= np.max(np.abs(s.speaker_subspace)) <= 1.0
            for s in self.turn_history
        )
        
        report = {
            'turns_processed': len(self.drift_history),
            'l2_normalization_compliant': bool(l2_compliant),
            'dimensional_boundaries_compliant': bool(dim_compliant),
            'emotion_drift': {
                'mean': float(np.mean(emotion_drifts)),
                'max': float(np.max(emotion_drifts)),
                'std': float(np.std(emotion_drifts))
            },
            'speaker_drift': {
                'mean': float(np.mean(speaker_drifts)),
                'max': float(np.max(speaker_drifts)),
                'std': float(np.std(speaker_drifts))
            },
            'speaker_consistency': {
                'mean': float(np.mean(speaker_consistency)),
                'min': float(np.min(speaker_consistency)),
                'std': float(np.std(speaker_consistency))
            },
            'reanchor_events': int(reanchor_count),
            'reanchor_rate': float(reanchor_count / len(self.drift_history)) if self.drift_history else 0.0,
            'stability_status': 'STABLE' if reanchor_count <= len(self.drift_history) * 0.1 else 'UNSTABLE'
        }
        
        return report
    
    def generate_embedding_stability_report(self, output_file: Optional[str] = None) -> Dict:
        """Generate EMBEDDING_STABILITY_REPORT.json"""
        
        report = {
            'timestamp': str(np.datetime64('now')),
            'configuration': {
                'emotion_dims': list(self.emotion_dims),
                'speaker_dims': list(self.speaker_dims),
                'ema_alpha': self.ema_alpha,
                'reanchor_threshold': self.reanchor_threshold
            },
            'turns_processed': len(self.drift_history),
            'stability_metrics': self.get_stability_report(),
            'turn_history': [
                {
                    'turn_id': m.turn_id,
                    'emotion_drift': m.emotion_drift,
                    'speaker_drift': m.speaker_drift,
                    'speaker_consistency': m.speaker_consistency,
                    'l2_normalized': m.l2_normalization_status,
                    'reanchor_triggered': m.re_anchor_triggered,
                    'remarks': m.remarks
                }
                for m in self.drift_history
            ]
        }
        
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
        
        return report


# Example usage
if __name__ == "__main__":
    enforcer = EmbeddingDisciplineEnforcer()
    
    # Create synthetic embeddings for testing
    n_turns = 10
    embeddings = np.random.randn(n_turns, 256)
    
    # Normalize them
    embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    
    print("Processing embedding sequence...")
    metrics_list = enforcer.process_sequence(embeddings)
    
    for m in metrics_list:
        print(f"  Turn {m.turn_id}: emotion_drift={m.emotion_drift:.4f}, "
              f"speaker_consistency={m.speaker_consistency:.4f}, "
              f"reanchor={m.re_anchor_triggered}")
    
    report = enforcer.generate_embedding_stability_report(
        "outputs/v3_realism/EMBEDDING_STABILITY_REPORT.json"
    )
    
    print(f"\n✓ Stability Report Generated")
    print(f"  Turns processed: {report['turns_processed']}")
    print(f"  L2 compliant: {report['stability_metrics']['l2_normalization_compliant']}")
    print(f"  Dimensional compliant: {report['stability_metrics']['dimensional_boundaries_compliant']}")
    print(f"  Stability: {report['stability_metrics']['stability_status']}")
