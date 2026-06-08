"""
PHASE 2: EMBEDDING STABILITY HARDENER
Enforce strict L2 normalization and dimensional boundaries

Purpose:
- Verify all embeddings have L2 norm = 1.0 (tolerance 0.01)
- Enforce dimensional boundaries:
  - Emotion dimensions [0-1]: should fall within [-0.1, 1.1]
  - Speaker dimensions [2-255]: should fall within [-1, 1]
- Apply re-anchoring when similarity < 0.85
- Generate EMBEDDING_STABILITY_REPORT.json

Author: Production Hardening
Date: 2026-03-02
"""

import json
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingValidation:
    """Validation for single embedding."""
    sample_id: str
    l2_norm: float
    l2_norm_valid: bool
    emotion_dims_valid: bool
    speaker_dims_valid: bool
    re_anchor_triggered: bool
    re_anchor_similarity: Optional[float] = None
    overall_valid: bool = False


class EmbeddingStabilityHardener:
    """
    Enforce L2 norm and dimensional boundaries on embeddings.
    
    Embeddings expected to be 256-dimensional:
    - Dims 0-1: Emotion (scale 0-1)
    - Dims 2-255: Speaker identity (scale -1 to 1)
    """
    
    # Strict boundaries
    L2_NORM_TARGET = 1.0
    L2_NORM_TOLERANCE = 0.01
    
    # Dimension ranges
    EMOTION_DIM_RANGE = (0, 1)  # Dimensions 0-1
    EMOTION_VALUE_RANGE = (-0.1, 1.1)  # Allow slight overflow
    
    SPEAKER_DIM_RANGE = (2, 255)  # Dimensions 2-255
    SPEAKER_VALUE_RANGE = (-1.0, 1.0)  # Strict
    
    # Re-anchoring threshold
    RE_ANCHOR_SIMILARITY_THRESHOLD = 0.85
    
    def __init__(self, reference_speaker_embedding: Optional[np.ndarray] = None):
        self.reference_speaker = reference_speaker_embedding
        self.validations: List[EmbeddingValidation] = []
    
    def validate_embedding(self,
                          embedding: np.ndarray,
                          sample_id: str) -> EmbeddingValidation:
        """
        Validate single embedding against all constraints.
        
        Args:
            embedding: 1D array, expected 256 dimensions
            sample_id: Identifier for this embedding
        
        Returns:
            EmbeddingValidation with detailed results
        """
        
        validation = EmbeddingValidation(sample_id=sample_id, l2_norm=0.0)
        
        # Check dimension count
        if len(embedding) != 256:
            logger.warning(f"  {sample_id}: Embedding dimension {len(embedding)} != 256")
            validation.overall_valid = False
            self.validations.append(validation)
            return validation
        
        # Gate 1: L2 Norm
        l2_norm = float(np.linalg.norm(embedding, ord=2))
        validation.l2_norm = l2_norm
        
        l2_valid = abs(l2_norm - self.L2_NORM_TARGET) <= self.L2_NORM_TOLERANCE
        validation.l2_norm_valid = l2_valid
        
        if not l2_valid:
            logger.debug(f"  {sample_id}: L2 norm {l2_norm:.4f} out of bounds "
                        f"(target {self.L2_NORM_TARGET:.2f} ± {self.L2_NORM_TOLERANCE:.3f})")
        
        # Gate 2: Emotion dimension boundaries
        emotion_dims = embedding[self.EMOTION_DIM_RANGE[0]:self.EMOTION_DIM_RANGE[1]+1]
        emotion_valid = np.all(
            (emotion_dims >= self.EMOTION_VALUE_RANGE[0]) &
            (emotion_dims <= self.EMOTION_VALUE_RANGE[1])
        )
        validation.emotion_dims_valid = emotion_valid
        
        if not emotion_valid:
            out_of_bounds = np.sum(
                (emotion_dims < self.EMOTION_VALUE_RANGE[0]) |
                (emotion_dims > self.EMOTION_VALUE_RANGE[1])
            )
            logger.debug(f"  {sample_id}: {out_of_bounds} emotion dims out of "
                        f"[{self.EMOTION_VALUE_RANGE[0]}, {self.EMOTION_VALUE_RANGE[1]}]")
        
        # Gate 3: Speaker dimension boundaries
        speaker_dims = embedding[self.SPEAKER_DIM_RANGE[0]:self.SPEAKER_DIM_RANGE[1]+1]
        speaker_valid = np.all(
            (speaker_dims >= self.SPEAKER_VALUE_RANGE[0]) &
            (speaker_dims <= self.SPEAKER_VALUE_RANGE[1])
        )
        validation.speaker_dims_valid = speaker_valid
        
        if not speaker_valid:
            out_of_bounds = np.sum(
                (speaker_dims < self.SPEAKER_VALUE_RANGE[0]) |
                (speaker_dims > self.SPEAKER_VALUE_RANGE[1])
            )
            logger.debug(f"  {sample_id}: {out_of_bounds} speaker dims out of "
                        f"[{self.SPEAKER_VALUE_RANGE[0]}, {self.SPEAKER_VALUE_RANGE[1]}]")
        
        # Gate 4: Re-anchoring check
        validation.re_anchor_triggered = False
        if self.reference_speaker is not None:
            similarity = self._cosine_similarity(
                embedding[self.SPEAKER_DIM_RANGE[0]:self.SPEAKER_DIM_RANGE[1]+1],
                self.reference_speaker[self.SPEAKER_DIM_RANGE[0]:self.SPEAKER_DIM_RANGE[1]+1]
            )
            validation.re_anchor_similarity = similarity
            
            if similarity < self.RE_ANCHOR_SIMILARITY_THRESHOLD:
                validation.re_anchor_triggered = True
                logger.debug(f"  {sample_id}: Re-anchor triggered (similarity {similarity:.3f} < {self.RE_ANCHOR_SIMILARITY_THRESHOLD:.2f})")
        
        # Overall valid: all gates pass
        validation.overall_valid = (
            l2_valid and
            emotion_valid and
            speaker_valid and
            not validation.re_anchor_triggered  # Re-anchor is a warning, not a failure
        )
        
        if validation.overall_valid:
            logger.info(f"  ✓ {sample_id}: Valid")
        else:
            logger.warning(f"  ✗ {sample_id}: Invalid")
        
        self.validations.append(validation)
        
        return validation
    
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        a = np.asarray(a, dtype=np.float32)
        b = np.asarray(b, dtype=np.float32)
        
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)
        
        if a_norm < 1e-8 or b_norm < 1e-8:
            return 0.0
        
        similarity = np.dot(a, b) / (a_norm * b_norm)
        
        return float(np.clip(similarity, -1.0, 1.0))
    
    def validate_batch(self, embeddings: np.ndarray,
                      sample_ids: List[str]) -> List[EmbeddingValidation]:
        """
        Validate batch of embeddings.
        
        Args:
            embeddings: Shape (N, 256)
            sample_ids: List of N identifiers
        """
        
        results = []
        for i, (emb, sample_id) in enumerate(zip(embeddings, sample_ids)):
            result = self.validate_embedding(emb, sample_id)
            results.append(result)
        
        return results
    
    def generate_embedding_stability_report(self,
                                           output_file: Optional[str] = None) -> Dict:
        """Generate EMBEDDING_STABILITY_REPORT.json"""
        
        if not self.validations:
            return {'status': 'NO_VALIDATIONS', 'results': []}
        
        # Aggregate statistics
        valid_count = sum(1 for v in self.validations if v.overall_valid)
        l2_norms = [v.l2_norm for v in self.validations]
        re_anchor_count = sum(1 for v in self.validations if v.re_anchor_triggered)
        
        report = {
            'timestamp': str(datetime.now()),
            'total_embeddings': len(self.validations),
            'embeddings_valid': valid_count,
            'pass_rate': float(valid_count / len(self.validations)) if self.validations else 0.0,
            'conformance_rate': float(valid_count / len(self.validations)) if self.validations else 0.0,
            
            'l2_norm_statistics': {
                'target': self.L2_NORM_TARGET,
                'tolerance': self.L2_NORM_TOLERANCE,
                'mean': float(np.mean(l2_norms)),
                'std': float(np.std(l2_norms)),
                'min': float(np.min(l2_norms)),
                'max': float(np.max(l2_norms))
            },
            
            'dimension_validation': {
                'emotion_dims': {
                    'range': self.EMOTION_VALUE_RANGE,
                    'valid_count': sum(1 for v in self.validations if v.emotion_dims_valid)
                },
                'speaker_dims': {
                    'range': self.SPEAKER_VALUE_RANGE,
                    'valid_count': sum(1 for v in self.validations if v.speaker_dims_valid)
                }
            },
            
            're_anchoring': {
                'threshold': self.RE_ANCHOR_SIMILARITY_THRESHOLD,
                'triggered_count': re_anchor_count,
                'trigger_rate': float(re_anchor_count / len(self.validations)) if self.validations else 0.0
            },
            
            'validation_thresholds': {
                'l2_norm_band': [
                    self.L2_NORM_TARGET - self.L2_NORM_TOLERANCE,
                    self.L2_NORM_TARGET + self.L2_NORM_TOLERANCE
                ],
                'minimum_conformance_rate': 0.95
            },
            
            'per_embedding_results': [
                {
                    'sample_id': v.sample_id,
                    'l2_norm': float(v.l2_norm),
                    'l2_norm_valid': v.l2_norm_valid,
                    'emotion_dims_valid': v.emotion_dims_valid,
                    'speaker_dims_valid': v.speaker_dims_valid,
                    're_anchor_triggered': v.re_anchor_triggered,
                    're_anchor_similarity': float(v.re_anchor_similarity) if v.re_anchor_similarity else None,
                    'overall_valid': v.overall_valid
                }
                for v in self.validations
            ]
        }
        
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"✓ Embedding stability report saved: {output_file}")
        
        return report


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    hardener = EmbeddingStabilityHardener()
    
    # Create synthetic test embeddings
    logger.info("Creating synthetic embeddings for testing...\n")
    
    np.random.seed(42)
    num_samples = 10
    
    embeddings = []
    sample_ids = []
    
    for i in range(num_samples):
        # Create embedding in correct format
        emb = np.random.randn(256).astype(np.float32)
        
        # Set emotion dims to [0, 1]
        emb[0:2] = np.random.uniform(0, 1, 2)
        
        # Set speaker dims to [-1, 1]
        emb[2:256] = emb[2:256] / np.linalg.norm(emb[2:256]) * 0.99
        
        # Normalize entire embedding
        emb = emb / np.linalg.norm(emb)
        
        embeddings.append(emb)
        sample_ids.append(f"sample_{i:03d}")
    
    embeddings = np.array(embeddings)
    
    logger.info(f"Validating {len(embeddings)} embeddings...\n")
    
    # Validate batch
    results = hardener.validate_batch(embeddings, sample_ids)
    
    # Generate report
    report = hardener.generate_embedding_stability_report(
        "outputs/production/EMBEDDING_STABILITY_REPORT.json"
    )
    
    logger.info(f"\n✓ Embedding stability check complete")
    logger.info(f"  Valid: {report['embeddings_valid']}/{report['total_embeddings']}")
    logger.info(f"  Pass rate: {report['pass_rate']:.1%}")
