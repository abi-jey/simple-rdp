# Contributing

Thank you for your interest in contributing to Simple RDP!

## Development Setup

### Prerequisites

- Python 3.11+
- Poetry
- Git
- (Optional) Rust toolchain for RLE acceleration

### Clone and Install

```bash
git clone https://github.com/abi-jey/simple-rdp.git
cd simple-rdp
poetry install
```

### Install Pre-commit Hooks

```bash
poetry run pre-commit install
```

### Build Rust Extension (Optional)

```bash
maturin develop --release
```

## Development Workflow

### Running Tests

```bash
# Unit tests (no RDP connection needed)
poetry run pytest tests/ --ignore=tests/e2e

# With coverage
poetry run pytest tests/ --ignore=tests/e2e --cov=src/simple_rdp

# E2E tests (requires RDP server)
cp .env.example .env  # Edit with your credentials
poetry run pytest tests/e2e/
```

### Linting

```bash
# Run Ruff linter
poetry run ruff check src/

# Auto-fix issues
poetry run ruff check src/ --fix
```

### Type Checking

```bash
poetry run mypy src/
```

### Format Code

```bash
poetry run ruff format src/
```

### Run All Checks

```bash
poetry run pre-commit run --all-files
```

## Code Structure

```
simple-rdp/
├── src/simple_rdp/
│   ├── __init__.py      # Package exports
│   ├── client.py        # Main RDPClient class
│   ├── capabilities.py  # RDP capability negotiation
│   ├── credssp.py       # CredSSP/NLA authentication
│   ├── mcs.py           # MCS/T.125 protocol layer
│   ├── pdu.py           # RDP PDU encoding/decoding
│   ├── rle.py           # RLE bitmap decompression
│   ├── screen.py        # Display/video utilities
│   └── input.py         # Input type definitions
├── tests/
│   ├── test_*.py        # Unit tests
│   └── e2e/             # End-to-end tests
└── docs/                # MkDocs documentation
```

## Pull Request Guidelines

1. **Create a feature branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make your changes** with appropriate tests

3. **Run all checks**
   ```bash
   poetry run pre-commit run --all-files
   poetry run pytest tests/ --ignore=tests/e2e
   ```

4. **Commit with a clear message**
   ```bash
   git commit -m "feat: add new feature"
   ```

5. **Push and create PR**
   ```bash
   git push origin feature/my-feature
   ```

## Commit Message Format

We follow conventional commits:

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `test:` Test additions/changes
- `refactor:` Code refactoring
- `perf:` Performance improvements
- `chore:` Build/tooling changes

## Documentation

### Building Docs Locally

```bash
pip install mkdocs mkdocs-material mkdocstrings[python]
mkdocs serve
```

Open http://localhost:8000 to preview.

### Writing Documentation

- Add new pages to `docs/`
- Update navigation in `mkdocs.yml`
- Use Material for MkDocs features (admonitions, tabs, etc.)

## Issues

- Check existing issues before creating new ones
- Use issue templates when available
- Include reproduction steps for bugs
- Include environment details (OS, Python version)

## Questions?

Open a discussion on GitHub or reach out to the maintainers.
