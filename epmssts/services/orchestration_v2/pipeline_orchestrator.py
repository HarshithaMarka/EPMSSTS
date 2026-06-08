from __future__ import annotations

import asyncio
import io
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol, Sequence

import numpy as np
import psutil
import soundfile as sf
import torch

from .dialect_phoneme_transformer import DialectPhonemeTransformer
from .emotion_validator import EmotionValidator
from .naturalizer import Naturalizer
from .prosody_extractor import ProsodyExtractor
from .prosody_transfer import ProsodyTransferEngine
from .style_fusion_layer import StyleFusionLayer


class STTClient(Protocol):
    async def __call__(self, audio_bytes: bytes) -> Dict[str, Any]:
        ...


class TranslationClient(Protocol):
    async def __call__(self, text: str, target_language: str) -> Dict[str, Any]:
        ...


class EmbeddingClient(Protocol):
    async def __call__(self, audio_waveform: np.ndarray, sample_rate: int) -> np.ndarray:
        ...


class TextEncoderClient(Protocol):
    async def __call__(self, text: str, language: str) -> torch.Tensor:
        ...


class TTSClient(Protocol):
    async def __call__(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...


@dataclass
class ModuleTimeouts:
    stt_s: float = 1.7
    style_s: float = 1.0
    prosody_s: float = 0.35
    translation_s: float = 1.2
    dialect_transform_s: float = 0.3
    prosody_transfer_s: float = 0.3
    style_fusion_s: float = 0.4
    tts_s: float = 2.3
    emotion_validator_s: float = 0.8
    naturalizer_s: float = 0.2
    total_pipeline_s: float = 5.0


@dataclass
class GuardConfig:
    max_memory_percent: float = 85.0
    max_gpu_memory_percent: float = 70.0
    circuit_failure_threshold: int = 4
    circuit_open_seconds: float = 30.0


class AsyncCircuitBreaker:
    def __init__(self, failure_threshold: int, open_seconds: float):
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self._state: Dict[str, Dict[str, float]] = {}

    def _slot(self, key: str) -> Dict[str, float]:
        if key not in self._state:
            self._state[key] = {"failures": 0.0, "open_until": 0.0}
        return self._state[key]

    async def allow(self, key: str) -> bool:
        slot = self._slot(key)
        now = time.time()
        return now >= slot["open_until"]

    async def success(self, key: str) -> None:
        slot = self._slot(key)
        slot["failures"] = 0.0
        slot["open_until"] = 0.0

    async def failure(self, key: str) -> None:
        slot = self._slot(key)
        slot["failures"] += 1.0
        if slot["failures"] >= self.failure_threshold:
            slot["open_until"] = time.time() + self.open_seconds


class PipelineOrchestrator:
    def __init__(
        self,
        stt_client: STTClient,
        translation_client: TranslationClient,
        emotion_embedding_client: EmbeddingClient,
        dialect_embedding_client: EmbeddingClient,
        speaker_embedding_client: EmbeddingClient,
        text_encoder_client: TextEncoderClient,
        tts_fusion_client: TTSClient,
        baseline_tts_client: TTSClient,
        emotion_validator: EmotionValidator,
        prosody_extractor: Optional[ProsodyExtractor] = None,
        prosody_transfer_engine: Optional[ProsodyTransferEngine] = None,
        dialect_transformer: Optional[DialectPhonemeTransformer] = None,
        style_fusion_layer: Optional[StyleFusionLayer] = None,
        naturalizer: Optional[Naturalizer] = None,
        timeouts: Optional[ModuleTimeouts] = None,
        guards: Optional[GuardConfig] = None,
        max_concurrency: int = 24,
    ):
        self.stt_client = stt_client
        self.translation_client = translation_client
        self.emotion_embedding_client = emotion_embedding_client
        self.dialect_embedding_client = dialect_embedding_client
        self.speaker_embedding_client = speaker_embedding_client
        self.text_encoder_client = text_encoder_client
        self.tts_fusion_client = tts_fusion_client
        self.baseline_tts_client = baseline_tts_client
        self.emotion_validator = emotion_validator

        self.prosody_extractor = prosody_extractor or ProsodyExtractor()
        self.prosody_transfer_engine = prosody_transfer_engine or ProsodyTransferEngine()
        self.dialect_transformer = dialect_transformer or DialectPhonemeTransformer()
        self.style_fusion_layer = style_fusion_layer or StyleFusionLayer(text_dim=512, style_dim=256, num_heads=8)
        self.naturalizer = naturalizer or Naturalizer()

        self.timeouts = timeouts or ModuleTimeouts()
        self.guards = guards or GuardConfig()

        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._breaker = AsyncCircuitBreaker(
            failure_threshold=self.guards.circuit_failure_threshold,
            open_seconds=self.guards.circuit_open_seconds,
        )

    async def process(
        self,
        audio_bytes: bytes,
        target_language: str,
        request_id: str,
        enable_naturalizer: bool = True,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        async with self._semaphore:
            await self._guard_system_resources()

            result = await asyncio.wait_for(
                self._process_internal(audio_bytes, target_language, request_id, enable_naturalizer),
                timeout=self.timeouts.total_pipeline_s,
            )

            result["latency_ms"] = (time.perf_counter() - started) * 1000.0
            return result

    async def _process_internal(
        self,
        audio_bytes: bytes,
        target_language: str,
        request_id: str,
        enable_naturalizer: bool,
    ) -> Dict[str, Any]:
        waveform, sample_rate = self._decode_audio(audio_bytes)

        stt_payload = await self._run_with_guards(
            "stt",
            lambda: self.stt_client(audio_bytes),
            timeout_s=self.timeouts.stt_s,
        )

        transcript = str(stt_payload.get("transcript", "")).strip()
        whisper_segments = stt_payload.get("segments", [])

        emotion_task = asyncio.create_task(
            self._run_with_guards(
                "emotion_embed",
                lambda: self.emotion_embedding_client(waveform, sample_rate),
                timeout_s=self.timeouts.style_s,
            )
        )
        dialect_task = asyncio.create_task(
            self._run_with_guards(
                "dialect_embed",
                lambda: self.dialect_embedding_client(waveform, sample_rate),
                timeout_s=self.timeouts.style_s,
            )
        )
        speaker_task = asyncio.create_task(
            self._run_with_guards(
                "speaker_embed",
                lambda: self.speaker_embedding_client(waveform, sample_rate),
                timeout_s=self.timeouts.style_s,
            )
        )

        prosody = await self._run_with_guards(
            "prosody_extractor",
            lambda: self._run_cpu(lambda: self.prosody_extractor.extract(waveform, whisper_segments)),
            timeout_s=self.timeouts.prosody_s,
        )

        translation_payload = await self._run_with_guards(
            "translation",
            lambda: self.translation_client(transcript, target_language),
            timeout_s=self.timeouts.translation_s,
        )
        translated_text = str(translation_payload.get("translated_text", transcript))

        emotion_embedding, dialect_embedding, speaker_embedding = await asyncio.gather(
            emotion_task,
            dialect_task,
            speaker_task,
        )

        target_ipa_tokens = self._text_to_ipa_tokens(translated_text)

        dialect_result = await self._run_with_guards(
            "dialect_transform",
            lambda: self._run_cpu(
                lambda: self.dialect_transformer.transform(
                    ipa_tokens=target_ipa_tokens,
                    dialect_embedding=np.asarray(dialect_embedding, dtype=np.float32),
                )
            ),
            timeout_s=self.timeouts.dialect_transform_s,
        )

        mel_length_target = max(50, int(len(translated_text) * 4.5))

        prosody_tensor = await self._run_with_guards(
            "prosody_transfer",
            lambda: self._run_cpu(
                lambda: self.prosody_transfer_engine.transfer(
                    source=prosody,
                    translated_phonemes_ipa=dialect_result.tokens,
                    target_mel_length=mel_length_target,
                )
            ),
            timeout_s=self.timeouts.prosody_transfer_s,
        )

        text_features = await self._run_with_guards(
            "text_encoder",
            lambda: self.text_encoder_client(translated_text, target_language),
            timeout_s=self.timeouts.style_fusion_s,
        )

        style_embedding = self._build_unified_style_embedding(
            emotion_embedding=np.asarray(emotion_embedding, dtype=np.float32),
            dialect_embedding=np.asarray(dialect_embedding, dtype=np.float32),
            speaker_embedding=np.asarray(speaker_embedding, dtype=np.float32),
        )

        conditioned_features = await self._run_with_guards(
            "style_fusion",
            lambda: self._run_cpu(
                lambda: self._fuse_style(
                    text_features=text_features,
                    style_embedding=style_embedding,
                )
            ),
            timeout_s=self.timeouts.style_fusion_s,
        )

        async def synth_with_intensity(intensity: float) -> np.ndarray:
            payload = {
                "request_id": request_id,
                "text": translated_text,
                "target_language": target_language,
                "ipa_tokens": dialect_result.tokens,
                "prosody": prosody_tensor.as_dict(),
                "conditioned_features": conditioned_features,
                "style_embedding": style_embedding,
                "emotion_intensity": float(intensity),
            }
            try:
                tts_resp = await self._run_with_guards(
                    "tts_fusion",
                    lambda: self.tts_fusion_client(payload),
                    timeout_s=self.timeouts.tts_s,
                )
            except Exception:
                tts_resp = await self._run_with_guards(
                    "tts_baseline",
                    lambda: self.baseline_tts_client(payload),
                    timeout_s=self.timeouts.tts_s,
                )
            return self._extract_waveform(tts_resp)

        generated_waveform = await synth_with_intensity(1.0)

        validation = await self._run_with_guards(
            "emotion_validator",
            lambda: self.emotion_validator.validate_and_retry(
                source_emotion_embedding=np.asarray(emotion_embedding, dtype=np.float32),
                generated_waveform=generated_waveform,
                sample_rate=sample_rate,
                resynthesize=synth_with_intensity,
                base_intensity=1.0,
            ),
            timeout_s=self.timeouts.emotion_validator_s,
        )

        final_waveform = validation.waveform
        if enable_naturalizer:
            final_waveform = await self._run_with_guards(
                "naturalizer",
                lambda: self._run_cpu(lambda: self.naturalizer.process(final_waveform, sample_rate)),
                timeout_s=self.timeouts.naturalizer_s,
            )

        output_bytes = self._encode_audio(final_waveform, sample_rate)

        return {
            "request_id": request_id,
            "transcript": transcript,
            "translation": translated_text,
            "dialect_tokens": dialect_result.tokens,
            "audio_bytes": output_bytes,
            "metrics": {
                "emotion_similarity": float(validation.emotion_similarity),
                "retry_performed": bool(validation.retry_performed),
                "speaking_rate": float(prosody.speaking_rate),
                "voiced_ratio": float(prosody.voiced_ratio),
                "retroflex_rate": float(dialect_result.retroflex_rate),
                "vowel_elongation_ratio": float(dialect_result.vowel_elongation_ratio),
                "nasalization_rate": float(dialect_result.nasalization_rate),
            },
            "pipeline_version": "v3",
        }

    async def _run_with_guards(self, key: str, fn: Callable[[], Awaitable[Any]], timeout_s: float) -> Any:
        if not await self._breaker.allow(key):
            raise RuntimeError(f"circuit open for module: {key}")

        try:
            result = await asyncio.wait_for(fn(), timeout=timeout_s)
            await self._breaker.success(key)
            return result
        except Exception:
            await self._breaker.failure(key)
            raise

    async def _run_cpu(self, fn: Callable[[], Any]) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, fn)

    async def _guard_system_resources(self) -> None:
        mem = psutil.virtual_memory().percent
        if mem > self.guards.max_memory_percent:
            raise RuntimeError(f"host memory guard triggered: {mem:.1f}%")

        if torch.cuda.is_available():
            total = torch.cuda.get_device_properties(0).total_memory
            used = torch.cuda.memory_reserved(0)
            pct = (used / max(total, 1)) * 100.0
            if pct > self.guards.max_gpu_memory_percent:
                raise RuntimeError(f"gpu memory guard triggered: {pct:.1f}%")

    def _decode_audio(self, audio_bytes: bytes) -> tuple[np.ndarray, int]:
        y, sr = sf.read(io.BytesIO(audio_bytes), always_2d=False)
        y = np.asarray(y, dtype=np.float32)
        if y.ndim == 2:
            y = y.mean(axis=1)
        if sr != 16000:
            y = self._resample(y, sr, 16000)
            sr = 16000
        peak = float(np.max(np.abs(y))) if y.size else 0.0
        if peak > 0.0:
            y = y / peak
        return y.astype(np.float32), int(sr)

    def _resample(self, waveform: np.ndarray, src_sr: int, tgt_sr: int) -> np.ndarray:
        import librosa

        return librosa.resample(waveform, orig_sr=src_sr, target_sr=tgt_sr).astype(np.float32)

    def _text_to_ipa_tokens(self, text: str) -> List[str]:
        mapping = {
            "a": "a", "b": "b", "c": "k", "d": "d", "e": "e", "f": "f", "g": "g", "h": "h",
            "i": "i", "j": "dʒ", "k": "k", "l": "l", "m": "m", "n": "n", "o": "o", "p": "p",
            "q": "k", "r": "r", "s": "s", "t": "t", "u": "u", "v": "ʋ", "w": "w", "x": "ks",
            "y": "j", "z": "z",
        }
        tokens: List[str] = []
        for raw in text.lower().split():
            word_tokens: List[str] = []
            for ch in raw:
                if ch in mapping:
                    word_tokens.append(mapping[ch])
            if word_tokens:
                tokens.extend(word_tokens)
        if not tokens:
            tokens = ["ə", "n"]
        return tokens

    def _build_unified_style_embedding(
        self,
        emotion_embedding: np.ndarray,
        dialect_embedding: np.ndarray,
        speaker_embedding: np.ndarray,
    ) -> torch.Tensor:
        emo = torch.from_numpy(emotion_embedding.astype(np.float32)).reshape(-1)
        dia = torch.from_numpy(dialect_embedding.astype(np.float32)).reshape(-1)
        spk = torch.from_numpy(speaker_embedding.astype(np.float32)).reshape(-1)

        if dia.numel() < 64:
            dia = torch.nn.functional.pad(dia, (0, 64 - dia.numel()))
        if emo.numel() < 128:
            emo = torch.nn.functional.pad(emo, (0, 128 - emo.numel()))
        if spk.numel() < 256:
            spk = torch.nn.functional.pad(spk, (0, 256 - spk.numel()))

        unified = torch.cat([emo[:128], dia[:64], spk[:64]], dim=0)
        unified = torch.nn.functional.normalize(unified, dim=0)
        return unified.unsqueeze(0)

    def _fuse_style(self, text_features: torch.Tensor, style_embedding: torch.Tensor) -> torch.Tensor:
        if text_features.dim() == 2:
            text_features = text_features.unsqueeze(0)

        if text_features.size(-1) != self.style_fusion_layer.style_proj.out_features:
            raise ValueError(
                f"text feature dim {text_features.size(-1)} does not match style fusion dim {self.style_fusion_layer.style_proj.out_features}"
            )

        with torch.no_grad():
            fused = self.style_fusion_layer(text_features=text_features, style_embedding=style_embedding)
        return fused

    def _extract_waveform(self, tts_response: Dict[str, Any]) -> np.ndarray:
        if "waveform" in tts_response:
            y = np.asarray(tts_response["waveform"], dtype=np.float32)
            return y

        if "audio_bytes" in tts_response:
            y, _ = sf.read(io.BytesIO(tts_response["audio_bytes"]), always_2d=False)
            y = np.asarray(y, dtype=np.float32)
            if y.ndim == 2:
                y = y.mean(axis=1)
            return y

        raise ValueError("TTS response must include 'waveform' or 'audio_bytes'")

    def _encode_audio(self, waveform: np.ndarray, sample_rate: int) -> bytes:
        output = io.BytesIO()
        sf.write(output, waveform.astype(np.float32), sample_rate, format="WAV", subtype="PCM_16")
        return output.getvalue()
