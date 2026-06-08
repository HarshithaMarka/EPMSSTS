# EPMSSTS Testing Guide

## Overview

This document provides comprehensive information on testing the EPMSSTS system including unit tests, integration tests, and end-to-end tests.

## Test Structure

```
tests/
├── unit/                                 # Unit tests for individual services
│   ├── test_dialect.py                  # Dialect classifier tests
│   ├── test_emotion.py                  # Emotion detection tests
│   ├── test_stt.py                      # Speech-to-text tests
│   ├── test_translation.py              # Translation service tests
│   ├── test_tts.py                      # Text-to-speech tests
│   └── test_services_comprehensive.py   # NEW: Comprehensive service tests
├── integration/                          # Integration tests
│   ├── test_api.py                      # Basic API tests
│   └── test_api_comprehensive.py        # NEW: Enhanced API tests
└── __init__.py
```

## Running Tests

### Prerequisites

```bash
# Ensure dependencies are installed
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov
```

### Run All Tests

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=epmssts --cov-report=html

# Run with specific markers
pytest tests/ -m "not benchmark" -v
```

### Run Unit Tests Only

```bash
# All unit tests
pytest tests/unit/ -v

# Specific service tests
pytest tests/unit/test_services_comprehensive.py -v
pytest tests/unit/test_translation.py -v
pytest tests/unit/test_emotion.py -v
pytest tests/unit/test_stt.py -v
```

### Run Integration Tests Only

```bash
# All integration tests
pytest tests/integration/ -v

# Comprehensive API tests
pytest tests/integration/test_api_comprehensive.py -v

# Specific endpoint tests
pytest tests/integration/test_api_comprehensive.py::TestTranslationEndpoints -v
```

### Run Specific Test Classes

```bash
# Translation service tests
pytest tests/unit/test_services_comprehensive.py::TestTranslationService -v

# Emotion endpoint tests
pytest tests/integration/test_api_comprehensive.py::TestEmotionEndpoints -v

# Health check tests
pytest tests/integration/test_api_comprehensive.py::TestHealthEndpoints -v
```

### Run with Options

```bash
# Stop on first failure
pytest tests/ -x

# Show print statements
pytest tests/ -s

# Specific test by name
pytest tests/ -k "test_translate" -v

# Parallel execution (requires pytest-xdist)
pytest tests/ -n auto

# Generate HTML report
pytest tests/ --html=report.html --self-contained-html
```

## End-to-End Testing

### Comprehensive Flow Test

The system includes a comprehensive end-to-end test that validates the complete pipeline:

```bash
# Run complete flow test with generated audio
python test_complete_flow.py
```

This test:
1. ✅ Checks API health status
2. ✅ Tests Speech-to-Text transcription
3. ✅ Tests Emotion Detection
4. ✅ Tests Emotion Analysis (frontend compatible)
5. ✅ Tests Dialect Detection
6. ✅ Tests Text Translation
7. ✅ Tests Text-to-Speech synthesis
8. ✅ Tests complete speech-to-speech pipeline

### Sample Audio Testing

To test with real audio files:

```bash
# Upload a WAV file
curl -X POST "http://localhost:8000/stt/transcribe" \
  -F "file=@path/to/audio.wav"

# Get emotion from audio
curl -X POST "http://localhost:8000/emotion/detect" \
  -F "file=@path/to/audio.wav"

# Complete pipeline
curl -X POST "http://localhost:8000/process/speech-to-speech" \
  -F "file=@path/to/audio.wav" \
  -F "target_lang=hi" \
  -F "target_emotion=happy"
```

## Test Coverage

### Current Coverage Areas

#### Unit Tests (test_services_comprehensive.py)
- **TranslationService**: 8 tests
  - Initialization, language validation, translation, edge cases
- **SpeechToTextService**: 4 tests
  - Initialization, model loading, audio preprocessing
- **AudioEmotionService**: 3 tests
  - Initialization, emotion detection
- **DialectClassifier**: 3 tests
  - Initialization, dialect detection
- **Integration Tests**: 4 tests
  - Service interaction, error recovery
- **Performance Tests**: Benchmarking

#### Integration Tests (test_api_comprehensive.py)
- **Health Endpoints**: 2 tests
- **STT Endpoints**: 3 tests
- **Emotion Endpoints**: 3 tests
- **Dialect Endpoints**: 1 test
- **Translation Endpoints**: 4 tests
- **TTS Endpoints**: 2 tests
- **Pipeline Endpoints**: 1 test
- **Output Endpoint**: 1 test
- **Error Handling**: 2 tests
- **Concurrent Requests**: 1 test

**Total: 25+ comprehensive integration tests**

## Test Scenarios

### Successful Path Tests

```python
# Health check passes
✅ GET /health → 200 OK

