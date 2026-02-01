"""Tests for CredSSP module."""

import pytest

from simple_rdp.credssp import ASN1_CONTEXT_0
from simple_rdp.credssp import ASN1_INTEGER
from simple_rdp.credssp import ASN1_OCTET_STRING
from simple_rdp.credssp import ASN1_SEQUENCE
from simple_rdp.credssp import CREDSSP_VERSION
from simple_rdp.credssp import NONCE_SIZE
from simple_rdp.credssp import _decode_asn1_element
from simple_rdp.credssp import _decode_asn1_length
from simple_rdp.credssp import _encode_asn1_context
from simple_rdp.credssp import _encode_asn1_integer
from simple_rdp.credssp import _encode_asn1_length
from simple_rdp.credssp import _encode_asn1_octet_string
from simple_rdp.credssp import _encode_asn1_sequence
from simple_rdp.credssp import build_ts_credentials
from simple_rdp.credssp import build_ts_request
from simple_rdp.credssp import build_ts_request_with_credentials
from simple_rdp.credssp import build_ts_request_with_pub_key_auth
from simple_rdp.credssp import parse_ts_request


class TestConstants:
    """Tests for CredSSP constants."""

    def test_credssp_version(self) -> None:
        """Test CredSSP version constant."""
        assert CREDSSP_VERSION == 6

    def test_nonce_size(self) -> None:
        """Test nonce size constant."""
        assert NONCE_SIZE == 32

    def test_asn1_tags(self) -> None:
        """Test ASN.1 tag constants."""
        assert ASN1_SEQUENCE == 0x30
        assert ASN1_CONTEXT_0 == 0xA0
        assert ASN1_INTEGER == 0x02
        assert ASN1_OCTET_STRING == 0x04


class TestAsn1LengthEncoding:
    """Tests for ASN.1 length encoding."""

    def test_encode_short_length(self) -> None:
        """Test encoding short lengths (< 128)."""
        assert _encode_asn1_length(0) == bytes([0])
        assert _encode_asn1_length(127) == bytes([127])
        assert _encode_asn1_length(50) == bytes([50])

    def test_encode_medium_length(self) -> None:
        """Test encoding medium lengths (128-255)."""
        assert _encode_asn1_length(128) == bytes([0x81, 128])
        assert _encode_asn1_length(255) == bytes([0x81, 255])

    def test_encode_long_length(self) -> None:
        """Test encoding long lengths (256-65535)."""
        result = _encode_asn1_length(256)
        assert result == bytes([0x82, 0x01, 0x00])
        result = _encode_asn1_length(1000)
        assert result == bytes([0x82, 0x03, 0xE8])


class TestAsn1LengthDecoding:
    """Tests for ASN.1 length decoding."""

    def test_decode_short_length(self) -> None:
        """Test decoding short lengths."""
        length, consumed = _decode_asn1_length(bytes([50, 0x00]), 0)
        assert length == 50
        assert consumed == 1

    def test_decode_long_form_1_byte(self) -> None:
        """Test decoding long form 1 byte length."""
        length, consumed = _decode_asn1_length(bytes([0x81, 200]), 0)
        assert length == 200
        assert consumed == 2

    def test_decode_long_form_2_bytes(self) -> None:
        """Test decoding long form 2 byte length."""
        length, consumed = _decode_asn1_length(bytes([0x82, 0x01, 0x00]), 0)
        assert length == 256
        assert consumed == 3


class TestAsn1IntegerEncoding:
    """Tests for ASN.1 integer encoding."""

    def test_encode_small_integer(self) -> None:
        """Test encoding small integers."""
        result = _encode_asn1_integer(0)
        assert result[0] == ASN1_INTEGER
        assert result[2] == 0

    def test_encode_medium_integer(self) -> None:
        """Test encoding medium integers."""
        result = _encode_asn1_integer(100)
        assert result[0] == ASN1_INTEGER

    def test_encode_large_integer(self) -> None:
        """Test encoding large integers."""
        result = _encode_asn1_integer(65535)
        assert result[0] == ASN1_INTEGER
        assert len(result) > 3


