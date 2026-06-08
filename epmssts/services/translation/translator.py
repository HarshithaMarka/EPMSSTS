from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal, Optional

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


NLLB_MODEL_ID = "facebook/nllb-200-distilled-600M"

SupportedLang = Literal["te", "hi", "en"]


NLLB_LANG_CODES: Dict[SupportedLang, str] = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "te": "tel_Telu",
}


@dataclass
class TranslationResult:
    translated_text: str
    model: str = NLLB_MODEL_ID


class TranslationService:
    """
    Thin wrapper around NLLB-200 for pure text translation.

    - Model: facebook/nllb-200-distilled-600M.
    - Supported languages: Telugu (te), Hindi (hi), English (en).
    - No emotion or dialect conditioning – strictly text in → text out.
    """

    def __init__(
        self,
        model_id: str = NLLB_MODEL_ID,
        device: Optional[str] = None,
        max_new_tokens: int = 128,  # Reduced from 256 for speed
    ) -> None:
        if model_id != NLLB_MODEL_ID:
            raise ValueError(
                "EPMSSTS requires 'facebook/nllb-200-distilled-600M' for translation."
            )

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self._device = torch.device(device)
        self._model = None
        self._tokenizer = None
        self._max_new_tokens = max_new_tokens
        
        try:
            print(f"[TranslationService] Loading NLLB model: {model_id} on {device}")
            self._tokenizer = AutoTokenizer.from_pretrained(model_id)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(model_id).to(self._device)
            
            # Set model to eval mode for inference optimization
            self._model.eval()
            
            print(f"[TranslationService] NLLB model loaded successfully on {device}")
        except Exception as e:
            print(f"[TranslationService] Warning: Failed to load model: {str(e)}")
            print("[TranslationService] Translation service will be unavailable")

    def _validate_lang(self, lang: str) -> SupportedLang:
        if lang not in NLLB_LANG_CODES:
            raise ValueError(
                f"Unsupported language code '{lang}'. Expected one of: "
                f"{', '.join(NLLB_LANG_CODES.keys())}."
            )
        return lang  # type: ignore[return-value]

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> TranslationResult:
        """
        Perform pure text translation using NLLB-200.

        Args:
            text: Input text to translate (must be non-empty).
            source_lang: 'te' | 'hi' | 'en'.
            target_lang: 'te' | 'hi' | 'en'.
        """
        if self._model is None or self._tokenizer is None:
            # Return original text if model not loaded
            return TranslationResult(translated_text=text)
        
        if not text or not text.strip():
            raise ValueError("Text to translate must be non-empty.")

        src = self._validate_lang(source_lang)
        tgt = self._validate_lang(target_lang)

        if src == tgt:
            # Short-circuit trivial identity translation.
            return TranslationResult(translated_text=text)

        src_code = NLLB_LANG_CODES[src]
        tgt_code = NLLB_LANG_CODES[tgt]

        # Configure tokenizer with source language for correct prefixing.
        self._tokenizer.src_lang = src_code

        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            padding=False,
            truncation=True,
            max_length=512,
        ).to(self._device)

        forced_bos_token_id = self._tokenizer.convert_tokens_to_ids(tgt_code)

        with torch.no_grad():
            generated_tokens = self._model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                max_new_tokens=self._max_new_tokens,
                num_beams=1,  # Greedy decoding for speed
                do_sample=False,  # Deterministic output
                early_stopping=True,  # Stop when EOS is generated
            )

        translated = self._tokenizer.batch_decode(
            generated_tokens, skip_special_tokens=True
        )[0]

        return TranslationResult(translated_text=translated.strip())


__all__ = ["TranslationService", "TranslationResult", "SupportedLang", "NLLB_MODEL_ID"]

