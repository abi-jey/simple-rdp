# Display API Reference

The `Display` class provides video encoding and frame buffering capabilities using ffmpeg.

!!! info "Integrated with RDPClient"
    The `Display` is automatically integrated into `RDPClient`. Access it via `client.display`.
    
    Video streaming is "always-on" in the background when connected. You can consume the stream via `get_next_video_chunk()` or record the session to a file.

## Overview

The Display class manages:

- **Live video streaming** - Real-time H.264 encoding via ffmpeg subprocess (Fragmented MP4)
- **Automatic recording** - All sessions are recorded to a temp file
- **Real-time Queue** - Async queue for live consumers with back-pressure handling
- **Pipeline Statistics** - Detailed latency and performance metrics

---

## Classes

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
| `data` | `bytes` | Encoded video bytes (fMP4 atom) |
| `timestamp` | `float` | Creation timestamp |
| `sequence` | `int` | Chunk sequence number |

#### Properties

##### size_bytes

```python
@property
def size_bytes(self) -> int
```

Return the size of the encoded data in bytes.

---

### PipelineStats

A dataclass containing performance metrics.

```python
@dataclass
class PipelineStats:
    bitmap_to_buffer_ms: float
    frame_to_ffmpeg_ms: float
    ffmpeg_latency_ms: float
    total_e2e_estimate_ms: float
    frames_received: int
    frames_encoded: int
    chunks_produced: int
    queue_drops: int
    bitmaps_applied: int
    consumer_lag_chunks: int
```

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
        queue_size: int = 600,
    ) -> None
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `width` | `int` | `1920` | Frame width in pixels |
| `height` | `int` | `1080` | Frame height in pixels |
| `fps` | `int` | `30` | Target frames per second |
| `queue_size` | `int` | `600` | Max chunks in queue before dropping (~20s) |

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

---

### Encoding State

#### is_streaming

```python
@property
def is_streaming(self) -> bool
```

True if video encoding/streaming is active.

#### consumer_lag_chunks

```python
@property
def consumer_lag_chunks(self) -> int
```

Number of chunks waiting in the queue.
- 0-10: Healthy
- 10-50: Slight lag
- 50+: Significant lag
- 600 (Max): Chunks are being dropped

#### recording_duration_seconds

```python
@property
def recording_duration_seconds(self) -> float
```

How long encoding has been active in seconds.

#### effective_fps

```python
@property
def effective_fps(self) -> float
```

The actual frames per second being received/processed.

#### stats

```python
@property
def stats(self) -> dict[str, int]
```

Get raw statistics counters.

---

### Screen Buffer

#### raw_display_image

```python
@property
def raw_display_image(self) -> Image.Image | None
```

The current clean screen buffer (without pointer) as a PIL Image.

---

## Methods

### Streaming

#### get_next_video_chunk

```python
async def get_next_video_chunk(self, timeout: float = 1.0) -> VideoChunk | None
```

Wait for and return the next video chunk. This is the primary method for real-time consumers.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `timeout` | `float` | Maximum time to wait in seconds |

**Returns:** `VideoChunk` or `None` if timeout.

#### is_consumer_behind

```python
def is_consumer_behind(self, threshold: int = 10) -> bool
```

Check if the consumer is falling behind the live stream.

### Diagnostics

#### get_pipeline_stats

```python
def get_pipeline_stats(self) -> PipelineStats
```

Get detailed pipeline statistics including latency measurements.

#### print_stats

```python
def print_stats(self) -> None
```

Print current statistics to stdout.

### Utilities

#### transcode

```python
@staticmethod
def transcode(input_path: str, output_path: str) -> bool
```

Transcode a video file (e.g., .ts to .mp4) using stream copy.

### Screenshots

#### screenshot

```python
async def screenshot(self) -> Image.Image
```

Capture the current screen (with pointer) as a PIL Image.

#### save_screenshot

```python
async def save_screenshot(self, path: str) -> None
```

Save a screenshot to a file.
