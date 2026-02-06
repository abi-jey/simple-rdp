"""FastAPI server for RDP browser viewer.

Connects to an RDP server and streams H.264 video to the browser via MPEG-TS.
"""

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncGenerator
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from simple_rdp import RDPClient

logging.basicConfig(level=logging.INFO, format="%(message)s")
load_dotenv()

logger = logging.getLogger(__name__)

# Global state
rdp_client: RDPClient | None = None
connected_websockets: list[WebSocket] = []  # For input handling only
connection_error: str | None = None
video_streaming_clients: int = 0  # Track active video stream consumers
shutdown_event: asyncio.Event | None = None  # Signal for graceful shutdown

# JavaScript code to scancode mapping
# See: https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent/code
JS_CODE_TO_SCANCODE: dict[str, int] = {
    # Function keys
    "Escape": 0x01,
    "F1": 0x3B,
    "F2": 0x3C,
    "F3": 0x3D,
    "F4": 0x3E,
    "F5": 0x3F,
    "F6": 0x40,
    "F7": 0x41,
    "F8": 0x42,
    "F9": 0x43,
    "F10": 0x44,
    "F11": 0x57,
    "F12": 0x58,
    # Number row
    "Backquote": 0x29,
    "Digit1": 0x02,
    "Digit2": 0x03,
    "Digit3": 0x04,
    "Digit4": 0x05,
    "Digit5": 0x06,
    "Digit6": 0x07,
    "Digit7": 0x08,
    "Digit8": 0x09,
    "Digit9": 0x0A,
    "Digit0": 0x0B,
    "Minus": 0x0C,
    "Equal": 0x0D,
    "Backspace": 0x0E,
    # Top letter row
    "Tab": 0x0F,
    "KeyQ": 0x10,
    "KeyW": 0x11,
    "KeyE": 0x12,
    "KeyR": 0x13,
    "KeyT": 0x14,
    "KeyY": 0x15,
    "KeyU": 0x16,
    "KeyI": 0x17,
    "KeyO": 0x18,
    "KeyP": 0x19,
    "BracketLeft": 0x1A,
    "BracketRight": 0x1B,
    "Backslash": 0x2B,
    # Home row
    "CapsLock": 0x3A,
    "KeyA": 0x1E,
    "KeyS": 0x1F,
    "KeyD": 0x20,
    "KeyF": 0x21,
    "KeyG": 0x22,
    "KeyH": 0x23,
    "KeyJ": 0x24,
    "KeyK": 0x25,
    "KeyL": 0x26,
    "Semicolon": 0x27,
    "Quote": 0x28,
    "Enter": 0x1C,
    # Bottom letter row
    "ShiftLeft": 0x2A,
    "KeyZ": 0x2C,
    "KeyX": 0x2D,
    "KeyC": 0x2E,
    "KeyV": 0x2F,
    "KeyB": 0x30,
    "KeyN": 0x31,
    "KeyM": 0x32,
    "Comma": 0x33,
    "Period": 0x34,
    "Slash": 0x35,
    "ShiftRight": 0x36,
    # Bottom row
    "ControlLeft": 0x1D,
    "MetaLeft": 0xE05B,
    "AltLeft": 0x38,
    "Space": 0x39,
    "AltRight": 0xE038,
    "MetaRight": 0xE05C,
    "ContextMenu": 0xE05D,
    "ControlRight": 0xE01D,
    # Navigation
    "Insert": 0xE052,
    "Delete": 0xE053,
    "Home": 0xE047,
    "End": 0xE04F,
    "PageUp": 0xE049,
    "PageDown": 0xE051,
    # Arrow keys
    "ArrowUp": 0xE048,
    "ArrowDown": 0xE050,
    "ArrowLeft": 0xE04B,
    "ArrowRight": 0xE04D,
    # Numpad
    "NumLock": 0x45,
    "NumpadDivide": 0xE035,
    "NumpadMultiply": 0x37,
    "NumpadSubtract": 0x4A,
    "Numpad7": 0x47,
    "Numpad8": 0x48,
    "Numpad9": 0x49,
    "NumpadAdd": 0x4E,
    "Numpad4": 0x4B,
    "Numpad5": 0x4C,
    "Numpad6": 0x4D,
    "Numpad1": 0x4F,
    "Numpad2": 0x50,
    "Numpad3": 0x51,
    "NumpadEnter": 0xE01C,
    "Numpad0": 0x52,
    "NumpadDecimal": 0x53,
    # Other
    "PrintScreen": 0xE037,
    "ScrollLock": 0x46,
    "Pause": 0xE11D,
}


