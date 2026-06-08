from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import librosa
import numpy as np
import soundfile as sf
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from transformers import Wav2Vec2Model, Wav2Vec2Processor, get_linear_schedule_with_warmup


DIALECT_TO_ID = {"andhra": 0, "telangana": 1}
ID_TO_DIALECT = {0: "andhra", 1: "telangana"}
SUPPORTED_CONDITIONS = {"neutral", "happy", "angry", "whisper", "loud"}


@dataclass
class SampleRecord:
    audio_path: Path
    dialect: str
    speaker_id: str
    condition: str
    sentence_id: str


@dataclass
class CorpusValidationReport:
    valid: bool
    violations: List[str]
    speaker_counts: Dict[str, int]
    min_sentences_per_speaker: Dict[str, int]


def parse_sentence_id(path: Path) -> str:
    stem = path.stem
    if "__" in stem:
        return stem.split("__")[0]
    return stem


def load_real_corpus(root: Path) -> List[SampleRecord]:
    records: List[SampleRecord] = []
    for dialect in ("andhra", "telangana"):
        dialect_dir = root / dialect
        if not dialect_dir.exists():
            continue
        for speaker_dir in sorted([p for p in dialect_dir.iterdir() if p.is_dir()]):
            speaker_id = speaker_dir.name
            for condition_dir in sorted([p for p in speaker_dir.iterdir() if p.is_dir()]):
                condition = condition_dir.name.lower()
                for wav in sorted(condition_dir.glob("*.wav")):
                    records.append(
                        SampleRecord(
                            audio_path=wav,
                            dialect=dialect,
                            speaker_id=speaker_id,
                            condition=condition,
                            sentence_id=parse_sentence_id(wav),
                        )
                    )
    return records


def validate_real_corpus(records: List[SampleRecord]) -> CorpusValidationReport:
    violations: List[str] = []
    by_dialect: Dict[str, Dict[str, List[SampleRecord]]] = {"andhra": {}, "telangana": {}}

    for record in records:
        if record.condition not in SUPPORTED_CONDITIONS:
            violations.append(f"Unsupported condition {record.condition} for {record.audio_path}")
        by_dialect.setdefault(record.dialect, {}).setdefault(record.speaker_id, []).append(record)

    speaker_counts = {
        dialect: len(by_dialect.get(dialect, {}))
        for dialect in ("andhra", "telangana")
    }

    for dialect in ("andhra", "telangana"):
        if speaker_counts[dialect] < 10:
            violations.append(
                f"Dialect {dialect} has {speaker_counts[dialect]} speakers; minimum required is 10"
            )

    min_sentences_per_speaker: Dict[str, int] = {}
    for dialect in ("andhra", "telangana"):
        for speaker_id, samples in by_dialect.get(dialect, {}).items():
            sentence_count = len({s.sentence_id for s in samples})
            min_sentences_per_speaker[f"{dialect}/{speaker_id}"] = sentence_count
            if sentence_count < 5:
                violations.append(
                    f"Speaker {dialect}/{speaker_id} has {sentence_count} unique sentences; minimum required is 5"
                )

    dialect_sentence_sets = {}
    for dialect in ("andhra", "telangana"):
        dialect_sentence_sets[dialect] = {s.sentence_id for speaker in by_dialect.get(dialect, {}).values() for s in speaker}

    if dialect_sentence_sets["andhra"] != dialect_sentence_sets["telangana"]:
        violations.append("Sentence set mismatch between dialect groups")

    return CorpusValidationReport(
        valid=len(violations) == 0,
        violations=violations,
        speaker_counts=speaker_counts,
        min_sentences_per_speaker=min_sentences_per_speaker,
    )