class TestAsn1OctetString:
    """Tests for ASN.1 octet string encoding."""

    def test_encode_empty_octet_string(self) -> None:
        """Test encoding empty octet string."""
        result = _encode_asn1_octet_string(b"")
        assert result == bytes([ASN1_OCTET_STRING, 0])

    def test_encode_octet_string_with_data(self) -> None:
        """Test encoding octet string with data."""
        data = b"hello"
        result = _encode_asn1_octet_string(data)
        assert result[0] == ASN1_OCTET_STRING
        assert result[1] == len(data)
        assert result[2:] == data


class TestAsn1Context:
    """Tests for ASN.1 context-specific encoding."""

    def test_encode_context_0(self) -> None:
        """Test encoding with context tag 0."""
        content = b"\x01\x02"
        result = _encode_asn1_context(ASN1_CONTEXT_0, content)
        assert result[0] == ASN1_CONTEXT_0
        assert result[1] == len(content)
        assert result[2:] == content


class TestAsn1Sequence:
    """Tests for ASN.1 sequence encoding."""

    def test_encode_empty_sequence(self) -> None:
        """Test encoding empty sequence."""
        result = _encode_asn1_sequence(b"")
        assert result == bytes([ASN1_SEQUENCE, 0])

    def test_encode_sequence_with_content(self) -> None:
        """Test encoding sequence with content."""
        content = b"\x02\x01\x05"  # INTEGER 5
        result = _encode_asn1_sequence(content)
        assert result[0] == ASN1_SEQUENCE
        assert result[1] == len(content)
        assert result[2:] == content


class TestAsn1ElementDecoding:
    """Tests for ASN.1 element decoding."""

    def test_decode_integer_element(self) -> None:
        """Test decoding an integer element."""
        data = bytes([ASN1_INTEGER, 0x01, 0x05])
        tag, content, consumed = _decode_asn1_element(data, 0)
        assert tag == ASN1_INTEGER
        assert content == bytes([0x05])
        assert consumed == 3

    def test_decode_sequence_element(self) -> None:
        """Test decoding a sequence element."""
        inner = bytes([ASN1_INTEGER, 0x01, 0x05])
        data = bytes([ASN1_SEQUENCE, len(inner)]) + inner
        tag, content, consumed = _decode_asn1_element(data, 0)
        assert tag == ASN1_SEQUENCE
        assert content == inner
        assert consumed == len(data)


class TestTsRequest:
    """Tests for TSRequest building."""

    def test_build_ts_request_basic(self) -> None:
        """Test building basic TSRequest."""
        result = build_ts_request()
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[0] == ASN1_SEQUENCE

    def test_build_ts_request_with_nego_token(self) -> None:
        """Test building TSRequest with nego token."""
        nego_token = b"test_token_data"
        result = build_ts_request(nego_token=nego_token)
        assert isinstance(result, bytes)
        assert len(result) > len(nego_token)

    def test_build_ts_request_custom_version(self) -> None:
        """Test building TSRequest with custom version."""
        result = build_ts_request(version=3)
        assert isinstance(result, bytes)


class TestTsRequestWithPubKeyAuth:
    """Tests for TSRequest with pubKeyAuth."""

    def test_build_ts_request_with_pub_key_auth(self) -> None:
        """Test building TSRequest with pubKeyAuth."""
        pub_key_auth = b"encrypted_pub_key"
        result = build_ts_request_with_pub_key_auth(pub_key_auth)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_build_ts_request_with_client_nonce(self) -> None:
        """Test building TSRequest with client nonce."""
        pub_key_auth = b"encrypted_pub_key"
        client_nonce = b"a" * NONCE_SIZE
        result = build_ts_request_with_pub_key_auth(
            pub_key_auth=pub_key_auth,
            client_nonce=client_nonce,
        )
        assert isinstance(result, bytes)


