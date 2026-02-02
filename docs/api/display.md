# Display API Reference

The `Display` class provides video encoding and frame buffering capabilities using ffmpeg.

!!! info "Integrated with RDPClient"
    The `Display` is automatically integrated into `RDPClient`. Access it via `client.display` 
    or use the convenience methods `client.start_streaming()`, `client.start_file_recording()`, etc.
    
    For most use cases, you don't need to interact with Display directly.

## Overview

The Display class manages:

- **Raw frame storage** - Uncompressed RGB frames in a deque buffer (~10 seconds)
- **Live video streaming** - Real-time H.264 encoding via ffmpeg subprocess  
- **File recording** - Taps into streaming output for unlimited duration recording
- **Video buffering** - Async queue with configurable size limits (100MB default)
- **Frame eviction** - Automatic cleanup when buffers exceed limits

---

## Quick Start

```python
from simple_rdp import RDPClient

async with RDPClient(host="...", username="...", password="...") as client:
    # Start streaming to memory buffer
    await client.start_streaming()
    
    # Optionally also record to file (unlimited duration)
    await client.start_file_recording("session.ts")
    
    # ... perform actions ...
    
    # Stop recording (streaming continues)
    await client.stop_file_recording()
    
    # Stop streaming
    await client.stop_streaming()
    
    # Or save the raw frame buffer as video
    await client.save_video("clip.mp4")
```

---

## Classes

### ScreenBuffer

A dataclass representing a captured screen frame.

```python
@dataclass
class ScreenBuffer:
    width: int
    height: int
    data: bytes
    format: str = "RGB"
    timestamp: float = field(default_factory=time.time)
```

| Field | Type | Description |
|-------|------|-------------|
| `width` | `int` | Frame width in pixels |
| `height` | `int` | Frame height in pixels |
| `data` | `bytes` | Raw pixel data |
| `format` | `str` | Pixel format (default: `"RGB"`) |
| `timestamp` | `float` | Wall-clock capture timestamp |

#### Properties

##### size_bytes

```python
@property
def size_bytes(self) -> int
```

Return the size of the raw data in bytes.

---

### VideoChunk

A dataclass representing a chunk of encoded video data.

```python
@dataclass
class VideoChunk:
    data: bytes
    timestamp: float
    sequence: int
```

| Field | Type | Description |
|-------|------|-------------|
| `data` | `bytes` | Encoded video bytes |
| `timestamp` | `float` | Encoding timestamp |
| `sequence` | `int` | Chunk sequence number |

#### Properties

##### size_bytes

```python
@property
def size_bytes(self) -> int
```

Return the size of the encoded data in bytes.

---

### Display

The main class for managing screen capture and video encoding.