# STT works with valid audio
✅ POST /stt/transcribe → 200 OK with transcript

# Emotion detection returns valid values
✅ POST /emotion/detect → 200 OK with emotion and confidence

# Translation produces output
✅ POST /translate → 200 OK with translated_text

# Complete pipeline orchestrates all services
✅ POST /process/speech-to-speech → 200 OK with full results
```

### Error Handling Tests

```python
# Invalid language codes
❌ POST /translate with lang="invalid" → 400/422 Error

# Empty text translation
❌ POST /translate with text="" → 400/422 Error

# Missing file uploads
❌ POST /stt/transcribe without file → 422 Error

# Non-existent output file
❌ GET /output/nonexistent.wav → 404 Not Found

# Wrong HTTP method
❌ GET /translate → 405 Method Not Allowed
```

### Edge Case Tests

```python
# Identity translation (same source and target)
✅ POST /translate with source_lang="en", target_lang="en"

# Empty audio file
⚠️ POST /stt/transcribe with empty.wav → Graceful handling

# Very short audio
✅ POST /stt/transcribe with 0.5s audio → Processed

# TTS with invalid emotion
✅ POST /tts/synthesize with emotion="invalid" → Handled gracefully

# Concurrent requests
✅ 5x parallel GET /health → All succeed
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=epmssts --cov-report=xml
      - uses: codecov/codecov-action@v3
```

### Docker Testing

```bash
# Run tests inside Docker
docker-compose -f docker-compose.test.yml up

# Or with custom test command
docker build -t epmssts-test . && \
docker run -it epmssts-test pytest tests/ -v
```

## Performance Testing

### Benchmark Tests

```bash
# Run performance benchmarks
pytest tests/unit/test_services_comprehensive.py::TestPerformance -v --benchmark-only

# Compare with baseline
pytest tests/ --benchmark-compare
```

### Load Testing

```bash
# Using locust for load testing
pip install locust

# Create locustfile.py and run
locust -f locustfile.py -u 100 -r 10
```

Example Locust Configuration:

```python
from locust import HttpUser, task, between

class EPMSSTSUser(HttpUser):
    wait_time = between(1, 2)
    
    @task
    def health_check(self):
        self.client.get("/health")
    
    @task
    def translate(self):
        self.client.post("/translate", json={
            "text": "Hello",
            "source_lang": "en",
            "target_lang": "hi"
        })
```

## Debugging Tests

### Verbose Output

```bash
# Show all print statements
pytest tests/ -s

# Very verbose with all details
pytest tests/ -vv

# Show local variables in traceback
pytest tests/ -l
```

### Drop into Debugger

```python
import pytest

def test_something():
    pytest.set_trace()  # Drops into pdb debugger
    # ... test code
```

### Run Single Test with Debugging

```bash
pytest tests/unit/test_services_comprehensive.py::TestTranslationService::test_translate_english_text -s --pdb
```

## Test Configuration

### pytest.ini Configuration

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --strict-markers --tb=short
markers =
    unit: unit tests
    integration: integration tests
    benchmark: performance benchmarks
    slow: slow running tests
asyncio_mode = auto
```

### Ignoring Tests

```bash
# Skip slow tests
pytest tests/ -m "not slow"

# Skip benchmarks
pytest tests/ -m "not benchmark"

# Run only unit tests
pytest tests/ -m "unit"
```

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Clear Names**: Use descriptive test names
3. **Fixtures**: Reuse test data with fixtures
4. **Mocking**: Mock external services when needed
5. **Assertions**: Use specific assertions
6. **Coverage**: Aim for >80% code coverage
7. **Documentation**: Document complex test scenarios

## Common Issues

### Model Loading Timeouts

```bash
# Increase timeout for tests
pytest tests/ --timeout=300

# Or skip tests requiring models
pytest tests/ -k "not model_loading"
```

### Port Already in Use

```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or use different port
BACKEND_PORT=8001 pytest tests/
```

### Memory Issues

```bash
# Reduce workers for parallel tests
pytest tests/ -n 2

# Run tests sequentially
pytest tests/ -p no:xdist
```

## Test Report Examples

### HTML Report

```bash
pytest tests/ --html=report.html --self-contained-html
# Open report.html in browser
```

### Coverage Report

```bash
pytest tests/ --cov=epmssts --cov-report=html
# Open htmlcov/index.html in browser
```

### JUnit XML Report

```bash
pytest tests/ --junit-xml=junit.xml
# Use in CI/CD pipelines
```

## Conclusion

The EPMSSTS testing suite provides comprehensive coverage of:
- ✅ Individual service functionality
- ✅ API endpoint behavior
- ✅ Error handling and edge cases
- ✅ End-to-end pipeline orchestration
- ✅ Performance and load testing

Run tests regularly to ensure system reliability and catch regressions early!
