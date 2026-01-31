"""
RDP Client - Main client class for establishing RDP connections.
"""

from asyncio import StreamReader, StreamWriter, open_connection
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

    async def disconnect(self) -> None:
        """Disconnect from the RDP server."""
        # TODO: Implement disconnection logic
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
            logger.error(f"Failed to connect to RDP server: {e}")
            raise ConnectionError(f"Could not connect to {self._host}:{self._port}") from e
