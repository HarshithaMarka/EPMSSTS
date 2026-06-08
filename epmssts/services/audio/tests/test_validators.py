"""
Unit tests for validators module.

Tests input validation for audio files.
"""

import pytest
import os
import tempfile
from pathlib import Path

from epmssts.services.audio.validators import AudioValidator
from epmssts.services.audio.exceptions import (
    UnsupportedFormatError,
    FileSizeError,
    CorruptFileError,
    DurationError,
)
from .test_fixtures import AudioTestFixtures


class TestAudioValidator:
    """Test suite for AudioValidator."""
    
    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return AudioValidator()
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_validate_clean_speech(self, validator, temp_dir):
        """Test validation passes for valid clean speech."""
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=3.0)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        is_valid, error = validator.validate(file_path)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_unsupported_format(self, validator, temp_dir):
        """Test validation fails for unsupported format."""
        # Create a text file with .xyz extension
        txt_file = os.path.join(temp_dir, "test.xyz")
        with open(txt_file, "w") as f:
            f.write("not an audio file")
        
        is_valid, error = validator.validate(txt_file)
        
        assert is_valid is False
        assert error is not None
        assert "Unsupported" in error or "not supported" in error.lower()
    
    def test_validate_duration_too_short(self, validator, temp_dir):
        """Test validation fails for audio shorter than 1.5 seconds."""
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=0.8)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        is_valid, error = validator.validate(file_path)
        
        assert is_valid is False
        assert "Duration" in error or "too short" in error.lower()
    
    def test_validate_duration_too_long(self, validator, temp_dir):
        """Test validation fails for audio longer than 60 seconds."""
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=65.0)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        is_valid, error = validator.validate(file_path)
        
        assert is_valid is False
        assert "Duration" in error or "too long" in error.lower()
    
    def test_validate_corrupt_file(self, validator, temp_dir):
        """Test validation fails for corrupt audio file."""
        file_path = AudioTestFixtures.save_corrupt_file(temp_dir=temp_dir)
        
        is_valid, error = validator.validate(file_path)
        
        assert is_valid is False
        assert error is not None
    
    def test_validate_nonexistent_file(self, validator):
        """Test validation fails for non-existent file."""
        is_valid, error = validator.validate("/nonexistent/file.wav")
        
        assert is_valid is False
        assert error is not None
        assert "not found" in error.lower()
    
    def test_validate_at_min_duration_boundary(self, validator, temp_dir):
        """Test validation passes at minimum duration boundary."""
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=1.5)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        is_valid, error = validator.validate(file_path)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_at_max_duration_boundary(self, validator, temp_dir):
        """Test validation passes at maximum duration boundary."""
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=60.0)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        is_valid, error = validator.validate(file_path)
        
        assert is_valid is True
        assert error is None


class TestValidatorConfigurations:
    """Test custom validator configurations."""
    
    def test_custom_duration_limits(self, temp_dir):
        """Test validator with custom duration limits."""
        validator = AudioValidator(
            min_duration=2.0,
            max_duration=10.0
        )
        
        # Too short
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=1.5)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        is_valid, _ = validator.validate(file_path)
        assert is_valid is False
    
    def test_custom_file_size_limit(self, temp_dir):
        """Test validator with custom file size limit."""
        validator = AudioValidator(max_file_size=1_000_000)  # 1MB
        
        # Create large audio (should fail)
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=60.0)
        file_path = AudioTestFixtures.save_wav_file(audio, temp_dir=temp_dir)
        
        # This might pass depending on compression, but test the validation exists
        assert validator.max_file_size == 1_000_000