async def handle_key_event(data: dict[str, str | int | bool], pressed: bool) -> None:
    """Handle keyboard events from the browser."""
    global rdp_client

    if not rdp_client or not rdp_client.is_connected:
        return

    code = str(data.get("code", ""))
    key = str(data.get("key", ""))

    # Try to get scancode from code
    scancode = JS_CODE_TO_SCANCODE.get(code)

    if scancode:
        # Extended key check (scancodes > 0xFF have extended prefix)
        await rdp_client.send_key(scancode, is_press=pressed, is_release=not pressed)
    elif len(key) == 1 and pressed:
        # Single character - send as unicode (only on key down to avoid double input)
        await rdp_client.send_key(key, is_press=True, is_release=True)


async def connect_rdp() -> bool:
    """Connect to the RDP server. Returns True on success."""
    global rdp_client, connection_error

    host = os.getenv("RDP_HOST", "")
    username = os.getenv("RDP_USER", "")
    password = os.getenv("RDP_PASS", "")

    if not host or not username or not password:
        connection_error = "RDP_HOST, RDP_USER, RDP_PASS environment variables required"
        logger.error(connection_error)
        return False

    try:
        logger.info(f"Connecting to RDP server at {host}...")
        rdp_client = RDPClient(
            host=host,
            username=username,
            password=password,
            width=1920,
            height=1080,
            show_wallpaper=True,
        )
        await rdp_client.connect()
        connection_error = None
        logger.info("RDP connection established!")
        return True

    except Exception as e:
        connection_error = str(e)
        logger.exception(f"Failed to connect to RDP: {e}")
        rdp_client = None
        return False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan - cleanup RDP on shutdown."""
    global shutdown_event

    # Initialize shutdown event
    shutdown_event = asyncio.Event()

    # RDP connection happens on-demand when browser clients connect
    logger.info("Server starting - RDP will connect when browser client connects")

    yield

    # Signal shutdown to all generators
    logger.info("Signaling shutdown...")
    shutdown_event.set()

    # Give generators a moment to exit
    await asyncio.sleep(0.2)

    # Cleanup
    if rdp_client:
        if rdp_client.is_streaming:
            await rdp_client.stop_streaming()
        await rdp_client.disconnect()
        logger.info("RDP disconnected")


app = FastAPI(lifespan=lifespan)

# Serve static files
static_dir = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def index() -> HTMLResponse:
    """Serve the main HTML page."""
    html_path = os.path.join(static_dir, "index.html")
    with open(html_path) as f:
        return HTMLResponse(content=f.read())


@app.get("/status")
async def status() -> dict[str, str | int | bool | None]:
    """Get RDP connection status."""
    global rdp_client, connection_error
    return {
        "connected": rdp_client.is_connected if rdp_client else False,
        "host": os.getenv("RDP_HOST", ""),
        "clients": len(connected_websockets),
        "error": connection_error,
    }


@app.post("/connect")
async def connect() -> dict[str, str | bool | None]:
    """Trigger RDP connection."""
    success = await connect_rdp()

    # Start streaming if connected
    if success and rdp_client and not rdp_client.is_streaming:
        await rdp_client.start_streaming()
        logger.info("Video streaming started after reconnect")

    # Notify all connected websocket clients
    for ws in connected_websockets:
        with contextlib.suppress(Exception):
            await ws.send_json(
                {
                    "type": "status",
                    "connected": rdp_client.is_connected if rdp_client else False,
                    "host": os.getenv("RDP_HOST", ""),
                    "error": connection_error,
                },
            )

    return {
        "success": success,
        "connected": rdp_client.is_connected if rdp_client else False,
        "error": connection_error,
    }


async def video_stream_generator() -> AsyncIterator[bytes]:
    """Generator that yields fragmented MP4 video chunks from the Display streaming.

    This uses the Display's efficient ffmpeg-based encoding which produces
    H.264 video in fragmented MP4 format for MSE browser compatibility.

    RDP connection is established on-demand when the first browser client connects.
    """
    global rdp_client, video_streaming_clients, shutdown_event

    video_streaming_clients += 1
    logger.info(f"Video stream client connected. Total: {video_streaming_clients}")

    try:
        # Check if already shutting down
        if shutdown_event and shutdown_event.is_set():
            logger.info("Server is shutting down, not starting video stream")
            return

        # Connect to RDP if not already connected (on-demand connection)
        if not rdp_client or not rdp_client.is_connected:
            logger.info("Browser client connected - initiating RDP connection...")
            success = await connect_rdp()
            if not success:
                logger.error("Failed to connect to RDP server")
                # Yield nothing and exit - client will see connection error
                return

        # Check shutdown again after connection
        if shutdown_event and shutdown_event.is_set():
            return

        # Start streaming if not already active
        if rdp_client and rdp_client.is_connected and not rdp_client.is_streaming:
            await rdp_client.start_streaming()
            logger.info("Started video streaming for new client")

        while not (shutdown_event and shutdown_event.is_set()):
            # Check connection state
            client = rdp_client
            if client is None or not client.is_connected:
                # RDP disconnected, check if shutting down
                if shutdown_event and shutdown_event.is_set():
                    break
                # Try to reconnect
                logger.info("RDP connection lost, attempting to reconnect...")
                success = await connect_rdp()
                if not success:
                    await asyncio.sleep(2.0)  # Wait before retry
                    continue
                client = rdp_client
                if client is None:
                    continue

            if not client.is_streaming:
                # Streaming not active, try to start it
                await client.start_streaming()
                await asyncio.sleep(0.1)
                continue

            # Get next video chunk from the display's streaming buffer
            chunk = await client.display.get_next_video_chunk(timeout=0.5)

            if chunk:
                yield chunk.data
            else:
                # No chunk available, small sleep to avoid busy loop
                await asyncio.sleep(0.01)

        logger.info("Video stream generator exiting due to shutdown")

    except asyncio.CancelledError:
        logger.info("Video stream cancelled")
    except Exception as e:
        logger.error(f"Video stream error: {e}")
    finally:
        video_streaming_clients -= 1
        logger.info(f"Video stream client disconnected. Total: {video_streaming_clients}")

        # Stop streaming if no more clients
        if video_streaming_clients <= 0 and rdp_client and rdp_client.is_streaming:
            await rdp_client.stop_streaming()
            logger.info("Stopped video streaming - no more clients")


@app.get("/video")
async def video_stream() -> StreamingResponse:
    """HTTP endpoint for fragmented MP4 video streaming.

    Uses the Display's ffmpeg-based H.264 encoding for efficient streaming.
    The browser can consume this directly with a <video> element using MSE
    (Media Source Extensions).

    Content-Type: video/mp4 (fragmented MP4)
    """
    return StreamingResponse(
        video_stream_generator(),
        media_type="video/mp4",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.websocket("/ws/video")
async def websocket_video(websocket: WebSocket) -> None:
    """WebSocket endpoint for video streaming.

    Sends binary video chunks over WebSocket for lower latency.
    Better connection state awareness and reconnection handling.
    """
    global rdp_client, video_streaming_clients, shutdown_event

    await websocket.accept()
    video_streaming_clients += 1
    logger.info(f"Video WebSocket client connected. Total: {video_streaming_clients}")

    try:
        # Check if already shutting down
        if shutdown_event and shutdown_event.is_set():
            await websocket.close(1001, "Server shutting down")
            return

        # Connect to RDP if not already connected (on-demand connection)
        if not rdp_client or not rdp_client.is_connected:
            logger.info("Video client connected - initiating RDP connection...")
            await websocket.send_json({"type": "status", "message": "Connecting to RDP..."})
            success = await connect_rdp()
            if not success:
                await websocket.send_json({"type": "error", "message": "Failed to connect to RDP"})
                await websocket.close(1011, "RDP connection failed")
                return

        # Start streaming if not already active
        if rdp_client and rdp_client.is_connected and not rdp_client.is_streaming:
            await rdp_client.start_streaming()
            logger.info("Started video streaming for WebSocket client")

        # Send ready message
        await websocket.send_json({"type": "ready", "message": "Video stream ready"})

        # Stream video chunks
        while not (shutdown_event and shutdown_event.is_set()):
            client = rdp_client
            if client is None or not client.is_connected:
                if shutdown_event and shutdown_event.is_set():
                    break
                await websocket.send_json({"type": "status", "message": "RDP disconnected, reconnecting..."})
                success = await connect_rdp()
                if not success:
                    await asyncio.sleep(2.0)
                    continue
                client = rdp_client
                if client is None:
                    continue

            if not client.is_streaming:
                await client.start_streaming()
                await asyncio.sleep(0.1)
                continue

            # Get next video chunk
            chunk = await client.display.get_next_video_chunk(timeout=0.5)

            if chunk:
                # Send binary video data
                await websocket.send_bytes(chunk.data)
            else:
                await asyncio.sleep(0.01)

        logger.info("Video WebSocket closing due to shutdown")

    except WebSocketDisconnect:
        logger.info("Video WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Video WebSocket error: {e}")
    finally:
        video_streaming_clients -= 1
        logger.info(f"Video WebSocket client disconnected. Total: {video_streaming_clients}")

        # Stop streaming if no more clients
        if video_streaming_clients <= 0 and rdp_client and rdp_client.is_streaming:
            await rdp_client.stop_streaming()
            logger.info("Stopped video streaming - no more clients")


@app.get("/stream-status")
async def stream_status() -> dict[str, Any]:
    """Get detailed video streaming status for diagnostics."""
    global rdp_client, video_streaming_clients

    if not rdp_client:
        return {
            "streaming": False,
            "connected": False,
            "video_clients": video_streaming_clients,
            "stats": None,
        }

    display_stats = rdp_client.display.stats if rdp_client.display else {}

    # Calculate rates
    server_fps = rdp_client.display.effective_fps if rdp_client.display else 0

    return {
        "streaming": rdp_client.is_streaming if rdp_client else False,
        "connected": rdp_client.is_connected if rdp_client else False,
        "video_clients": video_streaming_clients,
        "server_fps": round(server_fps, 1),
        "video_queue_size": rdp_client.display._video_queue.qsize() if rdp_client and rdp_client.display else 0,
        "pending_chunks": len(rdp_client.display._video_chunks) if rdp_client and rdp_client.display else 0,
        "buffer_size_mb": round(rdp_client.display.video_buffer_size_mb, 2) if rdp_client and rdp_client.display else 0,
        "stats": {
            "frames_received": display_stats.get("frames_received", 0),
            "frames_encoded": display_stats.get("frames_encoded", 0),
            "bytes_encoded_mb": round(display_stats.get("bytes_encoded", 0) / 1024 / 1024, 2),
            "encoding_errors": display_stats.get("encoding_errors", 0),
            "bitmaps_applied": display_stats.get("bitmaps_applied", 0),
        },
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for input handling (mouse/keyboard)."""
    global rdp_client

    await websocket.accept()
    connected_websockets.append(websocket)
    logger.info(f"WebSocket client connected. Total clients: {len(connected_websockets)}")

    # Send initial status
    await websocket.send_json(
        {
            "type": "status",
            "connected": rdp_client.is_connected if rdp_client else False,
            "host": os.getenv("RDP_HOST", ""),
            "error": connection_error,
        },
    )

    try:
        while True:
            # Handle incoming messages for mouse/keyboard input
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            # Mouse events
            elif msg_type == "mouse_move" and rdp_client and rdp_client.is_connected:
                x, y = data.get("x", 0), data.get("y", 0)
                await rdp_client.mouse_move(x, y)

            elif msg_type == "mouse_down" and rdp_client and rdp_client.is_connected:
                x, y = data.get("x", 0), data.get("y", 0)
                button = data.get("button", "left")
                await rdp_client.mouse_button_down(x, y, button=button)

            elif msg_type == "mouse_up" and rdp_client and rdp_client.is_connected:
                x, y = data.get("x", 0), data.get("y", 0)
                button = data.get("button", "left")
                await rdp_client.mouse_button_up(x, y, button=button)

            elif msg_type == "mouse_click" and rdp_client and rdp_client.is_connected:
                x, y = data.get("x", 0), data.get("y", 0)
                button = data.get("button", "left")
                await rdp_client.mouse_click(x, y, button=button)

            elif msg_type == "mouse_wheel" and rdp_client and rdp_client.is_connected:
                x, y = data.get("x", 0), data.get("y", 0)
                delta = data.get("delta", 0)
                await rdp_client.mouse_wheel(x, y, delta)

            # Keyboard events
            elif msg_type == "key_down" and rdp_client and rdp_client.is_connected:
                await handle_key_event(data, pressed=True)

            elif msg_type == "key_up" and rdp_client and rdp_client.is_connected:
                await handle_key_event(data, pressed=False)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)
        logger.info(f"Total clients: {len(connected_websockets)}")


if __name__ == "__main__":
    import signal
    import sys

    import uvicorn

    def signal_handler(sig: int, frame: object) -> None:
        """Handle Ctrl+C gracefully."""
        logger.info("Received interrupt signal, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    uvicorn.run(app, host="0.0.0.0", port=8000)
