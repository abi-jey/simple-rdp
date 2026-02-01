"""Tests for RDP PDU layer module."""

import struct

from simple_rdp.pdu import CTRLACTION_COOPERATE
from simple_rdp.pdu import CTRLACTION_DETACH
from simple_rdp.pdu import CTRLACTION_GRANTED_CONTROL
from simple_rdp.pdu import CTRLACTION_REQUEST_CONTROL
from simple_rdp.pdu import INFO_DISABLECTRLALTDEL
from simple_rdp.pdu import INFO_LOGONNOTIFY
from simple_rdp.pdu import INFO_MOUSE
from simple_rdp.pdu import INFO_UNICODE
from simple_rdp.pdu import INPUT_EVENT_MOUSE
from simple_rdp.pdu import INPUT_EVENT_SCANCODE
from simple_rdp.pdu import INPUT_EVENT_SYNC
from simple_rdp.pdu import INPUT_EVENT_UNICODE
from simple_rdp.pdu import KBDFLAGS_DOWN
from simple_rdp.pdu import KBDFLAGS_EXTENDED
from simple_rdp.pdu import KBDFLAGS_RELEASE
from simple_rdp.pdu import PDUTYPE2_CONTROL
from simple_rdp.pdu import PDUTYPE2_INPUT
from simple_rdp.pdu import PDUTYPE2_SYNCHRONIZE
from simple_rdp.pdu import PDUTYPE2_UPDATE
from simple_rdp.pdu import PDUTYPE_CONFIRMACTIVEPDU
from simple_rdp.pdu import PDUTYPE_DATAPDU
from simple_rdp.pdu import PDUTYPE_DEMANDACTIVEPDU
from simple_rdp.pdu import PERF_DISABLE_CURSOR_SHADOW
from simple_rdp.pdu import PERF_DISABLE_FULLWINDOWDRAG
from simple_rdp.pdu import PERF_DISABLE_MENUANIMATIONS
from simple_rdp.pdu import PERF_DISABLE_THEMING
from simple_rdp.pdu import PERF_DISABLE_WALLPAPER
from simple_rdp.pdu import PTRFLAGS_BUTTON1
from simple_rdp.pdu import PTRFLAGS_BUTTON2
from simple_rdp.pdu import PTRFLAGS_BUTTON3
from simple_rdp.pdu import PTRFLAGS_DOWN
from simple_rdp.pdu import PTRFLAGS_MOVE
from simple_rdp.pdu import SEC_ENCRYPT
from simple_rdp.pdu import SEC_EXCHANGE_PKT
from simple_rdp.pdu import SEC_INFO_PKT
from simple_rdp.pdu import SEC_LICENSE_PKT
from simple_rdp.pdu import UPDATETYPE_BITMAP
from simple_rdp.pdu import UPDATETYPE_ORDERS
from simple_rdp.pdu import build_client_info_pdu
from simple_rdp.pdu import build_confirm_active_pdu
from simple_rdp.pdu import build_control_pdu
from simple_rdp.pdu import build_font_list_pdu
from simple_rdp.pdu import build_input_event_pdu
from simple_rdp.pdu import build_mouse_event
from simple_rdp.pdu import build_refresh_rect_pdu
from simple_rdp.pdu import build_scancode_event
from simple_rdp.pdu import build_security_exchange_pdu
from simple_rdp.pdu import build_share_control_header
from simple_rdp.pdu import build_share_data_header
from simple_rdp.pdu import build_suppress_output_pdu
from simple_rdp.pdu import build_synchronize_pdu
from simple_rdp.pdu import build_unicode_event
from simple_rdp.pdu import parse_bitmap_update
from simple_rdp.pdu import parse_demand_active_pdu
from simple_rdp.pdu import parse_update_pdu