class TestTsRequestWithCredentials:
    """Tests for TSRequest with credentials."""

    def test_build_ts_request_with_credentials(self) -> None:
        """Test building TSRequest with credentials."""
        auth_info = b"encrypted_credentials"
        result = build_ts_request_with_credentials(auth_info)
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestTsCredentials:
    """Tests for TSCredentials building."""

    def test_build_ts_credentials(self) -> None:
        """Test building TSCredentials."""
        # Build credentials with domain, user, password
        result = build_ts_credentials(
            domain="DOMAIN",
            username="user",
            password="pass",
        )
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestParseTsRequest:
    """Tests for TSRequest parsing."""

    def test_parse_ts_request_basic(self) -> None:
        """Test parsing basic TSRequest."""
        # Build a request and parse it back
        original = build_ts_request()
        result = parse_ts_request(original)
        assert "version" in result
        assert result["version"] == CREDSSP_VERSION

    def test_parse_ts_request_with_nego_token(self) -> None:
        """Test parsing TSRequest with nego token."""
        nego_token = b"test_token"
        original = build_ts_request(nego_token=nego_token)
        result = parse_ts_request(original)
        assert "nego_token" in result
        # The nego token should be recoverable


class TestCredSSPAuth:
    """Tests for CredSSPAuth class."""

    def test_credssp_auth_initialization(self) -> None:
        """Test CredSSPAuth can be initialized."""
        from simple_rdp.credssp import CredSSPAuth
        
        auth = CredSSPAuth(
            hostname="testserver",
            username="testuser",
            password="testpass",
            domain="DOMAIN",
        )
        assert auth.client_nonce is not None
        assert len(auth.client_nonce) == NONCE_SIZE
        assert auth.server_version == CREDSSP_VERSION

    def test_credssp_auth_client_nonce(self) -> None:
        """Test CredSSPAuth generates random client nonce."""
        from simple_rdp.credssp import CredSSPAuth
        
        auth1 = CredSSPAuth(hostname="test", username="u", password="p")
        auth2 = CredSSPAuth(hostname="test", username="u", password="p")
        # Nonces should be different (random)
        assert auth1.client_nonce != auth2.client_nonce

    def test_credssp_auth_server_version_setter(self) -> None:
        """Test CredSSPAuth server version setter."""
        from simple_rdp.credssp import CredSSPAuth
        
        auth = CredSSPAuth(hostname="test", username="u", password="p")
        auth.server_version = 3
        assert auth.server_version == 3

    def test_credssp_auth_pending_token_initial(self) -> None:
        """Test CredSSPAuth pending token is None initially."""
        from simple_rdp.credssp import CredSSPAuth
        
        auth = CredSSPAuth(hostname="test", username="u", password="p")
        assert auth.pending_token is None

    def test_credssp_auth_get_initial_token(self) -> None:
        """Test CredSSPAuth can get initial token."""
        from simple_rdp.credssp import CredSSPAuth
        
        auth = CredSSPAuth(
            hostname="testserver",
            username="testuser",
            password="testpass",
        )
        token = auth.get_initial_token()
        assert isinstance(token, bytes)
        assert len(token) > 0


class TestTsRequestWithNonce:
    """Tests for TSRequest with client nonce."""

    def test_build_ts_request_with_nonce(self) -> None:
        """Test building TSRequest with client nonce."""
        pub_key_auth = b"encrypted_pub_key"
        client_nonce = b"a" * NONCE_SIZE
        result = build_ts_request_with_pub_key_auth(
            pub_key_auth=pub_key_auth,
            client_nonce=client_nonce,
        )
        assert isinstance(result, bytes)
        assert len(result) > len(pub_key_auth) + NONCE_SIZE

    def test_build_ts_request_with_nego_and_nonce(self) -> None:
        """Test building TSRequest with nego token and nonce."""
        pub_key_auth = b"encrypted_pub_key"
        nego_token = b"nego_token_data"
        client_nonce = b"b" * NONCE_SIZE
        result = build_ts_request_with_pub_key_auth(
            pub_key_auth=pub_key_auth,
            nego_token=nego_token,
            client_nonce=client_nonce,
        )
        assert isinstance(result, bytes)
        assert len(result) > len(pub_key_auth) + len(nego_token) + NONCE_SIZE


