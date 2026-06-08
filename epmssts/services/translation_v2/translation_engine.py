"""
Translation Engine

NLLB-200 based translation engine with beam search, temperature control,
and GPU acceleration support.
"""

import logging
import torch
from typing import Optional, Dict, List, Tuple
from datetime import datetime

from .exceptions import (
    TranslationModelLoadError,
    TranslationInferenceError,
    EmptyTranslationError,
    TranslationTimeoutError,
)


logger = logging.getLogger(__name__)


class TranslationEngine:
    """
    Production translation engine using NLLB-200 or MarianMT.
    
    Features:
    - Beam search for quality
    - Temperature control
    - GPU acceleration
    - Warm startup
    - Token overflow protection
    """
    
    def __init__(
        self,
        model_name: str = "facebook/nllb-200-distilled-600M",
        device: str = "cpu",
        max_length: int = 512,
        beam_size: int = 4,
        temperature: float = 1.0,
        timeout_seconds: float = 5.0,
    ):
        self.model_name = model_name
        self.device = device
        self.max_length = max_length
        self.beam_size = beam_size
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        
        self.model = None
        self.tokenizer = None
        self.is_loaded = False
        
        # Statistics
        self.inference_count = 0
        self.total_inference_time_ms = 0.0
        self.empty_translation_count = 0
        self.timeout_count = 0
        
        # Language pair statistics
        self.language_pair_count = {}
    
    def load(self):
        """Load translation model and tokenizer"""
        try:
            logger.info(f"Loading translation model: {self.model_name}")
            
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            # Load model
            self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()
            
            self.is_loaded = True
            logger.info(f"Translation model loaded successfully on {self.device}")
            
            # Warm up model
            self._warmup()
        
        except Exception as e:
            raise TranslationModelLoadError(
                f"Failed to load translation model: {e}",
                model_name=self.model_name,
                original_error=e,
            )
    
    def _warmup(self):
        """Warm up model with dummy translation"""
        try:
            logger.info("Warming up translation model...")
            dummy_text = "Hello, this is a test sentence."
            self.translate(
                text=dummy_text,
                source_lang="en",
                target_lang="es",
            )
            logger.info("Model warmup complete")
        except Exception as e:
            logger.warning(f"Model warmup failed: {e}")
    
    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Optional[List[str]] = None,
        beam_size: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Tuple[str, float, Dict]:
        """
        Translate text from source to target language.
        
        Args:
            text: Source text
            source_lang: Source language code
            target_lang: Target language code
            context: Optional context sentences
            beam_size: Override beam size
            temperature: Override temperature
        
        Returns:
            Tuple of (translated_text, log_probability, metadata)
        """
        if not self.is_loaded:
            raise TranslationInferenceError(
                "Translation model not loaded",
                transcript=text,
                source_lang=source_lang,
                target_lang=target_lang,
            )
        
        start_time = datetime.now()
        
        try:
            # Override parameters if provided
            beam_size = beam_size or self.beam_size
            temperature = temperature or self.temperature
            
            # Prepare input
            input_text = self._prepare_input(text, context, source_lang, target_lang)
            
            # Tokenize
            inputs = self.tokenizer(
                input_text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_length,
            )
            inputs = inputs.to(self.device)
            
            # Generate translation
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=self.max_length,
                    num_beams=beam_size,
                    temperature=temperature,
                    early_stopping=True,
                    output_scores=True,
                    return_dict_in_generate=True,
                )
            
            # Decode
            translated_text = self.tokenizer.decode(
                outputs.sequences[0],
                skip_special_tokens=True,
            ).strip()
            
            # Compute log probability (if available)
            log_prob = self._compute_log_probability(outputs) if hasattr(outputs, 'scores') else None
            
            # Check for empty translation
            if not translated_text:
                self.empty_translation_count += 1
                raise EmptyTranslationError(
                    transcript=text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                )
            
            # Timing
            inference_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # Check timeout
            if inference_time_ms > self.timeout_seconds * 1000:
                self.timeout_count += 1
                logger.warning(f"Translation took {inference_time_ms:.1f}ms (timeout: {self.timeout_seconds}s)")
            
            # Update statistics
            self.inference_count += 1
            self.total_inference_time_ms += inference_time_ms
            
            lang_pair = f"{source_lang}-{target_lang}"
            self.language_pair_count[lang_pair] = self.language_pair_count.get(lang_pair, 0) + 1
            
            # Metadata
            metadata = {
                "beam_size": beam_size,
                "temperature": temperature,
                "input_length": len(text),
                "output_length": len(translated_text),
                "inference_time_ms": inference_time_ms,
            }
            
            return translated_text, log_prob, metadata
        
        except Exception as e:
            if isinstance(e, (EmptyTranslationError, TranslationTimeoutError)):
                raise
            
            raise TranslationInferenceError(
                f"Translation inference failed: {e}",
                transcript=text,
                source_lang=source_lang,
                target_lang=target_lang,
                original_error=e,
            )
    
    def _prepare_input(
        self,
        text: str,
        context: Optional[List[str]],
        source_lang: str,
        target_lang: str,
    ) -> str:
        """
        Prepare input for translation model.
        
        For NLLB, format is typically just the source text.
        Context can be prepended if available.
        """
        if context and len(context) > 0:
            # Prepend last 1-2 context sentences
            context_text = " ".join(context[-2:])
            input_text = f"{context_text} {text}"
        else:
            input_text = text
        
        return input_text
    
    def _compute_log_probability(self, outputs) -> Optional[float]:
        """Compute average log probability from model outputs"""
        try:
            if hasattr(outputs, 'scores') and outputs.scores:
                scores = outputs.scores
                log_probs = [torch.log_softmax(score, dim=-1).max().item() for score in scores]
                avg_log_prob = sum(log_probs) / len(log_probs) if log_probs else None
                return avg_log_prob
        except Exception as e:
            logger.warning(f"Failed to compute log probability: {e}")
        
        return None
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes"""
        # NLLB-200 supports 200+ languages
        # Return commonly used subset
        return [
            "en", "te", "hi", "es", "fr", "de", "zh", "ja",
            "ko", "ar", "ru", "pt", "it", "nl", "tr",
        ]
    
    def get_model_info(self) -> Dict:
        """Get model information"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "max_length": self.max_length,
            "beam_size": self.beam_size,
            "temperature": self.temperature,
            "is_loaded": self.is_loaded,
            "inference_count": self.inference_count,
            "average_inference_time_ms": (
                self.total_inference_time_ms / self.inference_count
                if self.inference_count > 0
                else 0.0
            ),
            "empty_translation_count": self.empty_translation_count,
            "timeout_count": self.timeout_count,
            "language_pair_distribution": self.language_pair_count,
        }
