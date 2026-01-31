# Simple RDP

A Python RDP client library designed for automation purposes. Unlike traditional RDP clients, Simple RDP does not provide an interactive session. Instead, it exposes screen capture and input transmission capabilities for building automation workflows.

## Features

- **Screen Capture**: Capture the remote desktop screen for processing
- **Input Transmission**: Send mouse movements, clicks, and keyboard input
- **Automation-Focused**: Built specifically for automation, not interactive use

## Installation

```bash
poetry install
```

## Usage

```python
from simple_rdp import RDPClient, ConnectionConfig

config = ConnectionConfig(
    host="remote-server.example.com",
    username="user",
    password="password"
)

with RDPClient(config) as client:
    # Capture screen
    frame = client.screen.capture()
    
    # Send input
    client.input.click(100, 200)
    client.input.type_text("Hello, World!")
```

## Development

### Setup

```bash
poetry install
```

### Running Tests

```bash
poetry run pytest
```

## Project Structure

```
simple-rdp/
├── src/
│   └── simple_rdp/
│       ├── __init__.py
│       ├── client.py      # RDP client connection handling
│       ├── screen.py      # Screen capture functionality
│       └── input.py       # Mouse and keyboard input
├── tests/
│   ├── test_client.py
│   ├── test_screen.py
│   └── test_input.py
├── pyproject.toml
└── README.md
```

## License

MIT
