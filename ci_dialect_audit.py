from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from epmssts.services.dialect.production_pipeline import (
    AcousticFeatureExtractor,
    ProductionDialectModel,
    RealCorpusDialectDataset,
    check_no_speaker_overlap,
    collate_batch,
    evaluate_model,
    load_real_corpus,
    make_dataloaders,
    speaker_disjoint_split,
    train_model,
    validate_real_corpus,
)


def fit_probe(x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, y_test: np.ndarray, epochs: int = 40) -> float:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = nn.Sequential(
        nn.Linear(x_train.shape[1], 128),
        nn.ReLU(),
        nn.Dropout(0.3),
        nn.Linear(128, 2),
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-2)
    crit = nn.CrossEntropyLoss(label_smoothing=0.05)

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
        return float((pred == yte).float().mean().item())


def extract_features_for_probe(model: ProductionDialectModel, records: List, device: torch.device) -> Tuple[np.ndarray, np.ndarray]:
    extractor = AcousticFeatureExtractor(sample_rate=16000)
    ds = RealCorpusDialectDataset(records, extractor)
    dl = DataLoader(ds, batch_size=4, shuffle=False, collate_fn=collate_batch)

    model.eval()
    features = []
    labels = []
    with torch.no_grad():
        for batch in dl:
            audio = batch["audio"].to(device)
            mask = batch["attention_mask"].to(device)
            engineered = batch["engineered"].to(device)
            wav_emb = model.extract_wav_embedding(audio, mask)
            fused = torch.cat([wav_emb, engineered], dim=1)
            features.append(fused.detach().cpu().numpy())
            labels.append(batch["labels"].numpy())
    if not features:
        return np.zeros((0, 0), dtype=np.float32), np.zeros((0,), dtype=np.int64)
    return np.concatenate(features, axis=0), np.concatenate(labels, axis=0)


def subset(records: List, predicate) -> List:
    return [r for r in records if predicate(r)]


def stability_test(model: ProductionDialectModel, records: List, device: torch.device) -> float:
    extractor = AcousticFeatureExtractor(sample_rate=16000)
    grouped = defaultdict(list)
    for r in records:
        grouped[(r.speaker_id, r.sentence_id)].append(r)

    stable = 0
    total = 0

    model.eval()
    with torch.no_grad():
        for (_speaker, _sentence), items in grouped.items():
            if len(items) < 2:
                continue
            preds = []
            for item in items:
                audio = extractor.load_audio(item.audio_path)
                engineered = extractor.extract_engineered_features(audio)
                audio_t = torch.tensor(audio, dtype=torch.float32, device=device).unsqueeze(0)
                mask = torch.ones_like(audio_t, dtype=torch.long, device=device)
                eng_t = torch.tensor(engineered, dtype=torch.float32, device=device).unsqueeze(0)
                logits = model(audio_t, mask, eng_t)
                pred = int(torch.argmax(logits, dim=1).item())
                preds.append(pred)
            total += 1
            if len(set(preds)) == 1:
                stable += 1

    if total == 0:
        return 0.0
    return stable / total


