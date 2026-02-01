/**
 * Simple RDP Viewer - Browser Client
 * With mouse and keyboard capture support
 */

class RDPViewer {
    constructor() {
        this.ws = null;
        this.canvas = document.getElementById('screen');
        this.ctx = this.canvas.getContext('2d');
        this.viewerContainer = document.getElementById('viewer-container');
        this.canvasWrapper = document.querySelector('.canvas-wrapper');
        this.statusEl = document.getElementById('status');
        this.statusText = document.getElementById('status-text');
        this.hostEl = document.getElementById('host');
        this.resolutionEl = document.getElementById('resolution');
        this.fpsEl = document.getElementById('fps');
        this.loadingEl = document.getElementById('loading');
        this.loadingText = document.getElementById('loading-text');
        this.errorPanel = document.getElementById('error-panel');
        this.errorText = document.getElementById('error-text');
        this.mouseBadge = document.getElementById('mouse-badge');
        this.keyboardBadge = document.getElementById('keyboard-badge');
        
        this.frameCount = 0;
        this.lastFpsUpdate = Date.now();
        this.fps = 0;
        
        // Canvas scaling
        this.nativeWidth = 0;
        this.nativeHeight = 0;
        
        // Input capture state
        this.mouseEnabled = false;
        this.keyboardEnabled = false;
        this.lastMouseX = 0;
        this.lastMouseY = 0;
        this.mouseMoveThrottle = null;
        
        // Bound event handlers (for removal)
        this.boundMouseMove = this.handleMouseMove.bind(this);
        this.boundMouseDown = this.handleMouseDown.bind(this);
        this.boundMouseUp = this.handleMouseUp.bind(this);
        this.boundContextMenu = this.handleContextMenu.bind(this);
        this.boundWheel = this.handleWheel.bind(this);
        this.boundKeyDown = this.handleKeyDown.bind(this);
        this.boundKeyUp = this.handleKeyUp.bind(this);
        
        this.connect();
        this.startFpsCounter();
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        console.log(`Connecting to ${wsUrl}...`);
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.setStatus(true, 'Connecting...');
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.setStatus(false, 'Disconnected');
            // Reconnect after 3 seconds
            setTimeout(() => this.connect(), 3000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.setStatus(false, 'Connection Error');
        };
        
        // Send ping every 30 seconds to keep connection alive
        setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'status':
                this.setStatus(data.connected, data.connected ? 'Connected' : 'Disconnected');
                this.hostEl.textContent = data.host || '-';
                
                // Show/hide error panel
                if (data.error) {
                    this.showError(data.error);
                } else {
                    this.hideError();
                }
                
                // Update loading text
                if (!data.connected && !data.error) {
                    this.loadingText.textContent = 'Waiting for RDP connection...';
                } else if (!data.connected && data.error) {
                    this.loadingText.textContent = 'RDP not connected. Click Reconnect to try again.';
                }
                break;
                
            case 'frame':
                this.renderFrame(data);
                this.hideError();
                break;
                
            case 'pong':
                // Ping response, connection is alive
                break;
                
            default:
                console.log('Unknown message type:', data.type);
        }
    }
    
    showError(error) {
        this.errorPanel.classList.remove('hidden');
        this.errorText.textContent = error;
    }
    
    hideError() {
        this.errorPanel.classList.add('hidden');
    }
    
    async reconnect() {
        console.log('Attempting to reconnect to RDP...');
        this.loadingText.textContent = 'Reconnecting to RDP server...';
        this.loadingEl.classList.remove('hidden');
        this.canvas.classList.add('hidden');
        this.hideError();
        
        try {
            const response = await fetch('/connect', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                console.log('RDP reconnection successful');
            } else {
                console.log('RDP reconnection failed:', data.error);
                this.showError(data.error);
            }
        } catch (error) {
            console.error('Reconnect request failed:', error);
            this.showError('Failed to send reconnect request');
        }
    }
    
    renderFrame(data) {
        const img = new Image();
        img.onload = () => {
            // Store native dimensions
            this.nativeWidth = data.width;
            this.nativeHeight = data.height;
            
            // Resize canvas if needed
            if (this.canvas.width !== data.width || this.canvas.height !== data.height) {
                this.canvas.width = data.width;
                this.canvas.height = data.height;
                this.resolutionEl.textContent = `${data.width}x${data.height}`;
            }
            
            // Draw the frame (cursor is composited on the server side)
            this.ctx.drawImage(img, 0, 0);
            
            // Hide loading, show canvas
            this.loadingEl.classList.add('hidden');
            this.canvas.classList.remove('hidden');
            
            // Update frame count for FPS
            this.frameCount++;
        };
        img.src = `data:image/jpeg;base64,${data.data}`;
    }
    
    setStatus(connected, text) {
        this.statusEl.className = `status ${connected ? 'connected' : 'disconnected'}`;
        this.statusText.textContent = text;
    }
    
    startFpsCounter() {
        setInterval(() => {
            const now = Date.now();
            const elapsed = (now - this.lastFpsUpdate) / 1000;
            this.fps = Math.round(this.frameCount / elapsed);
            this.fpsEl.textContent = this.fps;
            this.frameCount = 0;
            this.lastFpsUpdate = now;
        }, 1000);
    }
    
    // ==================== Mouse Handling ====================
    
    toggleMouse(enabled) {
        this.mouseEnabled = enabled;
        
        if (enabled) {
            this.canvas.addEventListener('mousemove', this.boundMouseMove);
            this.canvas.addEventListener('mousedown', this.boundMouseDown);
            this.canvas.addEventListener('mouseup', this.boundMouseUp);
            this.canvas.addEventListener('contextmenu', this.boundContextMenu);
            this.canvas.addEventListener('wheel', this.boundWheel, { passive: false });
            this.viewerContainer.classList.add('mouse-capture');
            this.mouseBadge.classList.add('active');
            console.log('Mouse capture enabled');
        } else {
            this.canvas.removeEventListener('mousemove', this.boundMouseMove);
            this.canvas.removeEventListener('mousedown', this.boundMouseDown);
            this.canvas.removeEventListener('mouseup', this.boundMouseUp);
            this.canvas.removeEventListener('contextmenu', this.boundContextMenu);
            this.canvas.removeEventListener('wheel', this.boundWheel);
            this.viewerContainer.classList.remove('mouse-capture');
            this.mouseBadge.classList.remove('active');
            console.log('Mouse capture disabled');
        }
    }
    
    getMouseCoords(e) {
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        return {
            x: Math.round((e.clientX - rect.left) * scaleX),
            y: Math.round((e.clientY - rect.top) * scaleY)
        };
    }
    
    handleMouseMove(e) {
        if (!this.mouseEnabled || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        
        const coords = this.getMouseCoords(e);
        
        // Throttle mouse moves to ~60/sec max
        if (this.mouseMoveThrottle) return;
        
        this.mouseMoveThrottle = setTimeout(() => {
            this.mouseMoveThrottle = null;
        }, 16);
        
        // Only send if position changed
        if (coords.x !== this.lastMouseX || coords.y !== this.lastMouseY) {
            this.lastMouseX = coords.x;
            this.lastMouseY = coords.y;
            
            this.ws.send(JSON.stringify({
                type: 'mouse_move',
                x: coords.x,
                y: coords.y
            }));
        }
    }
    
    handleMouseDown(e) {
        if (!this.mouseEnabled || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        
        const coords = this.getMouseCoords(e);
        const button = this.getButtonName(e.button);
        
        this.ws.send(JSON.stringify({
            type: 'mouse_down',
            x: coords.x,
            y: coords.y,
            button: button
        }));
        
        e.preventDefault();
    }
    
    handleMouseUp(e) {
        if (!this.mouseEnabled || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        
        const coords = this.getMouseCoords(e);
        const button = this.getButtonName(e.button);
        
        this.ws.send(JSON.stringify({
            type: 'mouse_up',
            x: coords.x,
            y: coords.y,
            button: button
        }));
        
        e.preventDefault();
    }
    
    handleContextMenu(e) {
        if (this.mouseEnabled) {
            e.preventDefault();
        }
    }
    
    handleWheel(e) {
        if (!this.mouseEnabled || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        
        const coords = this.getMouseCoords(e);
        
        // Normalize wheel delta
        const deltaY = Math.sign(e.deltaY) * -1; // Invert for natural scrolling
        
        this.ws.send(JSON.stringify({
            type: 'mouse_wheel',
            x: coords.x,
            y: coords.y,
            delta: deltaY * 120 // Windows wheel delta units
        }));
        
        e.preventDefault();
    }
    
    getButtonName(button) {
        switch (button) {
            case 0: return 'left';
            case 1: return 'middle';
            case 2: return 'right';
            default: return 'left';
        }
    }
    
    // ==================== Keyboard Handling ====================
    
    toggleKeyboard(enabled) {
        this.keyboardEnabled = enabled;
        
        if (enabled) {
            // Focus canvas to receive key events
            this.canvas.focus();
            document.addEventListener('keydown', this.boundKeyDown);
            document.addEventListener('keyup', this.boundKeyUp);
            this.viewerContainer.classList.add('keyboard-capture');
            this.keyboardBadge.classList.add('active');
            console.log('Keyboard capture enabled');
        } else {
            document.removeEventListener('keydown', this.boundKeyDown);
            document.removeEventListener('keyup', this.boundKeyUp);
            this.viewerContainer.classList.remove('keyboard-capture');
            this.keyboardBadge.classList.remove('active');
            console.log('Keyboard capture disabled');
        }
    }
    
    handleKeyDown(e) {
        if (!this.keyboardEnabled || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        
        // Don't capture if focus is on input elements
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        
        const keyData = this.mapKeyEvent(e);
        
        this.ws.send(JSON.stringify({
            type: 'key_down',
            ...keyData
        }));
        
        // Prevent default for most keys when capturing
        if (this.shouldPreventDefault(e)) {
            e.preventDefault();
        }
    }
    
    handleKeyUp(e) {
        if (!this.keyboardEnabled || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        
        // Don't capture if focus is on input elements
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        
        const keyData = this.mapKeyEvent(e);
        
        this.ws.send(JSON.stringify({
            type: 'key_up',
            ...keyData
        }));
        
        if (this.shouldPreventDefault(e)) {
            e.preventDefault();
        }
    }
    
    mapKeyEvent(e) {
        return {
            key: e.key,
            code: e.code,
            keyCode: e.keyCode,
            ctrlKey: e.ctrlKey,
            shiftKey: e.shiftKey,
            altKey: e.altKey,
            metaKey: e.metaKey
        };
    }
    
    shouldPreventDefault(e) {
        // Prevent default for most keys except browser shortcuts we want to keep
        const allowedCombos = [
            // Allow Ctrl+Shift+I for dev tools
            (e.ctrlKey && e.shiftKey && e.code === 'KeyI'),
            // Allow F12 for dev tools
            (e.code === 'F12'),
            // Allow Ctrl+R for reload (hold Shift to capture)
            (e.ctrlKey && !e.shiftKey && e.code === 'KeyR'),
        ];
        
        return !allowedCombos.some(allowed => allowed);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.viewer = new RDPViewer();
});
