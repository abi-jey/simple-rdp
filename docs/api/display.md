# Display API Reference

The `Display` class provides video encoding and frame buffering capabilities using ffmpeg.

## Overview

The Display class manages:

- **Raw frame storage** - Uncompressed RGB frames in a deque buffer
- **Live video encoding** - Real-time H.264 encoding via ffmpeg subprocess  
- **Video buffering** - Async queue with configurable size limits
- **Frame eviction** - Automatic cleanup when buffers exceed limits

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
    timestamp: float = field(default_factory=time.perf_counter)
```

| Field | Type | Description |
|-------|------|-------------|
| `width` | `int` | Frame width in pixels |
| `height` | `int` | Frame height in pixels |
| `data` | `bytes` | Raw pixel data |
| `format` | `str` | Pixel format (default: `"RGB"`) |
| `timestamp` | `float` | Capture timestamp |

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

Return the size of the chunk in bytes.

---

### Display

Main class for video encoding and frame management.

## Constructor

```python
Display(
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    max_video_buffer_mb: float = 100,
    max_raw_frames: int = 300,
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `width` | `int` | `1920` | Frame width in pixels |
| `height` | `int` | `1080` | Frame height in pixels |
| `fps` | `int` | `30` | Target frames per second for encoding |
| `max_video_buffer_mb` | `float` | `100` | Maximum video buffer size in MB |
| `max_raw_frames` | `int` | `300` | Maximum raw frames to keep in memory |

### Example

```python
from simple_rdp import Display

# Create display for 1080p at 30fps
display = Display(width=1920, height=1080, fps=30)

# Create display with custom buffer limits
display = Display(
    width=1280,
    height=720,
    fps=60,
    max_video_buffer_mb=200,
    max_raw_frames=600,
)
```

---

## Properties

### width

```python
@property
def width(self) -> int
```

Frame width in pixels.

### height

```python
@property
def height(self) -> int
```

Frame height in pixels.

### fps

```python
@property
def fps(self) -> int
```

Target frames per second.

### frame_count

```python
@property
def frame_count(self) -> int
```

Total number of frames received since creation.

### raw_frame_count

```python
@property
def raw_frame_count(self) -> int
```

Number of raw frames currently in buffer.

### video_buffer_size_mb

```python
@property
def video_buffer_size_mb(self) -> float
```

Current video buffer size in megabytes.

### is_encoding

```python
@property
def is_encoding(self) -> bool
```

Whether ffmpeg encoding is currently active.

### stats

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

---

## Methods

### start_encoding

```python
async def start_encoding(self) -> None
```

Start the ffmpeg encoding process.

This spawns an ffmpeg subprocess that encodes incoming raw frames to H.264 video in MPEG-TS format.

!!! warning "ffmpeg Required"
    Ensure ffmpeg is installed and available in PATH.

**Example:**

```python
display = Display(width=1920, height=1080)
await display.start_encoding()
# ... add frames ...
await display.stop_encoding()
```

---

### stop_encoding

```python
async def stop_encoding(self) -> None
```

Stop the ffmpeg encoding process.

Closes stdin to signal EOF and waits for the process to finish.

---

### add_frame

```python
async def add_frame(self, image: Image.Image) -> None
```

Add a frame from a PIL Image.

Converts the image to raw RGB bytes and stores it, then sends to ffmpeg for encoding.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `image` | `Image.Image` | PIL Image (will be converted to RGB if needed) |

**Example:**

```python
from PIL import Image

display = Display(width=1920, height=1080)
await display.start_encoding()

# Add a PIL Image
img = Image.new("RGB", (1920, 1080), color="blue")
await display.add_frame(img)
```

---

### add_raw_frame

```python
async def add_raw_frame(self, data: bytes) -> None
```

Add a raw RGB frame.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `data` | `bytes` | Raw RGB24 bytes (width × height × 3 bytes) |

**Example:**

```python
# Add raw RGB bytes
raw_data = b"\x00" * (1920 * 1080 * 3)  # Black frame
await display.add_raw_frame(raw_data)
```

---

### get_latest_frame

```python
def get_latest_frame(self) -> ScreenBuffer | None
```

Get the most recent raw frame.

**Returns:** `ScreenBuffer` or `None` if no frames exist.

---

### get_frames

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

### get_video_chunks

```python
def get_video_chunks(self) -> list[VideoChunk]
```

Get all buffered video chunks.

**Returns:** List of `VideoChunk` objects.

---

### get_next_video_chunk

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
while True:
    chunk = await display.get_next_video_chunk(timeout=1.0)
    if chunk:
        # Send chunk to client/stream
        await send_to_client(chunk.data)
```

---

### clear_raw_frames

```python
def clear_raw_frames(self) -> None
```

Clear all raw frames from buffer.

---

### clear_video_chunks

```python
def clear_video_chunks(self) -> None
```

Clear all video chunks from buffer.

---

### save_video

```python
async def save_video(self, path: str) -> bool
```

Save all buffered video chunks to a file.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Output file path |

**Returns:** `True` if successful, `False` otherwise.

**Example:**

```python
# Save buffered video
success = await display.save_video("recording.ts")
```

---

### save_raw_frames_as_video

```python
async def save_raw_frames_as_video(
    self, 
    path: str, 
    fps: int | None = None
) -> bool
```

Encode raw frames to video file using ffmpeg.

This is useful when not using live encoding.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Output file path |
| `fps` | `int \| None` | Frames per second (default: instance fps) |

**Returns:** `True` if successful, `False` otherwise.

**Example:**

```python
# Record frames without live encoding
display = Display(width=1920, height=1080)

for frame in frames:
    await display.add_frame(frame)

# Encode all frames at once
await display.save_raw_frames_as_video("recording.mp4", fps=30)
```

---

### print_stats

```python
def print_stats(self) -> None
```

Print current statistics to stdout.

**Output example:**

```
==================================================
           DISPLAY STATS
==================================================
📷 Raw frames in buffer:  150
   Total frames received: 1000
🎬 Frames encoded:        1000
💾 Video buffer:          45.23 MB
   Bytes encoded:         45.23 MB
   Chunks evicted:        0
❌ Encoding errors:       0
==================================================
```

---

## Usage Patterns

### Live Video Streaming

Stream encoded video chunks in real-time:

```python
import asyncio
from simple_rdp import RDPClient, Display


async def stream_rdp(host: str, username: str, password: str):
    display = Display(width=1920, height=1080, fps=30)
    
    async with RDPClient(
        host=host,
        username=username,
        password=password,
    ) as client:
        await display.start_encoding()
        
        try:
            # Capture loop
            async def capture():
                while True:
                    img = await client.screenshot()
                    await display.add_frame(img)
                    await asyncio.sleep(1/30)  # 30 FPS
            
            # Stream loop
            async def stream():
                while True:
                    chunk = await display.get_next_video_chunk()
                    if chunk:
                        yield chunk.data  # Send to client
            
            # Run both concurrently
            await asyncio.gather(capture(), stream())
        finally:
            await display.stop_encoding()
```

### Batch Recording

Record frames and encode later:

```python
from simple_rdp import RDPClient, Display


async def record_session(host: str, username: str, password: str):
    display = Display(width=1920, height=1080, max_raw_frames=1000)
    
    async with RDPClient(
        host=host,
        username=username,
        password=password,
    ) as client:
        # Capture frames
        for _ in range(300):  # 10 seconds at 30fps
            img = await client.screenshot()
            await display.add_frame(img)
            await asyncio.sleep(1/30)
        
        # Encode to video file
        await display.save_raw_frames_as_video("session.mp4", fps=30)
        
        display.print_stats()
```

---

## Buffer Management

### Raw Frame Buffer

- Uses `collections.deque` with `maxlen` for O(1) operations
- Automatically evicts oldest frames when limit reached
- Default: 300 frames (~10 seconds at 30fps, ~1.5GB for 1080p)

### Video Chunk Buffer

- Encoded chunks stored in a deque
- Automatic eviction when exceeding `max_video_buffer_mb`
- Default: 100MB buffer cap
- Oldest chunks evicted first

### Async Queue

- New video chunks added to an async queue for consumers
- Back-pressure: drops chunks if queue is full
- Use `get_next_video_chunk()` for streaming patterns
