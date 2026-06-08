"""
EMOTION VALIDATOR V2 - ADAPTIVE THRESHOLD
==========================================

Stabilization improvements:
- Adaptive threshold based on similarity distribution statistics
- Target retry rate <20%
- No more hardcoded 0.75 threshold
- Statistical calibration required before deployment
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol, Tuple

import numpy as np


class EmotionEmbeddingModel(Protocol):
    async def extract_embedding(self, audio_waveform: np.ndarray, sample_rate: int) -> np.ndarray:
        ...


@dataclass
class EmotionValidationResult:
    emotion_similarity: float
    retry_performed: bool
    waveform: np.ndarray
    threshold_used: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "emotion_similarity": float(self.emotion_similarity),
            "retry_performed": bool(self.retry_performed),
            "threshold_used": float(self.threshold_used),
        }


@dataclass
class ThresholdCalibration:
    """Statistics from calibration phase"""
    mean_similarity: float
    std_similarity: float
    p10: float
    p90: float
    adaptive_threshold: float
    sample_count: int
    estimated_retry_rate: float


class AdaptiveEmotionValidator:
    """
    Emotion validator with adaptive threshold calibration.
    
    Replaces hardcoded 0.75 with statistically derived threshold:
    threshold = mean - (0.5 * std)
    
    Requires calibration phase before production use.
    """
    
    def __init__(
        self,
        model: EmotionEmbeddingModel,
        calibration_path: Optional[Path] = None,
        fallback_threshold: float = 0.65,  # Lower fallback than old 0.75
    ):
        self.model = model
        self.fallback_threshold = fallback_threshold
        self.calibration: Optional[ThresholdCalibration] = None
        
        # Load calibration if available
        if calibration_path and calibration_path.exists():
            self._load_calibration(calibration_path)
        else:
            print(f"⚠️ No calibration found, using fallback threshold: {fallback_threshold}")
    
    def _load_calibration(self, path: Path) -> None:
        """Load pre-computed calibration statistics"""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            self.calibration = ThresholdCalibration(
                mean_similarity=data['mean_similarity'],
                std_similarity=data['std_similarity'],
                p10=data['p10'],
                p90=data['p90'],
                adaptive_threshold=data['adaptive_threshold'],
                sample_count=data['sample_count'],
                estimated_retry_rate=data['estimated_retry_rate']
            )
            
            print(f"✓ Loaded calibration: threshold={self.calibration.adaptive_threshold:.3f}, "
                  f"retry_rate={self.calibration.estimated_retry_rate:.1%}")
            
        except Exception as e:
            print(f"⚠️ Failed to load calibration: {e}")
            self.calibration = None
    
    @property
    def threshold(self) -> float:
        """Get current threshold (adaptive if calibrated, else fallback)"""
        if self.calibration:
            return self.calibration.adaptive_threshold
        return self.fallback_threshold
    
    async def validate_and_retry(
        self,
        source_emotion_embedding: np.ndarray,
        generated_waveform: np.ndarray,
        sample_rate: int,
        resynthesize: Callable[[float], Awaitable[np.ndarray]],
        base_intensity: float = 1.0,
    ) -> EmotionValidationResult:
        """
        Validate emotion preservation with adaptive threshold.
        Single retry on failure with intensity boost.
        """
        # Extract output embedding
        output_embedding = await self.model.extract_embedding(generated_waveform, sample_rate)
        similarity = self._cosine_similarity(source_emotion_embedding, output_embedding)
        
        current_threshold = self.threshold
        
        # Check if retry needed
        if similarity >= current_threshold:
            return EmotionValidationResult(
                emotion_similarity=float(similarity),
                retry_performed=False,
                waveform=generated_waveform,
                threshold_used=current_threshold
            )
        
        # Single retry with intensity boost
        boosted_intensity = min(1.35, base_intensity * 1.18)
        retried_waveform = await resynthesize(boosted_intensity)
        retried_embedding = await self.model.extract_embedding(retried_waveform, sample_rate)
        retried_similarity = self._cosine_similarity(source_emotion_embedding, retried_embedding)
        
        return EmotionValidationResult(
            emotion_similarity=float(retried_similarity),
            retry_performed=True,
            waveform=retried_waveform,
            threshold_used=current_threshold
        )
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity with numerical stability"""
        a_vec = a.astype(np.float32).reshape(-1)
        b_vec = b.astype(np.float32).reshape(-1)
        
        # L2 normalize
        a_norm = np.linalg.norm(a_vec)
        b_norm = np.linalg.norm(b_vec)
        
        if a_norm <= 1e-8 or b_norm <= 1e-8:
            return 0.0
        
        return float(np.dot(a_vec / a_norm, b_vec / b_norm))
    
    @staticmethod
    async def calibrate_threshold(
        model: EmotionEmbeddingModel,
        audio_samples: List[Tuple[np.ndarray, int]],  # (audio, sample_rate) pairs
        target_retry_rate: float = 0.20,
        output_path: Optional[Path] = None
    ) -> ThresholdCalibration:
        """
        Run calibration phase to compute adaptive threshold.
        
        Args:
            model: Emotion embedding model
            audio_samples: List of (audio_waveform, sample_rate) tuples
            target_retry_rate: Target retry rate (default 20%)
            output_path: Where to save calibration JSON
        
        Returns:
            Calibration statistics
        """
        print(f"\n🔧 Calibrating emotion threshold with {len(audio_samples)} samples...")
        
        if len(audio_samples) < 10:
            raise ValueError(f"Need at least 10 samples for calibration, got {len(audio_samples)}")
        
        # Compute pairwise similarities
        similarities = []
        
        for idx, (audio, sr) in enumerate(audio_samples, 1):
            # Extract source embedding
            source_emb = await model.extract_embedding(audio, sr)
            
            # Simulate output with perturbation (in real scenario, run full pipeline)
            # Add Gaussian noise to simulate processing artifacts
            noise = np.random.randn(*source_emb.shape) * 0.1
            output_emb = source_emb + noise
            output_emb = output_emb / (np.linalg.norm(output_emb) + 1e-8)
            
            # Compute similarity
            similarity = float(np.dot(
                source_emb / (np.linalg.norm(source_emb) + 1e-8),
                output_emb
            ))
            similarities.append(similarity)
            
            if idx % 10 == 0:
                print(f"  [{idx}/{len(audio_samples)}] Similarity: {similarity:.3f}")
        
        # Compute statistics
        mean_sim = float(np.mean(similarities))
        std_sim = float(np.std(similarities))
        p10 = float(np.percentile(similarities, 10))
        p90 = float(np.percentile(similarities, 90))
        
        # Adaptive threshold: mean - (0.5 * std)
        adaptive_threshold = mean_sim - (0.5 * std_sim)
        
        # Clamp to reasonable range
        adaptive_threshold = max(0.60, min(0.85, adaptive_threshold))
        
        # Estimate retry rate
        retry_rate = float(np.sum(np.array(similarities) < adaptive_threshold) / len(similarities))
        
        calibration = ThresholdCalibration(
            mean_similarity=mean_sim,
            std_similarity=std_sim,
            p10=p10,
            p90=p90,
            adaptive_threshold=adaptive_threshold,
            sample_count=len(similarities),
            estimated_retry_rate=retry_rate
        )
        
        print(f"\n📊 Calibration Results:")
        print(f"  Mean Similarity: {mean_sim:.3f}")
        print(f"  Std Similarity:  {std_sim:.3f}")
        print(f"  P10: {p10:.3f}")
        print(f"  P90: {p90:.3f}")
        print(f"  Adaptive Threshold: {adaptive_threshold:.3f}")
        print(f"  Estimated Retry Rate: {retry_rate:.1%}")
        
        if retry_rate > target_retry_rate:
            print(f"  ⚠️ Retry rate {retry_rate:.1%} exceeds target {target_retry_rate:.1%}")
        else:
            print(f"  ✓ Retry rate within target")
        
        # Save calibration
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump({
                    'mean_similarity': mean_sim,
                    'std_similarity': std_sim,
                    'p10': p10,
                    'p90': p90,
                    'adaptive_threshold': adaptive_threshold,
                    'sample_count': len(similarities),
                    'estimated_retry_rate': retry_rate,
                    'calibration_date': '2026-03-02'
                }, f, indent=2)
            print(f"  ✓ Calibration saved: {output_path}")
        
        return calibration


class NumpyEmotionEmbeddingModel:
    """Adapter for synchronous embedding extractors"""
    
    def __init__(self, extractor_fn: Callable[[np.ndarray, int], np.ndarray]):
        self.extractor_fn = extractor_fn

    async def extract_embedding(self, audio_waveform: np.ndarray, sample_rate: int) -> np.ndarray:
        loop = asyncio.get_running_loop()
        emb = await loop.run_in_executor(None, self.extractor_fn, audio_waveform, sample_rate)
        emb_arr = np.asarray(emb, dtype=np.float32)
        if emb_arr.ndim != 1:
            emb_arr = emb_arr.reshape(-1)
        return emb_arr
