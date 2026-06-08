"""
Uncertainty Estimation

Comprehensive uncertainty quantification for emotion predictions.
Combines entropy, probability margins, dispersion, and inter-model disagreement.
"""

import logging
import numpy as np
from typing import Dict, List

from .schemas import UncertaintyMetrics, ModelPrediction


logger = logging.getLogger(__name__)


class UncertaintyEstimator:
    """
    Estimates prediction uncertainty using multiple metrics.
    
    Metrics:
    1. Shannon entropy - distribution spread
    2. Max probability margin - gap between top 2 classes
    3. Confidence dispersion - variance across models
    4. Disagreement score - inter-model consistency
    """
    
    def __init__(
        self,
        entropy_threshold: float = 1.0,
        margin_threshold: float = 0.2,
        disagreement_threshold: float = 0.4,
    ):
        self.entropy_threshold = entropy_threshold
        self.margin_threshold = margin_threshold
        self.disagreement_threshold = disagreement_threshold
        
        # Statistics
        self.estimation_count = 0
        self.high_uncertainty_count = 0
    
    def estimate(
        self,
        fused_probs: Dict[str, float],
        model_predictions: List[ModelPrediction],
    ) -> UncertaintyMetrics:
        """
        Estimate uncertainty from fused probabilities and model predictions.
        
        Args:
            fused_probs: Final fused probabilities
            model_predictions: List of individual model predictions
        
        Returns:
            UncertaintyMetrics with comprehensive uncertainty quantification
        """
        # Metric 1: Shannon entropy of fused distribution
        entropy = self._compute_entropy(fused_probs)
        
        # Metric 2: Max probability margin (gap between top 2)
        max_prob_margin = self._compute_max_prob_margin(fused_probs)
        
        # Metric 3: Confidence dispersion across models
        confidence_dispersion = self._compute_confidence_dispersion(model_predictions)
        
        # Metric 4: Inter-model disagreement
        disagreement_score = self._compute_disagreement_score(model_predictions)
        
        # Determine if uncertainty is flagged
        uncertainty_flag = self._determine_uncertainty_flag(
            entropy, max_prob_margin, confidence_dispersion, disagreement_score
        )
        
        # Update statistics
        self.estimation_count += 1
        if uncertainty_flag:
            self.high_uncertainty_count += 1
        
        return UncertaintyMetrics(
            entropy=entropy,
            max_prob_margin=max_prob_margin,
            confidence_dispersion=confidence_dispersion,
            disagreement_score=disagreement_score,
            uncertainty_flag=uncertainty_flag,
        )
    
    def _compute_entropy(self, probs: Dict[str, float]) -> float:
        """Compute Shannon entropy of probability distribution"""
        probs_array = np.array(list(probs.values()))
        probs_safe = np.clip(probs_array, 1e-10, 1.0)
        
        entropy = -np.sum(probs_safe * np.log(probs_safe))
        return float(entropy)
    
    def _compute_max_prob_margin(self, probs: Dict[str, float]) -> float:
        """
        Compute margin between top 2 probabilities.
        
        High margin = confident prediction
        Low margin = uncertain (top classes are similar)
        """
        sorted_probs = sorted(probs.values(), reverse=True)
        
        if len(sorted_probs) < 2:
            return 1.0  # Only one class, maximum confidence
        
        margin = sorted_probs[0] - sorted_probs[1]
        return float(margin)
    
    def _compute_confidence_dispersion(
        self, model_predictions: List[ModelPrediction]
    ) -> float:
        """
        Compute dispersion (variance) of model confidences.
        
        High dispersion = models disagree on confidence level
        Low dispersion = models agree on confidence
        """
        if not model_predictions:
            return 0.0
        
        confidences = [pred.model_confidence for pred in model_predictions]
        
        if len(confidences) < 2:
            return 0.0  # Single model, no dispersion
        
        dispersion = float(np.var(confidences))
        return dispersion
    
    def _compute_disagreement_score(
        self, model_predictions: List[ModelPrediction]
    ) -> float:
        """
        Compute disagreement score across models.
        
        Measures how different the predicted labels are across models.
        """
        if len(model_predictions) < 2:
            return 0.0  # Single model, no disagreement
        
        # Get predicted label from each model
        predicted_labels = []
        for pred in model_predictions:
            label = max(pred.probabilities, key=pred.probabilities.get)
            predicted_labels.append(label)
        
        # Count unique predictions
        unique_labels = set(predicted_labels)
        
        # Disagreement = (unique_labels - 1) / (total_models - 1)
        # 0 = all agree, 1 = all different
        disagreement = (len(unique_labels) - 1) / (len(model_predictions) - 1)
        
        return float(disagreement)
    
    def _determine_uncertainty_flag(
        self,
        entropy: float,
        max_prob_margin: float,
        confidence_dispersion: float,
        disagreement_score: float,
    ) -> bool:
        """
        Determine if prediction should be flagged as uncertain.
        
        Flag if ANY of these conditions met:
        - High entropy (distribution is spread out)
        - Low margin (top classes are similar)
        - High disagreement (models don't agree)
        """
        if entropy > self.entropy_threshold:
            logger.debug(f"High entropy detected: {entropy:.3f}")
            return True
        
        if max_prob_margin < self.margin_threshold:
            logger.debug(f"Low probability margin detected: {max_prob_margin:.3f}")
            return True
        
        if disagreement_score > self.disagreement_threshold:
            logger.debug(f"High model disagreement detected: {disagreement_score:.3f}")
            return True
        
        return False
    
    def get_uncertainty_stats(self) -> Dict[str, any]:
        """Get uncertainty estimation statistics"""
        return {
            "total_estimations": self.estimation_count,
            "high_uncertainty_count": self.high_uncertainty_count,
            "high_uncertainty_pct": (
                self.high_uncertainty_count / self.estimation_count * 100
                if self.estimation_count > 0
                else 0.0
            ),
        }