class TestSecurityHeaderFlags:
    """Tests for security header flag constants."""

    def test_sec_info_pkt_flag(self) -> None:
        """Test SEC_INFO_PKT flag value."""
        assert SEC_INFO_PKT == 0x0040

    def test_flags_are_powers_of_two(self) -> None:
        """Test that flags are powers of two for bitwise OR."""
        from simple_rdp.pdu import SEC_ENCRYPT
        from simple_rdp.pdu import SEC_EXCHANGE_PKT
        from simple_rdp.pdu import SEC_LICENSE_PKT

        # Each flag should be a power of 2
        assert SEC_EXCHANGE_PKT & (SEC_EXCHANGE_PKT - 1) == 0
        assert SEC_ENCRYPT & (SEC_ENCRYPT - 1) == 0
        assert SEC_INFO_PKT & (SEC_INFO_PKT - 1) == 0
        assert SEC_LICENSE_PKT & (SEC_LICENSE_PKT - 1) == 0


class TestPduTypes:
    """Tests for PDU type constants."""

    def test_share_control_pdu_types(self) -> None:
        """Test share control PDU type values."""
        assert PDUTYPE_CONFIRMACTIVEPDU == 0x0003
        assert PDUTYPE_DATAPDU == 0x0007

    def test_share_data_pdu_types(self) -> None:
        """Test share data PDU type values."""
        assert PDUTYPE2_SYNCHRONIZE == 0x1F
        assert PDUTYPE2_CONTROL == 0x14


class TestInputEventTypes:
    """Tests for input event type constants."""

    def test_input_event_scancode(self) -> None:
        """Test scancode input event type."""
        assert INPUT_EVENT_SCANCODE == 0x0004

    def test_input_event_mouse(self) -> None:
        """Test mouse input event type."""
        assert INPUT_EVENT_MOUSE == 0x8001


class TestMouseEventFlags:
    """Tests for mouse event flag constants."""

    def test_ptrflags_move(self) -> None:
        """Test mouse move flag."""
        assert PTRFLAGS_MOVE == 0x0800

    def test_ptrflags_down(self) -> None:
        """Test mouse button down flag."""
        assert PTRFLAGS_DOWN == 0x8000

    def test_ptrflags_button1(self) -> None:
        """Test left button flag."""
        assert PTRFLAGS_BUTTON1 == 0x1000


class TestKeyboardEventFlags:
    """Tests for keyboard event flag constants."""

    def test_kbdflags_down(self) -> None:
        """Test key down flag."""
        assert KBDFLAGS_DOWN == 0x4000

    def test_kbdflags_release(self) -> None:
        """Test key release flag."""
        assert KBDFLAGS_RELEASE == 0x8000


class TestInfoPacketFlags:
    """Tests for info packet flag constants."""

    def test_info_mouse(self) -> None:
        """Test mouse support flag."""
        assert INFO_MOUSE == 0x00000001

    def test_info_unicode(self) -> None:
        """Test unicode support flag."""
        assert INFO_UNICODE == 0x00000010

    def test_combined_flags(self) -> None:
        """Test combining flags."""
        flags = INFO_MOUSE | INFO_UNICODE | INFO_LOGONNOTIFY | INFO_DISABLECTRLALTDEL
        assert flags & INFO_MOUSE
        assert flags & INFO_UNICODE


