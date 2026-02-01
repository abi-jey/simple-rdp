---
icon: material/heart
---

# Contributing

Thank you for your interest in contributing to Simple RDP! :heart:

## Development Setup

### Prerequisites

- [x] Python 3.11+
- [x] Poetry
- [x] Git
- [x] Rust toolchain (install from [rustup.rs](https://rustup.rs/))

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

### Build Rust Extension

```bash
maturin develop --release
```

## Development Workflow

### Running Tests

=== ":material-test-tube: Unit Tests"

    ```bash
    # Unit tests (no RDP connection needed)
    poetry run pytest tests/ --ignore=tests/e2e
    
    # With coverage
    poetry run pytest tests/ --ignore=tests/e2e --cov=src/simple_rdp
    ```

=== ":material-server-network: E2E Tests"

    ```bash
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

!!! success "Pre-commit hooks"
    ```bash
    poetry run pre-commit run --all-files
    ```

??? abstract "Code Structure"
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

- [x] Create a feature branch
- [x] Make changes with appropriate tests
- [x] Run all checks
- [x] Commit with a clear message
- [x] Push and create PR

??? example "Step-by-step"
    ```bash
    # 1. Create a feature branch
    git checkout -b feature/my-feature
    
    # 2. Make your changes with appropriate tests
    
    # 3. Run all checks
    poetry run pre-commit run --all-files
    poetry run pytest tests/ --ignore=tests/e2e
    
    # 4. Commit with a clear message
    git commit -m "feat: add new feature"
    
    # 5. Push and create PR
    git push origin feature/my-feature
    ```

## Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

`feat:`
:   New features

`fix:`
:   Bug fixes

`docs:`
:   Documentation changes

`test:`
:   Test additions/changes

`refactor:`
:   Code refactoring

`perf:`
:   Performance improvements

`chore:`
:   Build/tooling changes

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

!!! info "Before creating an issue"
    - Check existing issues before creating new ones
    - Use issue templates when available
    - Include reproduction steps for bugs
    - Include environment details (OS, Python version)

## Questions?

!!! question "Need help?"
    Open a [discussion on GitHub](https://github.com/abi-jey/simple-rdp/discussions) or reach out to the maintainers.
