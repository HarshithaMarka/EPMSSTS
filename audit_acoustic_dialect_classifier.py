import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import librosa
import numpy as np
import soundfile as sf
import torch
import torch.nn as nn
import torch.nn.functional as F

from epmssts.services.dialect.acoustic_classifier import (
    AcousticDialectClassifier,
    DialectClassifierHead,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_audio_mono_16k(path: Path) -> np.ndarray:
    audio, sr = sf.read(path)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    if sr != 16000:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
    return audio.astype(np.float32)


def audio_hash(audio: np.ndarray) -> str:
    return hashlib.md5(audio.tobytes()).hexdigest()


def mfcc_fingerprint(audio: np.ndarray) -> str:
    mfcc = librosa.feature.mfcc(y=audio, sr=16000, n_mfcc=13)
    mfcc_delta = librosa.feature.delta(mfcc)
    vec = np.concatenate([np.mean(mfcc, axis=1), np.mean(mfcc_delta, axis=1)], axis=0)
    vec = np.round(vec, 6)
    return hashlib.md5(vec.tobytes()).hexdigest()


def build_split(files: List[Path], test_ratio: float = 0.2, seed: int = 42) -> Tuple[List[Path], List[Path]]:
    rng = np.random.default_rng(seed)
    idx = np.arange(len(files))
    rng.shuffle(idx)
    split = int(len(files) * (1 - test_ratio))
    train_idx = idx[:split]
    test_idx = idx[split:]
    train_files = [files[i] for i in train_idx]
    test_files = [files[i] for i in test_idx]
    return train_files, test_files


def split_integrity_checks(train_files: List[Path], test_files: List[Path]) -> Dict[str, int]:
    train_set = set(train_files)
    test_set = set(test_files)
    path_overlap = len(train_set.intersection(test_set))

    train_hashes = set()
    test_hashes = set()
    train_mfcc = set()
    test_mfcc = set()

    for f in train_files:
        a = load_audio_mono_16k(f)
        train_hashes.add(audio_hash(a))
        train_mfcc.add(mfcc_fingerprint(a))

    for f in test_files:
        a = load_audio_mono_16k(f)
        test_hashes.add(audio_hash(a))
        test_mfcc.add(mfcc_fingerprint(a))

    waveform_dup = len(train_hashes.intersection(test_hashes))
    mfcc_dup = len(train_mfcc.intersection(test_mfcc))

    return {
        "path_overlap": path_overlap,
        "waveform_duplications": waveform_dup,
        "mfcc_identical_across_splits": mfcc_dup,
    }


def train_head(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    epochs: int = 25,
    lr: float = 1e-3,
    seed: int = 7,
) -> float:
    torch.manual_seed(seed)
    np.random.seed(seed)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = DialectClassifierHead(input_dim=128, hidden_dim=64, num_classes=2).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    crit = nn.CrossEntropyLoss()

    xtr = torch.tensor(x_train, dtype=torch.float32, device=device)
    ytr = torch.tensor(y_train, dtype=torch.long, device=device)
    xte = torch.tensor(x_test, dtype=torch.float32, device=device)
    yte = torch.tensor(y_test, dtype=torch.long, device=device)

    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        logits = model(xtr)
        loss = crit(logits, ytr)
        loss.backward()
        opt.step()

    model.eval()
    with torch.no_grad():
        pred = torch.argmax(model(xte), dim=1)
        acc = float((pred == yte).float().mean().item())
    return acc


def extract_embeddings(classifier: AcousticDialectClassifier, files: List[Path]) -> Tuple[np.ndarray, np.ndarray]:
    x = []
    y = []
    for f in files:
        audio = load_audio_mono_16k(f)
        emb = classifier.extract_wav2vec2_embedding(audio, 16000)
        x.append(emb)
        y.append(0 if "andhra" in f.name else 1)
    return np.array(x, dtype=np.float32), np.array(y, dtype=np.int64)


def gen_controlled_sample(
    dialect: str,
    speaker: str,
    emotion: str,
    volume: str,
    duration: float,
    sr: int,
    rng: np.random.Generator,
) -> np.ndarray:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    if dialect == "andhra":
        dialect_f1, dialect_f2 = 520.0, 1480.0
        harmonic_profile = [1.0, 0.32, 0.21, 0.12]
        pitch_wobble = 10.0
    else:
        dialect_f1, dialect_f2 = 470.0, 1620.0
        harmonic_profile = [1.0, 0.52, 0.39, 0.28]
        pitch_wobble = 20.0

    if speaker == "A":
        speaker_base = 170.0
        timbre_shift = -20.0
    else:
        speaker_base = 230.0
        timbre_shift = 25.0

    if emotion == "neutral":
        emo_pitch = 0.0
        emo_energy = 1.0
        emo_rate = 3.0
    elif emotion == "angry":
        emo_pitch = 18.0
        emo_energy = 1.25
        emo_rate = 5.5
    else:
        emo_pitch = 9.0
        emo_energy = 1.12
        emo_rate = 4.2

    volume_scale = {"whisper": 0.35, "normal": 1.0, "loud": 2.2}[volume]

    base_f0 = speaker_base + emo_pitch + rng.uniform(-5, 5)
    mod = pitch_wobble * np.sin(2 * np.pi * rng.uniform(2.2, 5.0) * t)
    if dialect == "telangana":
        mod += 8.0 * np.sign(np.sin(2 * np.pi * rng.uniform(6.5, 9.5) * t))
    f0 = base_f0 + mod

    sig = np.zeros_like(t)
    for i, h in enumerate(harmonic_profile, start=1):
        sig += h * np.sin(2 * np.pi * (i * f0) * t)

    f1 = dialect_f1 + timbre_shift + rng.uniform(-20, 20)
    f2 = dialect_f2 + timbre_shift + rng.uniform(-30, 30)
    sig += 0.22 * np.sin(2 * np.pi * f1 * t)
    sig += 0.18 * np.sin(2 * np.pi * f2 * t)

    env = 0.5 * (1.0 + np.sin(2 * np.pi * emo_rate * t))
    sig = sig * env * emo_energy

    noise = rng.normal(0.0, 0.02 if dialect == "andhra" else 0.03, size=sig.shape)
    sig = sig + noise

    sig = sig / (np.max(np.abs(sig)) + 1e-6)
    sig = np.clip(sig * volume_scale, -0.95, 0.95)
    return sig.astype(np.float32)


def build_controlled_dataset(
    per_combo: int = 6,
    sr: int = 16000,
    duration: float = 3.0,
    seed: int = 99,
) -> List[Dict]:
    rng = np.random.default_rng(seed)
    samples: List[Dict] = []
    for dialect in ["andhra", "telangana"]:
        for speaker in ["A", "B"]:
            for emotion in ["neutral", "angry", "happy"]:
                for volume in ["normal", "whisper", "loud"]:
                    for i in range(per_combo):
                        audio = gen_controlled_sample(
                            dialect=dialect,
                            speaker=speaker,
                            emotion=emotion,
                            volume=volume,
                            duration=duration,
                            sr=sr,
                            rng=rng,
                        )
                        samples.append(
                            {
                                "audio": audio,
                                "label": 0 if dialect == "andhra" else 1,
                                "dialect": dialect,
                                "speaker": speaker,
                                "emotion": emotion,
                                "volume": volume,
                                "id": f"{dialect}_{speaker}_{emotion}_{volume}_{i}",
                            }
                        )
    return samples


def embeddings_from_samples(classifier: AcousticDialectClassifier, samples: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
    x, y = [], []
    for s in samples:
        emb = classifier.extract_wav2vec2_embedding(s["audio"], 16000)
        x.append(emb)
        y.append(s["label"])
    return np.array(x, dtype=np.float32), np.array(y, dtype=np.int64)


def run_audit() -> Dict:
    logger.info("Starting leakage/overfitting audit...")

    dialect_dir = Path("data/dialect_acoustic/train")
    andhra_files = sorted((dialect_dir / "andhra").glob("*.wav"))
    telangana_files = sorted((dialect_dir / "telangana").glob("*.wav"))
    all_files = andhra_files + telangana_files

    if len(all_files) < 10:
        raise RuntimeError("Not enough dialect samples found in data/dialect_acoustic/train")

    train_files, test_files = build_split(all_files, test_ratio=0.2, seed=42)
    split_report = split_integrity_checks(train_files, test_files)

    classifier = AcousticDialectClassifier(model_path=Path("models/dialect_classifier.pth"), device="cpu")

    # Baseline embeddings
    x_train, y_train = extract_embeddings(classifier, train_files)
    x_test, y_test = extract_embeddings(classifier, test_files)
    baseline_acc = train_head(x_train, y_train, x_test, y_test, epochs=20, lr=1e-3, seed=11)

    # Label shuffle leakage test
    rng = np.random.default_rng(123)
    y_train_shuffled = y_train.copy()
    rng.shuffle(y_train_shuffled)
    shuffled_acc = train_head(x_train, y_train_shuffled, x_test, y_test, epochs=20, lr=1e-3, seed=13)

    # Controlled dataset for robustness checks
    controlled = build_controlled_dataset(per_combo=5, seed=777)

    # Cross-speaker: train A, test B (neutral+normal only)
    speaker_train = [s for s in controlled if s["speaker"] == "A" and s["emotion"] == "neutral" and s["volume"] == "normal"]
    speaker_test = [s for s in controlled if s["speaker"] == "B" and s["emotion"] == "neutral" and s["volume"] == "normal"]
    x_sp_tr, y_sp_tr = embeddings_from_samples(classifier, speaker_train)
    x_sp_te, y_sp_te = embeddings_from_samples(classifier, speaker_test)
    cross_speaker_acc = train_head(x_sp_tr, y_sp_tr, x_sp_te, y_sp_te, epochs=25, lr=1e-3, seed=21)

    # Cross-emotion: train neutral, test angry+happy (normal volume, both speakers)
    emo_train = [s for s in controlled if s["emotion"] == "neutral" and s["volume"] == "normal"]
    emo_test = [s for s in controlled if s["emotion"] in {"angry", "happy"} and s["volume"] == "normal"]
    x_em_tr, y_em_tr = embeddings_from_samples(classifier, emo_train)
    x_em_te, y_em_te = embeddings_from_samples(classifier, emo_test)
    cross_emotion_acc = train_head(x_em_tr, y_em_tr, x_em_te, y_em_te, epochs=25, lr=1e-3, seed=31)

    # Cross-volume: train normal, test whisper+loud (neutral, both speakers)
    vol_train = [s for s in controlled if s["volume"] == "normal" and s["emotion"] == "neutral"]
    vol_test = [s for s in controlled if s["volume"] in {"whisper", "loud"} and s["emotion"] == "neutral"]
    x_vo_tr, y_vo_tr = embeddings_from_samples(classifier, vol_train)
    x_vo_te, y_vo_te = embeddings_from_samples(classifier, vol_test)
    cross_volume_acc = train_head(x_vo_tr, y_vo_tr, x_vo_te, y_vo_te, epochs=25, lr=1e-3, seed=41)

    # Random embedding sanity test
    rng2 = np.random.default_rng(2026)
    x_train_rand = rng2.normal(0, 1, size=x_train.shape).astype(np.float32)
    x_test_rand = rng2.normal(0, 1, size=x_test.shape).astype(np.float32)
    random_embedding_acc = train_head(x_train_rand, y_train, x_test_rand, y_test, epochs=20, lr=1e-3, seed=51)

    data_leakage_detected = (
        split_report["path_overlap"] > 0
        or split_report["waveform_duplications"] > 0
        or split_report["mfcc_identical_across_splits"] > 0
        or shuffled_acc >= 0.70
    )

    overfitting_detected = (
        baseline_acc >= 0.95
        and (
            cross_speaker_acc < 0.75
            or cross_emotion_acc < 0.75
            or cross_volume_acc < 0.75
            or random_embedding_acc > 0.55
        )
    ) or data_leakage_detected

    # No real dialect-labeled cross-speaker/emotion/volume corpus exists in workspace.
    # Per user constraint, production readiness must not rely on synthetic-only metrics.
    synthetic_only = True

    production_ready = (
        not data_leakage_detected
        and cross_speaker_acc >= 0.75
        and cross_emotion_acc >= 0.75
        and cross_volume_acc >= 0.75
        and random_embedding_acc <= 0.55
        and not synthetic_only
    )

    result = {
        "data_leakage_detected": bool(data_leakage_detected),
        "cross_speaker_accuracy": float(cross_speaker_acc),
        "cross_emotion_accuracy": float(cross_emotion_acc),
        "cross_volume_accuracy": float(cross_volume_acc),
        "random_embedding_accuracy": float(random_embedding_acc),
        "overfitting_detected": bool(overfitting_detected),
        "production_ready": bool(production_ready),
    }

    detailed = {
        "split_integrity": split_report,
        "baseline_accuracy": float(baseline_acc),
        "label_shuffle_accuracy": float(shuffled_acc),
        "synthetic_only_audit": synthetic_only,
    }

    out = Path("ACOUSTIC_DIALECT_LEAKAGE_AUDIT.json")
    with out.open("w", encoding="utf-8") as f:
        json.dump({"result": result, "details": detailed}, f, indent=2)

    print(json.dumps(result, indent=2))
    logger.info(f"Saved full audit report: {out}")
    return result


if __name__ == "__main__":
    run_audit()
