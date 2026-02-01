"""
RDP Interleaved RLE Bitmap Decompression.

Uses the built-in Rust extension for high-performance decompression.
The Rust implementation releases the GIL during decompression,
so it doesn't block the asyncio event loop when used with run_in_executor.

The _rle module is compiled from Rust and bundled with this package.
"""

from simple_rdp._rle import decompress_rle

__all__ = ["decompress_rle"]
