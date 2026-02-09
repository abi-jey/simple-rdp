"""RDP PDU layer implementation.

This module implements RDP-specific PDUs for the connection sequence
and data exchange phases.
"""

import struct
from logging import getLogger
from typing import Any

logger = getLogger(__name__)

# Security header flags
SEC_EXCHANGE_PKT = 0x0001
SEC_TRANSPORT_REQ = 0x0002
SEC_TRANSPORT_RSP = 0x0004
SEC_ENCRYPT = 0x0008
SEC_RESET_SEQNO = 0x0010
SEC_IGNORE_SEQNO = 0x0020
SEC_INFO_PKT = 0x0040
SEC_LICENSE_PKT = 0x0080
SEC_LICENSE_ENCRYPT_CS = 0x0200
SEC_LICENSE_ENCRYPT_SC = 0x0200
SEC_REDIRECTION_PKT = 0x0400
SEC_SECURE_CHECKSUM = 0x0800
SEC_AUTODETECT_REQ = 0x1000
SEC_AUTODETECT_RSP = 0x2000
SEC_HEARTBEAT = 0x4000
SEC_FLAGSHI_VALID = 0x8000

# Share control PDU types
PDUTYPE_DEMANDACTIVEPDU = 0x0001
PDUTYPE_CONFIRMACTIVEPDU = 0x0003
PDUTYPE_DEACTIVATEALLPDU = 0x0006
PDUTYPE_DATAPDU = 0x0007
PDUTYPE_SERVER_REDIR_PKT = 0x000A

# Share data PDU types
PDUTYPE2_UPDATE = 0x02
PDUTYPE2_CONTROL = 0x14
PDUTYPE2_POINTER = 0x1B
PDUTYPE2_INPUT = 0x1C
PDUTYPE2_SYNCHRONIZE = 0x1F
PDUTYPE2_REFRESH_RECT = 0x21
PDUTYPE2_PLAY_SOUND = 0x22
PDUTYPE2_SUPPRESS_OUTPUT = 0x23
PDUTYPE2_SHUTDOWN_REQUEST = 0x24
PDUTYPE2_SHUTDOWN_DENIED = 0x25
PDUTYPE2_SAVE_SESSION_INFO = 0x26
PDUTYPE2_FONTLIST = 0x27
PDUTYPE2_FONTMAP = 0x28
PDUTYPE2_SET_KEYBOARD_INDICATORS = 0x29
PDUTYPE2_BITMAPCACHE_PERSISTENT_LIST = 0x2B
PDUTYPE2_BITMAPCACHE_ERROR_PDU = 0x2C
PDUTYPE2_SET_KEYBOARD_IME_STATUS = 0x2D
PDUTYPE2_OFFSCRCACHE_ERROR_PDU = 0x2E
PDUTYPE2_SET_ERROR_INFO_PDU = 0x2F
PDUTYPE2_DRAWNINEGRID_ERROR_PDU = 0x30
PDUTYPE2_DRAWGDIPLUS_ERROR_PDU = 0x31
PDUTYPE2_ARC_STATUS_PDU = 0x32
PDUTYPE2_STATUS_INFO_PDU = 0x36
PDUTYPE2_MONITOR_LAYOUT_PDU = 0x37

# Control actions
CTRLACTION_REQUEST_CONTROL = 0x0001
CTRLACTION_GRANTED_CONTROL = 0x0002
CTRLACTION_DETACH = 0x0003
CTRLACTION_COOPERATE = 0x0004

# Input event types
INPUT_EVENT_SYNC = 0x0000
INPUT_EVENT_UNUSED = 0x0002
INPUT_EVENT_SCANCODE = 0x0004
INPUT_EVENT_UNICODE = 0x0005
INPUT_EVENT_MOUSE = 0x8001
INPUT_EVENT_MOUSEX = 0x8002

# Mouse event flags
PTRFLAGS_HWHEEL = 0x0400
PTRFLAGS_WHEEL = 0x0200
PTRFLAGS_WHEEL_NEGATIVE = 0x0100
PTRFLAGS_MOVE = 0x0800
PTRFLAGS_DOWN = 0x8000
PTRFLAGS_BUTTON1 = 0x1000  # Left button
PTRFLAGS_BUTTON2 = 0x2000  # Right button
PTRFLAGS_BUTTON3 = 0x4000  # Middle button