def main() -> int:
    out_path = Path("DIALECT_CI_AUDIT_RESULTS.json")
    data_root = Path("data_real")
    model_path = Path("models/dialect_production.pt")

    records = load_real_corpus(data_root)
    report = validate_real_corpus(records)
    if not report.valid:
        payload = {
            "train_accuracy": 0.0,
            "test_accuracy": 0.0,
            "cross_speaker_accuracy": 0.0,
            "cross_emotion_accuracy": 0.0,
            "cross_volume_accuracy": 0.0,
            "shuffle_accuracy": 0.0,
            "random_embedding_accuracy": 0.0,
            "leakage_detected": True,
            "production_ready": False,
            "violations": report.violations,
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 1

    train_records, val_records, test_records, split_speakers = speaker_disjoint_split(records, seed=42)
    no_overlap = check_no_speaker_overlap(split_speakers)

    train_loader, val_loader, test_loader, engineered_dim = make_dataloaders(
        train_records,
        val_records,
        test_records,
        batch_size=4,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = ProductionDialectModel(
        wav_model_name="facebook/wav2vec2-base",
        engineered_dim=engineered_dim,
        dropout=0.3,
    )

    model, train_stats = train_model(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        device=device,
        max_epochs=20,
        learning_rate=2e-4,
        weight_decay=1e-2,
        label_smoothing=0.05,
        warmup_ratio=0.1,
        early_stopping_patience=4,
    )
    test_accuracy = evaluate_model(model, test_loader, device)

    torch.save({"model_state_dict": model.state_dict(), "split_speakers": split_speakers}, model_path)

    x_train, y_train = extract_features_for_probe(model, train_records, device)
    x_test, y_test = extract_features_for_probe(model, test_records, device)

    y_shuffled = y_train.copy()
    np.random.default_rng(77).shuffle(y_shuffled)
    shuffle_accuracy = fit_probe(x_train, y_shuffled, x_test, y_test)

    rng = np.random.default_rng(88)
    random_x_train = np.concatenate(
        [rng.normal(0, 1, size=(x_train.shape[0], 256)).astype(np.float32), x_train[:, 256:]],
        axis=1,
    )
    random_x_test = np.concatenate(
        [rng.normal(0, 1, size=(x_test.shape[0], 256)).astype(np.float32), x_test[:, 256:]],
        axis=1,
    )
    random_embedding_accuracy = fit_probe(random_x_train, y_train, random_x_test, y_test)

    train_speakers = {r.speaker_id for r in train_records}
    test_speakers = {r.speaker_id for r in test_records}
    speaker_overlap = bool(train_speakers.intersection(test_speakers))

    cross_speaker_test = subset(test_records, lambda r: r.speaker_id not in train_speakers)
    if not cross_speaker_test:
        cross_speaker_accuracy = 0.0
    else:
        cs_loader, _, _, _ = make_dataloaders(cross_speaker_test, cross_speaker_test, cross_speaker_test, batch_size=4)
        cross_speaker_accuracy = evaluate_model(model, cs_loader, device)

    neutral_train = subset(train_records, lambda r: r.condition == "neutral")
    emo_test = subset(test_records, lambda r: r.condition in {"happy", "angry"})
    if neutral_train and emo_test:
        nt_loader, _, et_loader, _ = make_dataloaders(neutral_train, neutral_train, emo_test, batch_size=4)
        emo_model = ProductionDialectModel("facebook/wav2vec2-base", engineered_dim=engineered_dim, dropout=0.3)
        emo_model, _ = train_model(
            model=emo_model,
            train_loader=nt_loader,
            val_loader=nt_loader,
            device=device,
            max_epochs=8,
            learning_rate=2e-4,
            weight_decay=1e-2,
            label_smoothing=0.05,
            warmup_ratio=0.1,
            early_stopping_patience=2,
        )
        cross_emotion_accuracy = evaluate_model(emo_model, et_loader, device)
    else:
        cross_emotion_accuracy = 0.0

    normal_train = subset(train_records, lambda r: r.condition == "neutral")
    vol_test = subset(test_records, lambda r: r.condition in {"whisper", "loud"})
    if normal_train and vol_test:
        n_loader, _, v_loader, _ = make_dataloaders(normal_train, normal_train, vol_test, batch_size=4)
        vol_model = ProductionDialectModel("facebook/wav2vec2-base", engineered_dim=engineered_dim, dropout=0.3)
        vol_model, _ = train_model(
            model=vol_model,
            train_loader=n_loader,
            val_loader=n_loader,
            device=device,
            max_epochs=8,
            learning_rate=2e-4,
            weight_decay=1e-2,
            label_smoothing=0.05,
            warmup_ratio=0.1,
            early_stopping_patience=2,
        )
        cross_volume_accuracy = evaluate_model(vol_model, v_loader, device)
    else:
        cross_volume_accuracy = 0.0

    _stability_score = stability_test(model, test_records, device)

    leakage_detected = (
        (shuffle_accuracy > 0.55)
        or (random_embedding_accuracy > 0.52)
        or (cross_speaker_accuracy < 0.75)
        or speaker_overlap
        or (not no_overlap)
    )

    production_ready = (
        (test_accuracy >= 0.75)
        and (cross_speaker_accuracy >= 0.75)
        and (shuffle_accuracy <= 0.55)
        and (random_embedding_accuracy <= 0.52)
        and (not speaker_overlap)
    )

    payload = {
        "train_accuracy": float(train_stats["train_accuracy"]),
        "test_accuracy": float(test_accuracy),
        "cross_speaker_accuracy": float(cross_speaker_accuracy),
        "cross_emotion_accuracy": float(cross_emotion_accuracy),
        "cross_volume_accuracy": float(cross_volume_accuracy),
        "shuffle_accuracy": float(shuffle_accuracy),
        "random_embedding_accuracy": float(random_embedding_accuracy),
        "leakage_detected": bool(leakage_detected),
        "production_ready": bool(production_ready),
        "speaker_overlap": bool(speaker_overlap),
        "transcript_used": False,
    }

    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
