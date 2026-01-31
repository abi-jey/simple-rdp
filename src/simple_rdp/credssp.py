"""
CredSSP (Credential Security Support Provider) implementation for NLA.

This module implements the CredSSP protocol as defined in MS-CSSP for
Network Level Authentication in RDP connections.
"""

import os
from hashlib import sha256
from logging import getLogger

import spnego

logger = getLogger(__name__)

# CredSSP version
CREDSSP_VERSION = 6

# Client nonce size (32 bytes for v5+)
NONCE_SIZE = 32

# Magic strings for CredSSP v5+ hash computation (including null terminator)
CLIENT_SERVER_HASH_MAGIC = b"CredSSP Client-To-Server Binding Hash\x00"
SERVER_CLIENT_HASH_MAGIC = b"CredSSP Server-To-Client Binding Hash\x00"

# ASN.1 Tag constants
ASN1_SEQUENCE = 0x30
ASN1_CONTEXT_0 = 0xA0
ASN1_CONTEXT_1 = 0xA1
ASN1_CONTEXT_2 = 0xA2
ASN1_CONTEXT_3 = 0xA3
ASN1_CONTEXT_4 = 0xA4
ASN1_CONTEXT_5 = 0xA5  # clientNonce for v5+
ASN1_INTEGER = 0x02
ASN1_OCTET_STRING = 0x04


def _encode_asn1_length(length: int) -> bytes:
    """Encode length in ASN.1 DER format."""
    if length < 0x80:
        return bytes([length])
    elif length < 0x100:
        return bytes([0x81, length])
    elif length < 0x10000:
        return bytes([0x82, (length >> 8) & 0xFF, length & 0xFF])
    else:
        return bytes([0x83, (length >> 16) & 0xFF, (length >> 8) & 0xFF, length & 0xFF])


