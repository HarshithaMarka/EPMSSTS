from pathlib import Path


def main() -> int:
    root = Path("data_real")
    dialects = ["andhra", "telangana"]
    conditions = ["neutral", "happy", "angry", "whisper", "loud"]

    for dialect in dialects:
        for speaker_idx in range(1, 11):
            speaker = f"speaker_{speaker_idx:02d}"
            for condition in conditions:
                path = root / dialect / speaker / condition
                path.mkdir(parents=True, exist_ok=True)

    print(
        "Created template under data_real with minimum required skeleton: "
        "10 speakers per dialect and required conditions."
    )
    print(
        "Populate each speaker with at least 5 sentence .wav files and keep sentence set identical across dialects."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
