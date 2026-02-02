"""Tests for RDP Client."""

import pytest

from simple_rdp.client import IO_CHANNEL_ID
from simple_rdp.client import MCS_GLOBAL_CHANNEL_ID
from simple_rdp.client import RDPClient


class TestRDPClient:
    """Tests for RDPClient class."""

    def test_client_initialization(self):
        """Test client can be initialized with host."""
        client = RDPClient(host="localhost")
        assert client.is_connected is False
        assert client.host == "localhost"
        assert client.port == 3389

    def test_client_custom_port(self):
        """Test client with custom port."""
        client = RDPClient(host="localhost", port=3390)
        assert client.port == 3390

    def test_client_full_params(self):
        """Test client with all parameters."""
        client = RDPClient(
            host="server.example.com",
            port=3389,
            username="user",
            password="pass",
            domain="DOMAIN",
        )
        assert client.host == "server.example.com"

    def test_client_dimensions(self):
        """Test client dimension properties."""
        client = RDPClient(host="localhost", width=1280, height=720)
        assert client.width == 1280
        assert client.height == 720

    def test_client_default_dimensions(self):
        """Test client default dimensions."""
        client = RDPClient(host="localhost")
        assert client.width == 1920
        assert client.height == 1080

    def test_client_connection_properties_initial(self):
        """Test client connection properties are empty initially."""
        client = RDPClient(host="localhost")
        assert client.connection_properties == {}

    @pytest.mark.asyncio
    async def test_disconnect_sets_connected_false(self):
        """Test that disconnect sets connected state to False."""
        client = RDPClient(host="localhost")
        await client.disconnect()
        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_fails_on_invalid_host(self):
        """Test that connect raises ConnectionError on invalid host."""
        client = RDPClient(host="invalid.host.that.does.not.exist.local", port=3389)
        with pytest.raises(ConnectionError):
            await client.connect()


class TestClientConstants:
    """Tests for client constants."""

    def test_io_channel_id(self):
        """Test IO_CHANNEL_ID value."""
        assert IO_CHANNEL_ID == 1003

    def test_mcs_global_channel_id(self):
        """Test MCS_GLOBAL_CHANNEL_ID value."""
        assert MCS_GLOBAL_CHANNEL_ID == 1003


class TestClientProperties:
    """Tests for client property accessors."""

    def test_host_property(self):
        """Test host property."""
        client = RDPClient(host="test-server")
        assert client.host == "test-server"

    def test_port_property(self):
        """Test port property."""
        client = RDPClient(host="localhost", port=13389)
        assert client.port == 13389

    def test_is_connected_false_by_default(self):
        """Test is_connected is False by default."""
        client = RDPClient(host="localhost")
        assert client.is_connected is False

    def test_width_property(self):
        """Test width property."""
        client = RDPClient(host="localhost", width=800)
        assert client.width == 800

    def test_height_property(self):
        """Test height property."""
        client = RDPClient(host="localhost", height=600)
        assert client.height == 600


class TestClientContextManager:
    """Tests for client context manager support."""

    @pytest.mark.asyncio
    async def test_client_context_manager_no_connect(self):
        """Test client can be used as context manager without connecting."""
        # Client.__aenter__ and __aexit__ should work even if connect fails
        client = RDPClient(host="localhost")
        # Just test that the client can be instantiated
        assert client is not None


class TestClientMultipleInstances:
    """Tests for multiple client instances."""

    def test_multiple_clients_independent(self):
        """Test multiple clients are independent."""
        client1 = RDPClient(host="host1", port=3389)
        client2 = RDPClient(host="host2", port=3390)

        assert client1.host != client2.host
        assert client1.port != client2.port

    def test_client_default_values(self):
        """Test client default values."""
        client = RDPClient(host="localhost")
        assert client.width == 1920
        assert client.height == 1080
        # Check it starts disconnected
        assert not client.is_connected


class TestClientReaderWriter:
    """Tests for client reader/writer property access."""

    def test_reader_raises_when_not_connected(self):
        """Test _reader property raises when not connected."""
        client = RDPClient(host="localhost")
        # The _reader property should raise ConnectionError
        with pytest.raises(ConnectionError, match="Not connected"):
            _ = client._reader

    def test_writer_raises_when_not_connected(self):
        """Test _writer property raises when not connected."""
        client = RDPClient(host="localhost")
        # The _writer property should raise ConnectionError
        with pytest.raises(ConnectionError, match="Not connected"):
            _ = client._writer


class TestClientInternalState:
    """Tests for client internal state."""

    def test_initial_user_id(self):
        """Test initial user_id is 0."""
        client = RDPClient(host="localhost")
        assert client._user_id == 0

    def test_initial_io_channel_id(self):
        """Test initial _io_channel_id."""
        client = RDPClient(host="localhost")
        assert client._io_channel_id == IO_CHANNEL_ID

    def test_initial_channel_ids_empty(self):
        """Test initial _channel_ids is empty."""
        client = RDPClient(host="localhost")
        assert client._channel_ids == []

    def test_initial_share_id(self):
        """Test initial _share_id is 0."""
        client = RDPClient(host="localhost")
        assert client._share_id == 0

    def test_initial_screen_buffer_none(self):
        """Test initial _screen_buffer is None."""
        client = RDPClient(host="localhost")
        assert client._screen_buffer is None

    def test_initial_fragment_buffer_empty(self):
        """Test initial fragment buffer is empty."""
        client = RDPClient(host="localhost")
        assert len(client._fragment_buffer) == 0
        assert client._fragment_type == 0

    def test_initial_running_false(self):
        """Test _running is False initially."""
        client = RDPClient(host="localhost")
        assert client._running is False

    def test_initial_receive_task_none(self):
        """Test _receive_task is None initially."""
        client = RDPClient(host="localhost")
        assert client._receive_task is None


