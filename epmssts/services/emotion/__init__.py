"""
Emotion-related services package.
"""

from epmssts.services.emotion.audio_emotion import AudioEmotionService, EmotionPrediction
from epmssts.services.emotion.text_emotion import TextEmotionService, TextEmotionConfig
from epmssts.services.emotion.fusion import fuse_emotions

__all__ = [
	"AudioEmotionService",
	"EmotionPrediction",
	"TextEmotionService",
	"TextEmotionConfig",
	"fuse_emotions",
]

