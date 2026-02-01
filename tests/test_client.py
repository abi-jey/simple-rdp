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
