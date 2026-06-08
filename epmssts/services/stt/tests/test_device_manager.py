"""
Tests for STT Device Manager

Tests GPU/CPU detection, initialization, and fallback logic.
"""

import pytest
from ..device_manager import DeviceManager, DeviceConfig
from ..exceptions import (
    GpuInitializationError,
    DeviceFallbackError,
    GpuOutOfMemoryError,
)


class TestDeviceManager:
    """Unit tests for DeviceManager"""
    
    def test_singleton_pattern(self):
        """Test that DeviceManager is a singleton"""
        dm1 = DeviceManager()
        dm2 = DeviceManager()
        assert dm1 is dm2
    
    def test_initialization_cpu_fallback(self):
        """Test CPU fallback when GPU not available"""
        dm = DeviceManager(prefer_gpu=False, fallback_to_cpu=True)
        config = dm.initialize()
        
        assert config.device_type == "cpu"
        assert dm.is_initialized
        assert "cpu" in config.device_name.lower() or "CPU" in config.device_name
    
    def test_device_config_has_required_fields(self):
        """Test DeviceConfig has all required fields"""
        dm = DeviceManager(prefer_gpu=False)
        config = dm.initialize()
        
        assert hasattr(config, 'device_type')
        assert hasattr(config, 'device_name')
        assert hasattr(config, 'supports_int8')
        assert hasattr(config, 'available_memory_mb')
    
    def test_get_pytorch_device_string(self):
        """Test PyTorch device string generation"""
        dm = DeviceManager(prefer_gpu=False)
        dm.initialize()
        
        device_str = dm.get_pytorch_device()
        assert device_str in ["cpu", "cuda:0"]
    
    def test_device_status_dict(self):
        """Test device status dictionary"""
        dm = DeviceManager(prefer_gpu=False)
        dm.initialize()
        status = dm.get_device_status()
        
        assert 'initialized' in status
        assert 'device_type' in status
        assert 'device_name' in status
        assert 'quantization' in status
    
    def test_health_check_initialized(self):
        """Test health check after initialization"""
        dm = DeviceManager(prefer_gpu=False)
        dm.initialize()
        health = dm.health_check()
        
        assert 'status' in health
        assert health['status'] in ['healthy', 'degraded', 'unhealthy']
    
    def test_health_check_not_initialized(self):
        """Test health check before initialization"""
        dm = DeviceManager(prefer_gpu=False)
        health = dm.health_check()
        
        assert health['status'] == 'unhealthy'
        assert 'reason' in health or 'error' in health
    
    def test_record_inference_success(self):
        """Test recording successful inferences"""
        dm = DeviceManager(prefer_gpu=False)
        dm.initialize()
        
        initial_count = dm.successful_cpu_inferences
        dm.record_inference_success()
        assert dm.successful_cpu_inferences == initial_count + 1
    
    def test_record_inference_error(self):
        """Test recording inference errors"""
        dm = DeviceManager(prefer_gpu=False)
        dm.initialize()
        
        # Note: GPU errors won't increment on CPU device
        initial_errors = dm.gpu_errors + dm.successful_cpu_inferences + dm.successful_gpu_inferences
        dm.record_inference_error()
        # For CPU, this shouldn't increment GPU errors
    
    def test_memory_check_cpu(self):
        """Test memory check on CPU"""
        dm = DeviceManager(prefer_gpu=False)
        dm.initialize()
        
        # CPU should always pass memory check
        assert dm.check_memory(1024) is True
        assert dm.check_memory(10000) is True
    
    def test_initialization_sets_flags(self):
        """Test that initialization sets all flags"""
        dm = DeviceManager(prefer_gpu=False)
        
        assert not dm.is_initialized
        assert dm.current_device is None
        
        config = dm.initialize()
        
        assert dm.is_initialized
        assert dm.current_device is not None
        assert dm.last_health_check is not None


class TestDeviceConfig:
    """Tests for DeviceConfig dataclass"""
    
    def test_device_config_creation(self):
        """Test creating DeviceConfig"""
        config = DeviceConfig(
            device_type="cpu",
            device_name="Intel Core i7",
            available_memory_mb=8192.0,
            supports_int8=True,
        )
        
        assert config.device_type == "cpu"
        assert config.device_name == "Intel Core i7"
    
    def test_device_config_defaults(self):
        """Test DeviceConfig default values"""
        config = DeviceConfig(device_type="cpu")
        
        assert config.device_index == 0
        assert config.compute_capability is None
        assert config.supports_float16 is False
        assert config.supports_int8 is True


class TestDeviceFallback:
    """Tests for device fallback logic"""
    
    def test_gpu_not_preferred_uses_cpu(self):
        """Test that CPU is used when GPU not preferred"""
        dm = DeviceManager(prefer_gpu=False)
        config = dm.initialize()
        assert config.device_type == "cpu"
    
    def test_fallback_disabled_fails_gracefully(self):
        """Test that initialization fails gracefully without fallback"""
        dm = DeviceManager(prefer_gpu=True, fallback_to_cpu=False)
        
        try:
            config = dm.initialize()
            # If GPU is available, this succeeds
            assert config.device_type == "gpu"
        except Exception as e:
            # If GPU not available and fallback disabled, error expected
            assert "fallback" in str(e).lower() or "not" in str(e).lower()