# Keyboard event flags
KBDFLAGS_EXTENDED = 0x0100
KBDFLAGS_EXTENDED1 = 0x0200
KBDFLAGS_DOWN = 0x4000
KBDFLAGS_RELEASE = 0x8000

# Update types
UPDATETYPE_ORDERS = 0x0000
UPDATETYPE_BITMAP = 0x0001
UPDATETYPE_PALETTE = 0x0002
UPDATETYPE_SYNCHRONIZE = 0x0003

# Info packet flags
INFO_MOUSE = 0x00000001
INFO_DISABLECTRLALTDEL = 0x00000002
INFO_AUTOLOGON = 0x00000008
INFO_UNICODE = 0x00000010
INFO_MAXIMIZESHELL = 0x00000020
INFO_LOGONNOTIFY = 0x00000040
INFO_COMPRESSION = 0x00000080
INFO_ENABLEWINDOWSKEY = 0x00000100
INFO_REMOTECONSOLEAUDIO = 0x00002000
INFO_FORCE_ENCRYPTED_CS_PDU = 0x00004000
INFO_RAIL = 0x00008000
INFO_LOGONERRORS = 0x00010000
INFO_MOUSE_HAS_WHEEL = 0x00020000
INFO_PASSWORD_IS_SC_PIN = 0x00040000
INFO_NOAUDIOPLAYBACK = 0x00080000
INFO_USING_SAVED_CREDS = 0x00100000
INFO_AUDIOCAPTURE = 0x00200000
INFO_VIDEO_DISABLE = 0x00400000
INFO_HIDEF_RAIL_SUPPORTED = 0x02000000

# Performance flags
PERF_DISABLE_WALLPAPER = 0x00000001
PERF_DISABLE_FULLWINDOWDRAG = 0x00000002
PERF_DISABLE_MENUANIMATIONS = 0x00000004
PERF_DISABLE_THEMING = 0x00000008
PERF_DISABLE_CURSOR_SHADOW = 0x00000020
PERF_DISABLE_CURSORSETTINGS = 0x00000040
PERF_ENABLE_FONT_SMOOTHING = 0x00000080
PERF_ENABLE_DESKTOP_COMPOSITION = 0x00000100


def build_client_info_pdu(
    domain: str = "",
    username: str = "",
    password: str = "",
    shell: str = "",
    work_dir: str = "",
    flags: int = INFO_MOUSE | INFO_UNICODE | INFO_LOGONNOTIFY | INFO_DISABLECTRLALTDEL,
    performance_flags: int = PERF_DISABLE_WALLPAPER,
) -> bytes:
    """Build Client Info PDU (TS_INFO_PACKET).

    This is sent after the channel join sequence to provide user credentials
    and session configuration.
    """
    data = bytearray()

    # Code page (4 bytes) - not used with INFO_UNICODE
    data += struct.pack("<I", 0)

    # Flags (4 bytes)
    data += struct.pack("<I", flags)

    # Encode strings as UTF-16LE (without null terminator for length fields)
    domain_bytes = domain.encode("utf-16-le")
    username_bytes = username.encode("utf-16-le")
    password_bytes = password.encode("utf-16-le")
    shell_bytes = shell.encode("utf-16-le")
    work_dir_bytes = work_dir.encode("utf-16-le")

    # String lengths (in bytes, excluding null terminator)
    data += struct.pack("<H", len(domain_bytes))
    data += struct.pack("<H", len(username_bytes))
    data += struct.pack("<H", len(password_bytes))
    data += struct.pack("<H", len(shell_bytes))
    data += struct.pack("<H", len(work_dir_bytes))

    # Strings with null terminators
    data += domain_bytes + b"\x00\x00"
    data += username_bytes + b"\x00\x00"
    data += password_bytes + b"\x00\x00"
    data += shell_bytes + b"\x00\x00"
    data += work_dir_bytes + b"\x00\x00"

    # Extended Info (TS_EXTENDED_INFO_PACKET)
    # Client address family (2 bytes) - AF_INET = 0x0002
    data += struct.pack("<H", 0x0002)

    # Client address length (2 bytes)
    client_address = b"\x00\x00"  # Empty address
    data += struct.pack("<H", len(client_address))
    data += client_address

    # Client directory length (2 bytes)
    client_dir = b"\x00\x00"
    data += struct.pack("<H", len(client_dir))
    data += client_dir

    # Time zone info (172 bytes) - simplified, all zeros
    data += bytes(172)

    # Client session ID (4 bytes)
    data += struct.pack("<I", 0)

    # Performance flags (4 bytes)
    data += struct.pack("<I", performance_flags)

    # Auto reconnect cookie length (2 bytes)
    data += struct.pack("<H", 0)

    return bytes(data)


