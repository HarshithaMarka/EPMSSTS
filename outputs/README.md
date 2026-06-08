# Audio Output Directory

This directory stores synthesized audio files from the TTS service.

## File Naming Convention

Files are named by session ID: `{session_id}.wav`

Example: `a1b2c3d4-e5f6-7890-abcd-ef1234567890.wav`

## Retention Policy

In production, files older than 24 hours should be automatically deleted to prevent disk space issues.

## Directory Structure

```
outputs/
├── README.md (this file)
└── *.wav (generated audio files)
```

## Notes

- This directory is created automatically at runtime if it doesn't exist
- Audio files are served via the `/output/{session_id}.wav` endpoint
- Do not manually delete files while the API is running
- Add this directory to `.gitignore` to avoid committing audio files
