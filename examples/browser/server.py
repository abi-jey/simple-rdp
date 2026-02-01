"""
FastAPI server for RDP browser viewer.

Connects to an RDP server and streams screenshots to the browser via WebSocket.
"""

import asyncio
import base64
import io
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from simple_rdp import RDPClient

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
rdp_client: RDPClient | None = None
connected_websockets: list[WebSocket] = []
frame_task: asyncio.Task | None = None
connection_error: str | None = None

# JavaScript code to scancode mapping
# See: https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent/code
JS_CODE_TO_SCANCODE: dict[str, int] = {
    # Function keys
    "Escape": 0x01, "F1": 0x3B, "F2": 0x3C, "F3": 0x3D, "F4": 0x3E,
    "F5": 0x3F, "F6": 0x40, "F7": 0x41, "F8": 0x42, "F9": 0x43,
    "F10": 0x44, "F11": 0x57, "F12": 0x58,
    # Number row
    "Backquote": 0x29, "Digit1": 0x02, "Digit2": 0x03, "Digit3": 0x04,
    "Digit4": 0x05, "Digit5": 0x06, "Digit6": 0x07, "Digit7": 0x08,
    "Digit8": 0x09, "Digit9": 0x0A, "Digit0": 0x0B, "Minus": 0x0C,
    "Equal": 0x0D, "Backspace": 0x0E,
    # Top letter row
    "Tab": 0x0F, "KeyQ": 0x10, "KeyW": 0x11, "KeyE": 0x12, "KeyR": 0x13,
    "KeyT": 0x14, "KeyY": 0x15, "KeyU": 0x16, "KeyI": 0x17, "KeyO": 0x18,
    "KeyP": 0x19, "BracketLeft": 0x1A, "BracketRight": 0x1B, "Backslash": 0x2B,
    # Home row
    "CapsLock": 0x3A, "KeyA": 0x1E, "KeyS": 0x1F, "KeyD": 0x20, "KeyF": 0x21,
    "KeyG": 0x22, "KeyH": 0x23, "KeyJ": 0x24, "KeyK": 0x25, "KeyL": 0x26,
    "Semicolon": 0x27, "Quote": 0x28, "Enter": 0x1C,
    # Bottom letter row
    "ShiftLeft": 0x2A, "KeyZ": 0x2C, "KeyX": 0x2D, "KeyC": 0x2E, "KeyV": 0x2F,
    "KeyB": 0x30, "KeyN": 0x31, "KeyM": 0x32, "Comma": 0x33, "Period": 0x34,
    "Slash": 0x35, "ShiftRight": 0x36,
    # Bottom row
    "ControlLeft": 0x1D, "MetaLeft": 0xE05B, "AltLeft": 0x38, "Space": 0x39,
    "AltRight": 0xE038, "MetaRight": 0xE05C, "ContextMenu": 0xE05D, "ControlRight": 0xE01D,
    # Navigation
    "Insert": 0xE052, "Delete": 0xE053, "Home": 0xE047, "End": 0xE04F,
    "PageUp": 0xE049, "PageDown": 0xE051,
    # Arrow keys
    "ArrowUp": 0xE048, "ArrowDown": 0xE050, "ArrowLeft": 0xE04B, "ArrowRight": 0xE04D,
    # Numpad
    "NumLock": 0x45, "NumpadDivide": 0xE035, "NumpadMultiply": 0x37,
    "NumpadSubtract": 0x4A, "Numpad7": 0x47, "Numpad8": 0x48, "Numpad9": 0x49,
    "NumpadAdd": 0x4E, "Numpad4": 0x4B, "Numpad5": 0x4C, "Numpad6": 0x4D,
    "Numpad1": 0x4F, "Numpad2": 0x50, "Numpad3": 0x51, "NumpadEnter": 0xE01C,
    "Numpad0": 0x52, "NumpadDecimal": 0x53,
    # Other
    "PrintScreen": 0xE037, "ScrollLock": 0x46, "Pause": 0xE11D,
}


async def handle_key_event(data: dict, pressed: bool) -> None:
    """Handle keyboard events from the browser."""
    global rdp_client
    
    if not rdp_client or not rdp_client.is_connected:
        return
    
    code = data.get("code", "")
    key = data.get("key", "")
    
    # Try to get scancode from code
    scancode = JS_CODE_TO_SCANCODE.get(code)
    
    if scancode:
        # Extended key check (scancodes > 0xFF have extended prefix)
        await rdp_client.send_key(scancode, is_press=pressed, is_release=not pressed)
    elif len(key) == 1:
        # Single character - send as unicode
        if pressed:  # Only send on key down to avoid double input
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
async def lifespan(app: FastAPI):
    """Application lifespan - try to connect to RDP on startup."""
    global frame_task
    
    # Try to connect but don't fail if it doesn't work
    await connect_rdp()
    
    # Start frame streaming task (handles disconnected state gracefully)
    frame_task = asyncio.create_task(stream_frames())
    
    yield
    
    # Cleanup
    if frame_task:
        frame_task.cancel()
        try:
            await frame_task
        except asyncio.CancelledError:
            pass
    
    if rdp_client:
        await rdp_client.disconnect()
        logger.info("RDP disconnected")


app = FastAPI(lifespan=lifespan)

