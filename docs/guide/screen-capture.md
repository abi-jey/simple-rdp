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
        img = await client.screenshot()
        print(f"Size: {img.size}")
        print(f"Mode: {img.mode}")  # RGB


asyncio.run(main())
```

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
            await asyncio.sleep(0.1)  # ~10 FPS


asyncio.run(capture_loop())
```

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

### 1. Use Rust Acceleration

Install the optional Rust extension for ~2x faster screen capture:

```bash
maturin develop --release
```

### 2. Disable Wallpaper

```python
client = RDPClient(
    ...,
    show_wallpaper=False,  # Reduces bandwidth
)
```

### 3. Lower Color Depth

```python
client = RDPClient(
    ...,
    color_depth=16,  # 16-bit color is faster
)
```

### 4. Appropriate Resolution

Use only the resolution you need:

```python
client = RDPClient(
    ...,
    width=1280,
    height=720,  # Smaller = faster
)
```

## Screen Update Mechanism

Simple RDP maintains an internal screen buffer that is updated incrementally as the RDP server sends bitmap updates. The `screenshot()` method returns a copy of this buffer.

The screen buffer is updated in the background by a receive loop that processes:

- Fast-Path bitmap updates (compressed with RLE)
- Bitmap update PDUs
- Pointer updates

This means screenshots always reflect the current screen state, not just the initial connection.
