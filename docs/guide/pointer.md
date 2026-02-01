# Pointer/Cursor

Simple RDP tracks the cursor state from the RDP server, including position, visibility, and cursor image.

## Cursor Properties

### Position

```python
# Get current cursor position
x, y = client.pointer_position
print(f"Cursor at: ({x}, {y})")
```

!!! note
    The RDP server only sends position updates when it programmatically moves the cursor (e.g., for focus changes). When you send mouse move events, track position locally.

### Visibility

```python
# Check if cursor is visible
if client.pointer_visible:
    print("Cursor is visible")
else:
    print("Cursor is hidden")
```

### Cursor Image

```python
# Get cursor image (PIL Image or None)
cursor_img = client.pointer_image
if cursor_img:
    cursor_img.save("cursor.png")
    print(f"Cursor size: {cursor_img.size}")
```

### Hotspot

The hotspot is the point within the cursor image that represents the actual click position:

```python
# Get hotspot offset
hotspot_x, hotspot_y = client.pointer_hotspot
print(f"Hotspot: ({hotspot_x}, {hotspot_y})")
```

## Compositing Cursor into Screenshots

For automation that needs to see the cursor in screenshots, you can composite it:

```python
from PIL import Image


async def screenshot_with_cursor(client, cursor_x, cursor_y):
    """Capture screenshot with cursor composited."""
    # Get the screenshot
    screenshot = await client.screenshot()
    
    # Get cursor state
    cursor_img = client.pointer_image
    if cursor_img is None or not client.pointer_visible:
        return screenshot
    
    # Calculate cursor position (accounting for hotspot)
    hotspot_x, hotspot_y = client.pointer_hotspot
    paste_x = cursor_x - hotspot_x
    paste_y = cursor_y - hotspot_y
    
    # Composite cursor onto screenshot
    result = screenshot.copy()
    if cursor_img.mode != "RGBA":
        cursor_img = cursor_img.convert("RGBA")
    
    try:
        result.paste(cursor_img, (paste_x, paste_y), cursor_img)
    except Exception:
        pass  # Cursor out of bounds
    
    return result
```

## Cursor Types

The RDP protocol supports various cursor update types:

| Update Type | Description |
|-------------|-------------|
| Position | Cursor moved by server |
| Default | System default arrow cursor |
| Null | Cursor hidden |
| Color | Colored cursor with transparency |
| Cached | Use previously cached cursor |
| New Pointer | New cursor image with palette |
| Large Pointer | High-resolution cursor (up to 384x384) |

Simple RDP handles all these types and maintains a cursor cache for efficient updates.

## Example: Track Cursor

```python
import asyncio
from simple_rdp import RDPClient


async def track_cursor():
    async with RDPClient(...) as client:
        await asyncio.sleep(2)
        
        local_x, local_y = 500, 500  # Track local position
        
        for _ in range(50):
            # Move cursor
            await client.mouse_move(local_x, local_y)
            
            # Take screenshot with cursor
            img = await screenshot_with_cursor(client, local_x, local_y)
            
            # Move in a pattern
            local_x += 10
            local_y += 5
            
            await asyncio.sleep(0.1)


asyncio.run(track_cursor())
```

## Browser Viewer Cursor Compositing

The browser viewer example demonstrates server-side cursor compositing. The cursor is drawn into each frame before sending to the browser, making it visible in the streamed video.

See [Browser Viewer Example](../examples/browser-viewer.md) for details.
