# Installation

## Requirements

- Python 3.11 or higher
- Windows RDP server with Network Level Authentication (NLA) enabled

## Install with pip

```bash
pip install simple-rdp
```

This installs Simple RDP with the native Rust extension for high-performance RLE bitmap decompression, providing up to 100x faster screenshot performance.

## Install from source

Building from source requires the Rust toolchain.

### Prerequisites

1. Install Rust from [rustup.rs](https://rustup.rs/)
2. Install maturin: `pip install maturin`

### Using maturin (recommended)

```bash
git clone https://github.com/abi-jey/simple-rdp.git
cd simple-rdp
maturin develop --release
```

### Using pip with build

```bash
git clone https://github.com/abi-jey/simple-rdp.git
cd simple-rdp
pip install -e .
```

## Verify Installation

```python
import simple_rdp
print(simple_rdp.__version__)

# Verify Rust extension is loaded
from simple_rdp._rle import decompress_rle
print("Rust extension loaded successfully")
```

## Performance

The native Rust extension provides significant performance improvements:

| Metric | Performance |
|--------|-------------|
| Screenshot FPS | ~30 FPS |
| Event Loop Usage | ~10% |
| RLE Decompression | 100x faster than pure Python |

## Dependencies

Simple RDP depends on the following packages (automatically installed):

- `pyspnego` - NTLM/Kerberos authentication
- `pyasn1` - ASN.1 encoding/decoding
- `pillow` - Image processing
- `asn1crypto` - Additional ASN.1 support
- `python-dotenv` - Environment variable loading

## Optional: MCP Server

To use Simple RDP with AI agents via the Model Context Protocol:

```bash
pip install simple-rdp[mcp]
```

See the [MCP Server guide](../guide/mcp-server.md) for usage details.
