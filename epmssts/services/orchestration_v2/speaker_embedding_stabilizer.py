"""
SPEAKER EMBEDDING STABILIZER - PRODUCTION FIX
==============================================

Stabilization improvements:
- L2 normalization enforced on all embeddings
- Speaker component frozen in style encoder
- EMA applied only on emotion subspace (first 2 dims)
- Re-anchoring when similarity < 0.85
- Prevents cross-talk between emotion and speaker vectors
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import torch
import torch.nn as nn


@dataclass
class SpeakerStabilityMetrics:
    """Metrics tracking speaker embedding stability"""
    turn_number: int
    similarity_to_baseline: float
    drift_detected: bool
    re_anchored: bool
    emotion_intensity: float


class StabilizedSpeakerEmbedding:
    """
    Speaker embedding with stability guarantees.
    
    Design:
    - Full embedding: [emotion_subspace (2d), speaker_subspace (254d)]
    - Emotion subspace: Updated with EMA (alpha=0.3)
    - Speaker subspace: Frozen to baseline
    - Re-anchor: Reset speaker when similarity < 0.85
    """
    
    def __init__(
        self,
        baseline_embedding: np.ndarray,
        ema_alpha: float = 0.3,
        similarity_threshold: float = 0.85
    ):
        """
        Args:
            baseline_embedding: Initial speaker embedding (256d), L2 normalized
            ema_alpha: EMA smoothing factor for emotion subspace (0.0-1.0)
            similarity_threshold: Re-anchor threshold (default 0.85)
        """
        assert baseline_embedding.shape[0] == 256, "Expected 256d embedding"
        
        # Store baseline (L2 normalized)
        self.baseline_embedding = baseline_embedding / (np.linalg.norm(baseline_embedding) + 1e-8)
        
        # Split into emotion (2d) and speaker (254d) subspaces
        self.emotion_subspace = self.baseline_embedding[:2].copy()
        self.speaker_subspace = self.baseline_embedding[2:].copy()
        
        # Config
        self.ema_alpha = ema_alpha
        self.similarity_threshold = similarity_threshold
        
        # Tracking
        self.turn_count = 0
        self.re_anchor_count = 0
        self.drift_events = 0
        self.metrics_history = []
    
    def update_emotion(self, emotion_intensity: np.ndarray) -> SpeakerStabilityMetrics:
        """
        Update emotion subspace with EMA, keep speaker frozen.
        
        Args:
            emotion_intensity: 2d array [arousal, valence]
        
        Returns:
            Stability metrics for this turn
        """
        assert len(emotion_intensity) == 2, "Expected 2d emotion vector [arousal, valence]"
        
        self.turn_count += 1
        
        # Apply EMA only to emotion subspace
        self.emotion_subspace = (
            self.ema_alpha * emotion_intensity + 
            (1 - self.ema_alpha) * self.emotion_subspace
        )
        
        # Reconstruct full embedding (speaker frozen)
        current_embedding = np.concatenate([self.emotion_subspace, self.speaker_subspace])
        
        # L2 normalize
        current_embedding = current_embedding / (np.linalg.norm(current_embedding) + 1e-8)
        
        # Compute similarity to baseline
        similarity = float(np.dot(current_embedding, self.baseline_embedding))
        
        # Check for drift
        drift_detected = similarity < self.similarity_threshold
        re_anchored = False
        
        if drift_detected:
            # Re-anchor: reset speaker subspace to baseline
            self.speaker_subspace = self.baseline_embedding[2:].copy()
            self.re_anchor_count += 1
            self.drift_events += 1
            re_anchored = True
            
            # Recompute similarity after re-anchoring
            current_embedding = np.concatenate([self.emotion_subspace, self.speaker_subspace])
            current_embedding = current_embedding / (np.linalg.norm(current_embedding) + 1e-8)
            similarity = float(np.dot(current_embedding, self.baseline_embedding))
        
        # Record metrics
        metrics = SpeakerStabilityMetrics(
            turn_number=self.turn_count,
            similarity_to_baseline=similarity,
            drift_detected=drift_detected,
            re_anchored=re_anchored,
            emotion_intensity=float(np.linalg.norm(emotion_intensity))
        )
        self.metrics_history.append(metrics)
        
        return metrics
    
    def get_current_embedding(self) -> np.ndarray:
        """Get current full embedding (L2 normalized)"""
        current = np.concatenate([self.emotion_subspace, self.speaker_subspace])
        return current / (np.linalg.norm(current) + 1e-8)
    
    def get_stability_summary(self) -> dict:
        """Get summary statistics for stability assessment"""
        if not self.metrics_history:
            return {}
        
        similarities = [m.similarity_to_baseline for m in self.metrics_history]
        
        return {
            'total_turns': self.turn_count,
            'mean_similarity': float(np.mean(similarities)),
            'min_similarity': float(np.min(similarities)),
            'drift_events': self.drift_events,
            're_anchor_count': self.re_anchor_count,
            'passed': (
                np.mean(similarities) >= 0.85 and 
                self.drift_events <= 3
            )
        }
    
    def reset_to_baseline(self) -> None:
        """Hard reset to baseline (for debugging/recovery)"""
        self.emotion_subspace = self.baseline_embedding[:2].copy()
        self.speaker_subspace = self.baseline_embedding[2:].copy()
        self.turn_count = 0
        self.re_anchor_count = 0
        self.drift_events = 0
        self.metrics_history = []


class StyleEncoderWithStability(nn.Module):
    """
    Style encoder wrapper with speaker stability built-in.
    
    Wraps UnifiedStyleEncoder and adds:
    - Automatic L2 normalization
    - Speaker subspace freezing
    - Session-level EMA tracking
    """
    
    def __init__(
        self,
        base_encoder: nn.Module,
        ema_alpha: float = 0.3,
        similarity_threshold: float = 0.85
    ):
        super().__init__()
        self.base_encoder = base_encoder
        self.ema_alpha = ema_alpha
        self.similarity_threshold = similarity_threshold
        
        # Session state (set via init_session)
        self.session_stabilizer: Optional[StabilizedSpeakerEmbedding] = None
    
    def init_session(self, baseline_audio: torch.Tensor) -> None:
        """
        Initialize session with baseline speaker embedding.
        Call this at the start of each conversation/session.
        
        Args:
            baseline_audio: First audio sample (1, seq_len)
        """
        with torch.no_grad():
            # Extract baseline embedding
            baseline_emb = self.base_encoder(baseline_audio)  # (1, 256)
            baseline_np = baseline_emb.squeeze(0).cpu().numpy()
            
            # Initialize stabilizer
            self.session_stabilizer = StabilizedSpeakerEmbedding(
                baseline_embedding=baseline_np,
                ema_alpha=self.ema_alpha,
                similarity_threshold=self.similarity_threshold
            )
    
    def forward(
        self,
        audio: torch.Tensor,
        emotion_intensity: Optional[np.ndarray] = None
    ) -> torch.Tensor:
        """
        Forward pass with stability.
        
        Args:
            audio: Input audio (1, seq_len)
            emotion_intensity: Optional 2d emotion vector for update
        
        Returns:
            Stabilized style embedding (1, 256)
        """
        # Extract raw embedding
        raw_emb = self.base_encoder(audio)  # (1, 256)
        
        # If no session active, return raw (L2 normalized)
        if self.session_stabilizer is None:
            return raw_emb / (torch.norm(raw_emb, dim=-1, keepdim=True) + 1e-8)
        
        # If emotion provided, update stabilizer
        if emotion_intensity is not None:
            self.session_stabilizer.update_emotion(emotion_intensity)
        
        # Get stabilized embedding
        stable_emb = self.session_stabilizer.get_current_embedding()
        stable_tensor = torch.from_numpy(stable_emb).float().unsqueeze(0)
        
        # Move to same device as input
        if audio.is_cuda:
            stable_tensor = stable_tensor.cuda()
        
        return stable_tensor
    
    def get_session_metrics(self) -> dict:
        """Get stability metrics for current session"""
        if self.session_stabilizer is None:
            return {'error': 'No active session'}
        return self.session_stabilizer.get_stability_summary()
    
    def reset_session(self) -> None:
        """Clear session state"""
        self.session_stabilizer = None


# Utility functions for testing/validation

def validate_speaker_stability(
    stabilizer: StabilizedSpeakerEmbedding,
    emotion_sequence: list[np.ndarray],
    verbose: bool = True
) -> dict:
    """
    Test speaker stability across emotion sequence.
    
    Args:
        stabilizer: Initialized stabilizer
        emotion_sequence: List of 2d emotion vectors
        verbose: Print turn-by-turn metrics
    
    Returns:
        Summary statistics
    """
    for idx, emotion in enumerate(emotion_sequence, 1):
        metrics = stabilizer.update_emotion(emotion)
        
        if verbose:
            status = "⚠️ DRIFT+ANCHOR" if metrics.re_anchored else (
                "⚠️ DRIFT" if metrics.drift_detected else "✓ STABLE"
            )
            print(f"Turn {idx}: {status} | Similarity={metrics.similarity_to_baseline:.3f}")
    
    return stabilizer.get_stability_summary()


def generate_emotion_sequence(turns: int, pattern: str = 'escalation') -> list[np.ndarray]:
    """
    Generate test emotion sequence.
    
    Args:
        turns: Number of conversation turns
        pattern: 'escalation', 'deescalation', or 'mixed'
    
    Returns:
        List of 2d emotion vectors [arousal, valence]
    """
    sequence = []
    
    for t in range(turns):
        if pattern == 'escalation':
            # Rising arousal, falling valence
            arousal = 0.3 + (t / turns) * 0.6
            valence = 0.7 - (t / turns) * 0.4
        
        elif pattern == 'deescalation':
            # Falling arousal, rising valence
            arousal = 0.9 - (t / turns) * 0.6
            valence = 0.3 + (t / turns) * 0.4
        
        else:  # mixed
            # Sinusoidal pattern
            arousal = 0.5 + 0.4 * np.sin(2 * np.pi * t / turns)
            valence = 0.5 + 0.3 * np.cos(2 * np.pi * t / turns)
        
        sequence.append(np.array([arousal, valence]))
    
    return sequence
