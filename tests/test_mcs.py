"""Tests for MCS layer module."""

import struct

import pytest

from simple_rdp.mcs import (
    CS_CLUSTER,
    CS_CORE,
    CS_NET,
    CS_SECURITY,
    GCC_OBJECT_ID,
    H221_CS_KEY,
    MCS_TYPE_ATTACH_USER_REQUEST,
    MCS_TYPE_CHANNEL_JOIN_REQUEST,
    MCS_TYPE_CONNECT_INITIAL,
    MCS_TYPE_ERECT_DOMAIN_REQUEST,
    MCS_TYPE_SEND_DATA_REQUEST,
    _ber_write_application_tag,
    _ber_write_boolean,
    _ber_write_integer,
    _ber_write_length,
    _ber_write_octet_string,
    _ber_write_sequence,
    _per_write_integer,
    _per_write_length,
    build_client_cluster_data,
    build_client_core_data,
    build_client_network_data,
    build_client_security_data,
    build_domain_parameters,
    build_gcc_conference_create_request,
    build_gcc_connect_data,
    build_mcs_attach_user_request,
    build_mcs_channel_join_request,
    build_mcs_connect_initial,
    build_mcs_erect_domain_request,
    build_mcs_send_data_request,
    parse_mcs_attach_user_confirm,
    parse_mcs_channel_join_confirm,
    parse_mcs_connect_response,
)


class TestBerEncoding:
    """Tests for BER encoding functions."""

    def test_ber_write_length_short_form(self) -> None:
        """Test BER length encoding - short form."""
        assert _ber_write_length(0) == bytes([0])
        assert _ber_write_length(127) == bytes([127])
        assert _ber_write_length(50) == bytes([50])

    def test_ber_write_length_long_form_1byte(self) -> None:
        """Test BER length encoding - long form 1 byte."""
        assert _ber_write_length(128) == bytes([0x81, 128])
        assert _ber_write_length(255) == bytes([0x81, 255])

    def test_ber_write_length_long_form_2bytes(self) -> None:
        """Test BER length encoding - long form 2 bytes."""
        result = _ber_write_length(256)
        assert result == bytes([0x82, 0x01, 0x00])
        result = _ber_write_length(0xFFFF)
        assert result == bytes([0x82, 0xFF, 0xFF])

    def test_ber_write_length_too_large(self) -> None:
        """Test BER length encoding - too large."""
        with pytest.raises(ValueError, match="Length too large"):
            _ber_write_length(0x10000)

    def test_ber_write_integer_zero(self) -> None:
        """Test BER integer encoding - zero."""
        result = _ber_write_integer(0)
        assert result == bytes([0x02, 0x01, 0x00])

    def test_ber_write_integer_small(self) -> None:
        """Test BER integer encoding - small value."""
        result = _ber_write_integer(100)
        assert result[0] == 0x02  # INTEGER tag
        assert result[1] == 1  # Length
        assert result[2] == 100

    def test_ber_write_integer_large(self) -> None:
        """Test BER integer encoding - large value."""
        result = _ber_write_integer(65535)
        assert result[0] == 0x02  # INTEGER tag
        # Value needs 3 bytes (leading 0 to avoid negative interpretation)

    def test_ber_write_integer_negative_raises(self) -> None:
        """Test BER integer encoding - negative raises."""
        with pytest.raises(ValueError, match="Negative integers"):
            _ber_write_integer(-1)

    def test_ber_write_integer_high_bit_set(self) -> None:
        """Test BER integer encoding - value with high bit set needs padding."""
        # 0x80 = 128, has high bit set, needs leading 0x00
        result = _ber_write_integer(128)
        assert result[0] == 0x02  # INTEGER tag
        # Should have 2 bytes of content: 0x00 0x80
        assert result[1] == 2  # Length
        assert result[2] == 0x00  # Leading zero
        assert result[3] == 0x80

    def test_ber_write_integer_0xFF(self) -> None:
        """Test BER integer encoding - 0xFF needs padding."""
        result = _ber_write_integer(0xFF)
        assert result[0] == 0x02  # INTEGER tag
        assert result[2] == 0x00  # Leading zero for high bit

    def test_ber_write_octet_string(self) -> None:
        """Test BER octet string encoding."""
        data = b"hello"
        result = _ber_write_octet_string(data)
        assert result[0] == 0x04  # OCTET STRING tag
        assert result[1] == len(data)  # Length
        assert result[2:] == data

    def test_ber_write_boolean_true(self) -> None:
        """Test BER boolean encoding - true."""
        result = _ber_write_boolean(True)
        assert result == bytes([0x01, 0x01, 0xFF])

    def test_ber_write_boolean_false(self) -> None:
        """Test BER boolean encoding - false."""
        result = _ber_write_boolean(False)
        assert result == bytes([0x01, 0x01, 0x00])

    def test_ber_write_sequence(self) -> None:
        """Test BER sequence encoding."""
        content = b"\x01\x02\x03"
        result = _ber_write_sequence(content)
        assert result[0] == 0x30  # SEQUENCE tag
        assert result[1] == len(content)
        assert result[2:] == content


