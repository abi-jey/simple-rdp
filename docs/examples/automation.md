# Automation Scripts

This page provides example automation scripts using Simple RDP.

## Basic Automation Template

```python
import asyncio
import os
from dotenv import load_dotenv
from simple_rdp import RDPClient

load_dotenv()


async def main():
    async with RDPClient(
        host=os.environ["RDP_HOST"],
        username=os.environ["RDP_USER"],
        password=os.environ["RDP_PASS"],
    ) as client:
        # Wait for desktop to load
        await asyncio.sleep(3)
        
        # Your automation code here
        
        # Capture final state
        await client.save_screenshot("result.png")


if __name__ == "__main__":
    asyncio.run(main())
```

## Launch Application

```python
async def launch_notepad(client):
    """Launch Notepad via Run dialog."""
    # Win+R to open Run dialog
    await client.send_key(0xE05B, is_press=True, is_release=False)  # Win down
    await client.send_key("r")
    await client.send_key(0xE05B, is_press=False, is_release=True)  # Win up
    await asyncio.sleep(0.5)
    
    # Type "notepad" and press Enter
    await client.send_text("notepad")
    await asyncio.sleep(0.1)
    await client.send_key(0x1C)  # Enter
    
    await asyncio.sleep(1)  # Wait for app to open
```

## Login Automation

```python
async def login(client, username, password):
    """Login to a Windows session or application."""
    # Click username field (adjust coordinates)
    await client.mouse_click(960, 500)
    await asyncio.sleep(0.2)
    
    # Clear existing text
    await client.send_key(0x1D, is_press=True, is_release=False)  # Ctrl
    await client.send_key("a")
    await client.send_key(0x1D, is_press=False, is_release=True)
    
    # Type username
    await client.send_text(username)
    
    # Tab to password field
    await client.send_key(0x0F)  # Tab
    await asyncio.sleep(0.1)
    
    # Type password
    await client.send_text(password)
    
    # Press Enter to login
    await client.send_key(0x1C)
    await asyncio.sleep(2)
```

## File Operations

```python
async def save_file(client, filename):
    """Save current file with Ctrl+S."""
    # Ctrl+S
    await client.send_key(0x1D, is_press=True, is_release=False)
    await client.send_key("s")
    await client.send_key(0x1D, is_press=False, is_release=True)
    await asyncio.sleep(0.5)
    
    # Type filename
    await client.send_text(filename)
    
    # Press Enter
    await client.send_key(0x1C)
    await asyncio.sleep(0.5)


async def open_file_dialog(client):
    """Open file dialog with Ctrl+O."""
    await client.send_key(0x1D, is_press=True, is_release=False)
    await client.send_key("o")
    await client.send_key(0x1D, is_press=False, is_release=True)
    await asyncio.sleep(0.5)
```

## Menu Navigation

```python
async def navigate_menu(client, *items):
    """Navigate through menus by clicking coordinates.
    
    Example:
        await navigate_menu(client,
            (50, 30),   # File menu
            (50, 100),  # Open option
        )
    """
    for x, y in items:
        await client.mouse_click(x, y)
        await asyncio.sleep(0.3)
```

## Scroll and Read

```python
async def scroll_and_capture(client, output_dir, num_pages=5):
    """Scroll through content and capture each page."""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(num_pages):
        # Capture current view
        await client.save_screenshot(f"{output_dir}/page_{i:03d}.png")
        
        # Scroll down (Page Down)
        await client.send_key(0xE051)
        await asyncio.sleep(0.5)
```

## Complete Example: Notepad Automation

```python
import asyncio
import os
from dotenv import load_dotenv
from simple_rdp import RDPClient

load_dotenv()


async def notepad_automation():
    async with RDPClient(
        host=os.environ["RDP_HOST"],
        username=os.environ["RDP_USER"],
        password=os.environ["RDP_PASS"],
    ) as client:
        await asyncio.sleep(3)  # Wait for desktop
        
        # Open Notepad
        await client.send_key(0xE05B, is_press=True, is_release=False)
        await client.send_key("r")
        await client.send_key(0xE05B, is_press=False, is_release=True)
        await asyncio.sleep(0.5)
        
        await client.send_text("notepad")
        await client.send_key(0x1C)
        await asyncio.sleep(1)
        
        # Type some text
        await client.send_text("Hello from Simple RDP!\n")
        await client.send_text("This text was typed automatically.\n")
        await client.send_text(f"Timestamp: {asyncio.get_event_loop().time()}\n")
        
        # Save file
        await client.send_key(0x1D, is_press=True, is_release=False)
        await client.send_key("s")
        await client.send_key(0x1D, is_press=False, is_release=True)
        await asyncio.sleep(0.5)
        
        await client.send_text("C:\\Users\\Public\\Documents\\test.txt")
        await client.send_key(0x1C)
        await asyncio.sleep(0.5)
        
        # Take screenshot
        await client.save_screenshot("notepad_result.png")
        
        # Close Notepad
        await client.send_key(0x38, is_press=True, is_release=False)  # Alt
        await client.send_key(0x3E)  # F4
        await client.send_key(0x38, is_press=False, is_release=True)


if __name__ == "__main__":
    asyncio.run(notepad_automation())
```

## Error Handling

```python
async def safe_automation(client):
    """Example with error handling."""
    try:
        # Your automation code
        await client.mouse_click(500, 300)
        await asyncio.sleep(0.5)
        
    except Exception as e:
        # Capture screenshot for debugging
        await client.save_screenshot("error_state.png")
        raise
```

## Tips for Reliable Automation

1. **Use adequate delays** - UI operations need time to complete
2. **Verify with screenshots** - Check state before proceeding
3. **Handle variability** - Screen positions may differ
4. **Log actions** - Debug automation failures more easily
5. **Use try/except** - Capture screenshots on failure