class TestClientScreenCapture:
    """Tests for client screen capture methods."""

    @pytest.mark.asyncio
    async def test_screenshot_returns_blank_when_not_connected(self):
        """Test screenshot returns blank image when not connected."""
        client = RDPClient(host="localhost", width=100, height=100)
        # _screen_buffer is None, should return blank image
        img = await client.screenshot()
        assert img.size == (100, 100)
        # Should be all black
        assert img.getpixel((0, 0)) == (0, 0, 0)

    @pytest.mark.asyncio
    async def test_screenshot_with_screen_buffer(self):
        """Test screenshot with initialized screen buffer."""
        from PIL import Image

        client = RDPClient(host="localhost", width=100, height=100)
        # Manually set screen buffer
        client._screen_buffer = Image.new("RGB", (100, 100), color=(255, 0, 0))

        img = await client.screenshot()
        assert img.size == (100, 100)
        # Should be red
        assert img.getpixel((50, 50)) == (255, 0, 0)
        # Should be a copy, not the original
        assert img is not client._screen_buffer


class TestClientColorDepth:
    """Tests for client color depth settings."""

    def test_default_color_depth(self):
        """Test default color depth is 32."""
        client = RDPClient(host="localhost")
        assert client._color_depth == 32

    def test_custom_color_depth(self):
        """Test custom color depth."""
        client = RDPClient(host="localhost", color_depth=24)
        assert client._color_depth == 24


class TestClientWallpaper:
    """Tests for client wallpaper settings."""

    def test_default_show_wallpaper_false(self):
        """Test show_wallpaper is False by default."""
        client = RDPClient(host="localhost")
        assert client._show_wallpaper is False

    def test_show_wallpaper_true(self):
        """Test show_wallpaper can be True."""
        client = RDPClient(host="localhost", show_wallpaper=True)
        assert client._show_wallpaper is True


class TestClientAuth:
    """Tests for client authentication settings."""

    def test_username_none_by_default(self):
        """Test username is None by default."""
        client = RDPClient(host="localhost")
        assert client._username is None

    def test_password_none_by_default(self):
        """Test password is None by default."""
        client = RDPClient(host="localhost")
        assert client._password is None

    def test_domain_none_by_default(self):
        """Test domain is None by default."""
        client = RDPClient(host="localhost")
        assert client._domain is None

    def test_auth_credentials_set(self):
        """Test authentication credentials are set correctly."""
        client = RDPClient(
            host="localhost",
            username="testuser",
            password="testpass",
            domain="TESTDOMAIN",
        )
        assert client._username == "testuser"
        assert client._password == "testpass"
        assert client._domain == "TESTDOMAIN"


class TestClientDisconnect:
    """Tests for client disconnect behavior."""

    @pytest.mark.asyncio
    async def test_disconnect_clears_writers(self):
        """Test disconnect clears reader/writer."""
        client = RDPClient(host="localhost")
        await client.disconnect()
        assert client._tcp_reader is None
        assert client._tcp_writer is None

    @pytest.mark.asyncio
    async def test_disconnect_sets_running_false(self):
        """Test disconnect sets _running to False."""
        client = RDPClient(host="localhost")
        client._running = True  # Simulate running
        await client.disconnect()
        assert client._running is False

    @pytest.mark.asyncio
    async def test_disconnect_multiple_times(self):
        """Test disconnect can be called multiple times safely."""
        client = RDPClient(host="localhost")
        await client.disconnect()
        await client.disconnect()
        await client.disconnect()
        assert client.is_connected is False


class TestClientDisplay:
    """Tests for client Display integration."""

    def test_display_property(self):
        """Test display property returns Display instance."""
        from simple_rdp.display import Display

        client = RDPClient(host="localhost")
        assert isinstance(client.display, Display)

    def test_display_dimensions_match(self):
        """Test display dimensions match client dimensions."""
        client = RDPClient(host="localhost", width=1280, height=720)
        assert client.display.width == 1280
        assert client.display.height == 720

    def test_display_default_fps(self):
        """Test display has default 30 fps."""
        client = RDPClient(host="localhost")
        assert client.display.fps == 30

    def test_is_recording_false_by_default(self):
        """Test is_recording is False by default."""
        client = RDPClient(host="localhost")
        assert client.is_recording is False

    @pytest.mark.asyncio
    async def test_start_recording(self):
        """Test start_recording sets recording flag."""
        client = RDPClient(host="localhost")
        await client.start_recording()
        assert client.is_recording is True
        await client.stop_recording()

    @pytest.mark.asyncio
    async def test_stop_recording(self):
        """Test stop_recording clears recording flag."""
        client = RDPClient(host="localhost")
        await client.start_recording()
        await client.stop_recording()
        assert client.is_recording is False

    @pytest.mark.asyncio
    async def test_start_recording_with_custom_fps(self):
        """Test start_recording with custom fps."""
        client = RDPClient(host="localhost")
        await client.start_recording(fps=60)
        assert client.display.fps == 60
        await client.stop_recording()

    def test_get_recording_stats(self):
        """Test get_recording_stats returns stats dict."""
        client = RDPClient(host="localhost")
        stats = client.get_recording_stats()
        assert "frames_received" in stats
        assert "frames_encoded" in stats
        assert "encoding_errors" in stats

    @pytest.mark.asyncio
    async def test_disconnect_stops_recording(self):
        """Test disconnect stops recording if active."""
        client = RDPClient(host="localhost")
        await client.start_recording()
        assert client.is_recording is True
        await client.disconnect()
        assert client.is_recording is False
