"""RDP Capabilities implementation.

This module handles capability sets for the RDP capability exchange phase.
"""

import struct
from logging import getLogger

logger = getLogger(__name__)

# Capability set types
CAPSTYPE_GENERAL = 0x0001
CAPSTYPE_BITMAP = 0x0002
CAPSTYPE_ORDER = 0x0003
CAPSTYPE_BITMAPCACHE = 0x0004
CAPSTYPE_CONTROL = 0x0005
CAPSTYPE_ACTIVATION = 0x0007
CAPSTYPE_POINTER = 0x0008
CAPSTYPE_SHARE = 0x0009
CAPSTYPE_COLORCACHE = 0x000A
CAPSTYPE_SOUND = 0x000C
CAPSTYPE_INPUT = 0x000D
CAPSTYPE_FONT = 0x000E
CAPSTYPE_BRUSH = 0x000F
CAPSTYPE_GLYPHCACHE = 0x0010
CAPSTYPE_OFFSCREENCACHE = 0x0011
CAPSTYPE_BITMAPCACHE_HOSTSUPPORT = 0x0012
CAPSTYPE_BITMAPCACHE_REV2 = 0x0013
CAPSTYPE_VIRTUALCHANNEL = 0x0014
CAPSTYPE_DRAWNINEGRIDCACHE = 0x0015
CAPSTYPE_DRAWGDIPLUS = 0x0016
CAPSTYPE_RAIL = 0x0017
CAPSTYPE_WINDOW = 0x0018
CAPSTYPE_COMPDESK = 0x0019
CAPSTYPE_MULTIFRAGMENTUPDATE = 0x001A
CAPSTYPE_LARGE_POINTER = 0x001B
CAPSTYPE_SURFACE_COMMANDS = 0x001C
CAPSTYPE_BITMAP_CODECS = 0x001D
CAPSTYPE_FRAME_ACKNOWLEDGE = 0x001E

# General capability set flags
OSMAJORTYPE_WINDOWS = 0x0001
OSMAJORTYPE_OS2 = 0x0002
OSMAJORTYPE_MACINTOSH = 0x0003
OSMAJORTYPE_UNIX = 0x0004
OSMAJORTYPE_IOS = 0x0005
OSMAJORTYPE_OSX = 0x0006
OSMAJORTYPE_ANDROID = 0x0007

OSMINORTYPE_UNSPECIFIED = 0x0000
OSMINORTYPE_WINDOWS_31X = 0x0001
OSMINORTYPE_WINDOWS_95 = 0x0002
OSMINORTYPE_WINDOWS_NT = 0x0003
OSMINORTYPE_OS2_V21 = 0x0004
OSMINORTYPE_POWER_PC = 0x0005
OSMINORTYPE_MACINTOSH = 0x0006
OSMINORTYPE_NATIVE_XSERVER = 0x0007
OSMINORTYPE_PSEUDO_XSERVER = 0x0008
OSMINORTYPE_WINDOWS_RT = 0x0009

# Extra flags for general capability
FASTPATH_OUTPUT_SUPPORTED = 0x0001
NO_BITMAP_COMPRESSION_HDR = 0x0400
LONG_CREDENTIALS_SUPPORTED = 0x0004
AUTORECONNECT_SUPPORTED = 0x0008
ENC_SALTED_CHECKSUM = 0x0010

# Input capability flags
INPUT_FLAG_SCANCODES = 0x0001
INPUT_FLAG_MOUSEX = 0x0004
INPUT_FLAG_FASTPATH_INPUT = 0x0008
INPUT_FLAG_UNICODE = 0x0010
INPUT_FLAG_FASTPATH_INPUT2 = 0x0020
INPUT_FLAG_UNUSED1 = 0x0040
INPUT_FLAG_MOUSE_HWHEEL = 0x0100


def build_capability_header(cap_type: int, data: bytes) -> bytes:
    """Build capability set header."""
    length = 4 + len(data)  # header (4 bytes) + data
    header = struct.pack("<HH", cap_type, length)
    return header + data