def speaker_disjoint_split(
    records: List[SampleRecord],
    seed: int = 42,
) -> Tuple[List[SampleRecord], List[SampleRecord], List[SampleRecord], Dict[str, Dict[str, List[str]]]]:
    rng = np.random.default_rng(seed)
    splits = {"train": [], "val": [], "test": []}
    split_speakers: Dict[str, Dict[str, List[str]]] = {"andhra": {}, "telangana": {}}

    for dialect in ("andhra", "telangana"):
        dialect_records = [r for r in records if r.dialect == dialect]
        speakers = sorted({r.speaker_id for r in dialect_records})
        rng.shuffle(speakers)

        n_total = len(speakers)
        n_train = max(1, int(round(n_total * 0.70)))
        n_val = max(1, int(round(n_total * 0.15)))
        n_test = n_total - n_train - n_val
        if n_test < 1:
            n_test = 1
            if n_train > n_val:
                n_train -= 1
            else:
                n_val -= 1

        train_speakers = speakers[:n_train]
        val_speakers = speakers[n_train:n_train + n_val]
        test_speakers = speakers[n_train + n_val:]

        split_speakers[dialect]["train"] = train_speakers
        split_speakers[dialect]["val"] = val_speakers
        split_speakers[dialect]["test"] = test_speakers

        for record in dialect_records:
            if record.speaker_id in train_speakers:
                splits["train"].append(record)
            elif record.speaker_id in val_speakers:
                splits["val"].append(record)
            elif record.speaker_id in test_speakers:
                splits["test"].append(record)

    return splits["train"], splits["val"], splits["test"], split_speakers


def check_no_speaker_overlap(split_speakers: Dict[str, Dict[str, List[str]]]) -> bool:
    for dialect in ("andhra", "telangana"):
        train_set = set(split_speakers[dialect].get("train", []))
        val_set = set(split_speakers[dialect].get("val", []))
        test_set = set(split_speakers[dialect].get("test", []))
        if train_set.intersection(val_set) or train_set.intersection(test_set) or val_set.intersection(test_set):
            return False
    return True


class AcousticFeatureExtractor:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def load_audio(self, path: Path) -> np.ndarray:
        audio, sr = sf.read(path)
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        if sr != self.sample_rate:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)
        return audio.astype(np.float32)

    def speaking_rate_proxy(self, audio: np.ndarray) -> float:
        onset_env = librosa.onset.onset_strength(y=audio, sr=self.sample_rate)
        tempo, _ = librosa.beat.beat_track(onset_envelope=onset_env, sr=self.sample_rate)
        return float(tempo / 60.0)

    def extract_engineered_features(self, audio: np.ndarray) -> np.ndarray:
        mfcc = librosa.feature.mfcc(y=audio, sr=self.sample_rate, n_mfcc=13)
        mfcc_delta = librosa.feature.delta(mfcc)
        mfcc_mean = np.mean(mfcc, axis=1)
        mfcc_delta_mean = np.mean(mfcc_delta, axis=1)

        f0, _, _ = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=self.sample_rate,
        )
        f0_valid = f0[~np.isnan(f0)]
        f0_mean = float(np.mean(f0_valid)) if len(f0_valid) else 0.0
        f0_var = float(np.var(f0_valid)) if len(f0_valid) else 0.0

        spectral_centroid = librosa.feature.spectral_centroid(y=audio, sr=self.sample_rate)[0]
        spectral_centroid_mean = float(np.mean(spectral_centroid))

        stft = np.abs(librosa.stft(audio))
        freqs = librosa.fft_frequencies(sr=self.sample_rate)
        f1_mask = (freqs >= 200) & (freqs <= 1000)
        f2_mask = (freqs >= 1000) & (freqs <= 3000)
        if np.any(f1_mask):
            f1 = float(freqs[f1_mask][np.argmax(np.mean(stft[f1_mask, :], axis=1))])
        else:
            f1 = 500.0
        if np.any(f2_mask):
            f2 = float(freqs[f2_mask][np.argmax(np.mean(stft[f2_mask, :], axis=1))])
        else:
            f2 = 1500.0

        rms = librosa.feature.rms(y=audio)[0]
        energy_mean = float(np.mean(rms))
        energy_std = float(np.std(rms))

        rate = self.speaking_rate_proxy(audio)

        engineered = np.concatenate(
            [
                mfcc_mean,
                mfcc_delta_mean,
                np.array(
                    [f0_mean, f0_var, spectral_centroid_mean, f1, f2, rate, energy_mean, energy_std],
                    dtype=np.float32,
                ),
            ]
        ).astype(np.float32)

        mean = engineered.mean()
        std = engineered.std() + 1e-6
        engineered = (engineered - mean) / std
        return engineered


