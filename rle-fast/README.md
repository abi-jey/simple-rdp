# rle-fast

Fast RLE (Run-Length Encoding) bitmap decompression for RDP, written in Rust.

This is a companion package for [simple-rdp](https://pypi.org/project/simple-rdp/).

## Installation

```bash
pip install rle-fast
```

Pre-built wheels are available for:
- Linux (x86_64, aarch64)
- macOS (x86_64, arm64)  
- Windows (x86_64)

## Usage

```python
from rle_fast import decompress_rle

# Decompress RLE-encoded bitmap data
pixels = decompress_rle(
    compressed_data,  # bytes: RLE compressed data
    width,            # int: bitmap width in pixels
    height,           # int: bitmap height in pixels
    bpp              # int: bits per pixel (8, 15, 16, or 24)
)
# Returns: bytes - decompressed RGB pixel data (3 bytes per pixel)
```

## Performance

The Rust implementation is ~20-50x faster than pure Python and releases the GIL during decompression, making it safe for use in async applications.

## License

MIT