class TestPerEncoding:
    """Tests for PER encoding functions."""

    def test_per_write_length_short(self) -> None:
        """Test PER length encoding - short."""
        assert _per_write_length(0) == bytes([0])
        assert _per_write_length(127) == bytes([127])

    def test_per_write_length_long(self) -> None:
        """Test PER length encoding - long."""
        result = _per_write_length(128)
        assert result == bytes([0x80, 128])

    def test_per_write_length_too_large(self) -> None:
        """Test PER length encoding - too large."""
        with pytest.raises(ValueError, match="Length too large for PER"):
            _per_write_length(0x4000)


class TestDomainParameters:
    """Tests for domain parameters building."""

    def test_build_domain_parameters_defaults(self) -> None:
        """Test building domain parameters with defaults."""
        result = build_domain_parameters()
        assert len(result) > 0
        assert isinstance(result, bytes)

    def test_build_domain_parameters_custom(self) -> None:
        """Test building domain parameters with custom values."""
        result = build_domain_parameters(
            max_channel_ids=100,
            max_user_ids=10,
            max_mcs_pdu_size=32768,
        )
        assert len(result) > 0


class TestMcsPduBuilding:
    """Tests for MCS PDU building functions."""

    def test_build_erect_domain_request(self) -> None:
        """Test building erect domain request."""
        result = build_mcs_erect_domain_request()
        assert len(result) > 0
        assert result[0] == MCS_TYPE_ERECT_DOMAIN_REQUEST

    def test_build_attach_user_request(self) -> None:
        """Test building attach user request."""
        result = build_mcs_attach_user_request()
        assert len(result) > 0
        assert result[0] == MCS_TYPE_ATTACH_USER_REQUEST

    def test_build_channel_join_request(self) -> None:
        """Test building channel join request."""
        user_id = 1001
        channel_id = 1003
        result = build_mcs_channel_join_request(user_id, channel_id)
        assert len(result) > 0
        assert result[0] == MCS_TYPE_CHANNEL_JOIN_REQUEST


class TestConstants:
    """Tests for MCS constants."""

    def test_gcc_object_id(self) -> None:
        """Test GCC object ID format."""
        assert len(GCC_OBJECT_ID) == 5
        assert isinstance(GCC_OBJECT_ID, bytes)

    def test_h221_cs_key(self) -> None:
        """Test H.221 client-to-server key."""
        assert H221_CS_KEY == b"Duca"

    def test_user_data_types(self) -> None:
        """Test user data type constants."""
        assert CS_CORE == 0xC001
        assert CS_SECURITY == 0xC002
        assert CS_NET == 0xC003

    def test_cluster_type(self) -> None:
        """Test cluster type constant."""
        assert CS_CLUSTER == 0xC004

    def test_mcs_type_constants(self) -> None:
        """Test MCS type constants."""
        assert MCS_TYPE_CONNECT_INITIAL == 0x65
        assert MCS_TYPE_ERECT_DOMAIN_REQUEST == 0x04
        assert MCS_TYPE_ATTACH_USER_REQUEST == 0x28
        assert MCS_TYPE_CHANNEL_JOIN_REQUEST == 0x38
        assert MCS_TYPE_SEND_DATA_REQUEST == 0x64

    def test_mcs_confirm_type_constants(self) -> None:
        """Test MCS confirm type constants."""
        from simple_rdp.mcs import MCS_TYPE_CONNECT_RESPONSE, MCS_TYPE_ATTACH_USER_CONFIRM, MCS_TYPE_CHANNEL_JOIN_CONFIRM
        
        assert MCS_TYPE_CONNECT_RESPONSE == 0x66
        assert MCS_TYPE_ATTACH_USER_CONFIRM == 0x2E
        assert MCS_TYPE_CHANNEL_JOIN_CONFIRM == 0x3E

    def test_server_user_data_types(self) -> None:
        """Test server user data type constants."""
        from simple_rdp.mcs import SC_CORE, SC_SECURITY, SC_NET
        
        assert SC_CORE == 0x0C01
        assert SC_SECURITY == 0x0C02
        assert SC_NET == 0x0C03