class RealCorpusDialectDataset(Dataset):
    def __init__(self, records: List[SampleRecord], feature_extractor: AcousticFeatureExtractor):
        self.records = records
        self.extractor = feature_extractor

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int):
        sample = self.records[idx]
        audio = self.extractor.load_audio(sample.audio_path)
        engineered = self.extractor.extract_engineered_features(audio)
        label = DIALECT_TO_ID[sample.dialect]
        return {
            "audio": audio,
            "engineered": engineered,
            "label": label,
            "speaker_id": sample.speaker_id,
            "condition": sample.condition,
            "sentence_id": sample.sentence_id,
            "path": str(sample.audio_path),
        }


def collate_batch(batch: List[Dict]) -> Dict[str, torch.Tensor]:
    max_len = max(len(item["audio"]) for item in batch)
    audio_tensor = torch.zeros(len(batch), max_len, dtype=torch.float32)
    attention_mask = torch.zeros(len(batch), max_len, dtype=torch.long)
    engineered = []
    labels = []

    speaker_ids = []
    conditions = []
    sentence_ids = []
    paths = []

    for i, item in enumerate(batch):
        audio = item["audio"]
        length = len(audio)
        audio_tensor[i, :length] = torch.from_numpy(audio)
        attention_mask[i, :length] = 1
        engineered.append(item["engineered"])
        labels.append(item["label"])

        speaker_ids.append(item["speaker_id"])
        conditions.append(item["condition"])
        sentence_ids.append(item["sentence_id"])
        paths.append(item["path"])

    return {
        "audio": audio_tensor,
        "attention_mask": attention_mask,
        "engineered": torch.tensor(np.stack(engineered), dtype=torch.float32),
        "labels": torch.tensor(labels, dtype=torch.long),
        "speaker_ids": speaker_ids,
        "conditions": conditions,
        "sentence_ids": sentence_ids,
        "paths": paths,
    }


