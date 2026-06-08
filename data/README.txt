Dataset collection structure for real microphone validation.

Required classes:
- happy
- sad
- angry
- neutral
- excited

Each class contains volume subsets:
- whisper
- normal
- loud

Minimum target for production validation:
- >=10 recordings per emotion
- >=3 recordings per volume band overall
- >=5 genuine sad recordings
- >=5 genuine angry recordings

Recommended naming:
<speaker>_<uttid>_<emotion>_<volume>.wav

Examples:
s01_u01_happy_whisper.wav
s01_u02_sad_normal.wav
s02_u03_angry_loud.wav
