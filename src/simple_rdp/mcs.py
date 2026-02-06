"""MCS (Multipoint Communication Service) layer implementation.

This module implements T.125 MCS PDUs for the RDP connection sequence.
"""

from logging import getLogger
from typing import Any

logger = getLogger(__name__)

# MCS PDU types (T.125)
MCS_TYPE_CONNECT_INITIAL = 0x65  # APPLICATION 101
MCS_TYPE_CONNECT_RESPONSE = 0x66  # APPLICATION 102
MCS_TYPE_ERECT_DOMAIN_REQUEST = 0x04
MCS_TYPE_ATTACH_USER_REQUEST = 0x28
MCS_TYPE_ATTACH_USER_CONFIRM = 0x2E
MCS_TYPE_CHANNEL_JOIN_REQUEST = 0x38
MCS_TYPE_CHANNEL_JOIN_CONFIRM = 0x3E
MCS_TYPE_SEND_DATA_REQUEST = 0x64
MCS_TYPE_SEND_DATA_INDICATION = 0x68

# GCC / T.124 constants
GCC_OBJECT_ID = bytes([0x00, 0x14, 0x7C, 0x00, 0x01])  # ITU-T T.124

# Client-to-server H.221 key
H221_CS_KEY = b"Duca"
H221_SC_KEY = b"McDn"

# User Data types (Client)
CS_CORE = 0xC001
CS_SECURITY = 0xC002
CS_NET = 0xC003
CS_CLUSTER = 0xC004
CS_MONITOR = 0xC005
CS_MCS_MSGCHANNEL = 0xC006
CS_MULTITRANSPORT = 0xC00A

# User Data types (Server)
SC_CORE = 0x0C01
SC_SECURITY = 0x0C02
SC_NET = 0x0C03
SC_MCS_MSGCHANNEL = 0x0C04
SC_MULTITRANSPORT = 0x0C05


def _ber_write_length(length: int) -> bytes:
    """Encode length in BER definite form."""
    if length < 0x80:
        return bytes([length])
    if length < 0x100:
        return bytes([0x81, length])
    if length < 0x10000:
        return bytes([0x82, (length >> 8) & 0xFF, length & 0xFF])
    raise ValueError(f"Length too large: {length}")