class ProductionDialectModel(nn.Module):
    def __init__(
        self,
        wav_model_name: str = "facebook/wav2vec2-base",
        engineered_dim: int = 34,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.processor = Wav2Vec2Processor.from_pretrained(wav_model_name)
        self.wav2vec2 = Wav2Vec2Model.from_pretrained(wav_model_name)

        hidden = self.wav2vec2.config.hidden_size
        self.wav_proj = nn.Linear(hidden, 256)
        self.fusion = nn.Linear(256 + engineered_dim, 128)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(128, 2)

    def extract_wav_embedding(self, audio: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        output = self.wav2vec2(input_values=audio, attention_mask=attention_mask)
        hidden_states = output.last_hidden_state
        pooled = hidden_states.mean(dim=1)
        return self.wav_proj(pooled)

    def forward(self, audio: torch.Tensor, attention_mask: torch.Tensor, engineered: torch.Tensor) -> torch.Tensor:
        wav_emb = self.extract_wav_embedding(audio, attention_mask)
        fused = torch.cat([wav_emb, engineered], dim=1)
        fused = self.fusion(fused)
        fused = self.relu(fused)
        fused = self.dropout(fused)
        logits = self.classifier(fused)
        return logits


def compute_accuracy(logits: torch.Tensor, labels: torch.Tensor) -> float:
    preds = torch.argmax(logits, dim=1)
    return float((preds == labels).float().mean().item())


def evaluate_model(model: ProductionDialectModel, loader: DataLoader, device: torch.device) -> float:
    model.eval()
    total = 0
    correct = 0
    with torch.no_grad():
        for batch in loader:
            audio = batch["audio"].to(device)
            mask = batch["attention_mask"].to(device)
            engineered = batch["engineered"].to(device)
            labels = batch["labels"].to(device)
            logits = model(audio, mask, engineered)
            preds = torch.argmax(logits, dim=1)
            total += labels.size(0)
            correct += int((preds == labels).sum().item())
    if total == 0:
        return 0.0
    return correct / total


def train_model(
    model: ProductionDialectModel,
    train_loader: DataLoader,
    val_loader: DataLoader,
    device: torch.device,
    max_epochs: int = 30,
    learning_rate: float = 2e-4,
    weight_decay: float = 1e-2,
    label_smoothing: float = 0.05,
    warmup_ratio: float = 0.1,
    early_stopping_patience: int = 5,
) -> Tuple[ProductionDialectModel, Dict[str, float]]:
    model.to(device)
    criterion = nn.CrossEntropyLoss(label_smoothing=label_smoothing)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    total_steps = max_epochs * max(1, len(train_loader))
    warmup_steps = int(total_steps * warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )

    best_val = -1.0
    best_state = None
    patience = 0

    last_train_acc = 0.0
    for _epoch in range(max_epochs):
        model.train()
        epoch_correct = 0
        epoch_total = 0
        for batch in train_loader:
            audio = batch["audio"].to(device)
            mask = batch["attention_mask"].to(device)
            engineered = batch["engineered"].to(device)
            labels = batch["labels"].to(device)

            optimizer.zero_grad()
            logits = model(audio, mask, engineered)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            scheduler.step()

            preds = torch.argmax(logits, dim=1)
            epoch_total += labels.size(0)
            epoch_correct += int((preds == labels).sum().item())

        last_train_acc = (epoch_correct / epoch_total) if epoch_total > 0 else 0.0
        val_acc = evaluate_model(model, val_loader, device)

        if val_acc > best_val:
            best_val = val_acc
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            patience = 0
        else:
            patience += 1
            if patience >= early_stopping_patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    return model, {"train_accuracy": float(last_train_acc), "val_accuracy": float(best_val)}


def make_dataloaders(
    train_records: List[SampleRecord],
    val_records: List[SampleRecord],
    test_records: List[SampleRecord],
    batch_size: int = 4,
) -> Tuple[DataLoader, DataLoader, DataLoader, int]:
    extractor = AcousticFeatureExtractor(sample_rate=16000)
    train_ds = RealCorpusDialectDataset(train_records, extractor)
    val_ds = RealCorpusDialectDataset(val_records, extractor)
    test_ds = RealCorpusDialectDataset(test_records, extractor)

    engineered_dim = 34
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collate_batch)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, collate_fn=collate_batch)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, collate_fn=collate_batch)
    return train_loader, val_loader, test_loader, engineered_dim


def eval_subset_accuracy(
    model: ProductionDialectModel,
    records: List[SampleRecord],
    condition_filter,
    device: torch.device,
    batch_size: int = 4,
) -> float:
    subset = [r for r in records if condition_filter(r)]
    if not subset:
        return 0.0
    loader, _, _, _ = make_dataloaders(subset, subset, subset, batch_size=batch_size)
    return evaluate_model(model, loader, device)


def predict_single(model: ProductionDialectModel, audio: np.ndarray, engineered: np.ndarray, device: torch.device) -> Tuple[int, float]:
    model.eval()
    with torch.no_grad():
        audio_t = torch.tensor(audio, dtype=torch.float32, device=device).unsqueeze(0)
        mask = torch.ones_like(audio_t, dtype=torch.long, device=device)
        eng_t = torch.tensor(engineered, dtype=torch.float32, device=device).unsqueeze(0)
        logits = model(audio_t, mask, eng_t)
        probs = F.softmax(logits, dim=1)
        pred = int(torch.argmax(probs, dim=1).item())
        conf = float(probs[0, pred].item())
    return pred, conf
