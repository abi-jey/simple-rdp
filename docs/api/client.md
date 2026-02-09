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
    capture_fps: int = 30,
    record_to: str | None = None,
    use_fast_path_input: bool = True,
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
| `capture_fps` | `int` | `30` | Target FPS for video capture |
| `record_to` | `str \| None` | `None` | Path to save recording on disconnect |
| `use_fast_path_input` | `bool` | `True` | Use fast-path for mouse input (lower latency) |

### Example

```python
client = RDPClient(
    host="192.168.1.100",
    username="admin",
    password="secret",
    record_to="session_recording.mp4",
)
```

---

## Properties

### Connection Info

#### host

The RDP server hostname or IP address.

#### port

The RDP server port number.

#### is_connected

Whether the client is currently connected.

#### width

Desktop width in pixels.

#### height

Desktop height in pixels.

### Video Streaming

#### is_streaming

Whether video streaming is active (always True when connected).

#### consumer_lag_chunks

Number of video chunks waiting in the queue. High values indicate the consumer is too slow.

#### record_to

The path where the session recording will be saved on disconnect.

### Pointer

#### pointer_position

Current cursor position as `(x, y)` tuple.

#### pointer_visible

Whether the cursor is currently visible.

#### pointer_image

The current cursor image as a PIL Image.

#### pointer_hotspot

The cursor hotspot offset as `(x, y)` tuple.

---

## Connection Methods

### connect

```python
async def connect(self) -> None
```

Establish connection to the RDP server and start video streaming.

### disconnect

```python
async def disconnect(self) -> None
```

Disconnect from the RDP server. Stops streaming and saves recording if `record_to` was set.

---

## Video Methods

### get_next_video_chunk

```python
async def get_next_video_chunk(self, timeout: float = 1.0) -> VideoChunk | None
```

Wait for and return the next video chunk (fMP4 format). Use this for real-time streaming.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `timeout` | `float` | Max wait time in seconds |

**Returns:** `VideoChunk` or `None`.

### is_consumer_behind

```python
def is_consumer_behind(self, threshold: int = 10) -> bool
```

Check if the video consumer is lagging behind the stream.

### get_pipeline_stats

```python
def get_pipeline_stats(self) -> PipelineStats
```

Get detailed pipeline latency statistics.

### transcode

```python
@staticmethod
def transcode(input_path: str, output_path: str) -> bool
```

Convert a video file (e.g. .ts to .mp4).

---

## Screen Capture Methods

### screenshot

```python
async def screenshot(self) -> Image.Image
```

Capture the current screen state as a PIL Image.

### save_screenshot

```python
async def save_screenshot(self, path: str) -> None
```

Save a screenshot to a file.

---

## Input Methods

### Keyboard

#### send_key

```python
async def send_key(key: str | int, is_press: bool = True, is_release: bool = True) -> None
```

Send a keyboard key (char or scancode).

#### send_text

```python
async def send_text(text: str) -> None
```

Type a text string.

### Mouse

#### mouse_move

```python
async def mouse_move(x: int, y: int) -> None
```

Move mouse to position.

#### mouse_click

```python
async def mouse_click(x: int, y: int, button: int = 1, double_click: bool = False) -> None
```

Click mouse at position.

#### mouse_drag

```python
async def mouse_drag(x1: int, y1: int, x2: int, y2: int, button: int = 1) -> None
```

Drag mouse from A to B.

#### mouse_wheel

```python
async def mouse_wheel(x: int, y: int, delta: int) -> None
```

Scroll mouse wheel.