def build_security_exchange_pdu(encrypted_client_random: bytes) -> bytes:
    """Build Security Exchange PDU.

    This is only used with Standard RDP Security (not TLS/NLA).
    """
    data = bytearray()

    # Security header flags (4 bytes)
    data += struct.pack("<I", SEC_EXCHANGE_PKT)

    # Length of encrypted client random (4 bytes)
    data += struct.pack("<I", len(encrypted_client_random) + 8)

    # Encrypted client random
    data += encrypted_client_random

    # Padding (8 bytes)
    data += bytes(8)

    return bytes(data)


def build_share_control_header(pdu_type: int, pdu_source: int, share_id: int = 0) -> bytes:
    """Build Share Control Header."""
    data = bytearray()

    # Total length placeholder (2 bytes) - will be filled by caller
    data += struct.pack("<H", 0)

    # PDU type (2 bytes)
    data += struct.pack("<H", pdu_type | 0x0010)  # Version 1

    # PDU source (2 bytes)
    data += struct.pack("<H", pdu_source)

    return bytes(data)


def build_share_data_header(
    share_id: int,
    pdu_source: int,
    pdu_type2: int,
    compressed_type: int = 0,
    compressed_length: int = 0,
) -> bytes:
    """Build Share Data Header."""
    data = bytearray()

    # Share ID (4 bytes)
    data += struct.pack("<I", share_id)

    # Padding (1 byte)
    data += bytes([0])

    # Stream ID (1 byte) - STREAM_MED = 0x01
    data += bytes([0x01])

    # Uncompressed length placeholder (2 bytes)
    data += struct.pack("<H", 0)

    # PDU type 2 (1 byte)
    data += bytes([pdu_type2])

    # Compressed type (1 byte)
    data += bytes([compressed_type])

    # Compressed length (2 bytes)
    data += struct.pack("<H", compressed_length)

    return bytes(data)


def build_synchronize_pdu(target_user: int) -> bytes:
    """Build Synchronize PDU."""
    data = bytearray()

    # Message type (2 bytes) - SYNCMSGTYPE_SYNC = 0x0001
    data += struct.pack("<H", 0x0001)

    # Target user (2 bytes)
    data += struct.pack("<H", target_user)

    return bytes(data)


def build_control_pdu(action: int, grant_id: int = 0, control_id: int = 0) -> bytes:
    """Build Control PDU."""
    data = bytearray()

    # Action (2 bytes)
    data += struct.pack("<H", action)

    # Grant ID (2 bytes)
    data += struct.pack("<H", grant_id)

    # Control ID (4 bytes)
    data += struct.pack("<I", control_id)

    return bytes(data)


def build_font_list_pdu() -> bytes:
    """Build Font List PDU."""
    data = bytearray()

    # Number of fonts (2 bytes)
    data += struct.pack("<H", 0)

    # Total number of fonts (2 bytes)
    data += struct.pack("<H", 0)

    # List flags (2 bytes) - FONTLIST_FIRST | FONTLIST_LAST = 0x0003
    data += struct.pack("<H", 0x0003)

    # Entry size (2 bytes)
    data += struct.pack("<H", 0x0032)

    return bytes(data)


def build_input_event_pdu(events: list[tuple[int, int, bytes]]) -> bytes:
    """Build Input Event PDU.

    Args:
        events: List of (event_time, event_type, event_data) tuples

    """
    data = bytearray()

    # Number of events (2 bytes)
    data += struct.pack("<H", len(events))

    # Padding (2 bytes)
    data += struct.pack("<H", 0)

    # Events
    for event_time, event_type, event_data in events:
        # Event time (4 bytes)
        data += struct.pack("<I", event_time)
        # Event type (2 bytes)
        data += struct.pack("<H", event_type)
        # Event data
        data += event_data

    return bytes(data)


def build_scancode_event(
    scan_code: int,
    is_release: bool = False,
    is_extended: bool = False,
) -> bytes:
    """Build keyboard scancode event data."""
    flags = 0
    if is_release:
        flags |= KBDFLAGS_RELEASE
    if is_extended:
        flags |= KBDFLAGS_EXTENDED

    data = bytearray()
    # Key flags (2 bytes)
    data += struct.pack("<H", flags)
    # Key code (2 bytes)
    data += struct.pack("<H", scan_code)
    # Padding (2 bytes)
    data += struct.pack("<H", 0)

    return bytes(data)


