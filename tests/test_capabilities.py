"""Tests for RDP capabilities module."""

import struct

from simple_rdp.capabilities import CAPSTYPE_BITMAP
from simple_rdp.capabilities import CAPSTYPE_GENERAL
from simple_rdp.capabilities import CAPSTYPE_INPUT
from simple_rdp.capabilities import CAPSTYPE_ORDER
from simple_rdp.capabilities import CAPSTYPE_POINTER
from simple_rdp.capabilities import FASTPATH_OUTPUT_SUPPORTED
from simple_rdp.capabilities import INPUT_FLAG_FASTPATH_INPUT
from simple_rdp.capabilities import INPUT_FLAG_SCANCODES
from simple_rdp.capabilities import INPUT_FLAG_UNICODE
from simple_rdp.capabilities import LONG_CREDENTIALS_SUPPORTED
from simple_rdp.capabilities import OSMAJORTYPE_UNIX
from simple_rdp.capabilities import OSMINORTYPE_NATIVE_XSERVER
from simple_rdp.capabilities import build_activation_capability
from simple_rdp.capabilities import build_bitmap_cache_capability
from simple_rdp.capabilities import build_bitmap_capability
from simple_rdp.capabilities import build_brush_capability
from simple_rdp.capabilities import build_capability_header
from simple_rdp.capabilities import build_client_capabilities
from simple_rdp.capabilities import build_color_cache_capability
from simple_rdp.capabilities import build_control_capability
from simple_rdp.capabilities import build_font_capability
from simple_rdp.capabilities import build_general_capability
from simple_rdp.capabilities import build_glyph_cache_capability
from simple_rdp.capabilities import build_input_capability
from simple_rdp.capabilities import build_multifragment_update_capability
from simple_rdp.capabilities import build_offscreen_cache_capability
from simple_rdp.capabilities import build_order_capability
from simple_rdp.capabilities import build_pointer_capability
from simple_rdp.capabilities import build_share_capability
from simple_rdp.capabilities import build_sound_capability
from simple_rdp.capabilities import build_virtual_channel_capability


class TestCapabilityHeader:
    """Tests for capability header building."""

    def test_build_capability_header_empty_data(self) -> None:
        """Test building header with empty data."""
        result = build_capability_header(CAPSTYPE_GENERAL, b"")
        assert len(result) == 4  # Just header
        cap_type, length = struct.unpack("<HH", result)
        assert cap_type == CAPSTYPE_GENERAL
        assert length == 4

    def test_build_capability_header_with_data(self) -> None:
        """Test building header with data."""
        data = b"\x01\x02\x03\x04"
        result = build_capability_header(CAPSTYPE_BITMAP, data)
        assert len(result) == 8  # 4 header + 4 data
        cap_type, length = struct.unpack("<HH", result[:4])
        assert cap_type == CAPSTYPE_BITMAP
        assert length == 8
        assert result[4:] == data


class TestGeneralCapability:
    """Tests for general capability set."""

    def test_build_general_capability_defaults(self) -> None:
        """Test building general capability with defaults."""
        result = build_general_capability()
        assert len(result) > 4  # Header + data

        # Check header
        cap_type, length = struct.unpack("<HH", result[:4])
        assert cap_type == CAPSTYPE_GENERAL
        assert length == len(result)

    def test_build_general_capability_custom_os(self) -> None:
        """Test building general capability with custom OS type."""
        result = build_general_capability(
            os_major_type=OSMAJORTYPE_UNIX,
            os_minor_type=OSMINORTYPE_NATIVE_XSERVER,
        )
        # After header, first 4 bytes are OS major/minor
        os_major, os_minor = struct.unpack("<HH", result[4:8])
        assert os_major == OSMAJORTYPE_UNIX
        assert os_minor == OSMINORTYPE_NATIVE_XSERVER

    def test_build_general_capability_extra_flags(self) -> None:
        """Test extra flags are correctly set."""
        flags = FASTPATH_OUTPUT_SUPPORTED | LONG_CREDENTIALS_SUPPORTED
        result = build_general_capability(extra_flags=flags)
        # Extra flags are at offset 14 from start (4 header + 10 data)
        extra_flags = struct.unpack("<H", result[14:16])[0]
        assert extra_flags == flags


