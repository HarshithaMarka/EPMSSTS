# Contributing to EPMSSTS

Thank you for considering contributing to the Emotion-Preserving Multilingual Speech-to-Speech Translation System (EPMSSTS)!

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please search the issue list to avoid duplicates. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title**
* **Describe the exact steps which reproduce the problem**
* **Provide specific examples to demonstrate the steps**
* **Describe the behavior you observed after following the steps**
* **Explain which behavior you expected to see instead and why**
* **Include screenshots and animated GIFs if possible**
* **Include your environment details** (OS, Python version, GPU/CPU, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

* **Use a clear and descriptive title**
* **Provide a step-by-step description of the suggested enhancement**
* **Provide specific examples to demonstrate the steps**
* **Describe the current behavior and the expected behavior**
* **Explain why this enhancement would be useful**

### Pull Requests

* Fill in the required template
* Follow Python code style guidelines (PEP 8)
* Include appropriate test cases
* Update documentation as needed
* End all files with a newline
* Avoid platform-dependent code

## Development Setup

### Prerequisites

* Python 3.10 or higher
* conda or pip for package management
* Docker (optional, for containerized development)

### Setting Up Development Environment

```bash
# Clone the repository
git clone <repository-url>
cd EPMSSTS

# Create conda environment
conda create -n epmssts-dev python=3.10
conda activate epmssts-dev

# Install development dependencies
pip install -r requirements.txt
pip install black flake8 isort mypy

# Run tests
pytest tests/ -v

# Run with development settings
uvicorn epmssts.api.main:app --reload
```

## Code Style Guidelines

### Python Code Style

* Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
* Use type hints for function signatures
* Use descriptive variable names
* Keep functions focused and small
* Document complex logic with comments

### Naming Conventions

```python
# Classes: PascalCase
class AudioEmotionService:
    pass

# Functions/methods: snake_case
def analyze_emotion_from_audio():
    pass

# Constants: UPPER_SNAKE_CASE
MAX_FILE_SIZE_MB = 10

# Private: _leading_underscore
_internal_method()
```

### Documentation

All modules, classes, and public functions should have docstrings:

```python
def process_audio(file_path: str, language: str = "auto") -> Dict[str, Any]:
    """
    Process audio file through the complete pipeline.
    
    Args:
        file_path: Path to audio file (WAV, MP3, FLAC)
        language: Language code or "auto" for auto-detection
        
    Returns:
        Dictionary containing transcription, emotion, and translations
        
    Raises:
        FileNotFoundError: If audio file not found
        ValueError: If language code invalid
    """
    pass
```

### Code Formatting

```bash
# Format code with black
black epmssts/ frontend/ tests/

# Sort imports with isort
isort epmssts/ frontend/ tests/

# Check style with flake8
flake8 epmssts/ frontend/ tests/

# Type checking with mypy
mypy epmssts/
```

## Testing Requirements

All contributions must include appropriate tests:

### Unit Tests

```python
def test_stt_transcription_success():
    """Test successful transcription."""
    service = SpeechToTextService()
    result = service.transcribe(audio_bytes, language="en")
    assert result.text is not None
    assert result.language == "en"
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_api_health_endpoint():
    """Test health check endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=epmssts --cov-report=html

# Run specific test file
pytest tests/unit/test_emotion.py -v

# Run with markers
pytest tests/ -m "not slow" -v
```

## Commit Messages

Write clear, meaningful commit messages:

```
[service] Brief description of change

Longer explanation of why this change was needed and what it does.
If fixing an issue, reference it: "Fixes #123"

- Bullet points for multiple changes
- Keep lines under 72 characters
```

## Documentation

Documentation improvements are always welcome! Please:

* Update README.md if adding features
* Add docstrings to new functions/classes
* Update API documentation in main.py endpoints
* Include examples for new functionality
* Check that documentation renders correctly

## Project Structure

When adding new features, follow this structure:

```
epmssts/services/<service_name>/
├── __init__.py          # Package initialization
├── model.py            # Core logic
├── handler.py          # Request handling (if applicable)
└── config.py           # Service configuration (if applicable)
```

## Git Workflow

1. Create a feature branch: `git checkout -b feature/description`
2. Make your changes with clear commits
3. Push to your fork: `git push origin feature/description`
4. Create a Pull Request with description of changes
5. Address review feedback
6. Merge when approved

## Version Numbering

We follow [Semantic Versioning](https://semver.org/):

* **MAJOR**: Breaking changes
* **MINOR**: New features (backward compatible)
* **PATCH**: Bug fixes (backward compatible)

Example: `1.2.3` = Major.Minor.Patch

## Questions?

Feel free to open an issue with the `question` label or contact the project maintainers.

---

Thank you for contributing to EPMSSTS! Your efforts help make speech-to-speech translation better for everyone.