def build_unicode_event(unicode_code: int, is_release: bool = False) -> bytes:
    """Build keyboard unicode event data."""
    flags = 0
    if is_release:
        flags |= KBDFLAGS_RELEASE

    data = bytearray()
    # Key flags (2 bytes)
    data += struct.pack("<H", flags)
    # Unicode code (2 bytes)
    data += struct.pack("<H", unicode_code)
    # Padding (2 bytes)
    data += struct.pack("<H", 0)

    return bytes(data)


def build_mouse_event(
    x: int,
    y: int,
    button: int = 0,  # 0=none, 1=left, 2=right, 3=middle
    is_down: bool = False,
    is_move: bool = True,
    wheel_delta: int = 0,  # Positive=up, negative=down
) -> bytes:
    """Build mouse event data."""
    flags = 0

    if is_move:
        flags |= PTRFLAGS_MOVE

    if button == 1:
        flags |= PTRFLAGS_BUTTON1
    elif button == 2:
        flags |= PTRFLAGS_BUTTON2
    elif button == 3:
        flags |= PTRFLAGS_BUTTON3

    if is_down and button > 0:
        flags |= PTRFLAGS_DOWN

    # Handle mouse wheel
    if wheel_delta != 0:
        flags |= PTRFLAGS_WHEEL
        if wheel_delta < 0:
            flags |= PTRFLAGS_WHEEL_NEGATIVE
            wheel_delta = -wheel_delta
        # Wheel delta is in the lower 9 bits (0-511), typically 120 per notch
        flags |= wheel_delta & 0x01FF

    data = bytearray()
    # Pointer flags (2 bytes)
    data += struct.pack("<H", flags)
    # X position (2 bytes)
    data += struct.pack("<H", x & 0xFFFF)
    # Y position (2 bytes)
    data += struct.pack("<H", y & 0xFFFF)

    return bytes(data)


# Fast-path input event codes
FASTPATH_INPUT_EVENT_SCANCODE = 0
FASTPATH_INPUT_EVENT_MOUSE = 1
FASTPATH_INPUT_EVENT_MOUSEX = 2
FASTPATH_INPUT_EVENT_SYNC = 3
FASTPATH_INPUT_EVENT_UNICODE = 4
FASTPATH_INPUT_EVENT_MOUSEREL = 5


def build_fast_path_mouse_event(
    x: int,
    y: int,
    button: int = 0,  # 0=none, 1=left, 2=right, 3=middle
    is_down: bool = False,
    is_move: bool = True,
    wheel_delta: int = 0,  # Positive=up, negative=down
) -> bytes:
    """Build a fast-path mouse event (TS_FP_POINTER_EVENT).

    Returns 7 bytes: eventHeader(1) + pointerFlags(2) + xPos(2) + yPos(2)
    """
    # Build pointer flags (same as slow-path)
    flags = 0

    if is_move:
        flags |= PTRFLAGS_MOVE

    if button == 1:
        flags |= PTRFLAGS_BUTTON1
    elif button == 2:
        flags |= PTRFLAGS_BUTTON2
    elif button == 3:
        flags |= PTRFLAGS_BUTTON3

    if is_down and button > 0:
        flags |= PTRFLAGS_DOWN

    # Handle mouse wheel
    if wheel_delta != 0:
        flags |= PTRFLAGS_WHEEL
        if wheel_delta < 0:
            flags |= PTRFLAGS_WHEEL_NEGATIVE
            wheel_delta = -wheel_delta
        # Wheel delta is in the lower 9 bits (0-511), typically 120 per notch
        flags |= wheel_delta & 0x01FF

    # eventHeader: eventCode (3 bits) in high bits, eventFlags (5 bits) in low bits
    # For mouse: eventCode = 1 (FASTPATH_INPUT_EVENT_MOUSE), eventFlags = 0
    # Format: eventCode << 5 | eventFlags
    event_header = (FASTPATH_INPUT_EVENT_MOUSE << 5) | 0

    data = bytearray()
    data += bytes([event_header])
    data += struct.pack("<H", flags)
    data += struct.pack("<H", x & 0xFFFF)
    data += struct.pack("<H", y & 0xFFFF)

    return bytes(data)