class TestBerApplicationTag:
    """Tests for BER application tag encoding."""

    def test_ber_write_application_tag_small(self) -> None:
        """Test application tag with small tag number."""
        content = b"\x01\x02"
        result = _ber_write_application_tag(5, content)
        assert result[0] == 0x65  # 0x60 | 5
        assert len(result) > 2

    def test_ber_write_application_tag_large(self) -> None:
        """Test application tag with large tag number (>30)."""
        content = b"\x01\x02"
        result = _ber_write_application_tag(101, content)  # MCS_TYPE_CONNECT_INITIAL
        assert result[0] == 0x7F  # Multi-byte encoding


class TestPerIntegerEncoding:
    """Tests for PER integer encoding."""

    def test_per_write_integer_small(self) -> None:
        """Test PER integer encoding - small value."""
        result = _per_write_integer(0)
        assert isinstance(result, bytes)

    def test_per_write_integer_medium(self) -> None:
        """Test PER integer encoding - medium value."""
        result = _per_write_integer(256)
        assert isinstance(result, bytes)
        assert len(result) >= 2

    def test_per_write_integer_large_2byte(self) -> None:
        """Test PER integer encoding - value requiring 2 bytes."""
        result = _per_write_integer(1000)
        assert isinstance(result, bytes)
        # Should be 2-byte format: 0x02, high, low
        assert result[0] == 0x02
        assert len(result) == 3

    def test_per_write_integer_max_2byte(self) -> None:
        """Test PER integer encoding - max 2-byte value."""
        result = _per_write_integer(65535)
        assert isinstance(result, bytes)
        assert result[0] == 0x02
        assert result[1] == 0xFF
        assert result[2] == 0xFF

    def test_per_write_integer_too_large(self) -> None:
        """Test PER integer encoding - too large raises error."""
        with pytest.raises(ValueError, match="Integer too large"):
            _per_write_integer(65536)


class TestClientCoreData:
    """Tests for Client Core Data building."""

    def test_build_client_core_data_defaults(self) -> None:
        """Test building client core data with defaults."""
        result = build_client_core_data()
        assert isinstance(result, bytes)
        assert len(result) > 100
        # Check header type
        header_type = struct.unpack("<H", result[:2])[0]
        assert header_type == CS_CORE

    def test_build_client_core_data_custom_resolution(self) -> None:
        """Test building client core data with custom resolution."""
        result = build_client_core_data(desktop_width=1280, desktop_height=720)
        assert isinstance(result, bytes)
        # Width and height are after header (4 bytes) and version (4 bytes)
        width = struct.unpack("<H", result[8:10])[0]
        height = struct.unpack("<H", result[10:12])[0]
        assert width == 1280
        assert height == 720

    def test_build_client_core_data_custom_client_name(self) -> None:
        """Test building client core data with custom client name."""
        result = build_client_core_data(client_name="testclient")
        assert isinstance(result, bytes)


class TestClientSecurityData:
    """Tests for Client Security Data building."""

    def test_build_client_security_data_defaults(self) -> None:
        """Test building client security data with defaults."""
        result = build_client_security_data()
        assert isinstance(result, bytes)
        # Header type
        header_type = struct.unpack("<H", result[:2])[0]
        assert header_type == CS_SECURITY
        # Fixed size of 12 bytes
        length = struct.unpack("<H", result[2:4])[0]
        assert length == 12

    def test_build_client_security_data_custom(self) -> None:
        """Test building client security data with custom encryption."""
        result = build_client_security_data(encryption_methods=0x0B)
        assert isinstance(result, bytes)
        encryption = struct.unpack("<I", result[4:8])[0]
        assert encryption == 0x0B


class TestClientNetworkData:
    """Tests for Client Network Data building."""

    def test_build_client_network_data_no_channels(self) -> None:
        """Test building client network data without channels."""
        result = build_client_network_data()
        assert isinstance(result, bytes)
        header_type = struct.unpack("<H", result[:2])[0]
        assert header_type == CS_NET

    def test_build_client_network_data_with_channels(self) -> None:
        """Test building client network data with channels."""
        channels = [("rdpdr", 0x80000000), ("cliprdr", 0xC0000000)]
        result = build_client_network_data(channels=channels)
        assert isinstance(result, bytes)
        # Should include channel definitions
        assert len(result) > 8


