"""
RDP Interleaved RLE Bitmap Decompression.

Uses the rle_fast Rust extension for high-performance decompression.
The Rust implementation releases the GIL during decompression,
so it doesn't block the asyncio event loop when used with run_in_executor.

Install the Rust extension:
    cd rle-fast && maturin develop --release

Or install pre-built wheels:
    pip install rle-fast
"""

from rle_fast import decompress_rle

__all__ = ["decompress_rle"]
