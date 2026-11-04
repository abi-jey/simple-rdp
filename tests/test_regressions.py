"""Regression coverage for the v0.8.10 repository review findings."""

import asyncio
import shutil
import struct
import subprocess
from importlib.metadata import version
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from PIL import Image
from simple_rdp._rle import decompress_rle

import simple_rdp
from simple_rdp.client import RDPClient
from simple_rdp.display import Display
from simple_rdp.pdu import INPUT_EVENT_UNICODE


@pytest.mark.asyncio
async def test_send_text_preserves_case_and_utf16() -> None:
    client = RDPClient("unused")
    with patch.object(client, "_send_input_events", new_callable=AsyncMock) as send:
        await client.send_text("Ab1é😀", chars_per_second=0)
    events = [event for call in send.call_args_list for event in call.args[0]]
    assert all(event[1] == INPUT_EVENT_UNICODE for event in events)
    codes = [struct.unpack("<HHH", event[2]) for event in events]
    units = [unit[0] for unit in struct.iter_unpack("<H", "Ab1é😀".encode("utf-16-le"))]
    assert [code[1] for code in codes[::2]] == units
    assert [code[1] for code in codes[1::2]] == units
    assert all(code[0] == 0 for code in codes[::2])
    assert all(code[0] == 0x8000 for code in codes[1::2])


@pytest.mark.asyncio
async def test_send_key_supports_supplementary_unicode() -> None:
    client = RDPClient("unused")
    with patch.object(client, "_send_input_events", new_callable=AsyncMock) as send:
        await client.send_key("😀")
    assert [struct.unpack("<HHH", e[2])[1] for e in send.call_args.args[0]] == [0xD83D, 0xD83D, 0xDE00, 0xDE00]


@pytest.mark.asyncio
@pytest.mark.parametrize("length", [5, 200, 300])
async def test_credssp_reads_fragmented_message(length: int) -> None:
    client = RDPClient("unused")
    reader = asyncio.StreamReader()
    client._tcp_reader = reader
    size = bytes([length]) if length < 128 else (b"\x81" + bytes([length]) if length < 256 else b"\x82\x01\x2c")
    packet = b"\x30" + size + b"x" * length
    receive = asyncio.create_task(client._recv_credssp_message())
    try:
        for byte in packet:
            reader.feed_data(bytes([byte]))
            await asyncio.sleep(0)
        assert await asyncio.wait_for(receive, 1) == packet
    finally:
        receive.cancel()
        await asyncio.gather(receive, return_exceptions=True)


@pytest.mark.asyncio
async def test_x224_reads_fragmented_packet() -> None:
    client = RDPClient("unused")
    client._tcp_reader = asyncio.StreamReader()
    client._tcp_writer = MagicMock(drain=AsyncMock())
    packet = bytes.fromhex("030000130ed000000000000200080002000000")
    receive = asyncio.create_task(client._start_x224())
    try:
        for byte in packet:
            client._reader.feed_data(bytes([byte]))
            await asyncio.sleep(0)
        await asyncio.wait_for(receive, 1)
        assert client.connection_properties["protocol"] == b"\x00\x00\x00\x02"
    finally:
        receive.cancel()
        await asyncio.gather(receive, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("length", range(19))
async def test_short_x224_response_is_connection_error(length: int) -> None:
    with pytest.raises(ConnectionError):
        await RDPClient("unused")._parse_x224_response(bytes(length))


@pytest.mark.asyncio
async def test_receive_loop_keeps_delayed_packet_intact() -> None:
    client = RDPClient("unused")
    client._tcp_reader = asyncio.StreamReader()
    client._running = client._connected = True
    with patch.object(client, "_process_server_pdu", new_callable=AsyncMock) as process:
        client._receive_task = asyncio.create_task(client._receive_loop())
        client._reader.feed_data(bytes.fromhex("0300000a02f080"))
        await asyncio.sleep(1.05)
        client._reader.feed_data(b"abc")
        for _ in range(20):
            await asyncio.sleep(0)
            if process.called:
                break
        await client.disconnect()
        process.assert_awaited_once_with(b"abc")


@pytest.mark.asyncio
async def test_server_eof_disconnects_once() -> None:
    client = RDPClient("unused")
    client._running = client._connected = True
    with patch.object(client, "_recv_x224_data", new_callable=AsyncMock) as receive:
        receive.side_effect = [asyncio.IncompleteReadError(b"", 1), asyncio.CancelledError()]
        client._receive_task = asyncio.create_task(client._receive_loop())
        await asyncio.wait_for(client._receive_task, 1)
        assert receive.await_count == 1
    assert not client.is_connected
    assert not client._running


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_failed_context_entry_closes_transport(cancel: bool) -> None:
    client = RDPClient("unused")
    writer = MagicMock(wait_closed=AsyncMock())

    async def open_transport() -> None:
        client._tcp_writer = writer

    error = asyncio.CancelledError if cancel else ConnectionError
    with (
        patch.object(client, "_start_tcp_connection", side_effect=open_transport),
        patch.object(client, "_start_x224", side_effect=error("failed")),
        pytest.raises(error),
    ):
        async with client:
            pytest.fail("Connection setup should fail")
    writer.close.assert_called_once()
    assert client._tcp_writer is None


@pytest.mark.parametrize("bpp", [8, 15, 16, 24])
def test_rle_foreground_run_crosses_first_scanline(bpp: int) -> None:
    pixel_bytes = (bpp + 7) // 8
    assert decompress_rle(b"\x24", 2, 2, bpp, False) == b"\xff" * (2 * pixel_bytes) + bytes(2 * pixel_bytes)


@pytest.mark.parametrize("width,height,bpp", [(0, 1, 24), (1, 0, 24), (1, 1, 32), (65535, 65535, 24)])
def test_invalid_rle_metadata_raises_value_error(width: int, height: int, bpp: int) -> None:
    with pytest.raises(ValueError):
        decompress_rle(b"", width, height, bpp, False)


def test_exported_version_matches_distribution() -> None:
    assert simple_rdp.__version__ == version("simple-rdp")


@pytest.mark.asyncio
async def test_failed_encoder_start_cleans_temp_file(tmp_path) -> None:
    display = Display(64, 64)
    with (
        patch("simple_rdp.display.tempfile.tempdir", str(tmp_path)),
        patch("simple_rdp.display.subprocess.Popen", side_effect=FileNotFoundError("ffmpeg")),
        pytest.raises(FileNotFoundError),
    ):
        await display.start_streaming()
    assert not display._streaming
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")
async def test_short_recording_drains_all_frames(tmp_path) -> None:
    display = Display(64, 64)
    output = tmp_path / "recording.mp4"
    await display.start_streaming()
    try:
        for _ in range(10):
            await display.add_frame(Image.new("RGB", (64, 64), "red"))
        assert await display.get_next_video_chunk(timeout=1) is not None
    finally:
        await display.stop_streaming(record_to=str(output))
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(output),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    )
    assert len(result.stdout) == 10 * 64 * 64 * 3
    assert display._temp_file_path is None


@pytest.mark.asyncio
@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")
async def test_failed_transcode_preserves_recording(tmp_path) -> None:
    from pathlib import Path

    display = Display(64, 64)
    await display.start_streaming()
    source = Path(display._temp_file_path)
    try:
        await display.add_frame(Image.new("RGB", (64, 64)))
        with patch.object(display, "transcode", return_value=False):
            await display.stop_streaming(record_to=str(tmp_path / "missing.mp4"))
        assert source.exists()
        assert source.stat().st_size > 0
    finally:
        await display.stop_streaming()
        source.unlink(missing_ok=True)
