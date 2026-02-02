# Screen Capture

Simple RDP provides screen capture capabilities through the `screenshot()` method.

## Basic Screenshot

```python
import asyncio
from simple_rdp import RDPClient


async def main():
    async with RDPClient(
        host="192.168.1.100",
        username="admin",
        password="secret",
    ) as client:
        # Wait for screen to render
        await asyncio.sleep(2)
        
        # Capture as PIL Image
        img = await client.screenshot()  # (1)!
        print(f"Size: {img.size}")  # (2)!
        print(f"Mode: {img.mode}")  # RGB


asyncio.run(main())
```

1.  :material-image: Returns a `PIL.Image.Image` in RGB mode
2.  :material-resize: Size matches the configured `width` and `height`

## Save Screenshot

```python
# Save directly to file
await client.save_screenshot("screenshot.png")

# Or save the PIL Image
img = await client.screenshot()
img.save("screenshot.png")
img.save("screenshot.jpg", quality=90)
```

## Continuous Capture

For video recording or monitoring:

```python
import asyncio
from simple_rdp import RDPClient


async def capture_loop():
    async with RDPClient(...) as client:
        await asyncio.sleep(2)  # Wait for initial render
        
        frame_count = 0
        while frame_count < 100:
            img = await client.screenshot()
            img.save(f"frames/frame_{frame_count:04d}.png")
            frame_count += 1
            await asyncio.sleep(0.1)  # ~10 FPS  # (1)!


asyncio.run(capture_loop())
```

1.  :material-speedometer: You can achieve up to 30 FPS with continuous capture

!!! tip "Performance"
    For higher frame rates, consider saving frames asynchronously.

## Screenshot with Cursor

The cursor can be composited into screenshots. Access cursor state via:

```python
# Get cursor position
x, y = client.pointer_position

# Check if cursor is visible
if client.pointer_visible:
    # Get cursor image (PIL Image or None)
    cursor_img = client.pointer_image
    
    # Get cursor hotspot (click point offset)
    hotspot_x, hotspot_y = client.pointer_hotspot
```

See [Pointer/Cursor](pointer.md) for more details.

## Image Processing

Screenshots are returned as PIL Images, making it easy to process:

```python
from PIL import Image

img = await client.screenshot()

# Crop a region
region = img.crop((100, 100, 500, 400))

# Resize
thumbnail = img.resize((480, 270))

# Convert to grayscale
gray = img.convert("L")

# Get pixel data
pixels = list(img.getdata())

# Convert to numpy array (with numpy installed)
import numpy as np
arr = np.array(img)
```

## Performance Tips

??? tip "Disable Wallpaper"
    ```python
    client = RDPClient(
        ...,
        show_wallpaper=False,  # Reduces bandwidth
    )
    ```

??? tip "Lower Color Depth"
    ```python
    client = RDPClient(
        ...,
        color_depth=16,  # 16-bit color is faster
    )
    ```

??? tip "Appropriate Resolution"
    Use only the resolution you need:
    
    ```python
    client = RDPClient(
        ...,
        width=1280,
        height=720,  # Smaller = faster
    )
    ```

## Screen Update Mechanism

!!! info "How Screen Capture Works"
    Simple RDP maintains an internal screen buffer that is updated incrementally as the RDP server sends bitmap updates. The `screenshot()` method returns a copy of this buffer.

    The screen buffer is updated in the background by a receive loop that processes:

    - :material-lightning-bolt: Fast-Path bitmap updates (compressed with RLE)
    - :material-image-frame: Bitmap update PDUs
    - :material-cursor-default: Pointer updates

    This means screenshots always reflect the current screen state, not just the initial connection.

---

## Video Recording with Display

For video recording and streaming, use the `Display` class which provides:

- :material-video: Live H.264 encoding via ffmpeg
- :material-database: Raw frame buffer with automatic eviction
- :material-play-box-multiple: Async video chunk queue for streaming

### Basic Video Recording

```python
import asyncio
from simple_rdp import RDPClient, Display


async def record_session():
    display = Display(width=1920, height=1080, fps=30)
    
    async with RDPClient(
        host="192.168.1.100",
        username="admin",
        password="secret",
    ) as client:
        await asyncio.sleep(2)  # Wait for initial render
        
        # Record 300 frames (~10 seconds at 30fps)
        for _ in range(300):
            img = await client.screenshot()
            await display.add_frame(img)  # (1)!
            await asyncio.sleep(1/30)
        
        # Save as video file
        await display.save_raw_frames_as_video("recording.mp4")  # (2)!
        display.print_stats()


asyncio.run(record_session())
```

1.  :material-image-plus: Adds frame to buffer (no encoding yet)
2.  :material-movie-open: Encodes all buffered frames to video

### Live Video Streaming

For real-time encoding and streaming:

```python
import asyncio
from simple_rdp import RDPClient, Display


async def stream_rdp():
    display = Display(width=1920, height=1080, fps=30)
    
    async with RDPClient(
        host="192.168.1.100",
        username="admin",
        password="secret",
    ) as client:
        await display.start_encoding()  # (1)!
        
        try:
            # Capture and encode loop
            for _ in range(300):
                img = await client.screenshot()
                await display.add_frame(img)  # (2)!
                await asyncio.sleep(1/30)
            
            # Save encoded video
            await display.save_video("stream.ts")  # (3)!
        finally:
            await display.stop_encoding()


asyncio.run(stream_rdp())
```

1.  :material-play: Starts ffmpeg subprocess for live encoding
2.  :material-export: Frame is immediately encoded to H.264
3.  :material-content-save: Saves buffered MPEG-TS chunks

### Streaming Video Chunks

Get encoded chunks for network streaming:

```python
async def get_video_stream(display: Display):
    while True:
        chunk = await display.get_next_video_chunk(timeout=1.0)
        if chunk:
            # Send to WebSocket, HTTP stream, etc.
            yield chunk.data
```

!!! tip "See Also"
    For complete API reference, see [Display API](../api/display.md).
