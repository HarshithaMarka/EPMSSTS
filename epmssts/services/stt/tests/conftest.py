"""Test fixtures and configuration for STT service tests."""

import pytest
import asyncio
from ..device_manager import DeviceManager
from ..model_manager import ModelManager
from ..confidence_scorer import TranscriptionConfidenceScorer
from .test_fixtures import SttAudioFixtures


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def device_manager():
    """Fixture for DeviceManager"""
    dm = DeviceManager(prefer_gpu=False, fallback_to_cpu=True)
    dm.initialize()
    return dm


@pytest.fixture
def confidence_scorer():
    """Fixture for ConfidenceScorer"""
    return TranscriptionConfidenceScorer()


@pytest.fixture
def audio_fixtures():
    """Fixture for audio test fixtures"""
    return SttAudioFixtures()