class TestClientClusterData:
    """Tests for Client Cluster Data building."""

    def test_build_client_cluster_data_defaults(self) -> None:
        """Test building client cluster data with defaults."""
        result = build_client_cluster_data()
        assert isinstance(result, bytes)
        header_type = struct.unpack("<H", result[:2])[0]
        assert header_type == CS_CLUSTER


class TestGccConference:
    """Tests for GCC conference building."""

    def test_build_gcc_conference_create_request(self) -> None:
        """Test building GCC conference create request."""
        user_data = build_client_core_data()
        result = build_gcc_conference_create_request(user_data)
        assert isinstance(result, bytes)
        assert len(result) > len(user_data)

    def test_build_gcc_connect_data(self) -> None:
        """Test building GCC connect data."""
        gcc_ccr = build_gcc_conference_create_request(build_client_core_data())
        result = build_gcc_connect_data(gcc_ccr)
        assert isinstance(result, bytes)
        assert len(result) > len(gcc_ccr)


class TestMcsConnectInitial:
    """Tests for MCS Connect Initial building."""

    def test_build_mcs_connect_initial_defaults(self) -> None:
        """Test building MCS connect initial with defaults."""
        # Build user data (client core + security + network)
        user_data = (
            build_client_core_data()
            + build_client_security_data()
            + build_client_network_data()
        )
        result = build_mcs_connect_initial(user_data)
        assert isinstance(result, bytes)
        assert len(result) > 100
        # Check APPLICATION tag (0x7F for multi-byte, then 0x65 for 101)
        assert result[0] == 0x7F

    def test_build_mcs_connect_initial_custom_resolution(self) -> None:
        """Test building MCS connect initial with custom resolution."""
        user_data = build_client_core_data(desktop_width=800, desktop_height=600)
        result = build_mcs_connect_initial(user_data)
        assert isinstance(result, bytes)


class TestMcsSendDataRequest:
    """Tests for MCS Send Data Request building."""

    def test_build_mcs_send_data_request(self) -> None:
        """Test building MCS send data request."""
        user_data = b"\x00\x01\x02\x03"
        result = build_mcs_send_data_request(
            user_id=1001,
            channel_id=1003,
            user_data=user_data,
        )
        assert isinstance(result, bytes)
        # Type byte has data priority in lower 2 bits
        assert (result[0] & 0xFC) == MCS_TYPE_SEND_DATA_REQUEST


class TestMcsParsingFunctions:
    """Tests for MCS parsing functions."""

    def test_parse_mcs_attach_user_confirm_valid(self) -> None:
        """Test parsing valid attach user confirm."""
        # Build a valid attach user confirm
        # Byte 0: bits 7-2 = choice (11 for attachUserConfirm), bit 1 = initiator present (1)
        # So (11 << 2) | 0x02 = 0x2E
        # Byte 1: result value (0 = success)
        # Bytes 2-3: user_id - 1001 (big-endian)
        data = bytes([0x2E, 0x00, 0x00, 0x00])  # Type, result, user_id offset = 0
        result = parse_mcs_attach_user_confirm(data)
        assert "result" in result
        assert result["result"] == 0

    def test_parse_mcs_attach_user_confirm_with_user_id(self) -> None:
        """Test parsing attach user confirm with user ID."""
        # User ID present, user_id = 1005 => offset = 4
        data = bytes([0x2E, 0x00, 0x00, 0x04])
        result = parse_mcs_attach_user_confirm(data)
        assert result["user_id"] == 1005

    def test_parse_mcs_attach_user_confirm_too_short(self) -> None:
        """Test parsing attach user confirm with too short data."""
        with pytest.raises(ValueError, match="too short"):
            parse_mcs_attach_user_confirm(b"\x2E")

    def test_parse_mcs_channel_join_confirm_valid(self) -> None:
        """Test parsing valid channel join confirm."""
        # Type: 0x3E (CHANNEL_JOIN_CONFIRM), result: 0, initiator: 1001, channel: 1003
        # Byte 0: (15 << 2) | 0x02 = 0x3E (type + channel present)
        data = bytes([
            0x3E,  # Type + channel present
            0x00,  # Result (success)
            0x00, 0x00,  # Initiator offset (0 => 1001)
            0x03, 0xEB,  # Requested channel (1003)
            0x03, 0xEB,  # Joined channel (1003)
        ])
        result = parse_mcs_channel_join_confirm(data)
        assert isinstance(result, dict)
        assert result["result"] == 0
        assert result["user_id"] == 1001
        assert result["channel_id"] == 1003

    def test_parse_mcs_channel_join_confirm_too_short(self) -> None:
        """Test parsing channel join confirm with too short data."""
        with pytest.raises(ValueError, match="too short"):
            parse_mcs_channel_join_confirm(bytes([0x3E, 0x00, 0x00, 0x00, 0x03]))

    def test_parse_mcs_channel_join_confirm_wrong_type(self) -> None:
        """Test parsing channel join confirm with wrong type."""
        # Type byte doesn't match expected
        data = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        with pytest.raises(ValueError, match="Expected Channel Join Confirm"):
            parse_mcs_channel_join_confirm(data)


