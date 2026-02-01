# Configuration

## Environment Variables

Simple RDP supports configuration through environment variables. Create a `.env` file in your project root:

```bash
# RDP Connection
RDP_HOST=192.168.1.100
RDP_PORT=3389
RDP_USER=your_username
RDP_PASS=your_password
RDP_DOMAIN=MYDOMAIN

# Display Settings
RDP_WIDTH=1920
RDP_HEIGHT=1080
RDP_COLOR_DEPTH=32
```

## Display Settings

### Resolution

Set the remote desktop resolution:

```python
client = RDPClient(
    host="...",
    width=1920,      # Horizontal resolution
    height=1080,     # Vertical resolution
)
```

Common resolutions:

| Resolution | Description |
|------------|-------------|
| 1920x1080 | Full HD (default) |
| 2560x1440 | 2K / QHD |
| 3840x2160 | 4K / UHD |
| 1280x720 | HD Ready |
| 1024x768 | XGA |

### Color Depth

```python
client = RDPClient(
    host="...",
    color_depth=32,  # 16, 24, or 32 bits per pixel
)
```

| Depth | Colors | Notes |
|-------|--------|-------|
| 16 | 65,536 | Lower bandwidth, faster |
| 24 | 16.7M | Good balance |
| 32 | 16.7M + Alpha | Best quality (default) |

### Performance Options

```python
client = RDPClient(
    host="...",
    show_wallpaper=False,  # Disable wallpaper for better performance
)
```

Disabling wallpaper reduces bandwidth and improves screen capture performance, which is recommended for automation use cases.

## Authentication

### Domain Authentication

For domain-joined machines:

```python
client = RDPClient(
    host="server.domain.local",
    username="admin",
    password="secret",
    domain="MYDOMAIN",
)
```

### Local Authentication

For local accounts, omit the domain or use the machine name:

```python
client = RDPClient(
    host="192.168.1.100",
    username="Administrator",
    password="secret",
    # domain not specified - uses local authentication
)
```

## Security Considerations

!!! danger "TLS Certificate Validation"
    This library does **NOT** validate TLS certificates when connecting to RDP servers.
    
    **Implications:**
    
    - Connections are vulnerable to man-in-the-middle (MITM) attacks
    - Server identity is not verified
    
    **Recommendations:**
    
    - Only use in trusted network environments
    - Use VPN for remote connections
    - Do not use for production workloads with sensitive data

## Logging

Enable debug logging for troubleshooting:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("simple_rdp")
logger.setLevel(logging.DEBUG)
```

Log levels:

- `DEBUG` - Protocol-level details, PDU parsing
- `INFO` - Connection events, screenshots
- `WARNING` - Non-critical issues
- `ERROR` - Connection failures, protocol errors
