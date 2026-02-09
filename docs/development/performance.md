# Performance

Simple RDP is designed for high-performance screen capture and input automation.

## Benchmarks

### Screenshot Performance

| Metric | Performance |
|--------|:-----------:|
| Screenshot FPS | ~30 FPS |
| CPU Usage | ~10% |
| RLE Decompression | Native Rust |

### Factors Affecting Performance

1. **Resolution** - Higher resolution = more data to process
2. **Color Depth** - 32-bit uses more bandwidth than 16-bit
3. **Screen Activity** - More changes = more bitmap updates
4. **Network Latency** - Affects input response time

## How It Works

Simple RDP uses a native Rust extension for RLE (Run-Length Encoding) bitmap decompression:

- Processes bytes ~100x faster than pure Python
- Releases the GIL during decompression
- Allows parallel processing of bitmap updates

## Optimization Tips

### 1. Disable Wallpaper

```python
client = RDPClient(
    ...,
    show_wallpaper=False,  # Default
)
```

Disabling wallpaper reduces:
- Initial connection time
- Bandwidth usage
- Number of bitmap updates

### 2. Use Appropriate Resolution

Only use the resolution you need:

```python
# For web automation
client = RDPClient(..., width=1280, height=720)

# For document work
client = RDPClient(..., width=1920, height=1080)
```

### 3. Lower Color Depth

If color accuracy isn't critical:

```python
client = RDPClient(..., color_depth=16)  # 65K colors
```

### 4. Batch Operations

Minimize round-trips by batching operations:

```python
# Less efficient
for char in "Hello":
    await client.send_key(char)
    await asyncio.sleep(0.1)

# More efficient
await client.send_text("Hello")
```

### 5. Minimize Screenshots

Only capture when needed:

```python
# Don't do this
while True:
    img = await client.screenshot()  # Captures every loop
    process(img)
    await asyncio.sleep(0.01)

# Do this
while True:
    if should_capture:
        img = await client.screenshot()
        process(img)
    await asyncio.sleep(0.1)
```

## Memory Usage

### Screen Buffer

The client maintains a screen buffer in memory:

```
Memory = width × height × 3 bytes (RGB)

1920×1080 = ~6.2 MB
2560×1440 = ~11.1 MB
3840×2160 = ~24.9 MB
```

### Cursor Cache

Cursor images are cached to avoid re-parsing:

```python
# Default cache size: unlimited
# Typical usage: < 1 MB
```

## Profiling

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Profile with cProfile

```python
import cProfile
import asyncio

async def benchmark():
    async with RDPClient(...) as client:
        await asyncio.sleep(2)
        for _ in range(100):
            await client.screenshot()

cProfile.run('asyncio.run(benchmark())')
```

### Measure FPS

```python
import time

async def measure_fps():
    async with RDPClient(...) as client:
        await asyncio.sleep(2)
        
        start = time.time()
        count = 0
        
        while time.time() - start < 10:  # 10 second test
            await client.screenshot()
            count += 1
        
        fps = count / 10
        print(f"FPS: {fps:.1f}")
```

## Network Considerations

### Bandwidth

Typical bandwidth usage:

| Activity | Bandwidth |
|----------|-----------|
| Idle desktop | ~10-50 KB/s |
| Normal work | ~100-500 KB/s |
| Video playback | ~1-5 MB/s |

### Latency

Mouse events use Fast-Path input for minimal latency:

- **Fast-Path**: Mouse events bypass TPKT/X.224/MCS headers (7 bytes per event vs ~30+ bytes slow-path)
- **Immediate Send**: Each mouse event is sent immediately without batching
- **No Timestamps**: Fast-path events don't include timestamps, reducing overhead

For responsive automation:

- LAN: < 10ms latency ideal
- VPN: 50-100ms acceptable
- High latency: Add appropriate delays

```python
# For high-latency connections
await client.mouse_click(500, 300)
await asyncio.sleep(0.2)  # Wait for response
```