# Serve static files
static_dir = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Local pointer position (updated by mouse events from browser)
local_pointer_x: int = 0
local_pointer_y: int = 0


def composite_cursor(frame: Image.Image, client: RDPClient) -> Image.Image:
    """Composite the cursor onto the frame image."""
    if not client.pointer_visible:
        return frame
    
    cursor_img = client.pointer_image
    if cursor_img is None:
        # Use a simple default cursor if no cursor image
        cursor_img = create_default_cursor()
    
    # Use local pointer position (updated by mouse events)
    hotspot_x, hotspot_y = client.pointer_hotspot
    cursor_x = local_pointer_x - hotspot_x
    cursor_y = local_pointer_y - hotspot_y
    
    # Make a copy of the frame to avoid modifying the original
    result = frame.copy()
    
    # Ensure cursor image is RGBA for proper alpha compositing
    if cursor_img.mode != "RGBA":
        cursor_img = cursor_img.convert("RGBA")
    
    # Paste cursor onto frame with alpha blending
    # Clamp position to valid range
    paste_x = max(0, min(cursor_x, frame.width - 1))
    paste_y = max(0, min(cursor_y, frame.height - 1))
    
    try:
        result.paste(cursor_img, (paste_x, paste_y), cursor_img)
    except Exception:
        # If paste fails (e.g., cursor out of bounds), return original
        pass
    
    return result


def create_default_cursor() -> Image.Image:
    """Create a simple default arrow cursor."""
    from PIL import ImageDraw
    
    size = 16
    cursor = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(cursor)
    
    # Draw a simple arrow shape
    arrow_points = [
        (0, 0), (0, 12), (3, 9), (6, 14), (8, 13), (5, 8), (10, 8), (0, 0)
    ]
    draw.polygon(arrow_points, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    
    return cursor


async def stream_frames():
    """Continuously capture frames and send to connected WebSocket clients."""
    global rdp_client
    
    logger.info("Frame streaming task started")
    frame_count = 0
    
    while True:
        try:
            has_client = rdp_client is not None
            is_connected = rdp_client.is_connected if rdp_client else False
            has_ws = len(connected_websockets) > 0
            
            if has_client and is_connected and has_ws:
                # Type narrowing (we already checked rdp_client is not None above)
                assert rdp_client is not None
                
                # Capture screenshot
                img = await rdp_client.screenshot()
                frame_count += 1
                
                if frame_count % 100 == 0:
                    logger.info(f"Streamed {frame_count} frames")
                
                # Composite cursor onto the frame
                img = composite_cursor(img, rdp_client)
                
                # Convert to JPEG for faster transmission
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=70)
                frame_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
                
                # Send to all connected clients
                disconnected = []
                for ws in connected_websockets:
                    try:
                        await ws.send_json({
                            "type": "frame",
                            "data": frame_data,
                            "width": img.width,
                            "height": img.height,
                        })
                    except Exception:
                        disconnected.append(ws)
                
                # Remove disconnected clients
                for ws in disconnected:
                    connected_websockets.remove(ws)
            
            # Target ~10 FPS for browser viewing
            await asyncio.sleep(0.1)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Frame streaming error: {e}")
            await asyncio.sleep(1)


@app.get("/")
async def index():
    """Serve the main HTML page."""
    html_path = os.path.join(static_dir, "index.html")
    with open(html_path) as f:
        return HTMLResponse(content=f.read())


@app.get("/status")
async def status():
    """Get RDP connection status."""
    global rdp_client, connection_error
    return {
        "connected": rdp_client.is_connected if rdp_client else False,
        "host": os.getenv("RDP_HOST", ""),
        "clients": len(connected_websockets),
        "error": connection_error,
    }


@app.post("/connect")
async def connect():
    """Trigger RDP connection."""
    global frame_task
    
    success = await connect_rdp()
    
    # Notify all connected websocket clients
    for ws in connected_websockets:
        try:
            await ws.send_json({
                "type": "status",
                "connected": rdp_client.is_connected if rdp_client else False,
                "host": os.getenv("RDP_HOST", ""),
                "error": connection_error,
            })
        except Exception:
            pass
    
    return {
        "success": success,
        "connected": rdp_client.is_connected if rdp_client else False,
        "error": connection_error,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for frame streaming."""
    global rdp_client
    
    await websocket.accept()
    connected_websockets.append(websocket)
    logger.info(f"WebSocket client connected. Total clients: {len(connected_websockets)}")
    
    # Send initial status
    await websocket.send_json({
        "type": "status",
        "connected": rdp_client.is_connected if rdp_client else False,
        "host": os.getenv("RDP_HOST", ""),
        "error": connection_error,
    })
    
    try:
        while True:
            # Handle incoming messages for mouse/keyboard input
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            
            # Mouse events - update local pointer position for compositing
            elif msg_type == "mouse_move" and rdp_client and rdp_client.is_connected:
                global local_pointer_x, local_pointer_y
                x, y = data.get("x", 0), data.get("y", 0)
                local_pointer_x, local_pointer_y = x, y
                await rdp_client.mouse_move(x, y)
            
            elif msg_type == "mouse_down" and rdp_client and rdp_client.is_connected:
                global local_pointer_x, local_pointer_y
                x, y = data.get("x", 0), data.get("y", 0)
                local_pointer_x, local_pointer_y = x, y
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
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