def _ber_write_integer(value: int) -> bytes:
    """Encode an integer in BER format."""
    # Determine the minimum number of bytes needed
    if value == 0:
        content = bytes([0])
    elif value > 0:
        content = value.to_bytes((value.bit_length() + 8) // 8, "big")
        if content[0] & 0x80:
            content = b"\x00" + content
    else:
        raise ValueError("Negative integers not supported")
    return bytes([0x02]) + _ber_write_length(len(content)) + content


def _ber_write_octet_string(data: bytes) -> bytes:
    """Encode an octet string in BER format."""
    return bytes([0x04]) + _ber_write_length(len(data)) + data


def _ber_write_boolean(value: bool) -> bytes:
    """Encode a boolean in BER format."""
    return bytes([0x01, 0x01, 0xFF if value else 0x00])


def _ber_write_sequence(content: bytes) -> bytes:
    """Encode a sequence in BER format."""
    return bytes([0x30]) + _ber_write_length(len(content)) + content


def _ber_write_application_tag(tag: int, content: bytes) -> bytes:
    """Encode an APPLICATION tag in BER format."""
    # For tags > 30, use multi-byte encoding
    if tag > 30:
        return bytes([0x7F, tag]) + _ber_write_length(len(content)) + content
    return bytes([0x60 | tag]) + _ber_write_length(len(content)) + content


def _per_write_length(length: int) -> bytes:
    """Encode length in PER format."""
    if length < 0x80:
        return bytes([length])
    if length < 0x4000:
        return bytes([0x80 | ((length >> 8) & 0x3F), length & 0xFF])
    raise ValueError(f"Length too large for PER: {length}")


def build_domain_parameters(
    max_channel_ids: int = 34,
    max_user_ids: int = 2,
    max_token_ids: int = 0,
    num_priorities: int = 1,
    min_throughput: int = 0,
    max_height: int = 1,
    max_mcs_pdu_size: int = 65535,
    protocol_version: int = 2,
) -> bytes:
    """Build MCS DomainParameters structure."""
    content = (
        _ber_write_integer(max_channel_ids)
        + _ber_write_integer(max_user_ids)
        + _ber_write_integer(max_token_ids)
        + _ber_write_integer(num_priorities)
        + _ber_write_integer(min_throughput)
        + _ber_write_integer(max_height)
        + _ber_write_integer(max_mcs_pdu_size)
        + _ber_write_integer(protocol_version)
    )
    return _ber_write_sequence(content)


def build_client_core_data(
    version: int = 0x00080004,
    desktop_width: int = 1920,
    desktop_height: int = 1080,
    color_depth: int = 0xCA01,  # RNS_UD_COLOR_8BPP
    sas_sequence: int = 0xAA03,  # RNS_UD_SAS_DEL
    keyboard_layout: int = 0x409,  # English (US)
    client_build: int = 2600,
    client_name: str = "rdpclient",
    keyboard_type: int = 4,
    keyboard_sub_type: int = 0,
    keyboard_function_key: int = 12,
    ime_file_name: str = "",
    post_beta2_color_depth: int = 0xCA01,
    client_product_id: int = 1,
    serial_number: int = 0,
    high_color_depth: int = 24,
    supported_color_depths: int = 0x07,  # 15, 16, 24 bpp
    early_capability_flags: int = 0x01,  # RNS_UD_CS_SUPPORT_ERRINFO_PDU
    client_dig_product_id: str = "",
    connection_type: int = 0,
    server_selected_protocol: int = 2,  # PROTOCOL_HYBRID (NLA)
) -> bytes:
    """Build Client Core Data (TS_UD_CS_CORE)."""
    data = bytearray()

    # Header: type (2) + length (2) - will be filled at the end
    header_pos = len(data)
    data += bytes(4)

    # version (4 bytes)
    data += version.to_bytes(4, "little")

    # desktopWidth (2 bytes)
    data += desktop_width.to_bytes(2, "little")

    # desktopHeight (2 bytes)
    data += desktop_height.to_bytes(2, "little")

    # colorDepth (2 bytes)
    data += color_depth.to_bytes(2, "little")

    # SASSequence (2 bytes)
    data += sas_sequence.to_bytes(2, "little")

    # keyboardLayout (4 bytes)
    data += keyboard_layout.to_bytes(4, "little")

    # clientBuild (4 bytes)
    data += client_build.to_bytes(4, "little")

    # clientName (32 bytes, UTF-16LE, null-terminated)
    name_encoded = client_name[:15].encode("utf-16-le")
    name_padded = name_encoded.ljust(32, b"\x00")
    data += name_padded

    # keyboardType (4 bytes)
    data += keyboard_type.to_bytes(4, "little")

    # keyboardSubType (4 bytes)
    data += keyboard_sub_type.to_bytes(4, "little")

    # keyboardFunctionKey (4 bytes)
    data += keyboard_function_key.to_bytes(4, "little")

    # imeFileName (64 bytes, UTF-16LE)
    ime_encoded = ime_file_name[:31].encode("utf-16-le")
    ime_padded = ime_encoded.ljust(64, b"\x00")
    data += ime_padded

    # postBeta2ColorDepth (2 bytes)
    data += post_beta2_color_depth.to_bytes(2, "little")

    # clientProductId (2 bytes)
    data += client_product_id.to_bytes(2, "little")

    # serialNumber (4 bytes)
    data += serial_number.to_bytes(4, "little")

    # highColorDepth (2 bytes)
    data += high_color_depth.to_bytes(2, "little")

    # supportedColorDepths (2 bytes)
    data += supported_color_depths.to_bytes(2, "little")

    # earlyCapabilityFlags (2 bytes)
    data += early_capability_flags.to_bytes(2, "little")

    # clientDigProductId (64 bytes)
    dig_encoded = client_dig_product_id[:31].encode("utf-16-le")
    dig_padded = dig_encoded.ljust(64, b"\x00")
    data += dig_padded

    # connectionType (1 byte)
    data += bytes([connection_type])

    # pad1octet (1 byte)
    data += bytes([0])

    # serverSelectedProtocol (4 bytes)
    data += server_selected_protocol.to_bytes(4, "little")

    # Fill in the header
    length = len(data)
    data[header_pos : header_pos + 2] = CS_CORE.to_bytes(2, "little")
    data[header_pos + 2 : header_pos + 4] = length.to_bytes(2, "little")

    return bytes(data)


def build_client_security_data(
    encryption_methods: int = 0x03,  # 40-bit and 128-bit
    ext_encryption_methods: int = 0,
) -> bytes:
    """Build Client Security Data (TS_UD_CS_SEC)."""
    data = bytearray()

    # Header: type (2) + length (2)
    data += CS_SECURITY.to_bytes(2, "little")
    data += (12).to_bytes(2, "little")  # Fixed size: 12 bytes

    # encryptionMethods (4 bytes)
    data += encryption_methods.to_bytes(4, "little")

    # extEncryptionMethods (4 bytes)
    data += ext_encryption_methods.to_bytes(4, "little")

    return bytes(data)


def build_client_network_data(channels: list[tuple[str, int]] | None = None) -> bytes:
    """Build Client Network Data (TS_UD_CS_NET).

    Args:
        channels: List of (name, options) tuples for virtual channels.

    """
    if channels is None:
        channels = []

    data = bytearray()

    # Header placeholder
    header_pos = len(data)
    data += bytes(4)

    # channelCount (4 bytes)
    data += len(channels).to_bytes(4, "little")

    # channelDefArray
    for name, options in channels:
        # name (8 bytes, null-terminated ASCII)
        name_bytes = name[:7].encode("ascii")
        name_padded = name_bytes.ljust(8, b"\x00")
        data += name_padded
        # options (4 bytes)
        data += options.to_bytes(4, "little")

    # Fill in the header
    length = len(data)
    data[header_pos : header_pos + 2] = CS_NET.to_bytes(2, "little")
    data[header_pos + 2 : header_pos + 4] = length.to_bytes(2, "little")

    return bytes(data)


def build_client_cluster_data(
    flags: int = 0x0D,  # REDIRECTION_SUPPORTED | REDIRECTION_VERSION4
    redirected_session_id: int = 0,
) -> bytes:
    """Build Client Cluster Data (TS_UD_CS_CLUSTER)."""
    data = bytearray()

    # Header: type (2) + length (2)
    data += CS_CLUSTER.to_bytes(2, "little")
    data += (12).to_bytes(2, "little")  # Fixed size: 12 bytes

    # Flags (4 bytes)
    data += flags.to_bytes(4, "little")

    # RedirectedSessionID (4 bytes)
    data += redirected_session_id.to_bytes(4, "little")

    return bytes(data)


def build_gcc_conference_create_request(user_data: bytes) -> bytes:
    """Build PER-encoded GCC Conference Create Request.

    This wraps the user data in the GCC/T.124 structure.
    """
    # The GCC CCR is PER-encoded (ALIGNED variant)
    data = bytearray()

    # ConnectGCCPDU choice + ConferenceCreateRequest fields
    data += bytes([0x00])  # extension bit + choice (conferenceCreateRequest)
    data += bytes([0x08])  # optional fields present: userData
    data += bytes([0x00])  # ConferenceName::numeric length (1 char)
    data += bytes([0x10])  # ConferenceName::numeric = "1"
    data += bytes([0x00])  # terminationMethod::automatic

    # Number of UserData sets = 1
    data += bytes([0x01])

    # UserData present + Key choice (h221NonStandard)
    data += bytes([0xC0])

    # h221NonStandard length (4 octets)
    data += bytes([0x00])

    # h221NonStandard key = "Duca"
    data += H221_CS_KEY

    # UserData::value length (PER encoded)
    data += _per_write_length(len(user_data))

    # UserData::value
    data += user_data

    return bytes(data)


def build_gcc_connect_data(gcc_ccr: bytes) -> bytes:
    """Build PER-encoded GCC Connect Data wrapper.

    This wraps the GCC Conference Create Request.
    """
    data = bytearray()

    # Key choice: object (0)
    data += bytes([0x00])

    # Object length
    data += bytes([len(GCC_OBJECT_ID)])

    # Object ID
    data += GCC_OBJECT_ID

    # connectPDU length (PER encoded)
    data += _per_write_length(len(gcc_ccr))

    # connectPDU (GCC Conference Create Request)
    data += gcc_ccr

    return bytes(data)


def build_mcs_connect_initial(
    user_data: bytes,
    target_params: bytes | None = None,
    min_params: bytes | None = None,
    max_params: bytes | None = None,
) -> bytes:
    """Build MCS Connect Initial PDU.

    Args:
        user_data: The GCC user data (client data blocks)
        target_params: Target domain parameters (optional)
        min_params: Minimum domain parameters (optional)
        max_params: Maximum domain parameters (optional)

    """
    # Default domain parameters if not provided
    if target_params is None:
        target_params = build_domain_parameters(max_channel_ids=34, max_user_ids=2)
    if min_params is None:
        min_params = build_domain_parameters(
            max_channel_ids=1,
            max_user_ids=1,
            max_token_ids=1,
            max_mcs_pdu_size=1056,
        )
    if max_params is None:
        max_params = build_domain_parameters(
            max_channel_ids=65535,
            max_user_ids=64535,
            max_token_ids=65535,
        )

    # Build GCC structures
    gcc_ccr = build_gcc_conference_create_request(user_data)
    gcc_connect_data = build_gcc_connect_data(gcc_ccr)

    # Build MCS Connect Initial content
    content = bytearray()

    # callingDomainSelector (OCTET STRING)
    content += _ber_write_octet_string(bytes([0x01]))

    # calledDomainSelector (OCTET STRING)
    content += _ber_write_octet_string(bytes([0x01]))

    # upwardFlag (BOOLEAN)
    content += _ber_write_boolean(True)

    # targetParameters (DomainParameters)
    content += target_params

    # minimumParameters (DomainParameters)
    content += min_params

    # maximumParameters (DomainParameters)
    content += max_params

    # userData (OCTET STRING)
    content += _ber_write_octet_string(gcc_connect_data)

    # Wrap in APPLICATION 101 tag
    mcs_ci = _ber_write_application_tag(MCS_TYPE_CONNECT_INITIAL, bytes(content))

    return mcs_ci


def _per_write_integer(value: int) -> bytes:
    """Encode an integer in PER (unaligned) format for MCS PDUs.

    For MCS Erect Domain Request, integers are encoded as:
    - 1 byte length prefix (number of bytes - 1)
    - Followed by the value in big-endian

    For value 0: encoded as 01 00 (1 byte length, value 0)
    For value 1: encoded as 01 01 (1 byte length, value 1)
    """
    if value < 256:
        return bytes([0x01, value])
    if value < 65536:
        return bytes([0x02, (value >> 8) & 0xFF, value & 0xFF])
    raise ValueError(f"Integer too large for PER encoding: {value}")


def build_mcs_erect_domain_request(sub_height: int = 0, sub_interval: int = 0) -> bytes:
    """Build MCS Erect Domain Request PDU.

    Per MS-RDPBCGR section 2.2.1.5, the format is:
    - Type: 0x04 (1 byte)
    - subHeight: PER-encoded integer
    - subInterval: PER-encoded integer

    For default values (0, 0), this produces: 04 01 00 01 00
    """
    data = bytearray()
    data.append(MCS_TYPE_ERECT_DOMAIN_REQUEST)
    data += _per_write_integer(sub_height)
    data += _per_write_integer(sub_interval)
    return bytes(data)


def build_mcs_attach_user_request() -> bytes:
    """Build MCS Attach User Request PDU."""
    return bytes([MCS_TYPE_ATTACH_USER_REQUEST])


def build_mcs_channel_join_request(user_id: int, channel_id: int) -> bytes:
    """Build MCS Channel Join Request PDU."""
    data = bytearray()
    data.append(MCS_TYPE_CHANNEL_JOIN_REQUEST)
    # User ID (2 bytes, big-endian, offset by 1001)
    data += (user_id - 1001).to_bytes(2, "big")
    # Channel ID (2 bytes, big-endian)
    data += channel_id.to_bytes(2, "big")
    return bytes(data)


def build_mcs_send_data_request(
    user_id: int,
    channel_id: int,
    data_priority: int = 1,  # High priority
    segmentation: int = 3,  # Begin + End
    user_data: bytes = b"",
) -> bytes:
    """Build MCS Send Data Request PDU.

    The type byte is already encoded as choice 25 << 2 = 0x64.
    Lower 2 bits are used for data priority.
    """
    pdu = bytearray()

    # Type (choice 25 = sendDataRequest, already shifted) + data priority (2 bits)
    # MCS_TYPE_SEND_DATA_REQUEST is 0x64, which is the already-shifted value
    # So we just OR in the data priority in the lower 2 bits
    pdu.append(MCS_TYPE_SEND_DATA_REQUEST | (data_priority & 0x03))

    # User ID (2 bytes, big-endian, offset by 1001)
    pdu += (user_id - 1001).to_bytes(2, "big")

    # Channel ID (2 bytes, big-endian)
    pdu += channel_id.to_bytes(2, "big")

    # Segmentation (1 byte)
    pdu.append(segmentation << 6)

    # User data length (PER encoded)
    # Use segmented length encoding for data > 16383 bytes
    if len(user_data) < 0x80:
        pdu.append(len(user_data))
    elif len(user_data) < 0x4000:
        pdu += bytes([0x80 | ((len(user_data) >> 8) & 0x3F), len(user_data) & 0xFF])
    else:
        raise ValueError("User data too large for single segment")

    # User data
    pdu += user_data

    return bytes(pdu)


def parse_mcs_connect_response(data: bytes) -> dict[str, Any]:
    """Parse MCS Connect Response PDU.

    Returns dict with: result, called_connect_id, domain_params, user_data
    """
    result: dict[str, Any] = {
        "result": None,
        "called_connect_id": None,
        "domain_params": None,
        "user_data": None,
        "server_data": {},
    }

    offset = 0

    # Check APPLICATION tag
    if data[offset] != 0x7F or data[offset + 1] != MCS_TYPE_CONNECT_RESPONSE:
        raise ValueError(f"Expected MCS Connect Response, got {data[offset]:02x} {data[offset + 1]:02x}")
    offset += 2

    # Parse length
    if data[offset] & 0x80:
        num_len_bytes = data[offset] & 0x7F
        _length = int.from_bytes(data[offset + 1 : offset + 1 + num_len_bytes], "big")
        offset += 1 + num_len_bytes
    else:
        _length = data[offset]
        offset += 1

    # Parse result (ENUMERATED)
    if data[offset] != 0x0A:  # ENUMERATED tag
        raise ValueError(f"Expected ENUMERATED for result, got {data[offset]:02x}")
    offset += 1
    result_len = data[offset]
    offset += 1
    result["result"] = int.from_bytes(data[offset : offset + result_len], "big")
    offset += result_len

    # Parse calledConnectId (INTEGER)
    if data[offset] != 0x02:  # INTEGER tag
        raise ValueError(f"Expected INTEGER for calledConnectId, got {data[offset]:02x}")
    offset += 1
    ccid_len = data[offset]
    offset += 1
    result["called_connect_id"] = int.from_bytes(data[offset : offset + ccid_len], "big")
    offset += ccid_len

    # Parse domainParameters (SEQUENCE)
    if data[offset] != 0x30:  # SEQUENCE tag
        raise ValueError(f"Expected SEQUENCE for domainParameters, got {data[offset]:02x}")
    offset += 1
    if data[offset] & 0x80:
        num_len_bytes = data[offset] & 0x7F
        dp_len = int.from_bytes(data[offset + 1 : offset + 1 + num_len_bytes], "big")
        offset += 1 + num_len_bytes
    else:
        dp_len = data[offset]
        offset += 1
    # Skip domain parameters content for now
    offset += dp_len

    # Parse userData (OCTET STRING)
    if data[offset] != 0x04:  # OCTET STRING tag
        raise ValueError(f"Expected OCTET STRING for userData, got {data[offset]:02x}")
    offset += 1
    if data[offset] & 0x80:
        num_len_bytes = data[offset] & 0x7F
        ud_len = int.from_bytes(data[offset + 1 : offset + 1 + num_len_bytes], "big")
        offset += 1 + num_len_bytes
    else:
        ud_len = data[offset]
        offset += 1

    result["user_data"] = data[offset : offset + ud_len]

    # Parse the GCC data within user_data
    _parse_gcc_connect_response(result["user_data"], result)

    return result


def _parse_gcc_connect_response(gcc_data: bytes, result: dict[str, Any]) -> None:
    """Parse the GCC Connect Response within MCS user data."""
    offset = 0

    # Skip GCC Connect Data header (object ID etc)
    # Key choice (1 byte)
    offset += 1
    # Object length (1 byte)
    obj_len = gcc_data[offset]
    offset += 1
    # Object ID
    offset += obj_len

    # connectPDU length (PER)
    if gcc_data[offset] & 0x80:
        offset += 2
    else:
        offset += 1

    # Skip GCC Conference Create Response header
    # Look for the H.221 key "McDn"
    mcdn_pos = gcc_data.find(H221_SC_KEY, offset)
    if mcdn_pos == -1:
        logger.warning("Could not find 'McDn' key in GCC response")
        return

    offset = mcdn_pos + len(H221_SC_KEY)

    # Parse user data length
    if gcc_data[offset] & 0x80:
        ud_len = ((gcc_data[offset] & 0x3F) << 8) | gcc_data[offset + 1]
        offset += 2
    else:
        ud_len = gcc_data[offset]
        offset += 1

    # Parse server data blocks
    end_offset = offset + ud_len
    while offset < end_offset and offset + 4 <= len(gcc_data):
        block_type = int.from_bytes(gcc_data[offset : offset + 2], "little")
        block_len = int.from_bytes(gcc_data[offset + 2 : offset + 4], "little")

        if block_len < 4 or offset + block_len > len(gcc_data):
            break

        block_data = gcc_data[offset + 4 : offset + block_len]

        if block_type == SC_CORE:
            result["server_data"]["core"] = _parse_server_core_data(block_data)
        elif block_type == SC_SECURITY:
            result["server_data"]["security"] = _parse_server_security_data(block_data)
        elif block_type == SC_NET:
            result["server_data"]["network"] = _parse_server_network_data(block_data)

        offset += block_len

    logger.debug(f"Parsed server data: {result['server_data']}")


def _parse_server_core_data(data: bytes) -> dict[str, Any]:
    """Parse Server Core Data (TS_UD_SC_CORE)."""
    result: dict[str, Any] = {}
    if len(data) >= 4:
        result["version"] = int.from_bytes(data[0:4], "little")
    if len(data) >= 8:
        result["client_requested_protocols"] = int.from_bytes(data[4:8], "little")
    if len(data) >= 12:
        result["early_capability_flags"] = int.from_bytes(data[8:12], "little")
    return result


def _parse_server_security_data(data: bytes) -> dict[str, Any]:
    """Parse Server Security Data (TS_UD_SC_SEC1)."""
    result: dict[str, Any] = {}
    if len(data) >= 4:
        result["encryption_method"] = int.from_bytes(data[0:4], "little")
    if len(data) >= 8:
        result["encryption_level"] = int.from_bytes(data[4:8], "little")
    # The rest contains server random and certificate for standard RDP security
    # For Enhanced RDP Security (TLS/NLA), these fields are typically 0
    return result


def _parse_server_network_data(data: bytes) -> dict[str, Any]:
    """Parse Server Network Data (TS_UD_SC_NET)."""
    result: dict[str, Any] = {"mcs_channel_id": 0, "channel_ids": []}
    if len(data) >= 2:
        result["mcs_channel_id"] = int.from_bytes(data[0:2], "little")
    if len(data) >= 4:
        channel_count = int.from_bytes(data[2:4], "little")
        for i in range(channel_count):
            if len(data) >= 4 + (i + 1) * 2:
                channel_id = int.from_bytes(data[4 + i * 2 : 6 + i * 2], "little")
                result["channel_ids"].append(channel_id)
    return result


def parse_mcs_attach_user_confirm(data: bytes) -> dict[str, Any]:
    """Parse MCS Attach User Confirm PDU.

    PER encoding (from MS-RDPBCGR example 2e 00 00 06):
    Byte 0: bits 7-2 = choice (11 for attachUserConfirm)
            bit 1 = initiator present flag
            bit 0 = first bit of result enum
    Byte 1: bits 7-4 = remaining 4 bits of result enum (so result is 5 bits total, but usually just check byte 1)
            bits 3-0 = padding
    Bytes 2-3: User ID (big-endian, offset by 1001) - only if initiator present
    """
    result: dict[str, Any] = {"result": None, "user_id": None}

    if len(data) < 2:
        raise ValueError("MCS Attach User Confirm too short")

    logger.debug(f"Attach User Confirm raw data: {data[: min(8, len(data))].hex(' ')}")

    first_byte = data[0]
    mcs_type = (first_byte >> 2) & 0x3F
    initiator_present = (first_byte >> 1) & 0x01

    if mcs_type != (MCS_TYPE_ATTACH_USER_CONFIRM >> 2):
        raise ValueError(f"Expected Attach User Confirm (type 11), got type {mcs_type}")

    # Result is encoded across byte boundary
    # Bit 0 of first byte + upper nibble of second byte form the result
    # But for simplicity, since result values are small (0-14), we can just read byte 1
    result_value = data[1]
    result["result"] = result_value

    logger.debug(f"Attach User Confirm: type={mcs_type}, initiator_present={initiator_present}, result={result_value}")

    # User ID (2 bytes, big-endian, add 1001) - only if initiator present
    if initiator_present and len(data) >= 4:
        user_id = int.from_bytes(data[2:4], "big") + 1001
        result["user_id"] = user_id
        logger.debug(f"User ID from confirm: {user_id}")

    return result


def parse_mcs_channel_join_confirm(data: bytes) -> dict[str, Any]:
    """Parse MCS Channel Join Confirm PDU.

    PER encoding (from MS-RDPBCGR example 3e 00 00 06 03 ef 03 ef):
    Byte 0: bits 7-2 = choice (15 for channelJoinConfirm)
            bit 1 = channelId present flag
            bit 0 = first bit of result enum
    Byte 1: result value
    Bytes 2-3: initiator (user ID - 1001, big-endian)
    Bytes 4-5: requested (channel ID, big-endian)
    Bytes 6-7: channelId (actual channel ID, big-endian) - only if present flag set
    """
    result: dict[str, Any] = {"result": None, "user_id": None, "channel_id": None}

    if len(data) < 6:
        raise ValueError(f"MCS Channel Join Confirm too short: {len(data)} bytes")

    logger.debug(f"Channel Join Confirm raw data: {data[: min(10, len(data))].hex(' ')}")

    first_byte = data[0]
    mcs_type = (first_byte >> 2) & 0x3F
    channel_id_present = (first_byte >> 1) & 0x01

    if mcs_type != (MCS_TYPE_CHANNEL_JOIN_CONFIRM >> 2):
        raise ValueError(f"Expected Channel Join Confirm (type 15), got type {mcs_type}")

    # Result is in byte 1
    result_value = data[1]
    result["result"] = result_value

    # initiator (user ID - 1001)
    user_id = int.from_bytes(data[2:4], "big") + 1001
    result["user_id"] = user_id

    # requested (channel ID)
    requested_channel = int.from_bytes(data[4:6], "big")

    # channelId (only if present flag is set and result is success)
    if channel_id_present and result_value == 0 and len(data) >= 8:
        result["channel_id"] = int.from_bytes(data[6:8], "big")
    else:
        result["channel_id"] = requested_channel

    logger.debug(
        f"Channel Join Confirm: type={mcs_type}, result={result_value}, "
        f"user_id={user_id}, requested={requested_channel}, channel_id={result['channel_id']}",
    )

    return result
