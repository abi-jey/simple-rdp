"""
RDP Client - Main client class for establishing RDP connections.
"""

import ssl
from asyncio import StreamReader
from asyncio import StreamWriter
from asyncio import open_connection
from logging import getLogger
from typing import Self

from simple_rdp.input import InputHandler
from simple_rdp.screen import ScreenCapture

logger = getLogger(__name__)


class RDPClient:
    """
    RDP Client for automation purposes.

    This client establishes an RDP connection and provides access to
    screen capture and input transmission for automation workflows.
    It does not provide an interactive session itself.
    """

    def __init__(
        self,
        host: str,
        port: int = 3389,
        username: str | None = None,
        password: str | None = None,
        domain: str | None = None,
    ) -> None:
        """
        Initialize the RDP client.

        Args:
            host: The hostname or IP address of the RDP server.
            port: The port number of the RDP server (default: 3389).
            username: The username for authentication.
            password: The password for authentication.
            domain: The domain for authentication.
        """
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._domain = domain
        self._connected = False
        self._screen = ScreenCapture()
        self._input = InputHandler()
        self._tcp_reader: StreamReader
        self._tcp_writer: StreamWriter
        self.connection_properties = {}

    @property
    def host(self) -> str:
        """Return the host address."""
        return self._host

    @property
    def port(self) -> int:
        """Return the port number."""
        return self._port

    @property
    def is_connected(self) -> bool:
        """Return whether the client is currently connected."""
        return self._connected

    @property
    def screen(self) -> ScreenCapture:
        """Return the screen capture handler."""
        return self._screen

    @property
    def input(self) -> InputHandler:
        """Return the input handler."""
        return self._input

    async def connect(self) -> None:
        """
        Establish connection to the RDP server.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        await self._start_tcp_connection()
        await self._start_x224()
        if self.connection_properties.get("protocol") in [b"\x00\x00\x00\x02", b"\x00\x00\x00\x01"]:
            await self._upgdate_to_tls()
        if self.connection_properties.get("protocol") == b"\x00\x00\x00\x02":
            await self._start_nla()
        else:
            raise ConnectionError("Unsupported RDP protocol selected by server.")

    async def disconnect(self) -> None:
        """Disconnect from the RDP server."""
        if self._tcp_writer:
            self._tcp_writer.close()
            await self._tcp_writer.wait_closed()
        if self._tcp_reader:
            self._tcp_reader = None  # type: ignore[assignment]

        self._connected = False

    async def __aenter__(self) -> Self:
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit."""
        await self.disconnect()

    async def _start_tcp_connection(self) -> None:
        """
        Start the TCP connection to the RDP server.
        """
        try:
            reader, writer = await open_connection(self._host, self._port)
            self._connected = True
            logger.info(f"Connected to RDP server at {self._host}:{self._port}")
            self._tcp_reader = reader
            self._tcp_writer = writer

        except Exception as e:
            logger.exception(f"Failed to connect to RDP server: {e}")
            raise ConnectionError(f"Could not connect to {self._host}:{self._port}") from e

    async def _start_x224(self) -> None:
        """
        Send an X.224 packet to the RDP server.

        Args:
            data: The packet data to send.
        """
        cookie = b"Cookie: mstshash=user\r\n"
        neg = b"\x01\x00\x08\x00\x03\x00\x00\x00"
        x224_length = 6 + len(cookie) + len(neg)
        x224_header = bytes([x224_length, 0xE0, 0x00, 0x00, 0x00, 0x00, 0x00])

        tpkt_length = 4 + len(x224_header) + len(cookie) + len(neg)
        tpkt_header = b"\x03\x00" + tpkt_length.to_bytes(2, "big")

        data = tpkt_header + x224_header + cookie + neg
        self._tcp_writer.write(data)
        await self._tcp_writer.drain()
        logger.info("Sent X.224 packet to RDP server.")
        response = await self._tcp_reader.read(1024)
        protocol = await self._parse_x224_response(response)
        self.connection_properties["protocol"] = protocol
        logger.info(f"X.224 negotiation completed with protocol: {protocol}")

    async def _parse_x224_response(self, data: bytes) -> bytes:
        """
        Parse the X.224 response from the RDP server.
        """
        if len(data) < 11:
            raise ConnectionError("Invalid X.224 response from server.")
        type_code = data[11]
        if type_code not in (0x02, 0x03):
            raise ConnectionError("Unexpected X.224 response type from server.")
        if type_code == 0x02:
            selected_proto = data[15:19]
            selected_proto = selected_proto[::-1]  # reverse to little-endian
            logger.debug(f"Server selected protocol: {selected_proto}")
            return selected_proto
        if type_code == 0x03:
            logger.info(f"Server requested RDP negotiation failed failure code: {data[14]}")
            raise ConnectionError("RDP negotiation failed as per server response.")
        raise ConnectionError(f"Unhandled X.224 response type: data: {data}")

    async def _upgdate_to_tls(self) -> None:
        """
        Upgrade the TCP connection to TLS.
        """
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        logger.info("Starting TLS Handshake...")
        try:
            await self._tcp_writer.start_tls(sslcontext=context, server_hostname=self._host)
            logger.info("TLS Handshake successful.")
        except Exception as e:
            logger.error(f"TLS Handshake failed: {e}")
            raise ConnectionError("TLS Handshake failed.") from e

    async def _start_nla(self) -> None:
        """
        Start Network Level Authentication (NLA).
        """
        logger.info("Starting NLA authentication...")
