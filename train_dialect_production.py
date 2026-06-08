from __future__ import annotations

import json
from pathlib import Path

import torch

from epmssts.services.dialect.production_pipeline import (
    ProductionDialectModel,
    check_no_speaker_overlap,
    load_real_corpus,
    make_dataloaders,
    speaker_disjoint_split,
    train_model,
    validate_real_corpus,
    evaluate_model,
)


def main() -> int:
    data_root = Path("data_real")
    model_path = Path("models/dialect_production.pt")
    result_path = Path("DIALECT_PRODUCTION_TRAINING_RESULTS.json")

    records = load_real_corpus(data_root)
    report = validate_real_corpus(records)

    if not report.valid:
        payload = {
            "status": "failed_dataset_validation",
            "violations": report.violations,
            "speaker_counts": report.speaker_counts,
            "min_sentences_per_speaker": report.min_sentences_per_speaker,
        }
        result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 1

    train_records, val_records, test_records, split_speakers = speaker_disjoint_split(records, seed=42)
    no_overlap = check_no_speaker_overlap(split_speakers)
    if not no_overlap:
        payload = {
            "status": "failed_split_validation",
            "reason": "speaker_overlap_detected",
            "split_speakers": split_speakers,
        }
        result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 1

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
        max_epochs=30,
        learning_rate=2e-4,
        weight_decay=1e-2,
        label_smoothing=0.05,
        warmup_ratio=0.1,
        early_stopping_patience=5,
    )

    test_accuracy = evaluate_model(model, test_loader, device)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "split_speakers": split_speakers,
            "engineered_dim": engineered_dim,
            "train_size": len(train_records),
            "val_size": len(val_records),
            "test_size": len(test_records),
        },
        model_path,
    )

    payload = {
        "status": "ok",
        "model_path": str(model_path),
        "train_accuracy": train_stats["train_accuracy"],
        "val_accuracy": train_stats["val_accuracy"],
        "test_accuracy": test_accuracy,
        "split_speakers": split_speakers,
        "speaker_overlap": not no_overlap,
        "transcript_used": False,
    }
    result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
