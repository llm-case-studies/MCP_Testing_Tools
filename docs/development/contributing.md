# Contributing Guide 🤝

Welcome to the **MCP Debug Wizard** community! We're thrilled you want to contribute to making MCP testing magical for everyone! 🧙‍♂️✨

## 🎯 Ways to Contribute

### 🐛 Bug Reports
- Found a bug? Please report it!
- Check existing [issues](https://github.com/llm-case-studies/MCP_Testing_Tools/issues) first
- Use our bug report template

### 💡 Feature Requests
- Have an idea? We'd love to hear it!
- Open a [feature request](https://github.com/llm-case-studies/MCP_Testing_Tools/issues/new)
- Join [discussions](https://github.com/llm-case-studies/MCP_Testing_Tools/discussions)

### 📖 Documentation
- Improve existing docs
- Add tutorials and examples
- Fix typos and clarity issues

### 🔧 Code Contributions
- Fix bugs
- Add new features
- Improve performance
- Add tests

### 🧪 Testing
- Test on different platforms
- Report compatibility issues
- Create test cases

## 🚀 Getting Started

### 1. Fork & Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR-USERNAME/MCP_Testing_Tools
cd MCP_Testing_Tools

# Add upstream remote
git remote add upstream https://github.com/llm-case-studies/MCP_Testing_Tools
```

### 2. Set Up Development Environment

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies

# Set up pre-commit hooks
pre-commit install

# Start development containers
docker-compose -f docker-compose.dev.yml up -d
```

### 3. Create a Branch

```bash
# Create feature branch
git checkout -b feature/amazing-new-feature

# Or bug fix branch
git checkout -b fix/important-bug-fix
```

## 📋 Development Workflow

### 1. Code Changes

```bash
# Make your changes
vim mock_server.py

# Test your changes
python -m pytest tests/
./scripts/run-tests.sh

# Format code
black .
isort .
flake8 .
```

### 2. Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_mock_server.py

# Run with coverage
pytest --cov=.

# Integration tests with Docker
./scripts/integration-tests.sh
```

### 3. Documentation

```bash
# Build docs locally
cd docs
mkdocs serve

# View at http://localhost:8000
```

### 4. Commit & Push

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "feat: add custom filter support for proxy spy

- Add FilterConfig model for custom filters
- Implement delay and error injection filters
- Add API endpoints for filter management
- Update documentation with filter examples

Closes #123"

# Push to your fork
git push origin feature/amazing-new-feature
```

### 5. Create Pull Request

1. Go to [GitHub repository](https://github.com/llm-case-studies/MCP_Testing_Tools)
2. Click "New Pull Request"
3. Select your branch
4. Fill out the PR template
5. Submit for review

## 🎨 Code Style Guidelines

### Python Code Style

We follow [PEP 8](https://pep8.org/) with some modifications:

```python
# Use type hints
def process_message(message: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Process MCP message with filtering.
    
    Args:
        message: The MCP message to process
        
    Returns:
        Tuple of (processed_message, was_modified)
    """
    # Implementation here
    return processed_message, False

# Use descriptive variable names
mcp_server_process = subprocess.Popen(...)
communication_log = []

# Constants in UPPER_CASE
DEFAULT_PORT = 9090
MAX_RETRY_ATTEMPTS = 3
```

### Code Formatting Tools

```bash
# Black for code formatting
black --line-length 88 .

# isort for import sorting
isort .

# flake8 for linting
flake8 . --max-line-length=88

# mypy for type checking
mypy .
```

### Documentation Style

```python
def complex_function(param1: str, param2: int) -> Dict[str, Any]:
    """One line description of what function does.
    
    Longer description if needed, explaining the purpose,
    behavior, and any important details.
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When parameter validation fails
        ConnectionError: When unable to connect to server
        
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result["status"])
        "success"
    """
```

## 🏗️ Project Structure

```
MCP_Testing_Tools/
├── docs/                    # Documentation
│   ├── api/                # API reference
│   ├── architecture/       # System design docs
│   ├── guides/            # User guides
│   └── tutorials/         # Step-by-step tutorials
├── src/                    # Source code (future refactor)
├── tests/                  # Test files
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── fixtures/          # Test data
├── scripts/               # Development scripts
├── docker/                # Docker configurations
├── *.py                   # Main application files
├── docker-compose.yml     # Production compose
├── docker-compose.dev.yml # Development compose
└── requirements*.txt      # Dependencies
```

## 🧪 Testing Guidelines

### Unit Tests

```python
import pytest
from unittest.mock import Mock, patch
from mock_server import app

@pytest.fixture
def client():
    """Test client for FastAPI app."""
    from fastapi.testclient import TestClient
    return TestClient(app)

def test_tools_list_endpoint(client):
    """Test the tools/list MCP endpoint."""
    response = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": "test-1",
        "method": "tools/list"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == "test-1"
    assert "result" in data
    assert "tools" in data["result"]

@patch('subprocess.Popen')
def test_proxy_start_server(mock_popen, client):
    """Test starting MCP server through proxy."""
    mock_process = Mock()
    mock_popen.return_value = mock_process
    
    response = client.post("/proxy/start", json={
        "command": ["uvx", "mcp-server-filesystem"]
    })
    
    assert response.status_code == 200
    mock_popen.assert_called_once()
```

### Integration Tests

```python
def test_full_workflow():
    """Test complete workflow from discovery to tool calling."""
    # Start services
    # Discover servers
    # Test connection
    # Call tools
    # Verify results
    pass

def test_proxy_with_real_server():
    """Test proxy with actual MCP server."""
    # Start real MCP server through proxy
    # Send MCP messages
    # Verify responses
    # Check logs
    pass
```

### Test Data

Create reusable test fixtures:

```python
# tests/fixtures/mcp_messages.py
VALID_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": "init-1",
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0.0"}
    }
}

TOOLS_LIST_REQUEST = {
    "jsonrpc": "2.0",
    "id": "tools-1",
    "method": "tools/list"
}
```

## 🎯 Feature Development

### Adding New Features

1. **Design First**
   - Create GitHub issue with feature proposal
   - Discuss architecture and implementation
   - Get feedback from maintainers

2. **Implementation**
   - Write tests first (TDD approach)
   - Implement feature
   - Update documentation
   - Add examples

3. **Testing**
   - Unit tests for core logic
   - Integration tests for workflows
   - Manual testing with real scenarios

### Example: Adding Custom Filter

```python
# 1. Define the interface
class MessageFilter:
    def apply(self, message: dict, direction: str) -> Tuple[dict, bool]:
        """Apply filter to message."""
        raise NotImplementedError

# 2. Implement specific filters
class DelayFilter(MessageFilter):
    def __init__(self, delay_ms: int):
        self.delay_ms = delay_ms
    
    def apply(self, message: dict, direction: str) -> Tuple[dict, bool]:
        time.sleep(self.delay_ms / 1000)
        return message, False

# 3. Add to filter registry
FILTER_REGISTRY = {
    "delay": DelayFilter,
    "error_injection": ErrorInjectionFilter,
    # ...
}

# 4. Update API endpoints
@app.post("/proxy/filters")
async def configure_filters(filters: List[FilterConfig]):
    # Implementation
    pass

# 5. Write tests
def test_delay_filter():
    filter = DelayFilter(100)
    start_time = time.time()
    result, modified = filter.apply({"test": "message"}, "incoming")
    elapsed = (time.time() - start_time) * 1000
    
    assert not modified
    assert elapsed >= 100
    assert result == {"test": "message"}
```

## 📝 Commit Message Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples

```bash
# Feature
git commit -m "feat(proxy): add message filtering capabilities"

# Bug fix
git commit -m "fix(mock): resolve JSON parsing error in tool responses"

# Documentation
git commit -m "docs: add troubleshooting guide for port conflicts"

# Breaking change
git commit -m "feat!: change API endpoint structure

BREAKING CHANGE: /api/servers endpoint now returns different format"
```

## 🔍 Code Review Process

### For Contributors

1. **Self Review**
   - Test your changes thoroughly
   - Check code style and formatting
   - Update documentation
   - Write descriptive commit messages

2. **PR Description**
   - Clearly describe what the PR does
   - Link to related issues
   - Include testing instructions
   - Add screenshots if relevant

3. **Respond to Feedback**
   - Address review comments promptly
   - Ask questions if feedback is unclear
   - Make requested changes
   - Re-request review when ready

### Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests are included and passing
- [ ] Documentation is updated
- [ ] No breaking changes (or properly documented)
- [ ] Performance impact considered
- [ ] Security implications reviewed
- [ ] Backward compatibility maintained

## 🏷️ Release Process

### Version Numbers

We use [Semantic Versioning](https://semver.org/):
- `MAJOR.MINOR.PATCH`
- Major: Breaking changes
- Minor: New features (backward compatible)
- Patch: Bug fixes

### Release Steps

1. **Prepare Release**
   ```bash
   # Update version numbers
   # Update CHANGELOG.md
   # Create release branch
   git checkout -b release/v1.2.0
   ```

2. **Testing**
   ```bash
   # Run full test suite
   ./scripts/run-all-tests.sh
   
   # Test Docker builds
   docker-compose build
   
   # Manual testing
   ./scripts/manual-test-checklist.sh
   ```

3. **Create Release**
   ```bash
   # Tag release
   git tag -a v1.2.0 -m "Release version 1.2.0"
   
   # Push tag
   git push origin v1.2.0
   ```

4. **GitHub Release**
   - Create GitHub release from tag
   - Include changelog
   - Attach any release artifacts

## 🎉 Recognition

Contributors are recognized in:
- [CONTRIBUTORS.md](../CONTRIBUTORS.md) file
- GitHub releases
- Project documentation

Thank you for contributing to the MCP Debug Wizard! Your help makes MCP testing magical for everyone! 🧙‍♂️✨

## 📞 Getting Help

- **Discord**: [MCP Community Discord](https://discord.gg/mcp) 
- **GitHub Discussions**: [Project Discussions](https://github.com/llm-case-studies/MCP_Testing_Tools/discussions)
- **Email**: maintainers@mcp-debug-wizard.dev
- **Documentation**: [Full Docs](../index.md)

---

**Remember**: No contribution is too small! Whether it's fixing a typo, reporting a bug, or adding a major feature - every contribution helps make the MCP ecosystem better! 🌟