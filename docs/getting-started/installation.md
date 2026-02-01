# Installation

## Requirements

- Python 3.11 or higher
- Windows RDP server with Network Level Authentication (NLA) enabled

## Install with pip

```bash
pip install simple-rdp
```

## Install from source

### Using Poetry (recommended)

```bash
git clone https://github.com/abi-jey/simple-rdp.git
cd simple-rdp
poetry install
```

### Using pip

```bash
git clone https://github.com/abi-jey/simple-rdp.git
cd simple-rdp
pip install -e .
```

## Optional: Rust Acceleration

Simple RDP includes an optional Rust extension for 100x faster RLE bitmap decompression. This significantly improves screenshot performance.

### Prerequisites

- Rust toolchain (install from [rustup.rs](https://rustup.rs/))
- Maturin: `pip install maturin`

### Building the Rust extension

The Rust extension is built as part of the main package when using maturin:

```bash
# Build and install with Rust extension
maturin develop --release
```

The library automatically uses the Rust extension when available, falling back to pure Python otherwise.

### Performance Comparison

| Mode | Screenshot FPS | Event Loop Usage |
|------|---------------|------------------|
| Pure Python | ~15 FPS | ~50% |
| Rust Acceleration | ~30 FPS | ~10% |

## Verify Installation

```python
import simple_rdp
print(simple_rdp.__version__)
```

## Dependencies

Simple RDP depends on the following packages (automatically installed):

- `pyspnego` - NTLM/Kerberos authentication
- `pyasn1` - ASN.1 encoding/decoding
- `pillow` - Image processing
- `asn1crypto` - Additional ASN.1 support
- `python-dotenv` - Environment variable loading
