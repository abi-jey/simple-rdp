"""Tests for RDP PDU layer module."""

import struct

import pytest

from simple_rdp.pdu import (
    CTRLACTION_COOPERATE,
    CTRLACTION_DETACH,
    CTRLACTION_GRANTED_CONTROL,
    CTRLACTION_REQUEST_CONTROL,
    INFO_DISABLECTRLALTDEL,
    INFO_LOGONNOTIFY,
    INFO_MOUSE,
    INFO_UNICODE,
    INPUT_EVENT_MOUSE,
    INPUT_EVENT_SCANCODE,
    INPUT_EVENT_SYNC,
    INPUT_EVENT_UNICODE,
    KBDFLAGS_DOWN,
    KBDFLAGS_EXTENDED,
    KBDFLAGS_RELEASE,
    PDUTYPE2_CONTROL,
    PDUTYPE2_INPUT,
    PDUTYPE2_SYNCHRONIZE,
    PDUTYPE2_UPDATE,
    PDUTYPE_CONFIRMACTIVEPDU,
    PDUTYPE_DATAPDU,
    PDUTYPE_DEMANDACTIVEPDU,
    PERF_DISABLE_CURSOR_SHADOW,
    PERF_DISABLE_FULLWINDOWDRAG,
    PERF_DISABLE_MENUANIMATIONS,
    PERF_DISABLE_THEMING,
    PERF_DISABLE_WALLPAPER,
    PTRFLAGS_BUTTON1,
    PTRFLAGS_BUTTON2,
    PTRFLAGS_BUTTON3,
    PTRFLAGS_DOWN,
    PTRFLAGS_MOVE,
    SEC_ENCRYPT,
    SEC_EXCHANGE_PKT,
    SEC_INFO_PKT,
    SEC_LICENSE_PKT,
    UPDATETYPE_BITMAP,
    UPDATETYPE_ORDERS,
    build_client_info_pdu,
    build_confirm_active_pdu,
    build_control_pdu,
    build_font_list_pdu,
    build_input_event_pdu,
    build_mouse_event,
    build_refresh_rect_pdu,
    build_scancode_event,
    build_security_exchange_pdu,
    build_share_control_header,
    build_share_data_header,
    build_suppress_output_pdu,
    build_synchronize_pdu,
    build_unicode_event,
    parse_bitmap_update,
    parse_demand_active_pdu,
    parse_update_pdu,
)


class TestSecurityHeaderFlags:
    """Tests for security header flag constants."""

    def test_sec_info_pkt_flag(self) -> None:
        """Test SEC_INFO_PKT flag value."""
        assert SEC_INFO_PKT == 0x0040

    def test_flags_are_powers_of_two(self) -> None:
        """Test that flags are powers of two for bitwise OR."""
        from simple_rdp.pdu import (
            SEC_ENCRYPT,
            SEC_EXCHANGE_PKT,
            SEC_LICENSE_PKT,
        )

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