def build_general_capability(
    os_major_type: int = OSMAJORTYPE_UNIX,
    os_minor_type: int = OSMINORTYPE_NATIVE_XSERVER,
    protocol_version: int = 0x0200,
    extra_flags: int = FASTPATH_OUTPUT_SUPPORTED | LONG_CREDENTIALS_SUPPORTED | AUTORECONNECT_SUPPORTED,
    update_capability_flag: int = 0,
    remote_unshare_flag: int = 0,
    compression_level: int = 0,
    refresh_rect_support: int = 1,
    suppress_output_support: int = 1,
) -> bytes:
    """Build General Capability Set."""
    data = bytearray()

    # osMajorType (2 bytes)
    data += struct.pack("<H", os_major_type)

    # osMinorType (2 bytes)
    data += struct.pack("<H", os_minor_type)

    # protocolVersion (2 bytes)
    data += struct.pack("<H", protocol_version)

    # pad2octetsA (2 bytes)
    data += struct.pack("<H", 0)

    # generalCompressionTypes (2 bytes) - must be 0
    data += struct.pack("<H", 0)

    # extraFlags (2 bytes)
    data += struct.pack("<H", extra_flags)

    # updateCapabilityFlag (2 bytes)
    data += struct.pack("<H", update_capability_flag)

    # remoteUnshareFlag (2 bytes)
    data += struct.pack("<H", remote_unshare_flag)

    # generalCompressionLevel (2 bytes)
    data += struct.pack("<H", compression_level)

    # refreshRectSupport (1 byte)
    data += struct.pack("B", refresh_rect_support)

    # suppressOutputSupport (1 byte)
    data += struct.pack("B", suppress_output_support)

    return build_capability_header(CAPSTYPE_GENERAL, bytes(data))


def build_bitmap_capability(
    preferred_bpp: int = 32,
    receive_1bpp: int = 1,
    receive_4bpp: int = 1,
    receive_8bpp: int = 1,
    desktop_width: int = 1920,
    desktop_height: int = 1080,
    desktop_resize: int = 1,
    bitmap_compression: int = 1,
    high_color_flags: int = 0,
    drawing_flags: int = 0x08 | 0x02,  # DRAW_ALLOW_DYNAMIC_COLOR_FIDELITY | DRAW_ALLOW_COLOR_SUBSAMPLING
    multiple_rectangle_support: int = 1,
) -> bytes:
    """Build Bitmap Capability Set."""
    data = bytearray()

    # preferredBitsPerPixel (2 bytes)
    data += struct.pack("<H", preferred_bpp)

    # receive1BitPerPixel (2 bytes)
    data += struct.pack("<H", receive_1bpp)

    # receive4BitsPerPixel (2 bytes)
    data += struct.pack("<H", receive_4bpp)

    # receive8BitsPerPixel (2 bytes)
    data += struct.pack("<H", receive_8bpp)

    # desktopWidth (2 bytes)
    data += struct.pack("<H", desktop_width)

    # desktopHeight (2 bytes)
    data += struct.pack("<H", desktop_height)

    # pad2octets (2 bytes)
    data += struct.pack("<H", 0)

    # desktopResizeFlag (2 bytes)
    data += struct.pack("<H", desktop_resize)

    # bitmapCompressionFlag (2 bytes)
    data += struct.pack("<H", bitmap_compression)

    # highColorFlags (1 byte)
    data += struct.pack("B", high_color_flags)

    # drawingFlags (1 byte)
    data += struct.pack("B", drawing_flags)

    # multipleRectangleSupport (2 bytes)
    data += struct.pack("<H", multiple_rectangle_support)

    # pad2octetsB (2 bytes)
    data += struct.pack("<H", 0)

    return build_capability_header(CAPSTYPE_BITMAP, bytes(data))


