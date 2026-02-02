---
icon: material/test-tube
---

# Testing with VirtualBox

This guide walks you through setting up a Windows virtual machine for testing Simple RDP.

## Prerequisites

- [VirtualBox](https://www.virtualbox.org/wiki/Downloads) installed
- Windows ISO image (download from [Microsoft](https://www.microsoft.com/software-download/windows11))
- At least 4GB RAM and 50GB disk space available

## Setting Up the VM

### 1. Create a New Virtual Machine

1. Open VirtualBox and click **New**
2. Configure the VM:
    - **Name**: `Windows-RDP-Test`
    - **Type**: Microsoft Windows
    - **Version**: Windows 11 (64-bit)
3. Allocate resources:
    - **Memory**: 4096 MB (minimum)
    - **Processors**: 2 cores
    - **Hard disk**: 50 GB (dynamically allocated)

### 2. Configure Network

!!! important "Network Configuration"
    The VM must be accessible from your host machine.

=== ":material-bridge: Bridged Adapter (Recommended)"

    Gives the VM its own IP on your local network:
    
    1. Select the VM → **Settings** → **Network**
    2. Set **Attached to**: `Bridged Adapter`
    3. Select your active network interface

=== ":material-transit-connection-variant: Host-Only Adapter"

    Creates a private network between host and VM:
    
    1. Go to **File** → **Host Network Manager**
    2. Click **Create** to add a host-only network
    3. In VM settings → **Network** → **Adapter 2**
    4. Enable and set to `Host-only Adapter`

### 3. Install Windows

1. Start the VM and select your Windows ISO
2. Follow the installation wizard
3. Create a local account (skip Microsoft account)

??? tip "Windows Activation"
    For testing purposes, you can use [Microsoft Activation Scripts](https://github.com/massgravel/Microsoft-Activation-Scripts):
    
    1. Open PowerShell as Administrator
    2. Run:
        ```powershell
        irm https://get.activated.win | iex
        ```
    3. Select option `1` for HWID activation

## Enabling Remote Desktop

### 1. Enable RDP in Windows Settings

1. Open **Settings** → **System** → **Remote Desktop**
2. Toggle **Remote Desktop** to **On**
3. Click **Confirm** when prompted

??? abstract "Alternative: Using System Properties"
    1. Press ++win+r++, type `sysdm.cpl`, press ++enter++
    2. Go to **Remote** tab
    3. Select **Allow remote connections to this computer**
    4. Uncheck **Allow connections only from computers running Remote Desktop with Network Level Authentication** (optional, for compatibility)
    5. Click **OK**

### 2. Configure Firewall

Remote Desktop should automatically configure the firewall. To verify:

1. Open **Windows Defender Firewall**
2. Click **Allow an app through firewall**
3. Ensure **Remote Desktop** is checked for your network type

### 3. Note Your Credentials

You'll need:

- **Username**: Your Windows account name
- **Password**: Your Windows account password

!!! warning "Password Required"
    RDP requires a password. If your account has no password, set one:
    
    1. Press ++ctrl+alt+del++
    2. Click **Change a password**
    3. Set a password

## Getting the VM's IP Address

### From Windows (inside VM)

Open Command Prompt or PowerShell and run:

```batch
ipconfig
```

Look for the **IPv4 Address** under your network adapter:

```
Ethernet adapter Ethernet:
   IPv4 Address. . . . . . . . . . . : 192.168.1.105
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . . : 192.168.1.1
```

### From Host (using VirtualBox)

```bash
VBoxManage guestproperty get "Windows-RDP-Test" "/VirtualBox/GuestInfo/Net/0/V4/IP"
```

## Testing the Connection

### 1. Verify RDP Port is Open

From your host machine:

=== ":material-linux: Linux"

    ```bash
    nc -zv 192.168.1.105 3389
    ```

=== ":material-apple: macOS"

    ```bash
    nc -zv 192.168.1.105 3389
    ```

=== ":material-microsoft-windows: Windows"

    ```powershell
    Test-NetConnection -ComputerName 192.168.1.105 -Port 3389
    ```

### 2. Test with Simple RDP

Create a test script:

```python
import asyncio
from simple_rdp import RDPClient


async def test_connection():
    async with RDPClient(
        host="192.168.1.105",  # Your VM's IP
        username="YourUsername",
        password="YourPassword",
    ) as client:
        print(f"Connected: {client.width}x{client.height}")
        
        # Wait for desktop to render
        await asyncio.sleep(3)
        
        # Take a screenshot
        img = await client.screenshot()
        img.save("vm_screenshot.png")
        print("Screenshot saved to vm_screenshot.png")
        
        # Test mouse click
        await client.mouse_click(client.width // 2, client.height // 2)
        print("Clicked center of screen")
        
        # Test keyboard
        await client.send_key(0xE05B)  # Windows key
        await asyncio.sleep(0.5)
        await client.send_key(0x01)    # Escape
        print("Tested keyboard input")


asyncio.run(test_connection())
```

Run it:

```bash
python test_rdp.py
```

### 3. Using Environment Variables

For convenience, create a `.env` file:

```bash
RDP_HOST=192.168.1.105
RDP_USER=YourUsername
RDP_PASS=YourPassword
```

Then use:

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
        await asyncio.sleep(2)
        await client.save_screenshot("test.png")


asyncio.run(main())
```

## Troubleshooting

??? failure "Connection refused"
    - Verify RDP is enabled in Windows
    - Check Windows Firewall allows RDP
    - Ensure the VM is running and accessible
    - Verify the IP address is correct

??? failure "Authentication failed"
    - Check username and password are correct
    - Ensure the Windows account has a password set
    - Try using `COMPUTERNAME\username` format

??? failure "Network unreachable"
    - Check VirtualBox network adapter settings
    - Verify host and VM are on the same network (for bridged)
    - Try pinging the VM from host: `ping 192.168.1.105`

??? failure "Timeout"
    - The VM may be sleeping - wake it first
    - Check if another RDP session is active
    - Increase connection timeout if needed

## VM Management Tips

### Snapshots

Take snapshots before testing to easily restore:

```bash
# Create snapshot
VBoxManage snapshot "Windows-RDP-Test" take "clean-state"

# Restore snapshot
VBoxManage snapshot "Windows-RDP-Test" restore "clean-state"
```

### Headless Mode

Run the VM without a GUI window:

```bash
VBoxManage startvm "Windows-RDP-Test" --type headless
```

### Power Management

```bash
# Graceful shutdown
VBoxManage controlvm "Windows-RDP-Test" acpipowerbutton

# Force power off
VBoxManage controlvm "Windows-RDP-Test" poweroff

# Save state (hibernate)
VBoxManage controlvm "Windows-RDP-Test" savestate
```
