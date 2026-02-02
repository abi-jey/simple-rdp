# RDPClient API Reference

The main class for establishing RDP connections and interacting with remote desktops.

## Constructor

```python
RDPClient(
    host: str,
    port: int = 3389,
    username: str | None = None,
    password: str | None = None,
    domain: str | None = None,
    width: int = 1920,
    height: int = 1080,
    color_depth: int = 32,
    show_wallpaper: bool = False,
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | *required* | RDP server hostname or IP address |
| `port` | `int` | `3389` | RDP server port |
| `username` | `str \| None` | `None` | Username for authentication |
| `password` | `str \| None` | `None` | Password for authentication |
| `domain` | `str \| None` | `None` | Domain for authentication |
| `width` | `int` | `1920` | Desktop width in pixels |
| `height` | `int` | `1080` | Desktop height in pixels |
| `color_depth` | `int` | `32` | Color depth (16, 24, or 32) |
| `show_wallpaper` | `bool` | `False` | Show desktop wallpaper |

### Example

```python
client = RDPClient(
    host="192.168.1.100",
    username="admin",
    password="secret",
    width=1920,
    height=1080,
)
```

---

## Properties

### host

```python
@property
def host(self) -> str
```

The RDP server hostname or IP address.

### port

```python
@property
def port(self) -> int
```

The RDP server port number.

### is_connected

```python
@property
def is_connected(self) -> bool
```

Whether the client is currently connected.

### width

```python
@property
def width(self) -> int
```

Desktop width in pixels.

### height

```python
@property
def height(self) -> int
```

Desktop height in pixels.

### pointer_position

```python
@property
def pointer_position(self) -> tuple[int, int]
```

Current cursor position as `(x, y)` tuple, as reported by the server.

### pointer_visible

```python
@property
def pointer_visible(self) -> bool
```

Whether the cursor is currently visible.

### pointer_image

```python
@property
def pointer_image(self) -> Image.Image | None
```

The current cursor image as a PIL Image, or `None` if not available.

### pointer_hotspot

```python
@property
def pointer_hotspot(self) -> tuple[int, int]
```

The cursor hotspot offset as `(x, y)` tuple.

---

## Connection Methods

### connect

```python
async def connect(self) -> None
```

Establish connection to the RDP server.

**Raises:**

- `ConnectionError` - If connection fails
- `AuthenticationError` - If authentication fails

**Example:**

```python
client = RDPClient(host="192.168.1.100", ...)
await client.connect()
```

### disconnect

```python
async def disconnect(self) -> None
```

Disconnect from the RDP server.

**Example:**

```python
await client.disconnect()
```

### Context Manager

```python
async with RDPClient(...) as client:
    # client is connected
    ...
# client is disconnected
```

---

## Screen Capture Methods

### screenshot

```python
async def screenshot(self) -> Image.Image
```

Capture the current screen state.

**Returns:** PIL Image of the current screen.

**Example:**

```python
img = await client.screenshot()
print(f"Size: {img.size}")
```

### save_screenshot

```python
async def save_screenshot(self, path: str) -> None
```

Save a screenshot to a file.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | File path to save the screenshot |

**Example:**

```python
await client.save_screenshot("screenshot.png")
```

---

## Video Recording Methods

### display

```python
@property
def display(self) -> Display
```

Access the integrated Display component for video recording.

**Returns:** `Display` instance for advanced video operations.

### is_recording

```python
@property
def is_recording(self) -> bool
```

Whether video recording is currently active.

### start_recording

```python
async def start_recording(self, fps: int = 30) -> None
```

Start video recording. Frames are captured automatically on screen updates.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `fps` | `int` | `30` | Target frames per second for encoding |

**Example:**

```python
await client.start_recording(fps=30)
# ... perform actions ...
await client.save_video("recording.ts")
```

### stop_recording

```python
async def stop_recording(self) -> None
```

Stop video recording. Called automatically by `save_video()`.

### save_video

```python
async def save_video(self, path: str) -> bool
```

Save the recorded video to a file.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Output file path (e.g., `"recording.ts"`) |

**Returns:** `True` if successful, `False` otherwise.

**Example:**

```python
await client.start_recording()
await asyncio.sleep(10)  # Record for 10 seconds
success = await client.save_video("session.ts")
```

### get_recording_stats

```python
def get_recording_stats(self) -> dict[str, Any]
```

Get video recording statistics.

**Returns:** Dictionary with:

- `frames_received` - Total frames added
- `frames_encoded` - Frames sent to encoder
- `bytes_encoded` - Total encoded bytes
- `chunks_evicted` - Chunks removed due to buffer limit
- `encoding_errors` - Number of encoding errors

---

## Keyboard Methods

### send_key

```python
async def send_key(
    self,
    key: str | int,
    is_press: bool = True,
    is_release: bool = True,
) -> None
```

Send a keyboard key event.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `key` | `str \| int` | *required* | Character string or scancode |
| `is_press` | `bool` | `True` | Send key press event |
| `is_release` | `bool` | `True` | Send key release event |

**Example:**

```python
# Send character
await client.send_key("a")

# Send scancode (Enter key)
await client.send_key(0x1C)

# Hold Ctrl key
await client.send_key(0x1D, is_press=True, is_release=False)
```

### send_text

```python
async def send_text(self, text: str) -> None
```

Send a text string as keyboard input.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `text` | `str` | The text to type |

**Example:**

```python
await client.send_text("Hello, World!")
```

---

## Mouse Methods

### mouse_move

```python
async def mouse_move(self, x: int, y: int) -> None
```

Move the mouse to a position.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `x` | `int` | X coordinate |
| `y` | `int` | Y coordinate |

### mouse_click

```python
async def mouse_click(
    self,
    x: int,
    y: int,
    button: int = 1,
    double_click: bool = False,
) -> None
```

Click the mouse at a position.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `x` | `int` | *required* | X coordinate |
| `y` | `int` | *required* | Y coordinate |
| `button` | `int` | `1` | Button (1=left, 2=right, 3=middle) |
| `double_click` | `bool` | `False` | Double-click |

### mouse_button_down

```python
async def mouse_button_down(
    self,
    x: int,
    y: int,
    button: int | str = 1,
) -> None
```

Press a mouse button down.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `x` | `int` | *required* | X coordinate |
| `y` | `int` | *required* | Y coordinate |
| `button` | `int \| str` | `1` | Button number or name |

### mouse_button_up

```python
async def mouse_button_up(
    self,
    x: int,
    y: int,
    button: int | str = 1,
) -> None
```

Release a mouse button.

### mouse_wheel

```python
async def mouse_wheel(
    self,
    x: int,
    y: int,
    delta: int,
) -> None
```

Scroll the mouse wheel.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `x` | `int` | X coordinate |
| `y` | `int` | Y coordinate |
| `delta` | `int` | Wheel delta (±120 per notch) |

### mouse_drag

```python
async def mouse_drag(
    self,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    button: int = 1,
) -> None
```

Drag the mouse from one position to another.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `x1, y1` | `int` | *required* | Starting position |
| `x2, y2` | `int` | *required* | Ending position |
| `button` | `int` | `1` | Button to hold |