def build_fast_path_input_pdu(events: list[bytes]) -> bytes:
    """Build a fast-path input PDU containing multiple events.

    Args:
        events: List of fast-path event data (from build_fast_path_mouse_event, etc.)

    Returns:
        Complete fast-path input PDU ready to send.
    """
    num_events = len(events)
    if num_events == 0:
        return b""

    # Concatenate all events
    events_data = b"".join(events)

    # Build header
    # fpInputHeader: action (2 bits) | numEvents (4 bits) | flags (2 bits)
    # action = 0 (FASTPATH_INPUT_ACTION_FASTPATH)
    # flags = 0 (no encryption for Enhanced RDP Security / TLS)
    # numEvents = number of events if <= 15, else 0 (use separate numEvents field)

    if num_events <= 15:
        # Pack numEvents into header
        fp_input_header = (num_events << 2) | 0  # action=0, flags=0
        header_data = bytes([fp_input_header])
        extra_num_events = b""
    else:
        # numEvents = 0 in header, use separate field
        fp_input_header = 0
        header_data = bytes([fp_input_header])
        extra_num_events = bytes([num_events])

    # Calculate total length: header + length field(s) + numEvents(optional) + events
    # We need to determine length field size first
    content = extra_num_events + events_data
    # Total = fpInputHeader(1) + length(1 or 2) + content
    total_len_with_1byte = 1 + 1 + len(content)
    total_len_with_2byte = 1 + 2 + len(content)

    if total_len_with_1byte <= 127:
        # Single byte length
        length_data = bytes([total_len_with_1byte])
    else:
        # Two byte length (big-endian, high bit set on length1)
        total_len = total_len_with_2byte
        length1 = 0x80 | ((total_len >> 8) & 0x7F)
        length2 = total_len & 0xFF
        length_data = bytes([length1, length2])

    return header_data + length_data + content


def build_confirm_active_pdu(
    share_id: int,
    originator_id: int,
    source_descriptor: bytes,
    capabilities: bytes,
) -> bytes:
    """Build Confirm Active PDU."""
    data = bytearray()

    # Share ID (4 bytes)
    data += struct.pack("<I", share_id)

    # Originator ID (2 bytes)
    data += struct.pack("<H", originator_id)

    # Source descriptor length (2 bytes)
    data += struct.pack("<H", len(source_descriptor))

    # Combined capabilities length (2 bytes)
    data += struct.pack("<H", len(capabilities))

    # Source descriptor
    data += source_descriptor

    # Number of capability sets (2 bytes) - encoded in capabilities
    # Padding (2 bytes)
    # Capability sets

    data += capabilities

    return bytes(data)


def parse_demand_active_pdu(data: bytes) -> dict[str, Any]:
    """Parse Demand Active PDU from server."""
    result: dict[str, Any] = {
        "share_id": 0,
        "source_descriptor": b"",
        "capabilities": [],
    }

    offset = 0

    # Share ID (4 bytes)
    result["share_id"] = struct.unpack_from("<I", data, offset)[0]
    offset += 4

    # Length of source descriptor (2 bytes)
    source_len = struct.unpack_from("<H", data, offset)[0]
    offset += 2

    # Combined capabilities length (2 bytes)
    _caps_len = struct.unpack_from("<H", data, offset)[0]
    offset += 2

    # Source descriptor
    result["source_descriptor"] = data[offset : offset + source_len]
    offset += source_len

    # Number of capability sets (2 bytes)
    num_caps = struct.unpack_from("<H", data, offset)[0]
    offset += 2

    # Padding (2 bytes)
    offset += 2

    # Parse capability sets
    for _ in range(num_caps):
        if offset + 4 > len(data):
            break

        cap_type = struct.unpack_from("<H", data, offset)[0]
        cap_len = struct.unpack_from("<H", data, offset + 2)[0]

        if cap_len < 4:
            break

        cap_data = data[offset : offset + cap_len]
        result["capabilities"].append({"type": cap_type, "data": cap_data})
        offset += cap_len

    return result


def parse_update_pdu(data: bytes) -> dict[str, Any]:
    """Parse Update PDU from server."""
    result: dict[str, Any] = {"update_type": 0, "data": b""}

    if len(data) < 2:
        return result

    result["update_type"] = struct.unpack_from("<H", data, 0)[0]
    result["data"] = data[2:]

    return result


