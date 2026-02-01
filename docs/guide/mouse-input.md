# Mouse Input

Simple RDP provides comprehensive mouse input capabilities for automation.

## Moving the Mouse

```python
# Move mouse to position (x, y)
await client.mouse_move(500, 300)
```

## Clicking

### Left Click

```python
# Left click at position
await client.mouse_click(500, 300)

# Explicit button number (1=left)
await client.mouse_click(500, 300, button=1)
```

### Right Click

```python
# Right click
await client.mouse_click(500, 300, button=2)
```

### Middle Click

```python
# Middle click
await client.mouse_click(500, 300, button=3)
```

### Double Click

```python
# Double left click
await client.mouse_click(500, 300, double_click=True)

# Double right click
await client.mouse_click(500, 300, button=2, double_click=True)
```

## Mouse Button Control

For more precise control, use separate down/up events:

```python
# Press button down
await client.mouse_button_down(500, 300, button="left")

# Do something while button is held...
await asyncio.sleep(0.5)

# Release button
await client.mouse_button_up(500, 300, button="left")
```

Button names: `"left"`, `"right"`, `"middle"` (or numbers 1, 2, 3)

## Dragging

```python
# Drag from (100, 100) to (300, 300) with left button
await client.mouse_drag(100, 100, 300, 300)

# Drag with right button
await client.mouse_drag(100, 100, 300, 300, button=2)
```

The `mouse_drag` method:

1. Moves to start position
2. Presses button down
3. Moves to end position
4. Releases button

## Mouse Wheel

```python
# Scroll up
await client.mouse_wheel(500, 300, delta=120)

# Scroll down
await client.mouse_wheel(500, 300, delta=-120)

# Scroll multiple notches
await client.mouse_wheel(500, 300, delta=360)  # 3 notches up
```

Standard wheel delta is ±120 per notch.

## Complete Example

```python
import asyncio
from simple_rdp import RDPClient


async def automation_example():
    async with RDPClient(
        host="192.168.1.100",
        username="admin",
        password="secret",
    ) as client:
        await asyncio.sleep(2)  # Wait for desktop
        
        # Click on Start button (bottom-left)
        await client.mouse_click(50, 1050)
        await asyncio.sleep(0.5)
        
        # Move to a menu item
        await client.mouse_move(100, 900)
        await asyncio.sleep(0.2)
        
        # Double-click to open an app
        await client.mouse_click(100, 900, double_click=True)
        await asyncio.sleep(1)
        
        # Scroll in a window
        await client.mouse_wheel(500, 500, delta=-360)
        
        # Drag a file
        await client.mouse_drag(200, 200, 400, 400)
        
        # Take screenshot of result
        await client.save_screenshot("result.png")


asyncio.run(automation_example())
```

## Button Reference

| Button | Number | Name |
|--------|--------|------|
| Left | 1 | `"left"` |
| Right | 2 | `"right"` |
| Middle | 3 | `"middle"` |

## Coordinate System

- Origin (0, 0) is the top-left corner of the screen
- X increases to the right
- Y increases downward
- Coordinates must be within the screen bounds (0 to width-1, 0 to height-1)

```
(0,0) ──────────────────► X (width)
  │
  │
  │
  │
  ▼
  Y (height)
```

## Tips for Reliable Automation

1. **Add delays after actions** - UI elements need time to respond

    ```python
    await client.mouse_click(500, 300)
    await asyncio.sleep(0.3)  # Wait for UI response
    ```

2. **Use screenshots to verify** - Capture screens before/after actions

3. **Handle different resolutions** - Calculate positions relative to screen size

    ```python
    center_x = client.width // 2
    center_y = client.height // 2
    await client.mouse_click(center_x, center_y)
    ```
