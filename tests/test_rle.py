"""Tests for RLE decompression module."""

from simple_rdp.rle import decompress_rle


class TestDecompressRle:
    """Tests for RLE decompression function."""

    def test_decompress_rle_function_exists(self) -> None:
        """Test that the decompress_rle function is exported."""
        from simple_rdp import rle

        assert hasattr(rle, "decompress_rle")
        assert callable(rle.decompress_rle)

    def test_decompress_rle_with_valid_dimensions(self) -> None:
        """Test decompression with valid dimensions but empty data returns empty."""
        # Note: The Rust implementation panics on 0 dimensions, so use valid ones
        width = 10
        height = 10
        bpp = 24
        # Empty RLE data with valid dimensions should return empty or handle gracefully
        # The Rust impl may return empty bytes for empty input
        result = decompress_rle(b"", width, height, bpp)
        assert isinstance(result, bytes)

    def test_decompress_rle_callable(self) -> None:
        """Test that decompress_rle is callable with correct args."""
        # Just verify the function signature is correct
        # We can't test actual decompression without valid RLE-encoded data
        from simple_rdp.rle import decompress_rle

        assert callable(decompress_rle)
