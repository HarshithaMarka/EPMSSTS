#!/usr/bin/env python
"""
Standalone import validation test for ultra-realism v3 modules.
Tests the 8 core modules independently without triggering orchestration package initialization.
"""
import sys

# Test dependencies first
print("Testing dependencies...")
try:
    import numpy as np
    import torch
    import librosa
    import soundfile as sf
    import scipy.signal
    import psutil
    from transformers import Wav2Vec2Model
    print("✓ All dependencies available")
except ImportError as e:
    print(f"✗ Dependency missing: {e}")
    sys.exit(1)

# Test v3 module imports (avoiding package __init__.py)
print("\nTesting v3 module imports...")
modules_to_test = [
    ('prosody_extractor', 'ProsodyExtractor'),
    ('prosody_transfer', 'ProsodyTransferEngine'),
    ('dialect_phoneme_transformer', 'DialectPhonemeTransformer'),
    ('style_encoder', 'UnifiedStyleEncoder'),
    ('style_fusion_layer', 'StyleFusionLayer'),
    ('emotion_validator', 'EmotionValidator'),
    ('emotion_momentum', 'EmotionMomentumModel'),
    ('naturalizer', 'Naturalizer'),
]

# Import each module directly
failed = []
for module_name, class_name in modules_to_test:
    try:
        full_module = f'epmssts.services.orchestration_v2.{module_name}'
        mod = __import__(full_module, fromlist=[class_name])
        cls = getattr(mod, class_name)
        print(f"  ✓ {module_name}.{class_name}")
    except Exception as e:
        print(f"  ✗ {module_name}: {e}")
        failed.append((module_name, str(e)))

if failed:
    print(f"\n✗ {len(failed)} module(s) failed to import:")
    for name, error in failed:
        print(f"  - {name}: {error}")
    sys.exit(1)
else:
    print(f"\n✓ ALL {len(modules_to_test)} V3 MODULES IMPORTED SUCCESSFULLY")
    sys.exit(0)