```python
class Display:
    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        max_video_buffer_mb: float = 100,
        max_raw_frames: int | None = None,
    ) -> None
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `width` | `int` | `1920` | Frame width in pixels |
| `height` | `int` | `1080` | Frame height in pixels |
| `fps` | `int` | `30` | Target frames per second |
| `max_video_buffer_mb` | `float` | `100` | Max video buffer size in MB |
| `max_raw_frames` | `int \| None` | `fps * 10` | Max raw frames to buffer (~10 seconds) |

---

## Properties

### Dimensions & Configuration

#### width

```python
@property
def width(self) -> int
```

Frame width in pixels.

#### height

```python
@property
def height(self) -> int
```

Frame height in pixels.

#### fps

```python
@property
def fps(self) -> int
```

Target frames per second for encoding.

#### max_raw_frames

```python
@property
def max_raw_frames(self) -> int
```

Maximum number of raw frames that can be buffered.

---

### Frame & Buffer Info

#### frame_count

```python
@property
def frame_count(self) -> int
```

Total number of frames added since creation.

#### raw_frame_count

```python
@property
def raw_frame_count(self) -> int
```

Current number of frames in the raw buffer.

#### raw_buffer_seconds

```python
@property
def raw_buffer_seconds(self) -> float
```

Current raw frame buffer size in seconds (based on fps).

#### max_raw_buffer_seconds

```python
@property
def max_raw_buffer_seconds(self) -> float
```

Maximum raw frame buffer size in seconds.

#### video_buffer_size_mb

```python
@property
def video_buffer_size_mb(self) -> float
```

Current video buffer size in megabytes.

---

### Encoding State

#### is_streaming

```python
@property
def is_streaming(self) -> bool
```

Whether video streaming to memory buffer is active.

#### is_file_recording

```python
@property
def is_file_recording(self) -> bool
```

Whether file recording is active.

#### is_encoding

```python
@property
def is_encoding(self) -> bool
```

Whether any ffmpeg encoding (streaming or file) is currently active.

---

### Statistics

#### stats

```python
@property
def stats(self) -> dict[str, int]
```

Get encoding statistics.

**Returns:** Dictionary with keys:

- `frames_received` - Total frames added
- `frames_encoded` - Frames sent to ffmpeg
- `bytes_encoded` - Total bytes of encoded video
- `chunks_evicted` - Video chunks removed due to buffer limit
- `encoding_errors` - Number of encoding errors
- `bitmaps_applied` - Number of RDP bitmap updates applied

---

### Timing

#### recording_duration_seconds

```python
@property
def recording_duration_seconds(self) -> float
```

How long encoding has been active in seconds. Returns 0 if not encoding.

#### session_duration_seconds

```python
@property
def session_duration_seconds(self) -> float
```

How long since the Display was created (wall-clock).

#### session_start_time

```python
@property
def session_start_time(self) -> float
```

The wall-clock timestamp when the session started.

#### buffer_delay_seconds

```python
@property
def buffer_delay_seconds(self) -> float
```

The delay between the oldest buffered frame and now. Indicates latency.

#### effective_fps

```python
@property
def effective_fps(self) -> float
```

The actual frames per second being received.

#### buffer_time_range

```python
@property
def buffer_time_range(self) -> tuple[float, float]
```

Return the time range of buffered frames as (oldest_time, newest_time) relative to session start.

---

### Screen Buffer

#### screen_buffer

```python
@property
def screen_buffer(self) -> Image.Image | None
```

The current screen buffer as a PIL Image, or None if not initialized.

---

## Methods

### Streaming

#### start_streaming

```python
async def start_streaming(self) -> None
```

Start streaming video to memory buffer.

Frames are encoded to MPEG-TS format and stored in chunks for live consumption via `get_next_video_chunk()`.

!!! warning "ffmpeg Required"
    Ensure ffmpeg is installed and available in PATH.

**Example:**

```python
display = Display(width=1920, height=1080)
await display.start_streaming()
# ... add frames ...
await display.stop_streaming()
```

---

#### stop_streaming

```python
async def stop_streaming(self) -> None
```

Stop streaming to memory buffer.

Also stops any active file recording (closes the file).

---

### File Recording

#### start_file_recording

```python
async def start_file_recording(self, path: str) -> None
```

Start recording video to a file.

Recording taps into the streaming output - if streaming is not active, it will be started automatically. This allows unlimited duration recording without memory limits.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Output file path (use `.ts` extension for MPEG-TS) |

**Example:**

```python
display = Display(width=1920, height=1080)
await display.start_file_recording("session.ts")
# ... recording continues for unlimited duration ...
await display.stop_file_recording()
```

---

#### stop_file_recording

```python
async def stop_file_recording(self) -> None
```

Stop file recording.

Closes the recording file but streaming continues independently.

---

### Frame Management

#### add_frame

```python
async def add_frame(self, image: Image.Image) -> None
```

Add a frame from a PIL Image.

Converts the image to raw RGB bytes and stores it, then sends to ffmpeg for encoding.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `image` | `Image.Image` | PIL Image (will be converted to RGB if needed) |

---

#### add_raw_frame

```python
async def add_raw_frame(self, data: bytes) -> None
```

Add a raw RGB frame.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `data` | `bytes` | Raw RGB24 bytes (width × height × 3 bytes) |

---

#### get_latest_frame

```python
def get_latest_frame(self) -> ScreenBuffer | None
```

Get the most recent raw frame.

---

#### get_frames

```python
def get_frames(self, count: int | None = None) -> list[ScreenBuffer]
```

Get recent raw frames.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `count` | `int \| None` | Number of frames to get. `None` for all. |

**Returns:** List of `ScreenBuffer` frames (oldest first).

---

#### clear_raw_frames

```python
def clear_raw_frames(self) -> None
```

Clear all raw frames from buffer.

---

### Video Chunks

#### get_video_chunks

```python
def get_video_chunks(self) -> list[VideoChunk]
```

Get all buffered video chunks.

---

#### get_next_video_chunk

```python
async def get_next_video_chunk(self, timeout: float = 1.0) -> VideoChunk | None
```

Wait for and return the next video chunk.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `timeout` | `float` | Maximum time to wait in seconds |

**Returns:** `VideoChunk` or `None` if timeout.

**Example:**

```python
# Stream video chunks
while display.is_streaming:
    chunk = await display.get_next_video_chunk(timeout=1.0)
    if chunk:
        await send_to_client(chunk.data)
