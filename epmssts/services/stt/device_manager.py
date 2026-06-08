"""
Device Management for STT Service

Handles GPU/CPU detection, initialization, fallback logic, and memory management.
Includes comprehensive error handling and observability.
"""

import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


@dataclass
class DeviceConfig:
    """Device configuration state"""
    device_type: str  # "gpu" or "cpu"
    device_index: int = 0
    compute_capability: Optional[Tuple[int, int]] = None
    device_name: Optional[str] = None
    total_memory_mb: Optional[float] = None
    available_memory_mb: Optional[float] = None
    supports_float16: bool = False
    supports_int8: bool = True
    quantization_method: Optional[str] = None


class DeviceManager:
    """
    Manages GPU/CPU device selection and fallback.
    
    Responsibilities:
    - Detect CUDA availability and GPU specs
    - Handle GPU initialization failures with CPU fallback
    - Monitor GPU memory and prevent OOM
    - Track device usage and errors
    - Provide device health status
    """
    
    def __init__(self, prefer_gpu: bool = True, fallback_to_cpu: bool = True):
        """
        Initialize device manager.
        
        Args:
            prefer_gpu: Try GPU first if available
            fallback_to_cpu: Fall back to CPU if GPU fails
        """
        self.prefer_gpu = prefer_gpu
        self.fallback_to_cpu = fallback_to_cpu
        self.current_device = None
        self.is_initialized = False
        self.initialization_error = None
        self.last_health_check = None
        self.gpu_errors = 0
        self.successful_gpu_inferences = 0
        self.successful_cpu_inferences = 0
        
    def initialize(self) -> DeviceConfig:
        """
        Initialize device management.
        
        Returns:
            DeviceConfig with selected device
            
        Raises:
            DeviceFallbackError: If both GPU and CPU fail
        """
        from .exceptions import GpuInitializationError, DeviceFallbackError
        
        try:
            # Try GPU first if preference enabled
            if self.prefer_gpu:
                try:
                    return self._initialize_gpu()
                except Exception as e:
                    logger.warning(f"GPU initialization failed: {e}")
                    self.gpu_errors += 1
                    
                    if not self.fallback_to_cpu:
                        raise GpuInitializationError(
                            f"GPU initialization failed and fallback disabled: {e}",
                            original_error=e
                        )
            
            # Fall back to CPU
            try:
                return self._initialize_cpu()
            except Exception as e:
                raise DeviceFallbackError(
                    f"Both GPU and CPU initialization failed: {e}"
                )
                
        except Exception as e:
            self.initialization_error = str(e)
            self.is_initialized = False
            raise
    
    def _initialize_gpu(self) -> DeviceConfig:
        """
        Initialize CUDA/GPU support.
        
        Returns:
            DeviceConfig for GPU
            
        Raises:
            Various exceptions if GPU unavailable or initialization fails
        """
        try:
            import torch
        except ImportError:
            raise ImportError("PyTorch not installed for GPU support")
        
        # Check if CUDA available
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA not available")
        
        # Get GPU details
        device_index = 0  # Use first GPU
        device_count = torch.cuda.device_count()
        
        if device_index >= device_count:
            raise RuntimeError(f"GPU {device_index} not found (available: {device_count})")
        
        # Get GPU properties
        device_props = torch.cuda.get_device_properties(device_index)
        total_memory_mb = device_props.total_memory / (1024 * 1024)
        
        # Check capability for float16
        compute_capability = device_props.major, device_props.minor
        supports_float16 = device_props.major >= 6  # Volta+ supports float16
        
        # Get current available memory
        available_memory_mb = torch.cuda.mem_get_info(device_index)[0] / (1024 * 1024)
        
        # Minimum 4GB free for model+inference
        if available_memory_mb < 4096:
            raise RuntimeError(
                f"Insufficient GPU memory: {available_memory_mb:.0f}MB < 4GB minimum"
            )
        
        config = DeviceConfig(
            device_type="gpu",
            device_index=device_index,
            compute_capability=compute_capability,
            device_name=device_props.name,
            total_memory_mb=total_memory_mb,
            available_memory_mb=available_memory_mb,
            supports_float16=supports_float16,
            supports_int8=True,
            quantization_method="float16" if supports_float16 else "float32",
        )
        
        self.current_device = config
        self.is_initialized = True
        self.last_health_check = datetime.now()
        
        logger.info(
            f"GPU initialized: {config.device_name} "
            f"(Compute {config.compute_capability}, "
            f"{config.available_memory_mb:.0f}MB available)"
        )
        
        return config
    
    def _initialize_cpu(self) -> DeviceConfig:
        """
        Initialize CPU-only support.
        
        Returns:
            DeviceConfig for CPU
        """
        import os
        
        # Get CPU info
        cpu_count = os.cpu_count() or 1
        device_name = f"CPU ({cpu_count} cores)"
        
        # Estimate available memory (conservative: 8GB)
        available_memory_mb = 8192.0
        
        config = DeviceConfig(
            device_type="cpu",
            device_index=0,
            device_name=device_name,
            available_memory_mb=available_memory_mb,
            supports_float16=True,  # Python float16 works on CPU
            supports_int8=True,
            quantization_method="int8",  # int8 recommended for CPU speed
        )
        
        self.current_device = config
        self.is_initialized = True
        self.last_health_check = datetime.now()
        
        logger.info(f"CPU initialized: {device_name} (int8 quantization recommended)")
        
        return config
    
    def check_memory(self, required_memory_mb: float) -> bool:
        """
        Check if sufficient memory available.
        
        Args:
            required_memory_mb: Memory needed in MB
            
        Returns:
            True if sufficient memory available
        """
        from .exceptions import GpuOutOfMemoryError
        
        if not self.current_device:
            return False
        
        if self.current_device.device_type == "gpu":
            try:
                import torch
                available_mb = torch.cuda.mem_get_info()[0] / (1024 * 1024)
                self.current_device.available_memory_mb = available_mb
                
                if available_mb < required_memory_mb:
                    raise GpuOutOfMemoryError(
                        f"Insufficient GPU memory: {available_mb:.0f}MB < {required_memory_mb:.0f}MB required",
                        available_memory=available_mb / 1024,  # Convert to GB
                        required_memory=required_memory_mb / 1024,
                    )
                return True
            except Exception as e:
                if isinstance(e, GpuOutOfMemoryError):
                    raise
                logger.error(f"Error checking GPU memory: {e}")
                return False
        else:
            # CPU memory check (simplified)
            return True
    
    def record_inference_success(self):
        """Record successful inference on current device"""
        if not self.current_device:
            return
        
        if self.current_device.device_type == "gpu":
            self.successful_gpu_inferences += 1
        else:
            self.successful_cpu_inferences += 1
    
    def record_inference_error(self):
        """Record inference error on current device"""
        if not self.current_device:
            return
        
        if self.current_device.device_type == "gpu":
            self.gpu_errors += 1
    
    def get_device_status(self) -> Dict[str, Any]:
        """Get current device status"""
        if not self.current_device:
            return {
                "initialized": False,
                "error": self.initialization_error,
            }
        
        status = {
            "initialized": self.is_initialized,
            "device_type": self.current_device.device_type,
            "device_name": self.current_device.device_name,
            "device_index": self.current_device.device_index,
            "available_memory_mb": self.current_device.available_memory_mb,
        }
        
        if self.current_device.compute_capability:
            status["compute_capability"] = self.current_device.compute_capability
        
        status["quantization"] = self.current_device.quantization_method
        status["supports_float16"] = self.current_device.supports_float16
        
        return status
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform device health check.
        
        Returns:
            Dict with health status
        """
        if not self.is_initialized or not self.current_device:
            return {"status": "unhealthy", "reason": "Not initialized"}
        
        try:
            if self.current_device.device_type == "gpu":
                # Try CUDA memory check
                import torch
                torch.cuda.synchronize()
                torch.cuda.memory._record_memory_history(max_entries=1)
                
            # Calculate error rate
            total = self.successful_gpu_inferences + self.successful_cpu_inferences + self.gpu_errors
            error_rate = self.gpu_errors / max(total, 1)
            
            status = "healthy"
            if error_rate > 0.05:
                status = "degraded"
            if error_rate > 0.2:
                status = "unhealthy"
            
            return {
                "status": status,
                "device": self.current_device.device_type,
                "gpu_error_rate": error_rate,
                "successful_inferences": self.successful_gpu_inferences + self.successful_cpu_inferences,
                "gpu_errors": self.gpu_errors,
            }
        
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "degraded",
                "error": str(e),
            }
    
    def get_pytorch_device(self):
        """
        Get PyTorch device string for model.
        
        Returns:
            String like "cuda:0" or "cpu"
        """
        if not self.current_device:
            return "cpu"
        
        if self.current_device.device_type == "gpu":
            return f"cuda:{self.current_device.device_index}"
        else:
            return "cpu"
