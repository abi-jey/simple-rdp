---
icon: material/keyboard
---

# Keyboard Input

Simple RDP supports sending keyboard input for text entry and key combinations.

## Typing Text

The easiest way to send text:

```python
# Type a string
await client.send_text("Hello, World!")
```

This sends each character as a Unicode key event.

## Sending Individual Keys

### By Character

```python
# Send single character
await client.send_key("a")
await client.send_key("A")  # Uppercase
await client.send_key("@")  # Special characters
```

### By Scancode

For special keys, use scancodes:

```python
# Common scancodes
await client.send_key(0x1C)  # Enter
await client.send_key(0x01)  # Escape
await client.send_key(0x0E)  # Backspace
await client.send_key(0x0F)  # Tab
await client.send_key(0x39)  # Space
```

## Key Press and Release

For modifier keys or key combinations, control press and release separately:

```python
# Press and hold
await client.send_key(0x1D, is_press=True, is_release=False)  # Ctrl down

# Type while holding
await client.send_key("a")  # Ctrl+A

# Release
await client.send_key(0x1D, is_press=False, is_release=True)  # Ctrl up
```

## Common Scancodes

??? abstract "Standard Keys"
    | Key | Scancode | Hex |
    |-----|----------|-----|
    | Escape | 1 | `0x01` |
    | 1-9 | 2-10 | `0x02`-`0x0A` |
    | 0 | 11 | `0x0B` |
    | Backspace | 14 | `0x0E` |
    | Tab | 15 | `0x0F` |
    | Q-P | 16-25 | `0x10`-`0x19` |
    | Enter | 28 | `0x1C` |
    | Left Ctrl | 29 | `0x1D` |
    | A-L | 30-38 | `0x1E`-`0x26` |
    | Left Shift | 42 | `0x2A` |
    | Z-M | 44-50 | `0x2C`-`0x32` |
    | Right Shift | 54 | `0x36` |
    | Left Alt | 56 | `0x38` |
    | Space | 57 | `0x39` |
    | Caps Lock | 58 | `0x3A` |
    | F1-F10 | 59-68 | `0x3B`-`0x44` |
    | F11 | 87 | `0x57` |
    | F12 | 88 | `0x58` |

### Extended Keys

!!! info "Extended Scancodes"
    For arrow keys and other extended keys, use scancodes with the `0xE0` prefix:

| Key | Scancode |
|-----|----------|
| Insert | `0xE052` |
| Delete | `0xE053` |
| Home | `0xE047` |
| End | `0xE04F` |
| Page Up | `0xE049` |
| Page Down | `0xE051` |
| Up Arrow | `0xE048` |
| Down Arrow | `0xE050` |
| Left Arrow | `0xE04B` |
| Right Arrow | `0xE04D` |

## Examples

### Copy-Paste Workflow

```python
# Select all (Ctrl+A)
await client.send_key(0x1D, is_press=True, is_release=False)  # Ctrl down
await client.send_key("a")
await client.send_key(0x1D, is_press=False, is_release=True)  # Ctrl up

# Copy (Ctrl+C)
await client.send_key(0x1D, is_press=True, is_release=False)
await client.send_key("c")
await client.send_key(0x1D, is_press=False, is_release=True)

# Paste (Ctrl+V)
await client.send_key(0x1D, is_press=True, is_release=False)
await client.send_key("v")
await client.send_key(0x1D, is_press=False, is_release=True)
```

### Open Run Dialog

```python
# Win+R
await client.send_key(0xE05B, is_press=True, is_release=False)  # Win key down
await client.send_key("r")
await client.send_key(0xE05B, is_press=False, is_release=True)  # Win key up
await asyncio.sleep(0.5)

# Type command
await client.send_text("notepad")

# Press Enter
await client.send_key(0x1C)
```

### Alt+Tab

```python
# Alt+Tab to switch windows
await client.send_key(0x38, is_press=True, is_release=False)  # Alt down
await client.send_key(0x0F)  # Tab
await client.send_key(0x38, is_press=False, is_release=True)  # Alt up
```

## Tips

!!! tip "Add delays between actions"
    ```python
    await client.send_text("username")
    await asyncio.sleep(0.1)
    await client.send_key(0x0F)  # Tab
    await asyncio.sleep(0.1)
    await client.send_text("password")
    ```

!!! success "Unicode Support"
    `send_text()` supports international text:
    
    ```python
    await client.send_text("こんにちは")  # Japanese
    await client.send_text("Привет")      # Russian
    await client.send_text("مرحبا")        # Arabic
    ```

!!! tip "Verify with screenshots"
    ```python
    await client.send_text("Hello")
    await asyncio.sleep(0.2)
    await client.save_screenshot("after_typing.png")
    ```
