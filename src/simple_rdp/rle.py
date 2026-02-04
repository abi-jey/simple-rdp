"""
RDP Interleaved RLE Bitmap Decompression.

Uses the built-in Rust extension for high-performance decompression.
The `decompress_rle` function is async and can be awaited directly:

    data = await decompress_rle(compressed, width, height, bpp, has_header)

The CPU-intensive decompression runs on a thread pool executor,
so it doesn't block the Python asyncio event loop.

The _rle module is compiled from Rust and bundled with this package.
"""

import asyncio
from functools import partial

from simple_rdp._rle import decompress_rle as _decompress_rle_sync


async def decompress_rle(
    compressed_data: bytes,
    width: int,
    height: int,
    bpp: int,
    has_header: bool = True,
) -> bytes:
    """
    Decompress RLE-compressed bitmap data asynchronously.

    This function runs the CPU-intensive Rust decompression on a thread pool
    to avoid blocking the asyncio event loop.

    Args:
        compressed_data: The compressed bitmap data (including optional header)
        width: Width of the bitmap in pixels
        height: Height of the bitmap in pixels
        bpp: Bits per pixel (8, 15, 16, or 24)
        has_header: Whether the data includes a TS_CD_HEADER (8 bytes)

    Returns:
        Decompressed bitmap data as bytes
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,  # Use default ThreadPoolExecutor
        partial(_decompress_rle_sync, compressed_data, width, height, bpp, has_header),
    )


__all__ = ["decompress_rle"]
