# Protocol Reference

Simple RDP implements the Microsoft RDP protocol (MS-RDPBCGR) for Remote Desktop connections.

## Protocol Stack

```
┌─────────────────────────────────────┐
│         RDP Application             │
│   (Screen capture, Input events)    │
├─────────────────────────────────────┤
│           RDP PDU Layer             │
│   (Bitmap updates, Input PDUs)      │
├─────────────────────────────────────┤
│            MCS Layer                │
│   (T.125 Multipoint Communication)  │
├─────────────────────────────────────┤
│          CredSSP / NLA              │
│   (NTLM authentication over TLS)    │
├─────────────────────────────────────┤
│          TLS / SSL                  │
│   (Transport encryption)            │
├─────────────────────────────────────┤
│           X.224 / TPKT              │
│   (Connection establishment)        │
├─────────────────────────────────────┤
│              TCP                    │
│         (Port 3389)                 │
└─────────────────────────────────────┘
```

## Connection Sequence

### 1. X.224 Connection Request

```
Client → Server: Connection Request PDU
Server → Client: Connection Confirm PDU
```

### 2. TLS Handshake

Standard TLS 1.2/1.3 handshake over the X.224 connection.

!!! warning
    Simple RDP does not validate server certificates.

### 3. CredSSP Authentication (NLA)

Network Level Authentication using CredSSP v6:

1. **NTLM Negotiate** - Client sends negotiation message
2. **NTLM Challenge** - Server responds with challenge
3. **NTLM Authenticate** - Client sends credentials
4. **TSRequest with Credentials** - Final authentication

### 4. MCS Connection

T.125 Multipoint Communication Service:

```
Client → Server: MCS Connect Initial
Server → Client: MCS Connect Response
Client → Server: Erect Domain Request
Client → Server: Attach User Request
Server → Client: Attach User Confirm
Client → Server: Channel Join Request (for each channel)
Server → Client: Channel Join Confirm
```

### 5. RDP Security Commencement

```
Client → Server: Client Info PDU (encrypted)
Server → Client: License Error PDU (typically "valid client")
```

### 6. Capability Exchange

```
Server → Client: Demand Active PDU (server capabilities)
Client → Server: Confirm Active PDU (client capabilities)
```

### 7. Connection Finalization

```
Client → Server: Synchronize PDU
Client → Server: Control PDU (Cooperate)
Client → Server: Control PDU (Request Control)
Client → Server: Font List PDU
Server → Client: Synchronize PDU
Server → Client: Control PDU (Granted Control)
Server → Client: Font Map PDU
```

### 8. Data Exchange

After finalization, the connection is established:

- Server sends bitmap updates (Fast-Path or Slow-Path)
- Client sends input events (keyboard, mouse)

## Implemented Features

### Bitmap Updates

| Update Type | Implemented | Notes |
|-------------|-------------|-------|
| Fast-Path Bitmap | ✅ | Primary method |
| Slow-Path Bitmap | ✅ | Fallback |
| Interleaved RLE | ✅ | With Rust acceleration |
| Raw Bitmap | ✅ | Uncompressed |

### Input Events

| Event Type | Implemented |
|------------|-------------|
| Keyboard Scancode | ✅ |
| Keyboard Unicode | ✅ |
| Mouse Movement | ✅ |
| Mouse Button | ✅ |
| Mouse Wheel | ✅ |

### Capabilities

| Capability | Implemented |
|------------|-------------|
| General | ✅ |
| Bitmap | ✅ |
| Order | ✅ |
| Pointer | ✅ |
| Input | ✅ |
| Virtual Channel | ✅ |
| Sound | ❌ |
| Font | ✅ |
| Brush | ✅ |
| Glyph Cache | ✅ |
| Offscreen Bitmap | ✅ |
| Large Pointer | ✅ |
| Desktop Composition | ❌ |

### Pointer Updates

| Update Type | Implemented |
|-------------|-------------|
| Position | ✅ |
| System Default | ✅ |
| Null (Hidden) | ✅ |
| Color Pointer | ✅ |
| Cached Pointer | ✅ |
| New Pointer | ✅ |
| Large Pointer | ✅ |

## Not Implemented

The following features are not implemented (not needed for automation):

- Sound/Audio redirection
- Clipboard redirection  
- File/Drive redirection
- Printer redirection
- Smart card redirection
- Desktop composition (Aero)
- RemoteFX codec
- H.264/AVC codec
- Graphics pipeline

## References

- [MS-RDPBCGR](https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpbcgr/) - RDP Basic Connectivity and Graphics Remoting
- [MS-RDPELE](https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpele/) - Licensing Extension
- [MS-CSSP](https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-cssp/) - Credential Security Support Provider
- [T.125](https://www.itu.int/rec/T-REC-T.125/) - Multipoint Communication Service Protocol

## Code Organization

| Module | Purpose |
|--------|---------|
| `client.py` | RDPClient, connection management, high-level API |
| `pdu.py` | PDU encoding/decoding, bitmap parsing |
| `mcs.py` | MCS layer, channel management |
| `credssp.py` | CredSSP/NLA authentication |
| `capabilities.py` | Capability set negotiation |
| `rle.py` | RLE bitmap decompression |
| `display.py` | Display class, video encoding |
| `input.py` | Input event types |