def parse_bitmap_update(data: bytes) -> list[dict[str, Any]]:
    """Parse Bitmap Update data."""
    bitmaps: list[dict[str, Any]] = []

    if len(data) < 2:
        return bitmaps

    offset = 0
    num_rects = struct.unpack_from("<H", data, offset)[0]
    offset += 2

    logger.debug(f"Parsing bitmap update: {len(data)} bytes, {num_rects} rectangles")

    for i in range(num_rects):
        if offset + 18 > len(data):
            logger.debug(f"Stopping at rect {i}: not enough data for header (offset={offset}, data_len={len(data)})")
            break

        bitmap = {
            "dest_left": struct.unpack_from("<H", data, offset)[0],
            "dest_top": struct.unpack_from("<H", data, offset + 2)[0],
            "dest_right": struct.unpack_from("<H", data, offset + 4)[0],
            "dest_bottom": struct.unpack_from("<H", data, offset + 6)[0],
            "width": struct.unpack_from("<H", data, offset + 8)[0],
            "height": struct.unpack_from("<H", data, offset + 10)[0],
            "bpp": struct.unpack_from("<H", data, offset + 12)[0],
            "flags": struct.unpack_from("<H", data, offset + 14)[0],
            "length": struct.unpack_from("<H", data, offset + 16)[0],
        }
        offset += 18

        # Validate bitmap data
        if bitmap["bpp"] not in (8, 15, 16, 24, 32):
            logger.debug(f"Rect {i}: Invalid bpp={bitmap['bpp']}, stopping parse (likely corrupt data)")
            break

        if bitmap["width"] == 0 or bitmap["height"] == 0:
            logger.debug(f"Rect {i}: Invalid dimensions {bitmap['width']}x{bitmap['height']}, skipping")
            offset += bitmap["length"]
            continue

        if offset + bitmap["length"] > len(data):
            logger.debug(
                f"Stopping at rect {i}: not enough data for bitmap "
                f"(need {bitmap['length']}, have {len(data) - offset})",
            )
            break

        bitmap["data"] = data[offset : offset + bitmap["length"]]
        offset += bitmap["length"]

        bitmaps.append(bitmap)

    logger.debug(f"Parsed {len(bitmaps)} valid bitmaps")
    return bitmaps


def build_refresh_rect_pdu(rectangles: list[tuple[int, int, int, int]]) -> bytes:
    """Build Refresh Rect PDU to request screen redraw.

    This PDU is sent by the client to request the server to redraw
    one or more rectangles of the session screen area.

    Args:
        rectangles: List of (left, top, right, bottom) tuples defining
                   the areas to refresh.

    Returns:
        The Refresh Rect PDU data (without Share Data Header).

    """
    data = bytearray()

    # numberOfAreas (1 byte)
    data += bytes([len(rectangles)])

    # pad3Octets (3 bytes)
    data += bytes(3)

    # areasToRefresh - array of TS_RECTANGLE16
    for left, top, right, bottom in rectangles:
        data += struct.pack("<H", left)
        data += struct.pack("<H", top)
        data += struct.pack("<H", right)
        data += struct.pack("<H", bottom)

    return bytes(data)


def build_suppress_output_pdu(allow_display_updates: bool, rectangle: tuple[int, int, int, int] | None = None) -> bytes:
    """Build Suppress Output PDU to control display updates.

    This PDU is sent by the client to toggle the sending of
    desktop display updates from the server.

    Args:
        allow_display_updates: If True, the server should send display updates.
                              If False, the server should stop sending updates.
        rectangle: Optional (left, top, right, bottom) tuple defining the
                  desktop rectangle to allow updates for (only used when
                  allow_display_updates is True).

    Returns:
        The Suppress Output PDU data (without Share Data Header).

    """
    data = bytearray()

    # allowDisplayUpdates (1 byte) - 0x00 = suppress, 0x01 = allow
    data += bytes([0x01 if allow_display_updates else 0x00])

    # pad3Octets (3 bytes)
    data += bytes(3)

    # desktopRect (TS_RECTANGLE16) - only if allowDisplayUpdates is TRUE
    if allow_display_updates and rectangle:
        left, top, right, bottom = rectangle
        data += struct.pack("<H", left)
        data += struct.pack("<H", top)
        data += struct.pack("<H", right)
        data += struct.pack("<H", bottom)

    return bytes(data)