class TestClientInfoPdu:
    """Tests for client info PDU building."""

    def test_build_client_info_pdu_empty(self) -> None:
        """Test building client info PDU with empty values."""
        result = build_client_info_pdu()
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_build_client_info_pdu_with_credentials(self) -> None:
        """Test building client info PDU with credentials."""
        result = build_client_info_pdu(
            domain="WORKGROUP",
            username="testuser",
            password="testpass",
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_build_client_info_pdu_custom_flags(self) -> None:
        """Test building client info PDU with custom flags."""
        flags = INFO_MOUSE | INFO_UNICODE
        result = build_client_info_pdu(flags=flags)
        assert isinstance(result, bytes)


class TestSynchronizePdu:
    """Tests for synchronize PDU building."""

    def test_build_synchronize_pdu(self) -> None:
        """Test building synchronize PDU."""
        result = build_synchronize_pdu(target_user=1001)
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestControlPdu:
    """Tests for control PDU building."""

    def test_build_control_pdu_cooperate(self) -> None:
        """Test building cooperate control PDU."""
        result = build_control_pdu(CTRLACTION_COOPERATE)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_build_control_pdu_request_control(self) -> None:
        """Test building request control PDU."""
        result = build_control_pdu(CTRLACTION_REQUEST_CONTROL)
        assert isinstance(result, bytes)


class TestInputEvents:
    """Tests for input event building."""

    def test_build_scancode_event_keydown(self) -> None:
        """Test building scancode event - key down."""
        scancode = 0x1E  # 'A' key
        result = build_scancode_event(scancode, is_release=False)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_build_scancode_event_keyup(self) -> None:
        """Test building scancode event - key up."""
        scancode = 0x1E  # 'A' key
        result = build_scancode_event(scancode, is_release=True)
        assert isinstance(result, bytes)

    def test_build_scancode_event_extended(self) -> None:
        """Test building extended scancode event."""
        scancode = 0x4D  # Right arrow
        result = build_scancode_event(scancode, is_extended=True)
        assert isinstance(result, bytes)

    def test_build_mouse_event_move(self) -> None:
        """Test building mouse move event."""
        result = build_mouse_event(x=100, y=200, is_move=True)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_build_mouse_event_click(self) -> None:
        """Test building mouse click event."""
        result = build_mouse_event(
            x=100,
            y=200,
            button=PTRFLAGS_BUTTON1,
            is_down=True,
            is_move=False,
        )
        assert isinstance(result, bytes)


class TestPerformanceFlags:
    """Tests for performance flag constants."""

    def test_perf_disable_wallpaper(self) -> None:
        """Test disable wallpaper flag."""
        assert PERF_DISABLE_WALLPAPER == 0x00000001

    def test_perf_disable_fullwindowdrag(self) -> None:
        """Test disable full window drag flag."""
        assert PERF_DISABLE_FULLWINDOWDRAG == 0x00000002

    def test_perf_disable_menuanimations(self) -> None:
        """Test disable menu animations flag."""
        assert PERF_DISABLE_MENUANIMATIONS == 0x00000004

    def test_perf_disable_theming(self) -> None:
        """Test disable theming flag."""
        assert PERF_DISABLE_THEMING == 0x00000008

    def test_perf_disable_cursor_shadow(self) -> None:
        """Test disable cursor shadow flag."""
        assert PERF_DISABLE_CURSOR_SHADOW == 0x00000020


class TestShareControlHeader:
    """Tests for share control header building."""

    def test_build_share_control_header(self) -> None:
        """Test building share control header."""
        result = build_share_control_header(
            pdu_type=PDUTYPE_DATAPDU,
            pdu_source=1001,
        )
        assert isinstance(result, bytes)
        assert len(result) == 6

    def test_build_share_control_header_confirm_active(self) -> None:
        """Test building confirm active share control header."""
        result = build_share_control_header(
            pdu_type=PDUTYPE_CONFIRMACTIVEPDU,
            pdu_source=1001,
        )
        assert isinstance(result, bytes)


class TestShareDataHeader:
    """Tests for share data header building."""

    def test_build_share_data_header(self) -> None:
        """Test building share data header."""
        result = build_share_data_header(
            share_id=0x12345678,
            pdu_source=1001,
            pdu_type2=PDUTYPE2_INPUT,
        )
        assert isinstance(result, bytes)
        assert len(result) == 12

    def test_build_share_data_header_synchronize(self) -> None:
        """Test building synchronize share data header."""
        result = build_share_data_header(
            share_id=0x00000000,
            pdu_source=1001,
            pdu_type2=PDUTYPE2_SYNCHRONIZE,
        )
        assert isinstance(result, bytes)


class TestSecurityExchangePdu:
    """Tests for security exchange PDU building."""

    def test_build_security_exchange_pdu(self) -> None:
        """Test building security exchange PDU."""
        encrypted_random = bytes([0x00] * 32)
        result = build_security_exchange_pdu(encrypted_random)
        assert isinstance(result, bytes)
        # Should include header flags + length + data + padding
        assert len(result) == 4 + 4 + 32 + 8


class TestFontListPdu:
    """Tests for font list PDU building."""

    def test_build_font_list_pdu(self) -> None:
        """Test building font list PDU."""
        result = build_font_list_pdu()
        assert isinstance(result, bytes)
        assert len(result) == 8  # 4 x 2-byte fields


class TestInputEventPdu:
    """Tests for input event PDU building."""

    def test_build_input_event_pdu_empty(self) -> None:
        """Test building input event PDU with no events."""
        result = build_input_event_pdu([])
        assert isinstance(result, bytes)

    def test_build_input_event_pdu_with_events(self) -> None:
        """Test building input event PDU with events."""
        event_data = bytes([0x00] * 4)
        events = [(0, INPUT_EVENT_SCANCODE, event_data)]
        result = build_input_event_pdu(events)
        assert isinstance(result, bytes)


class TestUnicodeEvent:
    """Tests for unicode event building."""

    def test_build_unicode_event_keydown(self) -> None:
        """Test building unicode event - key down."""
        result = build_unicode_event(ord("A"), is_release=False)
        assert isinstance(result, bytes)

    def test_build_unicode_event_keyup(self) -> None:
        """Test building unicode event - key up."""
        result = build_unicode_event(ord("A"), is_release=True)
        assert isinstance(result, bytes)


class TestConfirmActivePdu:
    """Tests for confirm active PDU building."""

    def test_build_confirm_active_pdu(self) -> None:
        """Test building confirm active PDU."""
        from simple_rdp.capabilities import build_client_capabilities
        
        result = build_confirm_active_pdu(
            share_id=0x12345678,
            originator_id=1001,
            source_descriptor=b"RDP",
            capabilities=build_client_capabilities(),
        )
        assert isinstance(result, bytes)
        assert len(result) > 100  # Should contain capabilities


class TestRefreshRectPdu:
    """Tests for refresh rect PDU building."""

    def test_build_refresh_rect_pdu_single(self) -> None:
        """Test building refresh rect PDU with single rect."""
        rectangles = [(0, 0, 1920, 1080)]
        result = build_refresh_rect_pdu(rectangles)
        assert isinstance(result, bytes)

    def test_build_refresh_rect_pdu_multiple(self) -> None:
        """Test building refresh rect PDU with multiple rects."""
        rectangles = [(0, 0, 100, 100), (100, 0, 100, 100)]
        result = build_refresh_rect_pdu(rectangles)
        assert isinstance(result, bytes)


class TestSuppressOutputPdu:
    """Tests for suppress output PDU building."""

    def test_build_suppress_output_pdu_allow(self) -> None:
        """Test building suppress output PDU - allow updates."""
        result = build_suppress_output_pdu(
            allow_display_updates=True,
            rectangle=(0, 0, 1920, 1080),
        )
        assert isinstance(result, bytes)

    def test_build_suppress_output_pdu_suppress(self) -> None:
        """Test building suppress output PDU - suppress updates."""
        result = build_suppress_output_pdu(allow_display_updates=False)
        assert isinstance(result, bytes)


class TestParsingFunctions:
    """Tests for PDU parsing functions."""

    def test_parse_update_pdu_bitmap(self) -> None:
        """Test parsing bitmap update PDU."""
        # Build a minimal bitmap update header
        data = struct.pack("<H", UPDATETYPE_BITMAP)  # Update type
        result = parse_update_pdu(data)
        assert isinstance(result, dict)
        assert result["update_type"] == UPDATETYPE_BITMAP
        assert result["data"] == b""

    def test_parse_update_pdu_with_data(self) -> None:
        """Test parsing update PDU with data."""
        extra_data = b"\x01\x02\x03\x04"
        data = struct.pack("<H", UPDATETYPE_BITMAP) + extra_data
        result = parse_update_pdu(data)
        assert result["update_type"] == UPDATETYPE_BITMAP
        assert result["data"] == extra_data

    def test_parse_update_pdu_empty(self) -> None:
        """Test parsing empty update PDU."""
        result = parse_update_pdu(b"")
        assert result["update_type"] == 0
        assert result["data"] == b""

    def test_parse_bitmap_update_empty(self) -> None:
        """Test parsing empty bitmap update."""
        # Number of rectangles: 0
        data = struct.pack("<H", 0)
        result = parse_bitmap_update(data)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_parse_bitmap_update_too_short(self) -> None:
        """Test parsing bitmap update with insufficient data."""
        result = parse_bitmap_update(b"\x00")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_parse_demand_active_pdu(self) -> None:
        """Test parsing demand active PDU."""
        # Build a minimal demand active PDU
        share_id = 0x12345678
        source_descriptor = b"RDP"
        
        data = struct.pack("<I", share_id)  # Share ID
        data += struct.pack("<H", len(source_descriptor))  # Source descriptor length
        data += struct.pack("<H", 0)  # Combined capabilities length
        data += source_descriptor  # Source descriptor
        data += struct.pack("<H", 0)  # Number of capability sets
        data += struct.pack("<H", 0)  # Padding
        
        result = parse_demand_active_pdu(data)
        assert isinstance(result, dict)
        assert result["share_id"] == share_id
        assert result["source_descriptor"] == source_descriptor
        assert result["capabilities"] == []

    def test_parse_demand_active_pdu_with_capabilities(self) -> None:
        """Test parsing demand active PDU with capabilities."""
        share_id = 0x12345678
        source_descriptor = b"RDP"
        
        # Build a fake capability
        cap_type = 1
        cap_data = b"\x00\x01\x02\x03"
        cap_len = 4 + len(cap_data)
        capability = struct.pack("<HH", cap_type, cap_len) + cap_data
        
        data = struct.pack("<I", share_id)  # Share ID
        data += struct.pack("<H", len(source_descriptor))  # Source descriptor length
        data += struct.pack("<H", len(capability))  # Combined capabilities length
        data += source_descriptor  # Source descriptor
        data += struct.pack("<H", 1)  # Number of capability sets
        data += struct.pack("<H", 0)  # Padding
        data += capability
        
        result = parse_demand_active_pdu(data)
        assert len(result["capabilities"]) == 1
        assert result["capabilities"][0]["type"] == cap_type

    def test_parse_demand_active_pdu_truncated_cap_header(self) -> None:
        """Test parsing demand active PDU with truncated capability header."""
        share_id = 0x12345678
        source_descriptor = b"RDP"
        
        data = struct.pack("<I", share_id)  # Share ID
        data += struct.pack("<H", len(source_descriptor))  # Source descriptor length
        data += struct.pack("<H", 0)  # Combined capabilities length
        data += source_descriptor  # Source descriptor
        data += struct.pack("<H", 1)  # Says 1 capability, but not enough data
        data += struct.pack("<H", 0)  # Padding
        # No capability data - should stop gracefully
        
        result = parse_demand_active_pdu(data)
        assert result["capabilities"] == []

    def test_parse_demand_active_pdu_invalid_cap_len(self) -> None:
        """Test parsing demand active PDU with cap_len < 4."""
        share_id = 0x12345678
        source_descriptor = b"RDP"
        
        # Build a capability with invalid length (less than 4)
        capability = struct.pack("<HH", 1, 2)  # cap_type=1, cap_len=2 (invalid)
        
        data = struct.pack("<I", share_id)
        data += struct.pack("<H", len(source_descriptor))
        data += struct.pack("<H", len(capability))
        data += source_descriptor
        data += struct.pack("<H", 1)  # 1 capability
        data += struct.pack("<H", 0)  # Padding
        data += capability
        
        result = parse_demand_active_pdu(data)
        # Should stop parsing at invalid cap_len
        assert result["capabilities"] == []

    def test_parse_bitmap_update_with_rects(self) -> None:
        """Test parsing bitmap update with valid rectangles."""
        # Build a bitmap update with one rectangle
        num_rects = 1
        data = struct.pack("<H", num_rects)  # Number of rectangles
        
        # Add bitmap header (18 bytes)
        data += struct.pack("<H", 0)  # dest_left
        data += struct.pack("<H", 0)  # dest_top
        data += struct.pack("<H", 10)  # dest_right
        data += struct.pack("<H", 10)  # dest_bottom
        data += struct.pack("<H", 10)  # width
        data += struct.pack("<H", 10)  # height
        data += struct.pack("<H", 24)  # bpp (24-bit)
        data += struct.pack("<H", 0)  # flags
        bitmap_data = b"\x00" * 30
        data += struct.pack("<H", len(bitmap_data))  # length
        data += bitmap_data
        
        result = parse_bitmap_update(data)
        assert len(result) == 1
        assert result[0]["width"] == 10
        assert result[0]["height"] == 10
        assert result[0]["bpp"] == 24

    def test_parse_bitmap_update_invalid_bpp(self) -> None:
        """Test parsing bitmap update with invalid bpp stops."""
        num_rects = 1
        data = struct.pack("<H", num_rects)
        
        # Add bitmap header with invalid bpp
        data += struct.pack("<H", 0)  # dest_left
        data += struct.pack("<H", 0)  # dest_top
        data += struct.pack("<H", 10)  # dest_right
        data += struct.pack("<H", 10)  # dest_bottom
        data += struct.pack("<H", 10)  # width
        data += struct.pack("<H", 10)  # height
        data += struct.pack("<H", 99)  # bpp (invalid)
        data += struct.pack("<H", 0)  # flags
        data += struct.pack("<H", 10)  # length
        
        result = parse_bitmap_update(data)
        assert len(result) == 0

    def test_parse_bitmap_update_zero_dimensions(self) -> None:
        """Test parsing bitmap update with zero dimensions."""
        num_rects = 1
        data = struct.pack("<H", num_rects)
        
        # Add bitmap header with zero width
        data += struct.pack("<H", 0)  # dest_left
        data += struct.pack("<H", 0)  # dest_top
        data += struct.pack("<H", 0)  # dest_right
        data += struct.pack("<H", 0)  # dest_bottom
        data += struct.pack("<H", 0)  # width = 0 (invalid)
        data += struct.pack("<H", 10)  # height
        data += struct.pack("<H", 24)  # bpp
        data += struct.pack("<H", 0)  # flags
        data += struct.pack("<H", 0)  # length
        
        result = parse_bitmap_update(data)
        assert len(result) == 0

    def test_parse_bitmap_update_insufficient_data(self) -> None:
        """Test parsing bitmap update with insufficient data for bitmap."""
        num_rects = 1
        data = struct.pack("<H", num_rects)
        
        # Add bitmap header that claims more data than available
        data += struct.pack("<H", 0)  # dest_left
        data += struct.pack("<H", 0)  # dest_top
        data += struct.pack("<H", 10)  # dest_right
        data += struct.pack("<H", 10)  # dest_bottom
        data += struct.pack("<H", 10)  # width
        data += struct.pack("<H", 10)  # height
        data += struct.pack("<H", 24)  # bpp
        data += struct.pack("<H", 0)  # flags
        data += struct.pack("<H", 1000)  # length (more than available)
        data += b"\x00" * 10  # Only 10 bytes of data
        
        result = parse_bitmap_update(data)
        assert len(result) == 0

    def test_parse_bitmap_update_truncated_header(self) -> None:
        """Test parsing bitmap update with truncated header for second rect."""
        # First rect is valid, second rect header is truncated
        num_rects = 2
        data = struct.pack("<H", num_rects)
        
        # First rectangle (valid)
        data += struct.pack("<H", 0)  # dest_left
        data += struct.pack("<H", 0)  # dest_top
        data += struct.pack("<H", 10)  # dest_right
        data += struct.pack("<H", 10)  # dest_bottom
        data += struct.pack("<H", 10)  # width
        data += struct.pack("<H", 10)  # height
        data += struct.pack("<H", 24)  # bpp
        data += struct.pack("<H", 0)  # flags
        bitmap_data = b"\x00" * 10
        data += struct.pack("<H", len(bitmap_data))  # length
        data += bitmap_data
        
        # Second rectangle - only partial header (not enough for 18 bytes)
        data += struct.pack("<H", 0)  # Only 2 bytes - not enough for header
        
        result = parse_bitmap_update(data)
        # Should have parsed only the first valid rect
        assert len(result) == 1


class TestMoreMouseEvents:
    """Additional tests for mouse events."""

    def test_build_mouse_event_button2(self) -> None:
        """Test building mouse right-click event."""
        result = build_mouse_event(
            x=200,
            y=300,
            button=PTRFLAGS_BUTTON2,
            is_down=True,
            is_move=False,
        )
        assert isinstance(result, bytes)

    def test_build_mouse_event_button3(self) -> None:
        """Test building mouse middle-click event."""
        result = build_mouse_event(
            x=200,
            y=300,
            button=PTRFLAGS_BUTTON3,
            is_down=True,
            is_move=False,
        )
        assert isinstance(result, bytes)

    def test_build_mouse_event_button_int_1(self) -> None:
        """Test building mouse left-click with button=1."""
        result = build_mouse_event(
            x=100, y=100, button=1, is_down=True, is_move=False
        )
        assert isinstance(result, bytes)
        # First 2 bytes are flags
        flags = struct.unpack("<H", result[:2])[0]
        assert flags & PTRFLAGS_BUTTON1  # Button1 flag set
        assert flags & PTRFLAGS_DOWN  # Down flag set

    def test_build_mouse_event_button_int_2(self) -> None:
        """Test building mouse right-click with button=2."""
        result = build_mouse_event(
            x=100, y=100, button=2, is_down=True, is_move=False
        )
        assert isinstance(result, bytes)
        flags = struct.unpack("<H", result[:2])[0]
        assert flags & PTRFLAGS_BUTTON2  # Button2 flag set
        assert flags & PTRFLAGS_DOWN  # Down flag set

    def test_build_mouse_event_button_int_3(self) -> None:
        """Test building mouse middle-click with button=3."""
        result = build_mouse_event(
            x=100, y=100, button=3, is_down=True, is_move=False
        )
        assert isinstance(result, bytes)
        flags = struct.unpack("<H", result[:2])[0]
        assert flags & PTRFLAGS_BUTTON3  # Button3 flag set
        assert flags & PTRFLAGS_DOWN  # Down flag set

    def test_build_mouse_event_no_down_flag_without_button(self) -> None:
        """Test that PTRFLAGS_DOWN is not set when button=0."""
        result = build_mouse_event(
            x=100, y=100, button=0, is_down=True, is_move=True
        )
        flags = struct.unpack("<H", result[:2])[0]
        assert not (flags & PTRFLAGS_DOWN)  # Down should NOT be set


class TestMoreConstants:
    """Additional tests for constants."""

    def test_control_actions(self) -> None:
        """Test control action constants."""
        assert CTRLACTION_REQUEST_CONTROL == 0x0001
        assert CTRLACTION_GRANTED_CONTROL == 0x0002
        assert CTRLACTION_DETACH == 0x0003
        assert CTRLACTION_COOPERATE == 0x0004

    def test_input_event_types(self) -> None:
        """Test input event type constants."""
        assert INPUT_EVENT_SYNC == 0x0000
        assert INPUT_EVENT_SCANCODE == 0x0004
        assert INPUT_EVENT_UNICODE == 0x0005
        assert INPUT_EVENT_MOUSE == 0x8001

    def test_update_types(self) -> None:
        """Test update type constants."""
        assert UPDATETYPE_ORDERS == 0x0000
        assert UPDATETYPE_BITMAP == 0x0001

    def test_pdu_types(self) -> None:
        """Test PDU type constants."""
        assert PDUTYPE_DEMANDACTIVEPDU == 0x0001
        assert PDUTYPE_CONFIRMACTIVEPDU == 0x0003

    def test_pdu2_types(self) -> None:
        """Test PDU2 type constants."""
        assert PDUTYPE2_UPDATE == 0x02
        assert PDUTYPE2_INPUT == 0x1C

    def test_keyboard_flags(self) -> None:
        """Test keyboard flag constants."""
        assert KBDFLAGS_EXTENDED == 0x0100
        assert KBDFLAGS_DOWN == 0x4000
        assert KBDFLAGS_RELEASE == 0x8000

    def test_security_flags(self) -> None:
        """Test security flag constants."""
        assert SEC_EXCHANGE_PKT == 0x0001
        assert SEC_ENCRYPT == 0x0008
        assert SEC_INFO_PKT == 0x0040
        assert SEC_LICENSE_PKT == 0x0080
