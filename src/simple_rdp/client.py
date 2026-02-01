"""
RDP Client - Main client class for establishing RDP connections.
"""

import asyncio
import contextlib
import ssl
import struct
import time
from asyncio import StreamReader
from asyncio import StreamWriter
from asyncio import open_connection
from logging import getLogger
from typing import Any
from typing import Self

from PIL import Image

from simple_rdp.capabilities import build_client_capabilities
from simple_rdp.credssp import CredSSPAuth
from simple_rdp.credssp import build_ts_request
from simple_rdp.credssp import build_ts_request_with_credentials
from simple_rdp.credssp import build_ts_request_with_pub_key_auth
from simple_rdp.credssp import parse_ts_request
from simple_rdp.mcs import build_client_cluster_data
from simple_rdp.mcs import build_client_core_data
from simple_rdp.mcs import build_client_network_data
from simple_rdp.mcs import build_client_security_data
from simple_rdp.mcs import build_mcs_attach_user_request
from simple_rdp.mcs import build_mcs_channel_join_request
from simple_rdp.mcs import build_mcs_connect_initial
from simple_rdp.mcs import build_mcs_erect_domain_request
from simple_rdp.mcs import build_mcs_send_data_request
from simple_rdp.mcs import parse_mcs_attach_user_confirm
from simple_rdp.mcs import parse_mcs_channel_join_confirm
from simple_rdp.mcs import parse_mcs_connect_response
from simple_rdp.pdu import CTRLACTION_COOPERATE
from simple_rdp.pdu import CTRLACTION_REQUEST_CONTROL
from simple_rdp.pdu import INPUT_EVENT_MOUSE
from simple_rdp.pdu import INPUT_EVENT_SCANCODE
from simple_rdp.pdu import INPUT_EVENT_UNICODE
from simple_rdp.pdu import PDUTYPE2_CONTROL
from simple_rdp.pdu import PDUTYPE2_FONTLIST
from simple_rdp.pdu import PDUTYPE2_INPUT
from simple_rdp.pdu import PDUTYPE2_REFRESH_RECT
from simple_rdp.pdu import PDUTYPE2_SUPPRESS_OUTPUT
from simple_rdp.pdu import PDUTYPE2_SYNCHRONIZE
from simple_rdp.pdu import PDUTYPE_CONFIRMACTIVEPDU
from simple_rdp.pdu import PDUTYPE_DATAPDU
from simple_rdp.pdu import PDUTYPE_DEMANDACTIVEPDU
from simple_rdp.pdu import PERF_DISABLE_WALLPAPER
from simple_rdp.pdu import SEC_INFO_PKT
from simple_rdp.pdu import UPDATETYPE_BITMAP
from simple_rdp.pdu import build_client_info_pdu
from simple_rdp.pdu import build_control_pdu
from simple_rdp.pdu import build_font_list_pdu
from simple_rdp.pdu import build_input_event_pdu
from simple_rdp.pdu import build_mouse_event
from simple_rdp.pdu import build_refresh_rect_pdu
from simple_rdp.pdu import build_scancode_event
from simple_rdp.pdu import build_suppress_output_pdu
from simple_rdp.pdu import build_synchronize_pdu
from simple_rdp.pdu import build_unicode_event
from simple_rdp.pdu import parse_bitmap_update
from simple_rdp.pdu import parse_demand_active_pdu

logger = getLogger(__name__)