class TestAsn1EncodingEdgeCases:
    """Tests for ASN.1 encoding edge cases."""

    def test_encode_asn1_length_boundary_127(self) -> None:
        """Test encoding length at boundary of 127."""
        assert _encode_asn1_length(127) == bytes([127])

    def test_encode_asn1_length_boundary_128(self) -> None:
        """Test encoding length at boundary of 128."""
        assert _encode_asn1_length(128) == bytes([0x81, 128])

    def test_encode_asn1_length_boundary_255(self) -> None:
        """Test encoding length at boundary of 255."""
        assert _encode_asn1_length(255) == bytes([0x81, 255])

    def test_encode_asn1_length_boundary_256(self) -> None:
        """Test encoding length at boundary of 256."""
        assert _encode_asn1_length(256) == bytes([0x82, 0x01, 0x00])

    def test_encode_asn1_context_higher_tag(self) -> None:
        """Test encoding context with higher tag numbers."""
        from simple_rdp.credssp import ASN1_CONTEXT_1
        from simple_rdp.credssp import ASN1_CONTEXT_2
        
        content = b"\x00\x01\x02"
        result1 = _encode_asn1_context(ASN1_CONTEXT_1, content)
        assert result1[0] == ASN1_CONTEXT_1
        
        result2 = _encode_asn1_context(ASN1_CONTEXT_2, content)
        assert result2[0] == ASN1_CONTEXT_2


class TestParseTsRequestAdvanced:
    """Advanced tests for TSRequest parsing to cover all branches."""

    def test_parse_ts_request_with_pub_key_auth(self) -> None:
        """Test parsing TSRequest with pubKeyAuth field."""
        # Build a request with pubKeyAuth and parse it back
        pub_key_auth = b"test_pub_key_auth_data"
        original = build_ts_request_with_pub_key_auth(pub_key_auth=pub_key_auth)
        result = parse_ts_request(original)
        assert "pub_key_auth" in result
        assert result["pub_key_auth"] == pub_key_auth

    def test_parse_ts_request_with_client_nonce(self) -> None:
        """Test parsing TSRequest with clientNonce field."""
        pub_key_auth = b"encrypted_key"
        client_nonce = b"c" * NONCE_SIZE
        original = build_ts_request_with_pub_key_auth(
            pub_key_auth=pub_key_auth,
            client_nonce=client_nonce,
        )
        result = parse_ts_request(original)
        assert "client_nonce" in result
        assert result["client_nonce"] == client_nonce

    def test_parse_ts_request_with_auth_info(self) -> None:
        """Test parsing TSRequest with authInfo field."""
        auth_info = b"encrypted_creds_data"
        original = build_ts_request_with_credentials(auth_info=auth_info)
        result = parse_ts_request(original)
        assert "auth_info" in result
        assert result["auth_info"] == auth_info

    def test_parse_ts_request_invalid_not_sequence(self) -> None:
        """Test parsing TSRequest fails if not a SEQUENCE."""
        # Build invalid data that's not a SEQUENCE
        invalid_data = bytes([ASN1_INTEGER, 0x01, 0x05])
        with pytest.raises(ValueError, match="Expected SEQUENCE"):
            parse_ts_request(invalid_data)


class TestCredSSPAuthAdvanced:
    """Advanced tests for CredSSPAuth class."""

    def test_credssp_auth_complete_attribute(self) -> None:
        """Test CredSSPAuth complete attribute."""
        from simple_rdp.credssp import CredSSPAuth
        
        auth = CredSSPAuth(hostname="test", username="u", password="p")
        # Initially, complete is False (depends on underlying SPNEGO context)
        # This just accesses the property
        _ = auth.complete

    def test_credssp_auth_hostname_stored(self) -> None:
        """Test CredSSPAuth stores hostname."""
        from simple_rdp.credssp import CredSSPAuth
        
        auth = CredSSPAuth(hostname="myserver.local", username="u", password="p")
        assert auth._hostname == "myserver.local"

    def test_credssp_auth_domain_stored(self) -> None:
        """Test CredSSPAuth stores domain."""
        from simple_rdp.credssp import CredSSPAuth
        
        auth = CredSSPAuth(hostname="test", username="u", password="p", domain="MYDOMAIN")
        assert auth._domain == "MYDOMAIN"


