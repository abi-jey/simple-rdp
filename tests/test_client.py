"""Tests for RDP Client."""

import pytest

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