def build_order_capability() -> bytes:
    """Build Order Capability Set.

    We disable all drawing order support to force the server to send
    bitmap updates instead, which are easier to process for screenshot
    purposes.
    """
    data = bytearray()

    # terminalDescriptor (16 bytes)
    data += bytes(16)

    # pad4octetsA (4 bytes)
    data += struct.pack("<I", 0)

    # desktopSaveXGranularity (2 bytes)
    data += struct.pack("<H", 1)

    # desktopSaveYGranularity (2 bytes)
    data += struct.pack("<H", 20)

    # pad2octetsA (2 bytes)
    data += struct.pack("<H", 0)

    # maximumOrderLevel (2 bytes) - ORD_LEVEL_1_ORDERS
    data += struct.pack("<H", 1)

    # numberFonts (2 bytes)
    data += struct.pack("<H", 0)

    # orderFlags (2 bytes)
    # NEGOTIATEORDERSUPPORT | ZEROBOUNDSDELTASSUPPORT | COLORINDEXSUPPORT
    # We need these flags but will not support any actual orders
    data += struct.pack("<H", 0x0002 | 0x0008 | 0x0020)

    # orderSupport (32 bytes) - bitmap of supported orders
    # Set ALL to 0 to disable order support and force bitmap updates
    order_support = bytearray(32)
    data += bytes(order_support)

    # textFlags (2 bytes)
    data += struct.pack("<H", 0)

    # orderSupportExFlags (2 bytes)
    data += struct.pack("<H", 0)

    # pad4octetsB (4 bytes)
    data += struct.pack("<I", 0)

    # desktopSaveSize (4 bytes)
    data += struct.pack("<I", 480 * 480)

    # pad2octetsC (2 bytes)
    data += struct.pack("<H", 0)

    # pad2octetsD (2 bytes)
    data += struct.pack("<H", 0)

    # textANSICodePage (2 bytes)
    data += struct.pack("<H", 0)

    # pad2octetsE (2 bytes)
    data += struct.pack("<H", 0)

    return build_capability_header(CAPSTYPE_ORDER, bytes(data))


def build_bitmap_cache_capability() -> bytes:
    """Build Bitmap Cache Capability Set (Rev 1)."""
    data = bytearray()

    # pad1 (4 bytes)
    data += struct.pack("<I", 0)

    # pad2 (4 bytes)
    data += struct.pack("<I", 0)

    # pad3 (4 bytes)
    data += struct.pack("<I", 0)

    # pad4 (4 bytes)
    data += struct.pack("<I", 0)

    # pad5 (4 bytes)
    data += struct.pack("<I", 0)

    # pad6 (4 bytes)
    data += struct.pack("<I", 0)

    # Cache0Entries (2 bytes)
    data += struct.pack("<H", 200)

    # Cache0MaximumCellSize (2 bytes)
    data += struct.pack("<H", 256)

    # Cache1Entries (2 bytes)
    data += struct.pack("<H", 600)

    # Cache1MaximumCellSize (2 bytes)
    data += struct.pack("<H", 1024)

    # Cache2Entries (2 bytes)
    data += struct.pack("<H", 1000)

    # Cache2MaximumCellSize (2 bytes)
    data += struct.pack("<H", 4096)

    return build_capability_header(CAPSTYPE_BITMAPCACHE, bytes(data))


def build_bitmap_cache_rev2_capability() -> bytes:
    """Build Bitmap Cache Capability Set Rev 2."""
    data = bytearray()

    # cacheFlags (2 bytes)
    data += struct.pack("<H", 0x0003)  # PERSISTENT_KEYS_EXPECTED_FLAG | ALLOW_CACHE_WAITING_LIST_FLAG

    # pad2 (1 byte)
    data += struct.pack("B", 0)

    # numCellCaches (1 byte)
    data += struct.pack("B", 3)

    # bitmapCache0CellInfo (4 bytes)
    data += struct.pack("<I", 120 | (1 << 31))  # 120 entries, persistent

    # bitmapCache1CellInfo (4 bytes)
    data += struct.pack("<I", 120 | (1 << 31))

    # bitmapCache2CellInfo (4 bytes)
    data += struct.pack("<I", 2048 | (1 << 31))

    # bitmapCache3CellInfo (4 bytes)
    data += struct.pack("<I", 0)

    # bitmapCache4CellInfo (4 bytes)
    data += struct.pack("<I", 0)

    # pad3 (12 bytes)
    data += bytes(12)

    return build_capability_header(CAPSTYPE_BITMAPCACHE_REV2, bytes(data))


def build_pointer_capability(color_pointer_cache_size: int = 25, pointer_cache_size: int = 25) -> bytes:
    """Build Pointer Capability Set."""
    data = bytearray()

    # colorPointerFlag (2 bytes)
    data += struct.pack("<H", 1)

    # colorPointerCacheSize (2 bytes)
    data += struct.pack("<H", color_pointer_cache_size)

    # pointerCacheSize (2 bytes)
    data += struct.pack("<H", pointer_cache_size)

    return build_capability_header(CAPSTYPE_POINTER, bytes(data))