class TestBitmapCapability:
    """Tests for bitmap capability set."""

    def test_build_bitmap_capability_defaults(self) -> None:
        """Test building bitmap capability with defaults."""
        result = build_bitmap_capability()
        cap_type, length = struct.unpack("<HH", result[:4])
        assert cap_type == CAPSTYPE_BITMAP
        assert length == len(result)

    def test_build_bitmap_capability_custom_resolution(self) -> None:
        """Test building bitmap capability with custom resolution."""
        result = build_bitmap_capability(
            desktop_width=1280,
            desktop_height=720,
        )
        # Desktop width/height are at specific offsets
        assert len(result) > 4


class TestOrderCapability:
    """Tests for order capability set."""

    def test_build_order_capability_defaults(self) -> None:
        """Test building order capability with defaults."""
        result = build_order_capability()
        cap_type, length = struct.unpack("<HH", result[:4])
        assert cap_type == CAPSTYPE_ORDER
        assert length == len(result)


class TestPointerCapability:
    """Tests for pointer capability set."""

    def test_build_pointer_capability_defaults(self) -> None:
        """Test building pointer capability with defaults."""
        result = build_pointer_capability()
        cap_type, length = struct.unpack("<HH", result[:4])
        assert cap_type == CAPSTYPE_POINTER
        assert length == len(result)


class TestInputCapability:
    """Tests for input capability set."""

    def test_build_input_capability_defaults(self) -> None:
        """Test building input capability with defaults."""
        result = build_input_capability()
        cap_type, length = struct.unpack("<HH", result[:4])
        assert cap_type == CAPSTYPE_INPUT
        assert length == len(result)

    def test_build_input_capability_flags(self) -> None:
        """Test input capability flags."""
        flags = INPUT_FLAG_SCANCODES | INPUT_FLAG_FASTPATH_INPUT | INPUT_FLAG_UNICODE
        result = build_input_capability(input_flags=flags)
        # Flags are at offset 4 after header
        input_flags = struct.unpack("<H", result[4:6])[0]
        assert input_flags == flags


class TestAdditionalCapabilities:
    """Tests for additional capability sets."""

    def test_build_control_capability(self) -> None:
        """Test building control capability."""
        result = build_control_capability()
        assert isinstance(result, bytes)
        assert len(result) > 4

    def test_build_activation_capability(self) -> None:
        """Test building activation capability."""
        result = build_activation_capability()
        assert isinstance(result, bytes)
        assert len(result) > 4

    def test_build_share_capability(self) -> None:
        """Test building share capability."""
        result = build_share_capability()
        assert isinstance(result, bytes)
        assert len(result) > 4

    def test_build_font_capability(self) -> None:
        """Test building font capability."""
        result = build_font_capability()
        assert isinstance(result, bytes)
        assert len(result) > 4

    def test_build_color_cache_capability(self) -> None:
        """Test building color cache capability."""
        result = build_color_cache_capability()
        assert isinstance(result, bytes)
        assert len(result) > 4

    def test_build_sound_capability(self) -> None:
        """Test building sound capability."""
        result = build_sound_capability()
        assert isinstance(result, bytes)
        assert len(result) > 4

    def test_build_brush_capability(self) -> None:
        """Test building brush capability."""
        result = build_brush_capability()
        assert isinstance(result, bytes)
        assert len(result) > 4

    def test_build_glyph_cache_capability(self) -> None:
        """Test building glyph cache capability."""
        result = build_glyph_cache_capability()
        assert isinstance(result, bytes)
        assert len(result) > 4

    def test_build_offscreen_cache_capability(self) -> None:
        """Test building offscreen cache capability."""
        result = build_offscreen_cache_capability()
        assert isinstance(result, bytes)
        assert len(result) > 4

    def test_build_bitmap_cache_capability(self) -> None:
        """Test building bitmap cache capability."""
        result = build_bitmap_cache_capability()
        assert isinstance(result, bytes)
        assert len(result) > 4

    def test_build_virtual_channel_capability(self) -> None:
        """Test building virtual channel capability."""
        result = build_virtual_channel_capability()
        assert isinstance(result, bytes)
        assert len(result) > 4

    def test_build_multifragment_update_capability(self) -> None:
        """Test building multifragment update capability."""
        result = build_multifragment_update_capability()
        assert isinstance(result, bytes)
        assert len(result) > 4


class TestClientCapabilities:
    """Tests for combined client capabilities."""

    def test_build_client_capabilities(self) -> None:
        """Test building all client capabilities."""
        result = build_client_capabilities()
        assert isinstance(result, bytes)
        assert len(result) > 100  # Should be quite large