```

---

#### clear_video_chunks

```python
def clear_video_chunks(self) -> None
```

Clear all video chunks from buffer.

---

### Saving Video

#### save_video

```python
async def save_video(self, path: str) -> bool
```

Save all buffered video chunks to a file.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Output file path |

**Returns:** `True` if successful, `False` otherwise.

---

#### save_buffer_as_video

```python
async def save_buffer_as_video(
    self, 
    path: str, 
    use_true_timing: bool = True
) -> bool
```

Encode the raw frame buffer to a video file.

When `use_true_timing=True` (default), the video duration matches the actual elapsed wall-clock time between frames.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Output file path |
| `use_true_timing` | `bool` | Match real elapsed time (default: True) |

**Returns:** `True` if successful, `False` otherwise.

**Example:**

```python
# Save the last ~10 seconds of buffered frames
await display.save_buffer_as_video("clip.mp4")
```

---

### Screenshots

#### screenshot

```python
async def screenshot(self) -> Image.Image
```

Capture the current screen as a PIL Image.

---

#### save_screenshot

```python
async def save_screenshot(self, path: str) -> None
```

Save a screenshot to a file.

---

### Utilities

#### print_stats

```python
def print_stats(self) -> None
```

Print current statistics to stdout.

---

## Usage Patterns

### Live Video Streaming

Stream encoded video chunks in real-time:

```python
async with RDPClient(host="...", username="...", password="...") as client:
    await client.start_streaming()
    
    display = client.display
    
    async def stream_chunks():
        while client.is_streaming:
            chunk = await display.get_next_video_chunk(timeout=1.0)
            if chunk:
                yield chunk.data
    
    async for data in stream_chunks():
        await send_to_websocket(data)
```

### Full Session Recording

Record an entire session to a file:

```python
async with RDPClient(host="...", username="...", password="...") as client:
    # Start recording to file (auto-starts streaming)
    await client.start_file_recording("full_session.ts")
    
    # Perform actions for any duration...
    await client.mouse_move(500, 300)
    await asyncio.sleep(300)  # 5 minutes
    
    # Stop recording
    await client.stop_file_recording()
    await client.stop_streaming()
```

### Simultaneous Streaming + Recording

Stream live while also saving to file:

```python
async with RDPClient(host="...", username="...", password="...") as client:
    # Start both
    await client.start_streaming()
    await client.start_file_recording("backup.ts")
    
    # Stream to clients
    async def stream():
        while client.is_streaming:
            chunk = await client.display.get_next_video_chunk()
            if chunk:
                await broadcast_to_clients(chunk.data)
    
    asyncio.create_task(stream())
    
    # ... session runs ...
    
    # Stop recording, streaming continues
    await client.stop_file_recording()
```

---

## Buffer Management

### Raw Frame Buffer

- Uses `collections.deque` with `maxlen` for O(1) operations
- Automatically evicts oldest frames when limit reached
- Default: `fps * 10` frames (~10 seconds)
- Uses wall-clock timestamps (`time.time()`) for accurate timing

### Video Chunk Buffer

- Encoded chunks stored in a deque
- Automatic eviction when exceeding `max_video_buffer_mb`
- Default: 100MB buffer cap (~2-5 minutes of video)
- Oldest chunks evicted first

### File Recording

- Taps into streaming output (same ffmpeg process)
- Writes chunks to file AND memory buffer
- No memory limits - unlimited duration
- Uses MPEG-TS format for robustness
