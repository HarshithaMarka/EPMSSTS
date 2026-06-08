"""
Retry Handler

Intelligent retry logic for failed or low-quality translations.
Adjusts parameters and switches strategies on retry.
"""

import logging
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass

from .schemas import RetryInfo, RetryReason
from .exceptions import MaxRetriesExceededError, FallbackModelUnavailableError


logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Retry configuration"""
    
    max_retries: int = 2
    min_confidence_threshold: float = 0.6
    min_emotion_preservation_threshold: float = 0.6
    
    # Parameter adjustments on retry
    beam_size_adjustments: List[int] = None
    temperature_adjustments: List[float] = None
    
    enable_fallback_model: bool = False
    
    def __post_init__(self):
        if self.beam_size_adjustments is None:
            # First retry: increase beams, second retry: decrease
            self.beam_size_adjustments = [6, 3]
        
        if self.temperature_adjustments is None:
            # First retry: slightly higher temp, second retry: lower temp
            self.temperature_adjustments = [1.2, 0.8]


class RetryHandler:
    """
    Intelligent retry handler for translation failures.
    
    Retry triggers:
    - Empty output
    - Low translation confidence
    - Emotion preservation failure
    - Repetitive loop detected
    - Length mismatch
    
    Retry strategies:
    - Adjust beam width
    - Adjust temperature
    - Switch to fallback model (if available)
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        
        # Statistics
        self.retry_attempt_count = 0
        self.retry_success_count = 0
        self.retry_failure_count = 0
        
        # Retry reason distribution
        self.retry_reasons = {
            "empty_output": 0,
            "low_confidence": 0,
            "emotion_mismatch": 0,
            "repetitive_loop": 0,
            "length_mismatch": 0,
        }
    
    def should_retry(
        self,
        translated_text: str,
        translation_confidence: float,
        emotion_preservation_score: Optional[float],
        repetition_detected: bool,
        retry_count: int,
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if translation should be retried.
        
        Returns:
            Tuple of (should_retry, retry_reason)
        """
        if retry_count >= self.config.max_retries:
            return False, None
        
        # Check 1: Empty output
        if not translated_text or len(translated_text.strip()) == 0:
            self.retry_reasons["empty_output"] += 1
            return True, RetryReason.EMPTY_OUTPUT.value
        
        # Check 2: Low translation confidence
        if translation_confidence < self.config.min_confidence_threshold:
            self.retry_reasons["low_confidence"] += 1
            return True, RetryReason.LOW_CONFIDENCE.value
        
        # Check 3: Emotion preservation failure
        if emotion_preservation_score is not None:
            if emotion_preservation_score < self.config.min_emotion_preservation_threshold:
                self.retry_reasons["emotion_mismatch"] += 1
                return True, RetryReason.EMOTION_MISMATCH.value
        
        # Check 4: Repetitive loop
        if repetition_detected:
            self.retry_reasons["repetitive_loop"] += 1
            return True, RetryReason.REPETITIVE_LOOP.value
        
        return False, None
    
    def get_retry_parameters(
        self,
        retry_count: int,
        retry_reason: str,
    ) -> Dict:
        """
        Get adjusted parameters for retry attempt.
        
        Args:
            retry_count: Current retry attempt number (0-indexed)
            retry_reason: Reason for retry
        
        Returns:
            Dictionary of adjusted parameters
        """
        adjustments = {}
        
        # Adjust beam size
        if retry_count < len(self.config.beam_size_adjustments):
            adjustments["beam_size"] = self.config.beam_size_adjustments[retry_count]
        
        # Adjust temperature
        if retry_count < len(self.config.temperature_adjustments):
            adjustments["temperature"] = self.config.temperature_adjustments[retry_count]
        
        # Reason-specific adjustments
        if retry_reason == RetryReason.REPETITIVE_LOOP.value:
            # Lower temperature to reduce randomness
            adjustments["temperature"] = 0.7
        
        elif retry_reason == RetryReason.LOW_CONFIDENCE.value:
            # Increase beam size for better search
            adjustments["beam_size"] = max(
                adjustments.get("beam_size", 4), 6
            )
        
        elif retry_reason == RetryReason.EMOTION_MISMATCH.value:
            # Slightly higher temperature for variation
            adjustments["temperature"] = 1.1
        
        return adjustments
    
    async def execute_with_retry(
        self,
        translation_func: Callable,
        validation_func: Callable,
        **kwargs
    ) -> tuple[str, Dict]:
        """
        Execute translation with retry logic.
        
        Args:
            translation_func: Async function to call for translation
            validation_func: Function to validate translation result
            **kwargs: Arguments to pass to translation_func
        
        Returns:
            Tuple of (translated_text, retry_info_dict)
        """
        retry_count = 0
        retry_reasons_list = []
        retry_adjustments_list = []
        last_error = None
        
        while retry_count <= self.config.max_retries:
            try:
                # Get retry parameters (if retry)
                if retry_count > 0:
                    retry_params = self.get_retry_parameters(
                        retry_count - 1,
                        retry_reasons_list[-1]
                    )
                    kwargs.update(retry_params)
                    retry_adjustments_list.append(str(retry_params))
                
                # Execute translation
                result = await translation_func(**kwargs)
                translated_text, metadata = result
                
                # Validate result
                should_retry, retry_reason, validation_data = validation_func(
                    translated_text, metadata, retry_count
                )
                
                if not should_retry:
                    # Success!
                    if retry_count > 0:
                        self.retry_success_count += 1
                    
                    retry_info = {
                        "retry_count": retry_count,
                        "retry_reasons": retry_reasons_list,
                        "retry_adjustments": retry_adjustments_list,
                        "final_attempt": False,
                    }
                    
                    return translated_text, retry_info
                
                # Need to retry
                retry_count += 1
                retry_reasons_list.append(retry_reason)
                self.retry_attempt_count += 1
                
                logger.info(
                    f"Retry {retry_count}/{self.config.max_retries} "
                    f"(reason: {retry_reason})"
                )
            
            except Exception as e:
                last_error = str(e)
                logger.error(f"Translation attempt {retry_count} failed: {e}")
                retry_count += 1
                retry_reasons_list.append("error")
        
        # Max retries exceeded
        self.retry_failure_count += 1
        raise MaxRetriesExceededError(
            max_retries=self.config.max_retries,
            last_error=last_error,
        )
    
    def get_retry_stats(self) -> Dict:
        """Get retry statistics"""
        total_attempts = self.retry_success_count + self.retry_failure_count
        
        return {
            "retry_attempt_count": self.retry_attempt_count,
            "retry_success_count": self.retry_success_count,
            "retry_failure_count": self.retry_failure_count,
            "retry_success_rate": (
                self.retry_success_count / total_attempts
                if total_attempts > 0
                else 0.0
            ),
            "retry_reasons_distribution": dict(self.retry_reasons),
        }
