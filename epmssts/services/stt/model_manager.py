"""
Model Management for STT Service

Handles Whisper model loading, caching, warmup, and lifecycle.
Integrates with DeviceManager for GPU/CPU optimization.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from threading import Lock
from pathlib import Path


logger = logging.getLogger(__name__)


class ModelManager:
    """
    Singleton-pattern model manager for Whisper.
    
    Responsibilities:
    - Load/unload Whisper model
    - Cache model in memory
    - Handle model lifecycle (init, warmup, shutdown)
    - Manage model quantization
    - Track model metrics
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.model = None
        self.device_manager = None
        self.current_model_name = None
        self.current_model_size = None
        self.is_loaded = False
        self.load_time = None
        self.last_inference_time = None
        self.total_inferences = 0
        self.load_error = None
        self._initialized = True
    
    def initialize(
        self,
        device_manager,
        model_size: str = "medium",
        quantization: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initialize model manager and load model.
        
        Args:
            device_manager: DeviceManager instance
            model_size: Size of Whisper model to load
            quantization: Quantization method (int8, float16, None)
            
        Returns:
            Dict with model info
        """
        from .exceptions import ModelLoadError
        
        self.device_manager = device_manager
        self.current_model_size = model_size
        
        try:
            self._load_model(model_size, quantization)
            return self.get_model_status()
        except Exception as e:
            self.load_error = str(e)
            raise ModelLoadError(
                message=f"Failed to load {model_size} model: {e}",
                details={"model_size": model_size, "error": str(e)},
            )
    
    def _load_model(self, model_size: str, quantization: Optional[str]):
        """
        Load Whisper model using faster-whisper.
        
        Args:
            model_size: Whisper model size
            quantization: Quantization method
        """
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ImportError(
                "faster-whisper not installed. Install with: "
                "pip install faster-whisper"
            )
        
        if not self.device_manager or not self.device_manager.is_initialized:
            raise RuntimeError("Device manager not initialized")
        
        start_time = datetime.now()
        
        # Select device and quantization
        device = self.device_manager.get_pytorch_device().split(":")[0]  # "cuda" or "cpu"
        
        if quantization is None:
            if device == "cuda" and self.device_manager.current_device.supports_float16:
                quantization = "float16"
            elif device == "cpu":
                quantization = "int8"
            else:
                quantization = "float32"
        
        logger.info(
            f"Loading Whisper {model_size} on {device} "
            f"with {quantization} quantization"
        )
        
        # Load model
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=quantization,
            num_workers=2,
            cpu_threads=4,
            download_root=None,  # Use default cache
        )
        
        load_duration = (datetime.now() - start_time).total_seconds()
        
        self.is_loaded = True
        self.current_model_name = f"whisper-{model_size}"
        self.load_time = load_duration
        
        logger.info(f"Model loaded successfully in {load_duration:.2f}s")
        
        # Warmup with dummy inference
        self._warmup_model()
    
    def _warmup_model(self):
        """Warmup model with dummy inference"""
        import numpy as np
        
        try:
            # Create 1 second of silence
            dummy_audio = np.zeros(16000, dtype=np.float32)
            
            logger.debug("Warming up model with dummy inference...")
            _ = self.model.transcribe(dummy_audio, language="en")
            logger.debug("Model warmup complete")
        except Exception as e:
            logger.warning(f"Model warmup failed (non-critical): {e}")
    
    def transcribe(
        self,
        audio: bytes,
        language: Optional[str] = None,
        **kwargs,
    ) -> tuple:
        """
        Transcribe audio using loaded model.
        
        Args:
            audio: Audio bytes or numpy array
            language: Language code (e.g., 'en', 'es')
            **kwargs: Additional arguments for transcribe
            
        Returns:
            Tuple of (segments, info)
            
        Raises:
            ModelNotInitializedError: If model not loaded
            InferenceError: If transcription fails
        """
        from .exceptions import ModelNotInitializedError, InferenceError
        import numpy as np
        import io
        import soundfile as sf
        
        if not self.is_loaded or self.model is None:
            raise ModelNotInitializedError("Model not loaded")
        
        try:
            # Convert bytes to audio array if needed
            if isinstance(audio, bytes):
                audio_array, sr = sf.read(io.BytesIO(audio))
                
                # Resample to 16kHz if needed
                if sr != 16000:
                    import librosa
                    audio_array = librosa.resample(
                        audio_array,
                        orig_sr=sr,
                        target_sr=16000,
                    )
            else:
                audio_array = audio
            
            # Ensure float32
            if audio_array.dtype != np.float32:
                audio_array = audio_array.astype(np.float32)
            
            # Normalize to [-1, 1]
            max_val = np.abs(audio_array).max()
            if max_val > 0:
                audio_array = audio_array / max_val
            
            self.last_inference_time = datetime.now()
            self.total_inferences += 1
            
            # Run transcription
            segments, info = self.model.transcribe(
                audio_array,
                language=language,
                **kwargs,
            )
            
            return segments, info
        
        except Exception as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)
            raise InferenceError(
                message=f"Transcription failed: {e}",
                original_error=e,
            )
    
    def get_model_status(self) -> Dict[str, Any]:
        """Get current model status"""
        return {
            "is_loaded": self.is_loaded,
            "model_name": self.current_model_name or "none",
            "model_size": self.current_model_size or "unknown",
            "device_type": self.device_manager.current_device.device_type if self.device_manager else "unknown",
            "is_gpu_available": (
                self.device_manager.current_device.device_type == "gpu"
                if self.device_manager and self.device_manager.current_device
                else False
            ),
            "model_memory_mb": None,  # Could be calculated from model size
            "quantization": None,
            "load_time_seconds": self.load_time,
            "total_inferences": self.total_inferences,
        }
    
    def unload(self):
        """Unload model and free memory"""
        if self.model is None:
            return
        
        try:
            del self.model
            self.model = None
            self.is_loaded = False
            logger.info("Model unloaded")
        except Exception as e:
            logger.error(f"Error during model unload: {e}")
