# Input Types API Reference

Types and utilities for mouse and keyboard input.

## MouseButton

```python
from simple_rdp import MouseButton
```

Enum for mouse button identifiers.

### Values

| Value | Description |
|-------|-------------|
| `MouseButton.LEFT` | Left mouse button |
| `MouseButton.RIGHT` | Right mouse button |
| `MouseButton.MIDDLE` | Middle mouse button |

### Example

```python
from simple_rdp import MouseButton

button = MouseButton.LEFT
```

---

## KeyModifier

```python
from simple_rdp import KeyModifier
```

Enum for keyboard modifier keys.

### Values

| Value | Description |
|-------|-------------|
| `KeyModifier.SHIFT` | Shift key |
| `KeyModifier.CTRL` | Control key |
| `KeyModifier.ALT` | Alt key |
| `KeyModifier.WIN` | Windows key |

### Example

```python
from simple_rdp import KeyModifier

modifiers = (KeyModifier.CTRL, KeyModifier.SHIFT)
```

---

## MouseEvent

```python
from simple_rdp import MouseEvent
```

Dataclass representing a mouse event.

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `x` | `int` | *required* | X coordinate |
| `y` | `int` | *required* | Y coordinate |
| `button` | `MouseButton \| None` | `None` | Mouse button |
| `pressed` | `bool` | `False` | Whether button is pressed |

### Example

```python
from simple_rdp import MouseEvent, MouseButton

event = MouseEvent(
    x=500,
    y=300,
    button=MouseButton.LEFT,
    pressed=True,
)
```

---

## KeyEvent

```python
from simple_rdp import KeyEvent
```

Dataclass representing a keyboard event.

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `key_code` | `int` | *required* | Key scancode |
| `pressed` | `bool` | `True` | Whether key is pressed |
| `modifiers` | `tuple[KeyModifier, ...]` | `()` | Active modifiers |

### Example

```python
from simple_rdp import KeyEvent, KeyModifier

event = KeyEvent(
    key_code=0x1E,  # 'A' key
    pressed=True,
    modifiers=(KeyModifier.SHIFT,),  # Shift+A
)
```

---

## Common Scancodes Reference

### Alphanumeric Keys

| Key | Scancode | Hex |
|-----|----------|-----|
| 1-9, 0 | 2-11 | `0x02`-`0x0B` |
| Q-P | 16-25 | `0x10`-`0x19` |
| A-L | 30-38 | `0x1E`-`0x26` |
| Z-M | 44-50 | `0x2C`-`0x32` |

### Special Keys

| Key | Scancode | Hex |
|-----|----------|-----|
| Escape | 1 | `0x01` |
| Backspace | 14 | `0x0E` |
| Tab | 15 | `0x0F` |
| Enter | 28 | `0x1C` |
| Left Ctrl | 29 | `0x1D` |
| Left Shift | 42 | `0x2A` |
| Right Shift | 54 | `0x36` |
| Left Alt | 56 | `0x38` |
| Space | 57 | `0x39` |
| Caps Lock | 58 | `0x3A` |

### Function Keys

| Key | Scancode | Hex |
|-----|----------|-----|
| F1-F10 | 59-68 | `0x3B`-`0x44` |
| F11 | 87 | `0x57` |
| F12 | 88 | `0x58` |

### Extended Keys

Extended keys use the `0xE0` prefix:

| Key | Scancode | Hex |
|-----|----------|-----|
| Insert | E0 52 | `0xE052` |
| Delete | E0 53 | `0xE053` |
| Home | E0 47 | `0xE047` |
| End | E0 4F | `0xE04F` |
| Page Up | E0 49 | `0xE049` |
| Page Down | E0 51 | `0xE051` |
| Up Arrow | E0 48 | `0xE048` |
| Down Arrow | E0 50 | `0xE050` |
| Left Arrow | E0 4B | `0xE04B` |
| Right Arrow | E0 4D | `0xE04D` |
| Left Win | E0 5B | `0xE05B` |
| Right Win | E0 5C | `0xE05C` |