def build_input_capability(
    input_flags: int = INPUT_FLAG_SCANCODES | INPUT_FLAG_MOUSEX | INPUT_FLAG_UNICODE | INPUT_FLAG_FASTPATH_INPUT2,
    keyboard_layout: int = 0x409,
    keyboard_type: int = 4,
    keyboard_subtype: int = 0,
    keyboard_function_keys: int = 12,
) -> bytes:
    """Build Input Capability Set."""
    data = bytearray()

    # inputFlags (2 bytes)
    data += struct.pack("<H", input_flags)

    # pad2octetsA (2 bytes)
    data += struct.pack("<H", 0)

    # keyboardLayout (4 bytes)
    data += struct.pack("<I", keyboard_layout)

    # keyboardType (4 bytes)
    data += struct.pack("<I", keyboard_type)

    # keyboardSubType (4 bytes)
    data += struct.pack("<I", keyboard_subtype)

    # keyboardFunctionKey (4 bytes)
    data += struct.pack("<I", keyboard_function_keys)

    # imeFileName (64 bytes)
    data += bytes(64)

    return build_capability_header(CAPSTYPE_INPUT, bytes(data))


def build_brush_capability() -> bytes:
    """Build Brush Capability Set."""
    data = bytearray()

    # brushSupportLevel (4 bytes) - BRUSH_COLOR_FULL = 0x0002
    data += struct.pack("<I", 0x0002)

    return build_capability_header(CAPSTYPE_BRUSH, bytes(data))


def build_glyph_cache_capability() -> bytes:
    """Build Glyph Cache Capability Set."""
    data = bytearray()

    # GlyphCache (40 bytes) - 10 cache definitions, each 4 bytes
    for _ in range(10):
        # CacheEntries (2 bytes)
        data += struct.pack("<H", 254)
        # CacheMaximumCellSize (2 bytes)
        data += struct.pack("<H", 256)

    # FragCache (4 bytes)
    data += struct.pack("<HH", 256, 256)

    # GlyphSupportLevel (2 bytes) - GLYPH_SUPPORT_FULL = 0x0002
    data += struct.pack("<H", 0x0002)

    # pad2octets (2 bytes)
    data += struct.pack("<H", 0)

    return build_capability_header(CAPSTYPE_GLYPHCACHE, bytes(data))


def build_offscreen_cache_capability() -> bytes:
    """Build Offscreen Bitmap Cache Capability Set."""
    data = bytearray()

    # offscreenSupportLevel (4 bytes)
    data += struct.pack("<I", 1)  # TRUE

    # offscreenCacheSize (2 bytes) - in KB
    data += struct.pack("<H", 7680)

    # offscreenCacheEntries (2 bytes)
    data += struct.pack("<H", 2000)

    return build_capability_header(CAPSTYPE_OFFSCREENCACHE, bytes(data))


def build_virtual_channel_capability(flags: int = 0, chunk_size: int = 1600) -> bytes:
    """Build Virtual Channel Capability Set."""
    data = bytearray()

    # flags (4 bytes)
    data += struct.pack("<I", flags)

    # VCChunkSize (4 bytes) - optional
    data += struct.pack("<I", chunk_size)

    return build_capability_header(CAPSTYPE_VIRTUALCHANNEL, bytes(data))


def build_sound_capability() -> bytes:
    """Build Sound Capability Set."""
    data = bytearray()

    # soundFlags (2 bytes) - SOUND_BEEPS_FLAG = 0x0001
    data += struct.pack("<H", 0x0001)

    # pad2octetsA (2 bytes)
    data += struct.pack("<H", 0)

    return build_capability_header(CAPSTYPE_SOUND, bytes(data))


def build_control_capability() -> bytes:
    """Build Control Capability Set."""
    data = bytearray()

    # controlFlags (2 bytes)
    data += struct.pack("<H", 0)

    # remoteDetachFlag (2 bytes)
    data += struct.pack("<H", 0)

    # controlInterest (2 bytes)
    data += struct.pack("<H", 2)

    # detachInterest (2 bytes)
    data += struct.pack("<H", 2)

    return build_capability_header(CAPSTYPE_CONTROL, bytes(data))


def build_activation_capability() -> bytes:
    """Build Window Activation Capability Set."""
    data = bytearray()

    # helpKeyFlag (2 bytes)
    data += struct.pack("<H", 0)

    # helpKeyIndexFlag (2 bytes)
    data += struct.pack("<H", 0)

    # helpExtendedKeyFlag (2 bytes)
    data += struct.pack("<H", 0)

    # windowManagerKeyFlag (2 bytes)
    data += struct.pack("<H", 0)

    return build_capability_header(CAPSTYPE_ACTIVATION, bytes(data))