class TestMcsConnectResponseParsing:
    """Tests for MCS Connect Response parsing."""

    def test_parse_mcs_connect_response_wrong_tag(self) -> None:
        """Test parsing MCS connect response with wrong APPLICATION tag."""
        # Wrong tag - not 0x7F 0x66
        data = bytes([0x00, 0x00, 0x00])
        with pytest.raises(ValueError, match="Expected MCS Connect Response"):
            parse_mcs_connect_response(data)

    def test_parse_mcs_connect_response_wrong_type(self) -> None:
        """Test parsing MCS connect response with wrong type byte."""
        # Right 0x7F but wrong type (0x65 instead of 0x66)
        data = bytes([0x7F, 0x65, 0x00])
        with pytest.raises(ValueError, match="Expected MCS Connect Response"):
            parse_mcs_connect_response(data)


class TestMcsSendDataRequestLengths:
    """Tests for MCS Send Data Request with different lengths."""

    def test_build_mcs_send_data_request_short_data(self) -> None:
        """Test building MCS send data request with short data."""
        user_data = b"\x00" * 50
        result = build_mcs_send_data_request(
            user_id=1001,
            channel_id=1003,
            user_data=user_data,
        )
        assert isinstance(result, bytes)
        assert len(result) > len(user_data)

    def test_build_mcs_send_data_request_medium_data(self) -> None:
        """Test building MCS send data request with medium-length data."""
        user_data = b"\x00" * 200
        result = build_mcs_send_data_request(
            user_id=1001,
            channel_id=1003,
            user_data=user_data,
        )
        assert isinstance(result, bytes)

    def test_build_mcs_send_data_request_large_data(self) -> None:
        """Test building MCS send data request with large data."""
        user_data = b"\x00" * 5000
        result = build_mcs_send_data_request(
            user_id=1001,
            channel_id=1003,
            user_data=user_data,
        )
        assert isinstance(result, bytes)

    def test_build_mcs_send_data_request_too_large(self) -> None:
        """Test building MCS send data request with too large data."""
        user_data = b"\x00" * 20000  # > 16383 bytes
        with pytest.raises(ValueError, match="too large"):
            build_mcs_send_data_request(
                user_id=1001,
                channel_id=1003,
                user_data=user_data,
            )

    def test_build_mcs_send_data_request_custom_priority(self) -> None:
        """Test building MCS send data request with custom priority."""
        result = build_mcs_send_data_request(
            user_id=1001,
            channel_id=1003,
            data_priority=2,
            user_data=b"\x00" * 10,
        )
        assert isinstance(result, bytes)
        # Data priority should be in lower 2 bits
        assert (result[0] & 0x03) == 2

    def test_build_mcs_send_data_request_empty_data(self) -> None:
        """Test building MCS send data request with empty data."""
        result = build_mcs_send_data_request(
            user_id=1001,
            channel_id=1003,
            user_data=b"",
        )
        assert isinstance(result, bytes)
        # Should still have header bytes
        assert len(result) >= 6


class TestMcsErectDomainRequest:
    """Tests for MCS Erect Domain Request building."""

    def test_build_mcs_erect_domain_request_custom_values(self) -> None:
        """Test building erect domain request with custom values."""
        result = build_mcs_erect_domain_request(sub_height=5, sub_interval=10)
        assert len(result) > 0
        assert result[0] == MCS_TYPE_ERECT_DOMAIN_REQUEST


class TestMcsChannelJoinRequest:
    """Tests for MCS Channel Join Request building."""

    def test_build_mcs_channel_join_request_various_channels(self) -> None:
        """Test building channel join request for various channels."""
        for channel_id in [1003, 1004, 1005, 1006]:
            result = build_mcs_channel_join_request(user_id=1001, channel_id=channel_id)
            assert result[0] == MCS_TYPE_CHANNEL_JOIN_REQUEST
