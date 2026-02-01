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
        # Build a minimal valid attach user confirm
        # Type: 0x2E (ATTACH_USER_CONFIRM), result: 0 (success), user_id: 1001
        data = bytes([0x2E, 0x00, 0x03, 0xE9])  # Type, result, user_id (big endian)
        result = parse_mcs_attach_user_confirm(data)
        assert "result" in result or "user_id" in result

    def test_parse_mcs_channel_join_confirm_valid(self) -> None:
        """Test parsing valid channel join confirm."""
        # Type: 0x3E (CHANNEL_JOIN_CONFIRM), result: 0, initiator: 1001, channel: 1003
        data = bytes([
            0x3E,  # Type
            0x00,  # Result (success)
            0x03, 0xE9,  # Initiator (1001)
            0x03, 0xEB,  # Requested channel (1003)
            0x03, 0xEB,  # Joined channel (1003)
        ])
        result = parse_mcs_channel_join_confirm(data)
        assert isinstance(result, dict)