def build_share_capability() -> bytes:
    """Build Share Capability Set."""
    data = bytearray()

    # nodeId (2 bytes)
    data += struct.pack("<H", 0)

    # pad2octets (2 bytes)
    data += struct.pack("<H", 0)

    return build_capability_header(CAPSTYPE_SHARE, bytes(data))


def build_font_capability() -> bytes:
    """Build Font Capability Set."""
    data = bytearray()

    # fontSupportFlags (2 bytes) - FONTSUPPORT_FONTLIST = 0x0001
    data += struct.pack("<H", 0x0001)

    # pad2octets (2 bytes)
    data += struct.pack("<H", 0)

    return build_capability_header(CAPSTYPE_FONT, bytes(data))


def build_color_cache_capability() -> bytes:
    """Build Color Cache Capability Set."""
    data = bytearray()

    # colorTableCacheSize (2 bytes)
    data += struct.pack("<H", 6)

    # pad2octets (2 bytes)
    data += struct.pack("<H", 0)

    return build_capability_header(CAPSTYPE_COLORCACHE, bytes(data))


def build_multifragment_update_capability(max_request_size: int = 65535) -> bytes:
    """Build Multifragment Update Capability Set."""
    data = bytearray()

    # MaxRequestSize (4 bytes)
    data += struct.pack("<I", max_request_size)

    return build_capability_header(CAPSTYPE_MULTIFRAGMENTUPDATE, bytes(data))


def build_large_pointer_capability() -> bytes:
    """Build Large Pointer Capability Set."""
    data = bytearray()

    # largePointerSupportFlags (2 bytes)
    data += struct.pack("<H", 0x0001)  # LARGE_POINTER_FLAG_96x96

    return build_capability_header(CAPSTYPE_LARGE_POINTER, bytes(data))


def build_surface_commands_capability() -> bytes:
    """Build Surface Commands Capability Set."""
    data = bytearray()

    # cmdFlags (4 bytes)
    data += struct.pack("<I", 0x00000052)  # SURFCMDS_SETSURFACEBITS | SURFCMDS_FRAMEMARKER | SURFCMDS_STREAMSURF

    # reserved (4 bytes)
    data += struct.pack("<I", 0)

    return build_capability_header(CAPSTYPE_SURFACE_COMMANDS, bytes(data))


def build_frame_acknowledge_capability(max_unacknowledged_frames: int = 2) -> bytes:
    """Build Frame Acknowledge Capability Set."""
    data = bytearray()

    # maxUnacknowledgedFrameCount (4 bytes)
    data += struct.pack("<I", max_unacknowledged_frames)

    return build_capability_header(CAPSTYPE_FRAME_ACKNOWLEDGE, bytes(data))


def build_client_capabilities(width: int = 1920, height: int = 1080, bpp: int = 32) -> bytes:
    """Build combined client capability sets for Confirm Active PDU.

    Returns the capabilities data including the count and padding.
    """
    caps = []

    caps.append(build_general_capability())
    caps.append(build_bitmap_capability(preferred_bpp=bpp, desktop_width=width, desktop_height=height))
    caps.append(build_order_capability())
    caps.append(build_bitmap_cache_rev2_capability())
    caps.append(build_pointer_capability())
    caps.append(build_input_capability())
    caps.append(build_brush_capability())
    caps.append(build_glyph_cache_capability())
    caps.append(build_offscreen_cache_capability())
    caps.append(build_virtual_channel_capability())
    caps.append(build_sound_capability())
    caps.append(build_control_capability())
    caps.append(build_activation_capability())
    caps.append(build_share_capability())
    caps.append(build_font_capability())
    caps.append(build_color_cache_capability())
    caps.append(build_multifragment_update_capability())
    caps.append(build_large_pointer_capability())
    caps.append(build_surface_commands_capability())
    caps.append(build_frame_acknowledge_capability())

    # Build combined data
    data = bytearray()

    # Number of capability sets (2 bytes)
    data += struct.pack("<H", len(caps))

    # Padding (2 bytes)
    data += struct.pack("<H", 0)

    # Capability sets
    for cap in caps:
        data += cap

    return bytes(data)