# Standard RDP channels
IO_CHANNEL_ID = 1003
MCS_GLOBAL_CHANNEL_ID = 1003


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
        width: int = 1920,
        height: int = 1080,
        color_depth: int = 32,
        show_wallpaper: bool = False,
    ) -> None:
        """
        Initialize the RDP client.

        Args:
            host: The hostname or IP address of the RDP server.
            port: The port number of the RDP server (default: 3389).
            username: The username for authentication.
            password: The password for authentication.
            domain: The domain for authentication.
            width: Desktop width in pixels.
            height: Desktop height in pixels.
            color_depth: Color depth in bits per pixel.
            show_wallpaper: Whether to show desktop wallpaper (default: False for performance).
        """
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._domain = domain
        self._width = width
        self._height = height
        self._color_depth = color_depth
        self._show_wallpaper = show_wallpaper
        self._connected = False
        self._tcp_reader: StreamReader | None = None
        self._tcp_writer: StreamWriter | None = None
        self.connection_properties: dict[str, Any] = {}

        # MCS/channel state
        self._user_id: int = 0
        self._io_channel_id: int = IO_CHANNEL_ID
        self._channel_ids: list[int] = []
        self._share_id: int = 0

        # Screen state - a buffer representing the current screen
        self._screen_buffer: Image.Image | None = None
        self._screen_lock = asyncio.Lock()

        # Pointer/cursor state
        self._pointer_x: int = 0
        self._pointer_y: int = 0
        self._pointer_visible: bool = True
        self._pointer_image: Image.Image | None = None
        self._pointer_hotspot: tuple[int, int] = (0, 0)
        self._pointer_cache: dict[int, tuple[Image.Image, tuple[int, int]]] = {}

        # Fast-Path fragmentation buffer
        self._fragment_buffer: bytearray = bytearray()
        self._fragment_type: int = 0

        # Receive loop task
        self._receive_task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def _reader(self) -> StreamReader:
        """Return the TCP reader, asserting it exists."""
        if self._tcp_reader is None:
            raise ConnectionError("Not connected")
        return self._tcp_reader

    @property
    def _writer(self) -> StreamWriter:
        """Return the TCP writer, asserting it exists."""
        if self._tcp_writer is None:
            raise ConnectionError("Not connected")
        return self._tcp_writer

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
    def width(self) -> int:
        """Return the desktop width."""
        return self._width

    @property
    def height(self) -> int:
        """Return the desktop height."""
        return self._height

    @property
    def pointer_position(self) -> tuple[int, int]:
        """Return the current pointer position (x, y)."""
        return (self._pointer_x, self._pointer_y)

    @property
    def pointer_visible(self) -> bool:
        """Return whether the pointer is visible."""
        return self._pointer_visible

    @property
    def pointer_image(self) -> Image.Image | None:
        """Return the current pointer image (RGBA)."""
        return self._pointer_image

    @property
    def pointer_hotspot(self) -> tuple[int, int]:
        """Return the pointer hotspot offset (x, y)."""
        return self._pointer_hotspot

    async def connect(self) -> None:
        """
        Establish connection to the RDP server.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        # Phase 1: Connection Initiation
        await self._start_tcp_connection()
        await self._start_x224()

        # Phase 2: TLS Upgrade (if required)
        protocol = self.connection_properties.get("protocol")
        if protocol in [b"\x00\x00\x00\x02", b"\x00\x00\x00\x01"]:
            await self._upgrade_to_tls()

        # Phase 3: NLA Authentication (if required)
        if protocol == b"\x00\x00\x00\x02":
            await self._start_nla()

        # Phase 4: Basic Settings Exchange (MCS Connect)
        await self._mcs_connect()

        # Phase 5: Channel Connection
        await self._mcs_erect_domain()
        await self._mcs_attach_user()
        await self._mcs_channel_join()

        # Phase 6: RDP Security Commencement (for standard RDP security - skipped with NLA)
        # With NLA/TLS, we skip the Security Exchange PDU

        # Phase 7: Secure Settings Exchange
        await self._send_client_info()

        # Phase 8: Licensing
        await self._handle_licensing()

        # Phase 9: Capabilities Exchange
        await self._handle_capability_exchange()

        # Phase 10: Connection Finalization
        await self._finalize_connection()

        # Initialize screen buffer
        self._screen_buffer = Image.new("RGB", (self._width, self._height), (0, 0, 0))

        # Start receive loop
        self._running = True
        self._receive_task = asyncio.create_task(self._receive_loop())

        # Request initial screen content
        await self._request_screen_refresh()

        self._connected = True
        logger.info("RDP connection established successfully")

    async def disconnect(self) -> None:
        """Disconnect from the RDP server."""
        self._running = False

        if self._receive_task:
            self._receive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._receive_task

        if self._tcp_writer:
            self._tcp_writer.close()
            try:
                await self._tcp_writer.wait_closed()
            except Exception as e:
                logger.debug(f"Error closing TCP writer (expected during shutdown): {e}")
        self._tcp_reader = None
        self._tcp_writer = None

        self._connected = False
        logger.info("Disconnected from RDP server")

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

    # ==================== Screen Capture ====================

    async def screenshot(self) -> Image.Image:
        """
        Capture the current screen.

        Returns:
            PIL Image of the current screen state.
        """
        async with self._screen_lock:
            if self._screen_buffer is None:
                return Image.new("RGB", (self._width, self._height), (0, 0, 0))
            return self._screen_buffer.copy()

    async def save_screenshot(self, path: str) -> None:
        """
        Save a screenshot to a file.

        Args:
            path: File path to save the screenshot.
        """
        img = await self.screenshot()
        img.save(path)
        logger.info(f"Screenshot saved to {path}")

    # ==================== Input Methods ====================

    async def send_key(
        self,
        key: str | int,
        is_press: bool = True,
        is_release: bool = True,
    ) -> None:
        """
        Send a keyboard key event.

        Args:
            key: Either a character string or a scan code integer.
            is_press: Whether to send key press event.
            is_release: Whether to send key release event.
        """
        events = []
        event_time = int(time.time() * 1000) & 0xFFFFFFFF

        if isinstance(key, str):
            # Send as unicode events
            for char in key:
                code = ord(char)
                if is_press:
                    events.append((event_time, INPUT_EVENT_UNICODE, build_unicode_event(code, is_release=False)))
                if is_release:
                    events.append((event_time, INPUT_EVENT_UNICODE, build_unicode_event(code, is_release=True)))
        else:
            # Send as scancode
            if is_press:
                events.append((event_time, INPUT_EVENT_SCANCODE, build_scancode_event(key, is_release=False)))
            if is_release:
                events.append((event_time, INPUT_EVENT_SCANCODE, build_scancode_event(key, is_release=True)))

        if events:
            await self._send_input_events(events)

    async def send_text(self, text: str) -> None:
        """
        Send a text string as keyboard input.

        Args:
            text: The text to type.
        """
        await self.send_key(text)

    async def mouse_move(self, x: int, y: int) -> None:
        """
        Move the mouse to a position.

        Args:
            x: X coordinate.
            y: Y coordinate.
        """
        event_time = int(time.time() * 1000) & 0xFFFFFFFF
        event_data = build_mouse_event(x, y, button=0, is_move=True)
        await self._send_input_events([(event_time, INPUT_EVENT_MOUSE, event_data)])

    async def mouse_click(
        self,
        x: int,
        y: int,
        button: int = 1,
        double_click: bool = False,
    ) -> None:
        """
        Click the mouse at a position.

        Args:
            x: X coordinate.
            y: Y coordinate.
            button: Button number (1=left, 2=right, 3=middle).
            double_click: Whether to double-click.
        """
        event_time = int(time.time() * 1000) & 0xFFFFFFFF
        events = []

        # Move to position
        events.append((event_time, INPUT_EVENT_MOUSE, build_mouse_event(x, y, button=0, is_move=True)))

        # Click down
        events.append(
            (event_time, INPUT_EVENT_MOUSE, build_mouse_event(x, y, button=button, is_down=True, is_move=False))
        )

        # Click up
        events.append(
            (event_time, INPUT_EVENT_MOUSE, build_mouse_event(x, y, button=button, is_down=False, is_move=False))
        )

        if double_click:
            # Second click
            events.append(
                (event_time, INPUT_EVENT_MOUSE, build_mouse_event(x, y, button=button, is_down=True, is_move=False))
            )
            events.append(
                (event_time, INPUT_EVENT_MOUSE, build_mouse_event(x, y, button=button, is_down=False, is_move=False))
            )

        await self._send_input_events(events)

    async def mouse_button_down(self, x: int, y: int, button: int | str = 1) -> None:
        """
        Press a mouse button down at a position.

        Args:
            x: X coordinate.
            y: Y coordinate.
            button: Button number (1=left, 2=right, 3=middle) or name ('left', 'right', 'middle').
        """
        button_num = self._normalize_button(button)
        event_time = int(time.time() * 1000) & 0xFFFFFFFF
        events = [
            (event_time, INPUT_EVENT_MOUSE, build_mouse_event(x, y, button=button_num, is_down=True, is_move=False))
        ]
        await self._send_input_events(events)

    async def mouse_button_up(self, x: int, y: int, button: int | str = 1) -> None:
        """
        Release a mouse button at a position.

        Args:
            x: X coordinate.
            y: Y coordinate.
            button: Button number (1=left, 2=right, 3=middle) or name ('left', 'right', 'middle').
        """
        button_num = self._normalize_button(button)
        event_time = int(time.time() * 1000) & 0xFFFFFFFF
        events = [
            (event_time, INPUT_EVENT_MOUSE, build_mouse_event(x, y, button=button_num, is_down=False, is_move=False))
        ]
        await self._send_input_events(events)

    async def mouse_wheel(self, x: int, y: int, delta: int) -> None:
        """
        Scroll the mouse wheel at a position.

        Args:
            x: X coordinate.
            y: Y coordinate.
            delta: Wheel delta (positive=up, negative=down). Standard is +/-120 per notch.
        """
        event_time = int(time.time() * 1000) & 0xFFFFFFFF
        event_data = build_mouse_event(x, y, button=0, is_move=False, wheel_delta=delta)
        await self._send_input_events([(event_time, INPUT_EVENT_MOUSE, event_data)])

    def _normalize_button(self, button: int | str) -> int:
        """Convert button name to number."""
        if isinstance(button, str):
            return {"left": 1, "right": 2, "middle": 3}.get(button.lower(), 1)
        return button

    async def mouse_drag(self, x1: int, y1: int, x2: int, y2: int, button: int = 1) -> None:
        """
        Drag the mouse from one position to another.

        Args:
            x1, y1: Starting position.
            x2, y2: Ending position.
            button: Button to hold during drag.
        """
        event_time = int(time.time() * 1000) & 0xFFFFFFFF
        events = []

        # Move to start position
        events.append((event_time, INPUT_EVENT_MOUSE, build_mouse_event(x1, y1, button=0, is_move=True)))

        # Button down
        events.append(
            (event_time, INPUT_EVENT_MOUSE, build_mouse_event(x1, y1, button=button, is_down=True, is_move=False))
        )

        # Move to end position
        events.append((event_time, INPUT_EVENT_MOUSE, build_mouse_event(x2, y2, button=0, is_move=True)))

        # Button up
        events.append(
            (event_time, INPUT_EVENT_MOUSE, build_mouse_event(x2, y2, button=button, is_down=False, is_move=False))
        )

        await self._send_input_events(events)

    # ==================== Connection Sequence Methods ====================

    async def _start_tcp_connection(self) -> None:
        """Start the TCP connection to the RDP server."""
        try:
            reader, writer = await open_connection(self._host, self._port)
            logger.info(f"Connected to RDP server at {self._host}:{self._port}")
            self._tcp_reader = reader
            self._tcp_writer = writer

        except Exception as e:
            logger.exception(f"Failed to connect to RDP server: {e}")
            raise ConnectionError(f"Could not connect to {self._host}:{self._port}") from e

    async def _start_x224(self) -> None:
        """Send X.224 Connection Request and handle response."""
        cookie = b"Cookie: mstshash=user\r\n"
        # RDP_NEG_REQ: type=0x01, flags=0x00, length=0x0008, protocols=0x00000003 (TLS|NLA)
        neg = b"\x01\x00\x08\x00\x03\x00\x00\x00"
        x224_length = 6 + len(cookie) + len(neg)
        x224_header = bytes([x224_length, 0xE0, 0x00, 0x00, 0x00, 0x00, 0x00])

        tpkt_length = 4 + len(x224_header) + len(cookie) + len(neg)
        tpkt_header = b"\x03\x00" + tpkt_length.to_bytes(2, "big")

        data = tpkt_header + x224_header + cookie + neg
        self._writer.write(data)
        await self._writer.drain()
        logger.debug("Sent X.224 Connection Request")

        response = await self._reader.read(1024)
        protocol = await self._parse_x224_response(response)
        self.connection_properties["protocol"] = protocol
        logger.info(f"X.224 negotiation completed, protocol: {protocol!r}")

    async def _parse_x224_response(self, data: bytes) -> bytes:
        """Parse the X.224 response from the RDP server."""
        if len(data) < 11:
            raise ConnectionError("Invalid X.224 response from server.")
        type_code = data[11]
        if type_code not in (0x02, 0x03):
            raise ConnectionError("Unexpected X.224 response type from server.")
        if type_code == 0x02:
            selected_proto = data[15:19]
            selected_proto = selected_proto[::-1]  # reverse to little-endian
            logger.debug(f"Server selected protocol: {selected_proto!r}")
            return selected_proto
        if type_code == 0x03:
            logger.info(f"Server RDP negotiation failed, code: {data[14]}")
            raise ConnectionError("RDP negotiation failed as per server response.")
        raise ConnectionError(f"Unhandled X.224 response type: data: {data!r}")

    async def _upgrade_to_tls(self) -> None:
        """Upgrade the TCP connection to TLS."""
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        logger.debug("Starting TLS Handshake...")
        try:
            await self._writer.start_tls(sslcontext=context, server_hostname=self._host)
            logger.info("TLS Handshake successful")
        except Exception as e:
            logger.error(f"TLS Handshake failed: {e}")
            raise ConnectionError("TLS Handshake failed.") from e

    async def _start_nla(self) -> None:
        """Start Network Level Authentication (NLA) using CredSSP."""
        logger.info("Starting NLA authentication...")

        if not self._username or not self._password:
            raise ConnectionError("Username and password are required for NLA authentication.")

        credssp = CredSSPAuth(
            hostname=self._host,
            username=self._username,
            password=self._password,
            domain=self._domain or "",
        )

        ssl_object = self._writer.get_extra_info("ssl_object")
        if ssl_object is None:
            raise ConnectionError("TLS connection not established - cannot perform NLA.")

        server_cert_der = ssl_object.getpeercert(binary_form=True)
        if server_cert_der is None:
            raise ConnectionError("Failed to get server certificate for NLA.")

        server_public_key = self._extract_public_key_from_cert(server_cert_der)
        logger.debug(f"Server public key length: {len(server_public_key)}")

        # Step 1: Send initial SPNEGO token
        initial_token = credssp.get_initial_token()
        ts_request = build_ts_request(nego_token=initial_token)
        await self._send_credssp_message(ts_request)
        logger.debug("Sent initial SPNEGO token")

        # Step 2: Process server challenge and complete SPNEGO
        while not credssp.complete:
            response = await self._recv_credssp_message()
            parsed = parse_ts_request(response)

            if parsed.get("version"):
                server_version = parsed["version"]
                if isinstance(server_version, int):
                    credssp.server_version = server_version
                    logger.debug(f"Server CredSSP version: {server_version}")

            if parsed.get("error_code"):
                raise ConnectionError(f"CredSSP error from server: {parsed['error_code']!r}")

            server_token = parsed.get("nego_token")
            if server_token is None:
                break

            if not isinstance(server_token, bytes):
                raise ConnectionError("Invalid nego_token type from server")

            response_token = credssp.process_challenge(server_token)

            if response_token:
                ts_request = build_ts_request(nego_token=response_token)
                await self._send_credssp_message(ts_request)
                logger.debug("Sent SPNEGO response token")

        logger.info("SPNEGO authentication completed")

        # Step 3: Send encrypted public key
        encrypted_pub_key = credssp.wrap_public_key(server_public_key)

        ts_request = build_ts_request_with_pub_key_auth(
            pub_key_auth=encrypted_pub_key,
            nego_token=credssp.pending_token,
            client_nonce=credssp.client_nonce if credssp.server_version >= 5 else None,
        )
        await self._send_credssp_message(ts_request)
        logger.debug(f"Sent encrypted public key (v{credssp.server_version} mode)")

        # Step 4: Receive and verify server's public key response
        response = await self._recv_credssp_message()
        parsed = parse_ts_request(response)

        if parsed.get("error_code"):
            raise ConnectionError(f"CredSSP public key verification failed: {parsed['error_code']!r}")

        server_pub_key_response = parsed.get("pub_key_auth")
        if server_pub_key_response is None:
            raise ConnectionError("Server did not send public key response")

        if not isinstance(server_pub_key_response, bytes):
            raise ConnectionError("Invalid pub_key_auth type from server")

        if not credssp.verify_server_public_key(server_pub_key_response, server_public_key):
            raise ConnectionError("Server public key verification failed")

        # Step 5: Send encrypted credentials
        encrypted_credentials = credssp.wrap_credentials(
            domain=self._domain or "",
            username=self._username,
            password=self._password,
        )
        ts_request = build_ts_request_with_credentials(auth_info=encrypted_credentials)
        await self._send_credssp_message(ts_request)
        logger.info("NLA authentication completed successfully")

    async def _mcs_connect(self) -> None:
        """Send MCS Connect Initial and process response."""
        # Build client data blocks
        protocol_value = 2  # PROTOCOL_HYBRID (NLA)
        if self.connection_properties.get("protocol") == b"\x00\x00\x00\x01":
            protocol_value = 1  # PROTOCOL_SSL

        user_data = (
            build_client_core_data(
                desktop_width=self._width,
                desktop_height=self._height,
                high_color_depth=self._color_depth,
                server_selected_protocol=protocol_value,
            )
            + build_client_security_data()
            + build_client_cluster_data()
            + build_client_network_data()  # No extra channels for now
        )

        mcs_ci = build_mcs_connect_initial(user_data)
        await self._send_x224_data(mcs_ci)
        logger.debug("Sent MCS Connect Initial")

        # Receive MCS Connect Response
        response = await self._recv_x224_data()
        mcs_response = parse_mcs_connect_response(response)

        if mcs_response["result"] != 0:
            raise ConnectionError(f"MCS Connect failed with result: {mcs_response['result']}")

        # Store server data
        self.connection_properties["server_data"] = mcs_response.get("server_data", {})

        # Get channel IDs from server network data
        if "network" in mcs_response.get("server_data", {}):
            net_data = mcs_response["server_data"]["network"]
            self._io_channel_id = net_data.get("mcs_channel_id", IO_CHANNEL_ID)
            self._channel_ids = net_data.get("channel_ids", [])

        logger.info("MCS Connect completed successfully")

    async def _mcs_erect_domain(self) -> None:
        """Send MCS Erect Domain Request."""
        erect_domain = build_mcs_erect_domain_request()
        await self._send_x224_data(erect_domain)
        logger.debug("Sent MCS Erect Domain Request")

    async def _mcs_attach_user(self) -> None:
        """Send MCS Attach User Request and process confirm."""
        attach_user = build_mcs_attach_user_request()
        await self._send_x224_data(attach_user)
        logger.debug("Sent MCS Attach User Request")

        # Receive Attach User Confirm
        response = await self._recv_x224_data()
        confirm = parse_mcs_attach_user_confirm(response)

        if confirm["result"] != 0:
            raise ConnectionError(f"MCS Attach User failed with result: {confirm['result']}")

        self._user_id = confirm["user_id"]
        logger.info(f"MCS Attach User completed, user_id: {self._user_id}")

    async def _mcs_channel_join(self) -> None:
        """Join MCS channels."""
        # Channels to join: user channel, I/O channel, and any virtual channels
        channels_to_join = [self._user_id, self._io_channel_id] + self._channel_ids

        for channel_id in channels_to_join:
            join_request = build_mcs_channel_join_request(self._user_id, channel_id)
            await self._send_x224_data(join_request)
            logger.debug(f"Sent MCS Channel Join Request for channel {channel_id}")

            response = await self._recv_x224_data()
            confirm = parse_mcs_channel_join_confirm(response)

            if confirm["result"] != 0:
                logger.warning(f"Failed to join channel {channel_id}: result={confirm['result']}")
            else:
                logger.debug(f"Joined channel {channel_id}")

        logger.info("MCS Channel Join completed")

    async def _send_client_info(self) -> None:
        """Send Client Info PDU."""
        # Set performance flags based on user preferences
        perf_flags = 0 if self._show_wallpaper else PERF_DISABLE_WALLPAPER

        info_pdu = build_client_info_pdu(
            domain=self._domain or "",
            username=self._username or "",
            password="",  # Password already sent via NLA
            performance_flags=perf_flags,
        )

        # Wrap in security header
        security_header = struct.pack("<I", SEC_INFO_PKT)
        pdu_data = security_header + info_pdu

        await self._send_mcs_data(pdu_data, self._io_channel_id)
        logger.debug("Sent Client Info PDU")

    async def _handle_licensing(self) -> None:
        """Handle server licensing PDUs."""
        # Receive licensing PDU(s)
        while True:
            response = await self._recv_x224_data()

            # Check if this is a licensing PDU
            if len(response) < 6:
                continue

            # Parse MCS Send Data Indication header
            if (response[0] >> 2) != 0x1A:  # MCS_TYPE_SEND_DATA_INDICATION >> 2
                # Not an MCS data PDU, might be demand active
                self._pending_data = response
                break

            # Skip MCS header and get security header
            mcs_header_len = 7  # Type + UserID + ChannelID + flags + length
            if response[6] & 0x80:
                mcs_header_len = 8

            pdu_data = response[mcs_header_len:]

            # Check security header
            if len(pdu_data) < 4:
                continue

            sec_flags = struct.unpack("<I", pdu_data[:4])[0]

            if sec_flags & 0x0080:  # SEC_LICENSE_PKT
                logger.debug("Received licensing PDU")
                # Check if this is the final "Valid Client" licensing response
                license_data = pdu_data[4:]
                if len(license_data) >= 4:
                    msg_type = license_data[0]
                    if msg_type == 0xFF:  # ERROR_ALERT
                        error_code = struct.unpack("<I", license_data[4:8])[0] if len(license_data) >= 8 else 0
                        if error_code == 0x07:  # STATUS_VALID_CLIENT
                            logger.info("Licensing completed (valid client)")
                            break
                        else:
                            logger.debug(f"License error code: {error_code:#x}")
                    continue
            else:
                # Non-licensing PDU, save for later processing
                self._pending_data = response
                break

    async def _handle_capability_exchange(self) -> None:
        """Handle Demand Active PDU and send Confirm Active PDU."""
        # Receive Demand Active PDU
        if hasattr(self, "_pending_data"):
            response = self._pending_data
            delattr(self, "_pending_data")
        else:
            response = await self._recv_x224_data()

        # Parse MCS header to get to the share control PDU
        pdu_data = self._extract_pdu_from_mcs(response)

        # Parse share control header
        if len(pdu_data) < 6:
            raise ConnectionError("Invalid Demand Active PDU")

        _total_length = struct.unpack("<H", pdu_data[0:2])[0]  # noqa: F841
        pdu_type = struct.unpack("<H", pdu_data[2:4])[0]
        _pdu_source = struct.unpack("<H", pdu_data[4:6])[0]  # noqa: F841

        if (pdu_type & 0x000F) != PDUTYPE_DEMANDACTIVEPDU:
            raise ConnectionError(f"Expected Demand Active PDU, got type {pdu_type:#x}")

        demand_active = parse_demand_active_pdu(pdu_data[6:])
        self._share_id = demand_active["share_id"]
        logger.info(f"Received Demand Active PDU, share_id: {self._share_id}")

        # Build Confirm Active PDU
        source_descriptor = b"RDP\x00"
        capabilities = build_client_capabilities(self._width, self._height, self._color_depth)

        confirm_data = bytearray()
        confirm_data += struct.pack("<I", self._share_id)
        confirm_data += struct.pack("<H", 0x03EA)  # originator ID
        confirm_data += struct.pack("<H", len(source_descriptor))
        confirm_data += struct.pack("<H", len(capabilities))
        confirm_data += source_descriptor
        confirm_data += capabilities

        # Wrap in share control header
        share_control_data = self._build_share_control_pdu(PDUTYPE_CONFIRMACTIVEPDU, bytes(confirm_data))

        await self._send_mcs_data(share_control_data, self._io_channel_id)
        logger.debug("Sent Confirm Active PDU")

    async def _finalize_connection(self) -> None:
        """Send finalization PDUs to complete the connection."""
        # Synchronize PDU
        sync_data = build_synchronize_pdu(self._user_id)
        share_data = self._build_share_data_pdu(PDUTYPE2_SYNCHRONIZE, sync_data)
        share_control = self._build_share_control_pdu(PDUTYPE_DATAPDU, share_data)
        await self._send_mcs_data(share_control, self._io_channel_id)
        logger.debug("Sent Synchronize PDU")

        # Control PDU - Cooperate
        control_data = build_control_pdu(CTRLACTION_COOPERATE)
        share_data = self._build_share_data_pdu(PDUTYPE2_CONTROL, control_data)
        share_control = self._build_share_control_pdu(PDUTYPE_DATAPDU, share_data)
        await self._send_mcs_data(share_control, self._io_channel_id)
        logger.debug("Sent Control Cooperate PDU")

        # Control PDU - Request Control
        control_data = build_control_pdu(CTRLACTION_REQUEST_CONTROL)
        share_data = self._build_share_data_pdu(PDUTYPE2_CONTROL, control_data)
        share_control = self._build_share_control_pdu(PDUTYPE_DATAPDU, share_data)
        await self._send_mcs_data(share_control, self._io_channel_id)
        logger.debug("Sent Control Request Control PDU")

        # Font List PDU
        font_data = build_font_list_pdu()
        share_data = self._build_share_data_pdu(PDUTYPE2_FONTLIST, font_data)
        share_control = self._build_share_control_pdu(PDUTYPE_DATAPDU, share_data)
        await self._send_mcs_data(share_control, self._io_channel_id)
        logger.debug("Sent Font List PDU")

        # Wait for server responses (Synchronize, Control Cooperate, Control Granted, Font Map)
        expected_responses = 4
        for _ in range(expected_responses):
            try:
                await asyncio.wait_for(self._recv_x224_data(), timeout=5.0)
                logger.debug("Received finalization response")
            except TimeoutError:
                logger.warning("Timeout waiting for finalization response")
                break

        logger.info("Connection finalization completed")

    async def _request_screen_refresh(self) -> None:
        """
        Request the server to send the current screen content.

        This sends both a Suppress Output PDU (to enable display updates)
        and a Refresh Rect PDU (to request the full screen).
        """
        # First, send Suppress Output PDU to allow display updates
        suppress_data = build_suppress_output_pdu(
            allow_display_updates=True,
            rectangle=(0, 0, self._width, self._height),
        )
        share_data = self._build_share_data_pdu(PDUTYPE2_SUPPRESS_OUTPUT, suppress_data)
        share_control = self._build_share_control_pdu(PDUTYPE_DATAPDU, share_data)
        await self._send_mcs_data(share_control, self._io_channel_id)
        logger.debug("Sent Suppress Output PDU (allow updates)")

        # Then, send Refresh Rect PDU to request full screen redraw
        refresh_data = build_refresh_rect_pdu([(0, 0, self._width, self._height)])
        share_data = self._build_share_data_pdu(PDUTYPE2_REFRESH_RECT, refresh_data)
        share_control = self._build_share_control_pdu(PDUTYPE_DATAPDU, share_data)
        await self._send_mcs_data(share_control, self._io_channel_id)
        logger.debug("Sent Refresh Rect PDU for full screen")

    # ==================== Receive Loop ====================

    async def _receive_loop(self) -> None:
        """Main loop to receive and process server PDUs."""
        while self._running:
            try:
                response = await asyncio.wait_for(self._recv_x224_data(), timeout=1.0)
                await self._process_server_pdu(response)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")
                if not self._running:
                    break

    async def _process_server_pdu(self, data: bytes) -> None:
        """Process a PDU received from the server."""
        try:
            # Check for Fast-Path marker
            if len(data) >= 2 and data[0:2] == b"\xff\x46":
                await self._process_fast_path_updates(data[2:])
                return

            pdu_data = self._extract_pdu_from_mcs(data)
            if len(pdu_data) < 6:
                return

            pdu_type = struct.unpack("<H", pdu_data[2:4])[0] & 0x000F

            if pdu_type == PDUTYPE_DATAPDU:
                await self._process_data_pdu(pdu_data[6:])
            elif pdu_type == PDUTYPE_DEMANDACTIVEPDU:
                # Deactivation/reactivation
                logger.info("Received Demand Active (reactivation)")
        except Exception as e:
            logger.debug(f"Error processing PDU: {e}")

    async def _process_fast_path_updates(self, data: bytes) -> None:
        """Process Fast-Path update PDUs."""
        # Fast-Path fragmentation constants
        FASTPATH_FRAGMENT_SINGLE = 0
        FASTPATH_FRAGMENT_LAST = 1
        FASTPATH_FRAGMENT_FIRST = 2
        FASTPATH_FRAGMENT_NEXT = 3

        offset = 0
        while offset < len(data):
            if offset + 1 > len(data):
                break

            # Parse update header
            update_header = data[offset]
            update_code = update_header & 0x0F
            fragmentation = (update_header >> 4) & 0x03
            compression = (update_header >> 6) & 0x03

            offset += 1

            # Parse compression flags if compression bit is set
            compression_flags = 0
            if compression & 0x02:
                if offset >= len(data):
                    break
                compression_flags = data[offset]
                offset += 1

            # Parse size (always 2 bytes per MS-RDPBCGR)
            if offset + 2 > len(data):
                break
            update_size = struct.unpack("<H", data[offset : offset + 2])[0]
            offset += 2

            # Get update data
            if offset + update_size > len(data):
                logger.debug(f"Fast-path update truncated: need {update_size} bytes, have {len(data) - offset}")
                break
            update_data = data[offset : offset + update_size]
            offset += update_size

            # Handle fragmentation
            if fragmentation == FASTPATH_FRAGMENT_SINGLE:
                # Single fragment - process directly
                await self._process_fast_path_update(update_code, update_data, compression_flags)
            elif fragmentation == FASTPATH_FRAGMENT_FIRST:
                # First fragment - start accumulating
                self._fragment_buffer = bytearray(update_data)
                self._fragment_type = update_code
                logger.debug(f"Fragment FIRST: type={update_code}, size={len(update_data)}")
            elif fragmentation == FASTPATH_FRAGMENT_NEXT:
                # Middle fragment - accumulate
                self._fragment_buffer.extend(update_data)
                logger.debug(f"Fragment NEXT: size={len(update_data)}, total={len(self._fragment_buffer)}")
            elif fragmentation == FASTPATH_FRAGMENT_LAST:
                # Last fragment - accumulate and process
                self._fragment_buffer.extend(update_data)
                logger.debug(f"Fragment LAST: size={len(update_data)}, total={len(self._fragment_buffer)}")
                await self._process_fast_path_update(
                    self._fragment_type, bytes(self._fragment_buffer), compression_flags
                )
                self._fragment_buffer = bytearray()

    async def _process_fast_path_update(self, update_code: int, update_data: bytes, compression_flags: int) -> None:
        """Process a complete (possibly reassembled) Fast-Path update."""
        if update_code == 0x01:  # FASTPATH_UPDATETYPE_BITMAP
            await self._process_fast_path_bitmap(update_data, compression_flags)
        elif update_code == 0x00:  # FASTPATH_UPDATETYPE_ORDERS
            pass  # Skip GDI orders for now
        elif update_code == 0x03:  # FASTPATH_UPDATETYPE_SYNCHRONIZE
            pass  # Synchronize update
        elif update_code == 0x05:  # FASTPATH_UPDATETYPE_PTR_NULL (hidden)
            self._pointer_visible = False
            logger.debug("Pointer hidden")
        elif update_code == 0x06:  # FASTPATH_UPDATETYPE_PTR_DEFAULT
            self._pointer_visible = True
            self._pointer_image = None  # Use system default
            logger.debug("Pointer set to default")
        elif update_code == 0x08:  # FASTPATH_UPDATETYPE_PTR_POSITION
            await self._process_pointer_position(update_data)
        elif update_code == 0x09:  # FASTPATH_UPDATETYPE_COLOR
            await self._process_color_pointer(update_data)
        elif update_code == 0x0A:  # FASTPATH_UPDATETYPE_CACHED
            await self._process_cached_pointer(update_data)
        elif update_code == 0x0B:  # FASTPATH_UPDATETYPE_POINTER (new pointer)
            await self._process_new_pointer(update_data)
        elif update_code == 0x0C:  # FASTPATH_UPDATETYPE_LARGE_POINTER
            await self._process_new_pointer(update_data, large=True)
        # Other update types (palette, etc.) are ignored for now

    async def _process_fast_path_bitmap(self, data: bytes, compression_flags: int) -> None:
        """Process a Fast-Path bitmap update."""
        # The data is the same format as slow-path Bitmap Update Data (TS_UPDATE_BITMAP_DATA)
        # which starts with updateType (2 bytes) + numberRectangles (2 bytes) + rectangles
        # We need to skip the updateType field (first 2 bytes)
        if len(data) < 4:
            return
        logger.debug(f"Fast-path bitmap: {len(data)} bytes, compression_flags=0x{compression_flags:02x}")
        logger.debug(f"Fast-path bitmap first 20 bytes: {data[:20].hex()}")
        update_type = struct.unpack("<H", data[0:2])[0]
        logger.debug(f"Fast-path bitmap updateType: 0x{update_type:04x}")
        await self._process_bitmap_update(data[2:])

    async def _process_pointer_position(self, data: bytes) -> None:
        """Process a Pointer Position Update."""
        if len(data) < 4:
            return
        # TS_POINTERPOSATTRIBUTE: position (4 bytes) = xPos (2) + yPos (2)
        self._pointer_x = struct.unpack("<H", data[0:2])[0]
        self._pointer_y = struct.unpack("<H", data[2:4])[0]
        self._pointer_visible = True
        logger.debug(f"Pointer position: ({self._pointer_x}, {self._pointer_y})")

    async def _process_cached_pointer(self, data: bytes) -> None:
        """Process a Cached Pointer Update."""
        if len(data) < 2:
            return
        cache_index = struct.unpack("<H", data[0:2])[0]
        if cache_index in self._pointer_cache:
            self._pointer_image, self._pointer_hotspot = self._pointer_cache[cache_index]
            self._pointer_visible = True
            logger.debug(f"Using cached pointer: index={cache_index}")
        else:
            logger.debug(f"Cached pointer not found: index={cache_index}")

    async def _process_color_pointer(self, data: bytes) -> None:
        """Process a Color Pointer Update (24-bpp)."""
        await self._parse_pointer_data(data, bpp=24)

    async def _process_new_pointer(self, data: bytes, large: bool = False) -> None:
        """Process a New Pointer Update (variable bpp)."""
        if len(data) < 2:
            return
        xor_bpp = struct.unpack("<H", data[0:2])[0]
        await self._parse_pointer_data(data[2:], bpp=xor_bpp)

    async def _parse_pointer_data(self, data: bytes, bpp: int = 24) -> None:
        """Parse pointer data from Color/New Pointer Update."""
        if len(data) < 14:
            return

        offset = 0
        cache_index = struct.unpack("<H", data[offset:offset + 2])[0]
        offset += 2

        # Hotspot: xPos (2) + yPos (2)
        hotspot_x = struct.unpack("<H", data[offset:offset + 2])[0]
        offset += 2
        hotspot_y = struct.unpack("<H", data[offset:offset + 2])[0]
        offset += 2

        width = struct.unpack("<H", data[offset:offset + 2])[0]
        offset += 2
        height = struct.unpack("<H", data[offset:offset + 2])[0]
        offset += 2

        length_and_mask = struct.unpack("<H", data[offset:offset + 2])[0]
        offset += 2
        length_xor_mask = struct.unpack("<H", data[offset:offset + 2])[0]
        offset += 2

        if len(data) < offset + length_xor_mask + length_and_mask:
            logger.debug(f"Pointer data truncated: need {offset + length_xor_mask + length_and_mask}, have {len(data)}")
            return

        xor_mask_data = data[offset:offset + length_xor_mask]
        offset += length_xor_mask
        and_mask_data = data[offset:offset + length_and_mask]

        # Create pointer image
        try:
            pointer_img = self._decode_pointer_image(
                width, height, bpp, xor_mask_data, and_mask_data
            )
            if pointer_img:
                self._pointer_image = pointer_img
                self._pointer_hotspot = (hotspot_x, hotspot_y)
                self._pointer_visible = True
                self._pointer_cache[cache_index] = (pointer_img, (hotspot_x, hotspot_y))
                logger.debug(f"New pointer: {width}x{height} bpp={bpp} hotspot=({hotspot_x},{hotspot_y}) cache={cache_index}")
        except Exception as e:
            logger.debug(f"Failed to decode pointer: {e}")

    def _decode_pointer_image(
        self, width: int, height: int, bpp: int, xor_data: bytes, and_data: bytes
    ) -> Image.Image | None:
        """Decode pointer bitmap data into an RGBA image."""
        if width == 0 or height == 0:
            return None

        # Create RGBA image
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        pixels = img.load()

        bytes_per_pixel = bpp // 8
        # XOR mask is bottom-up, padded to 2-byte boundary per row
        xor_row_size = ((width * bytes_per_pixel + 1) // 2) * 2
        # AND mask is 1-bpp, bottom-up, padded to 2-byte boundary per row
        and_row_size = ((width + 15) // 16) * 2

        for row in range(height):
            # Bottom-up: first row in data is bottom row of image
            src_row = height - 1 - row

            for col in range(width):
                # Get AND mask bit (1 = transparent, 0 = use XOR color)
                if and_data:
                    and_byte_idx = src_row * and_row_size + col // 8
                    and_bit = 7 - (col % 8)
                    if and_byte_idx < len(and_data):
                        is_transparent = (and_data[and_byte_idx] >> and_bit) & 1
                    else:
                        is_transparent = 1
                else:
                    is_transparent = 0

                # Get XOR color
                xor_offset = src_row * xor_row_size + col * bytes_per_pixel
                if xor_offset + bytes_per_pixel <= len(xor_data):
                    if bpp == 32:
                        b = xor_data[xor_offset]
                        g = xor_data[xor_offset + 1]
                        r = xor_data[xor_offset + 2]
                        a = xor_data[xor_offset + 3] if bytes_per_pixel >= 4 else 255
                    elif bpp == 24:
                        b = xor_data[xor_offset]
                        g = xor_data[xor_offset + 1]
                        r = xor_data[xor_offset + 2]
                        a = 255
                    elif bpp == 16:
                        pixel = struct.unpack("<H", xor_data[xor_offset:xor_offset + 2])[0]
                        r = ((pixel >> 10) & 0x1F) << 3
                        g = ((pixel >> 5) & 0x1F) << 3
                        b = (pixel & 0x1F) << 3
                        a = 255
                    else:
                        r = g = b = 0
                        a = 255
                else:
                    r = g = b = 0
                    a = 255

                if is_transparent:
                    # Check for XOR cursor (inverted colors)
                    if r != 0 or g != 0 or b != 0:
                        # XOR cursor - use semi-transparent
                        pixels[col, row] = (r, g, b, 128)
                    else:
                        # Fully transparent
                        pixels[col, row] = (0, 0, 0, 0)
                else:
                    pixels[col, row] = (r, g, b, a if bpp == 32 else 255)

        return img

    async def _process_data_pdu(self, data: bytes) -> None:
        """Process a Share Data PDU."""
        if len(data) < 12:
            return

        # Share data header
        _share_id = struct.unpack("<I", data[0:4])[0]  # noqa: F841
        pdu_type2 = data[8]

        pdu_content = data[12:]

        if pdu_type2 == 0x02:  # PDUTYPE2_UPDATE
            await self._process_update_pdu(pdu_content)

    async def _process_update_pdu(self, data: bytes) -> None:
        """Process an Update PDU."""
        if len(data) < 2:
            return

        update_type = struct.unpack("<H", data[0:2])[0]

        if update_type == UPDATETYPE_BITMAP:
            await self._process_bitmap_update(data[2:])

    async def _process_bitmap_update(self, data: bytes) -> None:
        """Process a Bitmap Update and update the screen buffer."""
        bitmaps = parse_bitmap_update(data)

        async with self._screen_lock:
            if self._screen_buffer is None:
                return

            for bitmap in bitmaps:
                try:
                    await self._apply_bitmap(bitmap)
                except Exception as e:
                    logger.debug(f"Error applying bitmap: {e}")

    async def _apply_bitmap(self, bitmap: dict[str, Any]) -> None:
        """Apply a bitmap update to the screen buffer."""
        if self._screen_buffer is None:
            return

        width = bitmap["width"]
        height = bitmap["height"]
        bpp = bitmap["bpp"]
        flags = bitmap["flags"]
        data = bitmap["data"]

        # Check if compressed
        is_compressed = flags & 0x0001
        has_compression_header = not (flags & 0x0400)  # NO_BITMAP_COMPRESSION_HDR

        if is_compressed:
            # Decompress using RLE in a thread pool to avoid blocking the event loop
            try:
                from simple_rdp.rle import decompress_rle

                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(
                    None,  # Use default ThreadPoolExecutor
                    decompress_rle,
                    data,
                    width,
                    height,
                    bpp,
                    has_compression_header,
                )
            except Exception as e:
                logger.debug(f"RLE decompression failed: {e}")
                return

        # Convert raw bitmap data to image
        try:
            if bpp == 32:
                rawmode = "BGRX"  # 32-bit with alpha/padding
                expected_size = width * height * 4
            elif bpp == 24:
                rawmode = "BGR"
                expected_size = width * height * 3
            elif bpp in (15, 16):
                rawmode = "BGR;16" if bpp == 16 else "BGR;15"
                expected_size = width * height * 2
            elif bpp == 8:
                rawmode = "P"
                expected_size = width * height
            else:
                logger.debug(f"Unsupported bpp: {bpp}")
                return

            if len(data) < expected_size:
                logger.debug(f"Bitmap data too short: {len(data)} < {expected_size}")
                return

            # RDP bitmaps are bottom-up, we need to flip them
            # Create image from raw data using the 'raw' decoder with proper rawmode
            img = Image.frombytes("RGB", (width, height), data[:expected_size], "raw", rawmode)

            # Flip vertically (RDP sends bottom-up)
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

            # Paste onto screen buffer
            x = bitmap["dest_left"]
            y = bitmap["dest_top"]
            self._screen_buffer.paste(img, (x, y))

        except Exception as e:
            logger.debug(f"Error creating bitmap image: {e}")

    # ==================== Input Sending ====================

    async def _send_input_events(self, events: list[tuple[int, int, bytes]]) -> None:
        """Send input events to the server."""
        input_pdu = build_input_event_pdu(events)
        share_data = self._build_share_data_pdu(PDUTYPE2_INPUT, input_pdu)
        share_control = self._build_share_control_pdu(PDUTYPE_DATAPDU, share_data)
        await self._send_mcs_data(share_control, self._io_channel_id)

    # ==================== PDU Building Helpers ====================

    def _build_share_control_pdu(self, pdu_type: int, data: bytes) -> bytes:
        """Build a Share Control PDU."""
        total_length = 6 + len(data)
        header = struct.pack("<HHH", total_length, pdu_type | 0x0010, self._user_id)
        return header + data

    def _build_share_data_pdu(self, pdu_type2: int, data: bytes) -> bytes:
        """Build a Share Data PDU."""
        header = bytearray()
        header += struct.pack("<I", self._share_id)
        header += bytes([0])  # padding
        header += bytes([0x01])  # stream ID = STREAM_MED
        header += struct.pack("<H", len(data) + 4)  # uncompressed length
        header += bytes([pdu_type2])
        header += bytes([0])  # compressed type
        header += struct.pack("<H", 0)  # compressed length
        return bytes(header) + data

    def _extract_pdu_from_mcs(self, data: bytes) -> bytes:
        """
        Extract PDU data from MCS Send Data Indication.

        Format:
        - Byte 0: Type (0x68 for Send Data Indication)
        - Bytes 1-2: Initiator (user ID - 1001)
        - Bytes 3-4: Channel ID
        - Byte 5: dataPriority (2 bits) + segmentation (2 bits) + padding
        - Bytes 6+: PER-encoded length (1 or 2 bytes)
        - Remaining: userData
        """
        if len(data) < 7:
            return b""

        # Check for Send Data Indication (choice 26)
        if (data[0] >> 2) != 0x1A:
            return data

        # Fixed header is 6 bytes (type + initiator + channel + flags)
        offset = 6

        # Parse PER-encoded length
        if data[offset] & 0x80:
            # 2-byte length: ((first & 0x3F) << 8) | second
            offset += 2
        else:
            # 1-byte length
            offset += 1

        return data[offset:]

    # ==================== Transport Layer ====================

    async def _send_x224_data(self, data: bytes) -> None:
        """Send data wrapped in X.224 Data TPDU."""
        x224_header = bytes([0x02, 0xF0, 0x80])
        tpkt_length = 4 + len(x224_header) + len(data)
        tpkt_header = bytes([0x03, 0x00, (tpkt_length >> 8) & 0xFF, tpkt_length & 0xFF])

        self._writer.write(tpkt_header + x224_header + data)
        await self._writer.drain()

    async def _recv_x224_data(self) -> bytes:
        """
        Receive data packet (either TPKT/X.224 or Fast-Path).

        Returns the payload data (without transport headers).
        """
        # Read first byte to determine packet type
        first_byte = await self._reader.readexactly(1)

        # Check if it's a TPKT header (version 0x03) or Fast-Path (action bits 0-1)
        if first_byte[0] == 0x03:
            # TPKT/Slow-path: Read remaining 3 bytes of TPKT header
            header_rest = await self._reader.readexactly(3)
            length = (header_rest[1] << 8) | header_rest[2]
            remaining = length - 4

            data = await self._reader.readexactly(remaining)

            # Skip X.224 header (3 bytes) if present
            if len(data) >= 3 and data[0] == 0x02:
                return data[3:]
            return data
        else:
            # Fast-Path: first byte is fpOutputHeader
            fp_header = first_byte[0]
            action = fp_header & 0x03
            flags = (fp_header >> 6) & 0x03

            if action != 0:
                # Not a fast-path PDU, might be some other format
                logger.debug(f"Unknown packet format, first byte: {first_byte[0]:#x}")
                return b""

            # Read length1
            length1 = await self._reader.readexactly(1)
            if length1[0] & 0x80:
                # 2-byte length: ((length1 & 0x7F) << 8) | length2
                length2 = await self._reader.readexactly(1)
                pdu_length = ((length1[0] & 0x7F) << 8) | length2[0]
                header_size = 3  # fpOutputHeader + length1 + length2
            else:
                # 1-byte length
                pdu_length = length1[0]
                header_size = 2  # fpOutputHeader + length1

            # Read remaining data (pdu_length includes header)
            remaining = pdu_length - header_size
            if remaining <= 0:
                return b""

            data = await self._reader.readexactly(remaining)

            # Check for encryption (flags & 0x02 = FASTPATH_OUTPUT_ENCRYPTED)
            if flags & 0x02:
                # Encrypted Fast-Path - skip 8-byte signature (we're using TLS, so this shouldn't happen)
                if len(data) >= 8:
                    data = data[8:]
                else:
                    return b""

            # Return the Fast-Path updates as-is for processing
            # We'll wrap it in a marker so the processing code knows it's Fast-Path
            return b"\xff\x46" + data  # Custom marker for Fast-Path (0xFF 0x46 = 'F')

    async def _send_mcs_data(self, data: bytes, channel_id: int) -> None:
        """Send data via MCS Send Data Request."""
        mcs_sdr = build_mcs_send_data_request(self._user_id, channel_id, user_data=data)
        await self._send_x224_data(mcs_sdr)

    async def _send_credssp_message(self, data: bytes) -> None:
        """Send a CredSSP message over the TLS connection."""
        self._writer.write(data)
        await self._writer.drain()

    async def _recv_credssp_message(self) -> bytes:
        """Receive a CredSSP message from the server."""
        header = await self._reader.read(2)
        if len(header) < 2:
            raise ConnectionError("Failed to read CredSSP message header")

        if header[0] != 0x30:
            raise ConnectionError(f"Invalid CredSSP message: expected SEQUENCE, got {header[0]:#x}")

        if header[1] < 0x80:
            total_length = header[1]
            length_bytes = 0
        elif header[1] == 0x81:
            length_data = await self._reader.read(1)
            total_length = length_data[0]
            length_bytes = 1
        elif header[1] == 0x82:
            length_data = await self._reader.read(2)
            total_length = (length_data[0] << 8) | length_data[1]
            length_bytes = 2
        else:
            raise ConnectionError(f"Unsupported ASN.1 length encoding: {header[1]:#x}")

        content = await self._reader.read(total_length)
        if len(content) < total_length:
            raise ConnectionError("Incomplete CredSSP message received")

        if length_bytes == 0:
            return header + content
        elif length_bytes == 1:
            return header + bytes([total_length]) + content
        else:
            return header + bytes([(total_length >> 8) & 0xFF, total_length & 0xFF]) + content

    def _extract_public_key_from_cert(self, cert_der: bytes) -> bytes:
        """
        Extract the raw public key from a DER-encoded certificate.

        For CredSSP, we need just the RSA public key content, not the
        full SubjectPublicKeyInfo structure.
        """
        from asn1crypto.x509 import Certificate

        cert = Certificate.load(cert_der)
        pubkey = cert["tbs_certificate"]["subject_public_key_info"]["public_key"].contents
        # Remove leading zero padding if present (common for RSA keys)
        if pubkey[0] == 0x00:
            pubkey = pubkey[1:]
        return bytes(pubkey)