class TestAsn1LengthLarge:
    """Tests for ASN.1 length encoding with large values."""

    def test_encode_asn1_length_large_3byte(self) -> None:
        """Test encoding length requiring 3-byte form."""
        # 0x10000 = 65536
        result = _encode_asn1_length(0x10000)
        # Should use 0x83 prefix for 3-byte length
        assert result[0] == 0x83
        assert len(result) == 4

    def test_encode_asn1_length_medium_large(self) -> None:
        """Test encoding length near 2-byte boundary."""
        result = _encode_asn1_length(0xFFFF)  # 65535
        assert result[0] == 0x82
        assert result[1] == 0xFF
        assert result[2] == 0xFF


class TestCredSSPAuthComputeHash:
    """Tests for CredSSPAuth hash computation methods."""

    def test_compute_client_server_hash(self) -> None:
        """Test computing client-to-server hash."""
        from hashlib import sha256

        from simple_rdp.credssp import CLIENT_SERVER_HASH_MAGIC
        from simple_rdp.credssp import CredSSPAuth
        
        auth = CredSSPAuth(hostname="test", username="u", password="p")
        public_key = b"test_public_key_data"
        
        # Compute expected hash
        expected = sha256(CLIENT_SERVER_HASH_MAGIC + auth.client_nonce + public_key).digest()
        result = auth.compute_client_server_hash(public_key)
        
        assert result == expected

    def test_compute_server_client_hash(self) -> None:
        """Test computing server-to-client hash."""
        from hashlib import sha256

        from simple_rdp.credssp import SERVER_CLIENT_HASH_MAGIC
        from simple_rdp.credssp import CredSSPAuth
        
        auth = CredSSPAuth(hostname="test", username="u", password="p")
        public_key = b"test_public_key_data"
        
        # Compute expected hash
        expected = sha256(SERVER_CLIENT_HASH_MAGIC + auth.client_nonce + public_key).digest()
        result = auth.compute_server_client_hash(public_key)
        
        assert result == expected


class TestCredSSPAuthSetters:
    """Tests for CredSSPAuth property setters."""

    def test_set_server_public_key(self) -> None:
        """Test setting server public key."""
        from simple_rdp.credssp import CredSSPAuth
        
        auth = CredSSPAuth(hostname="test", username="u", password="p")
        public_key = b"server_public_key"
        auth.set_server_public_key(public_key)
        assert auth._server_public_key == public_key


class TestTsCredentialsBuild:
    """Tests for building TS credentials."""

    def test_build_ts_credentials_unicode(self) -> None:
        """Test building TS credentials with unicode strings."""
        result = build_ts_credentials(
            domain="MYDOMAIN",
            username="myuser",
            password="mypassword123!"
        )
        assert isinstance(result, bytes)
        # Should contain the encoded strings
        assert len(result) > 0

    def test_build_ts_credentials_empty_domain(self) -> None:
        """Test building TS credentials with empty domain."""
        result = build_ts_credentials(
            domain="",
            username="user",
            password="pass"
        )
        assert isinstance(result, bytes)


class TestAsn1IntegerEdgeCases:
    """Edge case tests for ASN.1 integer encoding."""

    def test_encode_integer_exactly_128(self) -> None:
        """Test encoding integer 128 (boundary case)."""
        result = _encode_asn1_integer(128)
        assert result[0] == ASN1_INTEGER
        # 128 needs padding to avoid negative interpretation
        assert len(result) >= 3

    def test_encode_integer_255(self) -> None:
        """Test encoding integer 255."""
        result = _encode_asn1_integer(255)
        assert result[0] == ASN1_INTEGER
        assert len(result) >= 3

    def test_encode_integer_256(self) -> None:
        """Test encoding integer 256 (2 bytes needed)."""
        result = _encode_asn1_integer(256)
        assert result[0] == ASN1_INTEGER
        assert len(result) >= 4