def _encode_asn1_integer(value: int) -> bytes:
    """Encode an integer in ASN.1 DER format."""
    if value < 0x80:
        content = bytes([value])
    elif value < 0x100:
        content = bytes([0x00, value]) if value >= 0x80 else bytes([value])
    else:
        # Handle larger integers
        content = value.to_bytes((value.bit_length() + 8) // 8, "big")
        if content[0] & 0x80:
            content = b"\x00" + content
    return bytes([ASN1_INTEGER]) + _encode_asn1_length(len(content)) + content


def _encode_asn1_octet_string(data: bytes) -> bytes:
    """Encode an octet string in ASN.1 DER format."""
    return bytes([ASN1_OCTET_STRING]) + _encode_asn1_length(len(data)) + data


def _encode_asn1_context(tag: int, content: bytes) -> bytes:
    """Encode content with a context-specific tag."""
    return bytes([tag]) + _encode_asn1_length(len(content)) + content


def _encode_asn1_sequence(content: bytes) -> bytes:
    """Encode content as an ASN.1 SEQUENCE."""
    return bytes([ASN1_SEQUENCE]) + _encode_asn1_length(len(content)) + content


def _decode_asn1_length(data: bytes, offset: int) -> tuple[int, int]:
    """Decode ASN.1 DER length. Returns (length, bytes_consumed)."""
    if data[offset] < 0x80:
        return data[offset], 1
    num_octets = data[offset] & 0x7F
    length = 0
    for i in range(num_octets):
        length = (length << 8) | data[offset + 1 + i]
    return length, 1 + num_octets


def _decode_asn1_element(data: bytes, offset: int) -> tuple[int, bytes, int]:
    """Decode an ASN.1 element. Returns (tag, content, total_bytes_consumed)."""
    tag = data[offset]
    length, len_bytes = _decode_asn1_length(data, offset + 1)
    content_start = offset + 1 + len_bytes
    content = data[content_start : content_start + length]
    return tag, content, 1 + len_bytes + length


def build_ts_request(nego_token: bytes | None = None, version: int = CREDSSP_VERSION) -> bytes:
    """
    Build a TSRequest structure for CredSSP.

    TSRequest ::= SEQUENCE {
        version    [0] INTEGER,
        negoTokens [1] NegoData OPTIONAL,
        authInfo   [2] OCTET STRING OPTIONAL,
        pubKeyAuth [3] OCTET STRING OPTIONAL,
        errorCode  [4] INTEGER OPTIONAL,
        clientNonce [5] OCTET STRING OPTIONAL
    }
    """
    # Version field [0]
    version_content = _encode_asn1_integer(version)
    version_field = _encode_asn1_context(ASN1_CONTEXT_0, version_content)

    content = version_field

    # NegoTokens field [1] if present
    if nego_token:
        # NegoData ::= SEQUENCE OF SEQUENCE { negoToken [0] OCTET STRING }
        nego_token_inner = _encode_asn1_context(ASN1_CONTEXT_0, _encode_asn1_octet_string(nego_token))
        nego_data_seq = _encode_asn1_sequence(nego_token_inner)
        nego_data = _encode_asn1_sequence(nego_data_seq)
        content += _encode_asn1_context(ASN1_CONTEXT_1, nego_data)

    return _encode_asn1_sequence(content)


def build_ts_request_with_pub_key_auth(
    pub_key_auth: bytes,
    nego_token: bytes | None = None,
    client_nonce: bytes | None = None,
    version: int = CREDSSP_VERSION,
) -> bytes:
    """
    Build a TSRequest with pubKeyAuth for the final authentication step.

    For CredSSP v5+, this should include:
    - The final negoToken (if any)
    - The pubKeyAuth (encrypted hash)
    - The clientNonce (32 bytes)
    """
    version_content = _encode_asn1_integer(version)
    version_field = _encode_asn1_context(ASN1_CONTEXT_0, version_content)

    content = version_field

    # NegoTokens field [1] if present (final SPNEGO token)
    if nego_token:
        nego_token_inner = _encode_asn1_context(ASN1_CONTEXT_0, _encode_asn1_octet_string(nego_token))
        nego_data_seq = _encode_asn1_sequence(nego_token_inner)
        nego_data = _encode_asn1_sequence(nego_data_seq)
        content += _encode_asn1_context(ASN1_CONTEXT_1, nego_data)

    # pubKeyAuth field [3]
    pub_key_auth_field = _encode_asn1_context(ASN1_CONTEXT_3, _encode_asn1_octet_string(pub_key_auth))
    content += pub_key_auth_field

    # clientNonce field [5] for v5+
    if client_nonce:
        client_nonce_field = _encode_asn1_context(ASN1_CONTEXT_5, _encode_asn1_octet_string(client_nonce))
        content += client_nonce_field

    return _encode_asn1_sequence(content)


def build_ts_request_with_credentials(auth_info: bytes, version: int = CREDSSP_VERSION) -> bytes:
    """Build a TSRequest with authInfo (encrypted credentials)."""
    version_content = _encode_asn1_integer(version)
    version_field = _encode_asn1_context(ASN1_CONTEXT_0, version_content)

    auth_info_field = _encode_asn1_context(ASN1_CONTEXT_2, _encode_asn1_octet_string(auth_info))

    content = version_field + auth_info_field
    return _encode_asn1_sequence(content)


def parse_ts_request(data: bytes) -> dict[str, bytes | int | None]:
    """
    Parse a TSRequest structure.

    Returns a dict with keys: version, nego_token, auth_info, pub_key_auth, error_code, client_nonce
    """
    result: dict[str, bytes | int | None] = {
        "version": None,
        "nego_token": None,
        "auth_info": None,
        "pub_key_auth": None,
        "error_code": None,
        "client_nonce": None,
    }

    offset = 0

    # Outer SEQUENCE
    tag, content, _ = _decode_asn1_element(data, offset)
    if tag != ASN1_SEQUENCE:
        raise ValueError(f"Expected SEQUENCE, got {tag:#x}")

    # Parse fields within the sequence
    inner_offset = 0
    while inner_offset < len(content):
        field_tag, field_content, field_len = _decode_asn1_element(content, inner_offset)
        inner_offset += field_len

        if field_tag == ASN1_CONTEXT_0:  # version
            _, int_content, _ = _decode_asn1_element(field_content, 0)
            result["version"] = int.from_bytes(int_content, "big")

        elif field_tag == ASN1_CONTEXT_1:  # negoTokens
            # NegoData is SEQUENCE OF SEQUENCE { negoToken [0] OCTET STRING }
            _, outer_seq, _ = _decode_asn1_element(field_content, 0)
            _, inner_seq, _ = _decode_asn1_element(outer_seq, 0)
            _, token_ctx, _ = _decode_asn1_element(inner_seq, 0)
            _, token_data, _ = _decode_asn1_element(token_ctx, 0)
            result["nego_token"] = token_data

        elif field_tag == ASN1_CONTEXT_2:  # authInfo
            _, auth_data, _ = _decode_asn1_element(field_content, 0)
            result["auth_info"] = auth_data

        elif field_tag == ASN1_CONTEXT_3:  # pubKeyAuth
            _, pub_key_data, _ = _decode_asn1_element(field_content, 0)
            result["pub_key_auth"] = pub_key_data

        elif field_tag == ASN1_CONTEXT_4:  # errorCode
            _, err_content, _ = _decode_asn1_element(field_content, 0)
            result["error_code"] = int.from_bytes(err_content, "big")

        elif field_tag == ASN1_CONTEXT_5:  # clientNonce
            _, nonce_data, _ = _decode_asn1_element(field_content, 0)
            result["client_nonce"] = nonce_data

    return result


def build_ts_credentials(domain: str, username: str, password: str) -> bytes:
    """
    Build TSCredentials structure.

    TSCredentials ::= SEQUENCE {
        credType    [0] INTEGER,
        credentials [1] OCTET STRING
    }

    For password credentials (credType = 1):
    TSPasswordCreds ::= SEQUENCE {
        domainName  [0] OCTET STRING,
        userName    [1] OCTET STRING,
        password    [2] OCTET STRING
    }
    """
    # Encode strings as UTF-16LE (as per MS-CSSP)
    domain_bytes = domain.encode("utf-16-le")
    username_bytes = username.encode("utf-16-le")
    password_bytes = password.encode("utf-16-le")

    # TSPasswordCreds
    domain_field = _encode_asn1_context(ASN1_CONTEXT_0, _encode_asn1_octet_string(domain_bytes))
    username_field = _encode_asn1_context(ASN1_CONTEXT_1, _encode_asn1_octet_string(username_bytes))
    password_field = _encode_asn1_context(ASN1_CONTEXT_2, _encode_asn1_octet_string(password_bytes))

    ts_password_creds = _encode_asn1_sequence(domain_field + username_field + password_field)

    # TSCredentials
    cred_type_field = _encode_asn1_context(ASN1_CONTEXT_0, _encode_asn1_integer(1))  # 1 = password
    credentials_field = _encode_asn1_context(ASN1_CONTEXT_1, _encode_asn1_octet_string(ts_password_creds))

    return _encode_asn1_sequence(cred_type_field + credentials_field)


class CredSSPAuth:
    """
    CredSSP authentication handler.

    Manages the SPNEGO authentication and CredSSP message exchange.
    """

    def __init__(
        self,
        hostname: str,
        username: str,
        password: str,
        domain: str = "",
    ) -> None:
        """
        Initialize CredSSP authentication.

        Args:
            hostname: The target server hostname.
            username: The username for authentication.
            password: The password for authentication.
            domain: The domain for authentication (optional).
        """
        self._hostname = hostname
        self._username = username
        self._password = password
        self._domain = domain
        self._server_public_key: bytes | None = None
        self._client_nonce: bytes = os.urandom(NONCE_SIZE)
        self._server_version: int = CREDSSP_VERSION
        self._pending_token: bytes | None = None  # Store token to send with pubKeyAuth

        # Create SPNEGO context for NTLM authentication
        self._spnego_ctx = spnego.client(
            username=username,
            password=password,
            hostname=hostname,
            service="TERMSRV",
            protocol="ntlm",
        )

    @property
    def client_nonce(self) -> bytes:
        """Return the client nonce for v5+ authentication."""
        return self._client_nonce

    @property
    def server_version(self) -> int:
        """Return the server's CredSSP version."""
        return self._server_version

    @server_version.setter
    def server_version(self, version: int) -> None:
        """Set the server's CredSSP version."""
        self._server_version = version

    @property
    def pending_token(self) -> bytes | None:
        """Return any pending SPNEGO token to send with pubKeyAuth."""
        return self._pending_token

    def get_initial_token(self) -> bytes:
        """Get the initial SPNEGO token to send to the server."""
        token = self._spnego_ctx.step()
        if token is None:
            raise RuntimeError("Failed to generate initial SPNEGO token")
        return bytes(token)

    def process_challenge(self, server_token: bytes) -> bytes | None:
        """
        Process a challenge token from the server.

        Returns the response token, or None if authentication is complete.
        Note: For v5+, the final token should be sent WITH pubKeyAuth.
        """
        result = self._spnego_ctx.step(server_token)
        token = bytes(result) if result is not None else None

        # If SPNEGO is complete after this step, store the token to send with pubKeyAuth
        if token is not None and self._spnego_ctx.complete:
            self._pending_token = token
            return None  # Don't send separately; will be sent with pubKeyAuth

        return token

    @property
    def complete(self) -> bool:
        """Return whether authentication is complete."""
        return bool(self._spnego_ctx.complete)

    def set_server_public_key(self, public_key: bytes) -> None:
        """Store the server's public key for verification."""
        self._server_public_key = public_key

    def compute_client_server_hash(self, public_key: bytes) -> bytes:
        """
        Compute the Client-To-Server hash for CredSSP v5+.

        Hash = SHA256(ClientServerHashMagic || ClientNonce || SubjectPublicKey)
        """
        hash_input = CLIENT_SERVER_HASH_MAGIC + self._client_nonce + public_key
        return sha256(hash_input).digest()

    def compute_server_client_hash(self, public_key: bytes) -> bytes:
        """
        Compute the Server-To-Client hash for CredSSP v5+.

        Hash = SHA256(ServerClientHashMagic || ClientNonce || SubjectPublicKey)
        """
        hash_input = SERVER_CLIENT_HASH_MAGIC + self._client_nonce + public_key
        return sha256(hash_input).digest()

    def wrap_public_key(self, public_key: bytes) -> bytes:
        """
        Wrap (encrypt) the public key for pubKeyAuth.

        For CredSSP v5+, we hash the public key with the nonce.
        For v2-4, we encrypt the raw public key.
        """
        if self._server_version >= 5:
            # v5+: Encrypt the SHA-256 hash
            hash_value = self.compute_client_server_hash(public_key)
            logger.debug(f"CredSSP v{self._server_version}: using hash-based pubKeyAuth")
            return bytes(self._spnego_ctx.wrap(hash_value, encrypt=True).data)
        else:
            # v2-4: Encrypt the raw public key
            logger.debug(f"CredSSP v{self._server_version}: using raw pubKeyAuth")
            return bytes(self._spnego_ctx.wrap(public_key, encrypt=True).data)

    def verify_server_public_key(self, encrypted_response: bytes, public_key: bytes) -> bool:
        """
        Verify the server's public key response.

        For v5+: Server sends encrypted hash using ServerClientHashMagic.
        For v2-4: Server sends encrypted (public_key[0] + 1) || public_key[1:].
        """
        decrypted = bytes(self._spnego_ctx.unwrap(encrypted_response).data)

        if self._server_version >= 5:
            expected_hash = self.compute_server_client_hash(public_key)
            if decrypted != expected_hash:
                logger.warning("Server public key hash verification failed")
                return False
            logger.debug("Server public key hash verified successfully")
            return True
        else:
            # v2-4: First byte should be incremented by 1
            expected = bytes([(public_key[0] + 1) & 0xFF]) + public_key[1:]
            if decrypted != expected:
                logger.warning("Server public key verification failed (v2-4 mode)")
                return False
            logger.debug("Server public key verified successfully (v2-4 mode)")
            return True

    def unwrap_public_key(self, wrapped_data: bytes) -> bytes:
        """Unwrap (decrypt) the server's public key response."""
        return bytes(self._spnego_ctx.unwrap(wrapped_data).data)

    def wrap_credentials(self, domain: str, username: str, password: str) -> bytes:
        """Encrypt the credentials for authInfo."""
        ts_credentials = build_ts_credentials(domain, username, password)
        return bytes(self._spnego_ctx.wrap(ts_credentials, encrypt=True).data)
