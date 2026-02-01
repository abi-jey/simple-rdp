# Simple RDP Browser Viewer

A browser-based RDP viewer that uses FastAPI and WebSockets to stream the remote desktop to your browser.

## Requirements

```bash
pip install fastapi uvicorn python-dotenv
```

## Setup

1. Make sure you have the RDP credentials in your `.env` file (in the project root):

```env
RDP_HOST=192.168.1.100
RDP_USER=your_username
RDP_PASS=your_password
```

2. Run the server:

```bash
cd examples/browser
python server.py
```

Or with uvicorn directly:

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

3. Open your browser to http://localhost:8000

## Features

- **Live Screen Streaming**: View the remote desktop in real-time (~10 FPS)
- **Connection Status**: Visual indicator showing RDP connection state
- **Resolution Display**: Shows the current screen resolution
- **FPS Counter**: Real-time frame rate display

## Architecture

```
┌─────────────────┐     WebSocket     ┌─────────────────┐
│                 │ ◄───────────────► │                 │
│    Browser      │     (frames)      │  FastAPI Server │
│   (HTML/JS)     │                   │                 │
└─────────────────┘                   └────────┬────────┘
                                               │
                                               │ RDP Protocol
                                               │
                                      ┌────────▼────────┐
                                      │                 │
                                      │  Windows RDP    │
                                      │     Server      │
                                      │                 │
                                      └─────────────────┘
```

## Future Enhancements

- [ ] Mouse input forwarding
- [ ] Keyboard input forwarding
- [ ] Video streaming (H.264)
- [ ] Adaptive quality based on bandwidth
