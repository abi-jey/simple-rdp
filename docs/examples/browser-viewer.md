# Browser Viewer Example

The browser viewer is a web-based RDP viewer that streams the remote desktop to a browser using WebSocket.

## Features

- Real-time screen streaming (~10 FPS)
- Mouse capture with click, drag, and scroll
- Keyboard capture
- Cursor compositing into frames
- Responsive canvas scaling

## Setup

### Prerequisites

Install additional dependencies:

```bash
pip install fastapi uvicorn python-dotenv
```

### Configuration

Create a `.env` file in the examples/browser directory:

```bash
RDP_HOST=192.168.1.100
RDP_USER=your_username
RDP_PASS=your_password
RDP_WIDTH=1920
RDP_HEIGHT=1080
```

### Running

```bash
cd examples/browser
python server.py
```

Open http://localhost:8000 in your browser.

## Architecture

```
┌─────────────────┐     WebSocket      ┌──────────────────┐
│                 │◄──────────────────►│                  │
│  Browser Client │    JSON + base64   │   FastAPI Server │
│   (JavaScript)  │      frames        │     (Python)     │
│                 │                    │                  │
└─────────────────┘                    └────────┬─────────┘
                                                │
                                                │ RDP Protocol
                                                │
                                       ┌────────▼─────────┐
                                       │                  │
                                       │   RDP Server     │
                                       │   (Windows)      │
                                       │                  │
                                       └──────────────────┘
```

## Components

### Server (server.py)

The FastAPI server:

- Connects to the RDP server using Simple RDP
- Captures screenshots in a loop
- Composites the cursor into each frame
- Sends frames as base64-encoded JPEG via WebSocket
- Receives mouse/keyboard events and forwards to RDP

### Client (app.js)

The browser client:

- Displays frames on a canvas
- Captures mouse events (when enabled)
- Captures keyboard events (when enabled)
- Sends input events via WebSocket

## Code Walkthrough

### Frame Streaming

```python
async def stream_frames():
    while True:
        if rdp_client and rdp_client.is_connected:
            # Capture screenshot
            img = await rdp_client.screenshot()
            
            # Composite cursor
            img = composite_cursor(img, rdp_client)
            
            # Encode as JPEG
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=70)
            frame_data = base64.b64encode(buffer.getvalue()).decode()
            
            # Send to all connected browsers
            for ws in connected_websockets:
                await ws.send_json({
                    "type": "frame",
                    "data": frame_data,
                    "width": img.width,
                    "height": img.height,
                })
        
        await asyncio.sleep(0.1)  # ~10 FPS
```

### Mouse Event Handling

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    while True:
        data = await websocket.receive_json()
        
        if data["type"] == "mouse_move":
            await rdp_client.mouse_move(data["x"], data["y"])
        
        elif data["type"] == "mouse_click":
            await rdp_client.mouse_click(
                data["x"], data["y"],
                button=data.get("button", 1)
            )
```

### Cursor Compositing

```python
def composite_cursor(frame: Image.Image, client: RDPClient) -> Image.Image:
    if not client.pointer_visible:
        return frame
    
    cursor_img = client.pointer_image
    if cursor_img is None:
        cursor_img = create_default_cursor()
    
    hotspot_x, hotspot_y = client.pointer_hotspot
    cursor_x = local_pointer_x - hotspot_x
    cursor_y = local_pointer_y - hotspot_y
    
    result = frame.copy()
    result.paste(cursor_img, (cursor_x, cursor_y), cursor_img)
    return result
```

## Customization

### Adjust Frame Rate

```python
await asyncio.sleep(0.05)  # ~20 FPS
await asyncio.sleep(0.1)   # ~10 FPS (default)
await asyncio.sleep(0.2)   # ~5 FPS
```

### Adjust JPEG Quality

```python
img.save(buffer, format="JPEG", quality=50)  # Lower quality, smaller size
img.save(buffer, format="JPEG", quality=90)  # Higher quality
```

### Use PNG Instead

```python
img.save(buffer, format="PNG")  # Lossless, larger size
```

## Use Cases

1. **Remote Monitoring** - View RDP sessions from any browser
2. **Automation Debugging** - Watch automation scripts in real-time
3. **Mobile Access** - Control Windows machines from mobile browsers
4. **Screen Sharing** - Share RDP session with multiple viewers
