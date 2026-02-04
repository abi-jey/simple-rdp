/**
 * Simple RDP Viewer - Browser Client
 * With mouse and keyboard capture support
 * Uses MPEG-TS video streaming via Media Source Extensions
 */

class RDPViewer {
    constructor() {
        this.ws = null;
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
        
        // FPS tracking using video playback quality
        this.lastTotalFrames = 0;
        this.lastDroppedFrames = 0;
        this.lastFpsUpdate = Date.now();
        this.fps = 0;
        
        // Input capture state
        this.mouseEnabled = false;
        this.keyboardEnabled = false;
        this.lastMouseX = 0;
        this.lastMouseY = 0;
        this.mouseMoveThrottle = null;
        
        // Video streaming via WebSocket + MSE
        this.videoElement = null;
        this.mediaSource = null;
        this.sourceBuffer = null;
        this.videoStreamActive = false;
        this.pendingChunks = [];
        this.videoWs = null;  // WebSocket for video stream
        
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
                
                // Auto-start video stream when connected
                if (data.connected && !this.videoStreamActive) {
                    this.startVideoStream();
                }
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
        if (this.videoElement) {
            this.videoElement.classList.add('hidden');
        }
        this.hideError();
        
        // Stop existing video stream
        this.stopVideoStream();
        
        try {
            const response = await fetch('/connect', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                console.log('RDP reconnection successful');
                // Video stream will auto-start when status message is received
            } else {
                console.log('RDP reconnection failed:', data.error);
                this.showError(data.error);
            }
        } catch (error) {
            console.error('Reconnect request failed:', error);
            this.showError('Failed to send reconnect request');
        }
    }
    
    // ==================== Video Stream Mode (MPEG-TS via MSE) ====================
    
    async startVideoStream() {
        if (this.videoStreamActive) {
            console.log('Video stream already active');
            return;
        }
        
        console.log('Starting video stream...');
        
        // Check for MediaSource support with fragmented MP4
        if (!window.MediaSource || !MediaSource.isTypeSupported('video/mp4; codecs="avc1.42E01E"')) {
            console.warn('MediaSource Extensions not supported for H.264/MP4');
            this.showError('Video streaming not supported in this browser.');
            return;
        }
        
        // Create or show video element
        if (!this.videoElement) {
            this.videoElement = document.createElement('video');
            this.videoElement.id = 'video-stream';
            this.videoElement.autoplay = true;
            this.videoElement.muted = true;
            this.videoElement.playsInline = true;
            this.videoElement.style.width = '100%';
            this.videoElement.style.height = 'auto';
            this.videoElement.style.maxWidth = '100%';
            this.canvasWrapper.appendChild(this.videoElement);
        }
        
        // Show video element
        this.videoElement.classList.remove('hidden');
        
        try {
            // Initialize MediaSource
            this.mediaSource = new MediaSource();
            this.videoElement.src = URL.createObjectURL(this.mediaSource);
            
            await new Promise((resolve, reject) => {
                this.mediaSource.addEventListener('sourceopen', resolve, { once: true });
                this.mediaSource.addEventListener('error', reject, { once: true });
            });
            
            console.log('MediaSource opened, readyState:', this.mediaSource.readyState);
            
            // Add source buffer for H.264 in fragmented MP4 container
            // Try different codec strings for compatibility
            const codecs = [
                'video/mp4; codecs="avc1.42E01E"',  // Baseline profile (most compatible)
                'video/mp4; codecs="avc1.640028"',  // High profile L4.0
                'video/mp4; codecs="avc1.4D401F"',  // Main profile
                'video/mp4; codecs="avc1.64001F"',  // High profile
            ];
            
            for (const codec of codecs) {
                if (MediaSource.isTypeSupported(codec)) {
                    try {
                        this.sourceBuffer = this.mediaSource.addSourceBuffer(codec);
                        console.log(`Using codec: ${codec}`);
                        break;
                    } catch (e) {
                        console.warn(`Failed to add source buffer for ${codec}:`, e);
                    }
                } else {
                    console.log(`Codec not supported: ${codec}`);
                }
            }
            
            if (!this.sourceBuffer) {
                throw new Error('Could not create source buffer for H.264/MP4');
            }
            
            this.sourceBuffer.mode = 'segments';  // Changed from 'sequence' for fMP4
            this.sourceBuffer.addEventListener('updateend', () => this.processNextChunk());
            this.sourceBuffer.addEventListener('error', (e) => {
                console.error('SourceBuffer error:', e);
            });
            
            this.videoStreamActive = true;
            this.pendingChunks = [];
            this.maxPendingChunks = 30;  // Limit pending chunks to prevent memory bloat
            this.totalBytesReceived = 0;  // Track bytes for debugging
            this.chunksAppended = 0;  // Track appended chunks
            
            // Start fetching the video stream
            this.fetchVideoStream();
            
            console.log('Video stream initialized');
            this.loadingEl.classList.add('hidden');
            
        } catch (error) {
            console.error('Failed to initialize video stream:', error);
            this.stopVideoStream();
            this.showError(`Video stream error: ${error.message}`);
        }
    }
    
    async fetchVideoStream() {
        if (!this.videoStreamActive) return;
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/video`;
        
        console.log(`Connecting to video WebSocket: ${wsUrl}`);
        this.videoWs = new WebSocket(wsUrl);
        this.videoWs.binaryType = 'arraybuffer';
        
        this.videoWs.onopen = () => {
            console.log('Video WebSocket connected');
            this.totalBytesReceived = 0;
            this.firstChunkTime = null;
        };
        
        this.videoWs.onmessage = (event) => {
            if (event.data instanceof ArrayBuffer) {
                // Binary video data
                const chunk = new Uint8Array(event.data);
                if (chunk.length > 0) {
                    this.totalBytesReceived = (this.totalBytesReceived || 0) + chunk.length;
                    
                    // Log first chunk for debugging
                    if (!this.firstChunkTime) {
                        this.firstChunkTime = Date.now();
                        console.log(`First video chunk received: ${chunk.length} bytes`);
                        // Log first few bytes to verify it's fMP4 (should start with 'ftyp')
                        const header = Array.from(chunk.slice(0, 16)).map(b => b.toString(16).padStart(2, '0')).join(' ');
                        console.log(`First 16 bytes: ${header}`);
                    }
                    
                    // Drop oldest chunks if queue is too long (back-pressure)
                    while (this.pendingChunks.length >= this.maxPendingChunks) {
                        this.pendingChunks.shift();
                        console.debug('Dropped old video chunk (back-pressure)');
                    }
                    this.pendingChunks.push(chunk);
                    this.processNextChunk();
                }
            } else {
                // JSON control message
                try {
                    const msg = JSON.parse(event.data);
                    console.log('Video WebSocket message:', msg);
                    if (msg.type === 'error') {
                        this.showError(msg.message);
                    } else if (msg.type === 'status') {
                        this.loadingText.textContent = msg.message;
                    }
                } catch (e) {
                    console.warn('Unknown message format:', event.data);
                }
            }
        };
        
        this.videoWs.onclose = (event) => {
            console.log(`Video WebSocket closed: ${event.code} ${event.reason}`);
            if (this.videoStreamActive) {
                // Reconnect after delay
                console.log('Reconnecting video WebSocket in 2s...');
                setTimeout(() => this.fetchVideoStream(), 2000);
            }
        };
        
        this.videoWs.onerror = (error) => {
            console.error('Video WebSocket error:', error);
        };
    }
    
    processNextChunk() {
        if (!this.sourceBuffer || 
            this.sourceBuffer.updating || 
            this.pendingChunks.length === 0 ||
            !this.videoStreamActive) {
            return;
        }
        
        // Proactively trim buffer if it's getting too long (more than 5 seconds)
        if (this.sourceBuffer.buffered.length > 0) {
            const bufferedEnd = this.sourceBuffer.buffered.end(0);
            const bufferedStart = this.sourceBuffer.buffered.start(0);
            const bufferedDuration = bufferedEnd - bufferedStart;
            
            // Keep only last 3 seconds of video for lower latency
            if (bufferedDuration > 5 && !this.sourceBuffer.updating) {
                const removeEnd = bufferedEnd - 3;
                if (removeEnd > bufferedStart) {
                    try {
                        this.sourceBuffer.remove(bufferedStart, removeEnd);
                        // Also seek to near live edge if we're behind
                        if (this.videoElement && this.videoElement.currentTime < bufferedEnd - 2) {
                            this.videoElement.currentTime = bufferedEnd - 0.5;
                        }
                        return; // Wait for removal to complete
                    } catch (e) {
                        console.debug('Buffer trim failed:', e);
                    }
                }
            }
        }
        
        try {
            const chunk = this.pendingChunks.shift();
            this.sourceBuffer.appendBuffer(chunk);
            this.chunksAppended = (this.chunksAppended || 0) + 1;
            
            // Log first few chunks and periodically for debugging
            if (this.chunksAppended <= 5 || this.chunksAppended % 100 === 0) {
                const buffered = this.sourceBuffer.buffered.length > 0 
                    ? `${this.sourceBuffer.buffered.start(0).toFixed(2)}-${this.sourceBuffer.buffered.end(0).toFixed(2)}s`
                    : 'empty';
                console.log(`Chunk #${this.chunksAppended}: ${chunk.length} bytes, buffered: ${buffered}`);
            }
        } catch (error) {
            console.error('Error appending buffer:', error, 'chunk size:', this.pendingChunks[0]?.length);
            // If quota exceeded, remove old data aggressively
            if (error.name === 'QuotaExceededError' && this.sourceBuffer.buffered.length > 0) {
                const start = this.sourceBuffer.buffered.start(0);
                const end = this.sourceBuffer.buffered.end(0) - 2; // Keep only last 2 seconds
                if (end > start) {
                    this.sourceBuffer.remove(start, end);
                }
            }
        }
    }
    
    stopVideoStream() {
        console.log('Stopping video stream');
        this.videoStreamActive = false;
        this.pendingChunks = [];
        
        // Close video WebSocket
        if (this.videoWs) {
            this.videoWs.close();
            this.videoWs = null;
        }
        
        if (this.sourceBuffer && this.mediaSource && this.mediaSource.readyState === 'open') {
            try {
                this.mediaSource.removeSourceBuffer(this.sourceBuffer);
            } catch (e) {
                console.debug('Error removing source buffer:', e);
            }
        }
        this.sourceBuffer = null;
        
        if (this.mediaSource && this.mediaSource.readyState === 'open') {
            try {
                this.mediaSource.endOfStream();
            } catch (e) {
                console.debug('Error ending media source:', e);
            }
        }
        this.mediaSource = null;
        
        if (this.videoElement) {
            this.videoElement.classList.add('hidden');
            this.videoElement.src = '';
        }
        
        console.log('Video stream stopped');
    }
    
    setStatus(connected, text) {
        this.statusEl.className = `status ${connected ? 'connected' : 'disconnected'}`;
        this.statusText.textContent = text;
    }
    
    startFpsCounter() {
        setInterval(() => {
            // Use actual video playback quality stats if available
            if (this.videoElement && typeof this.videoElement.getVideoPlaybackQuality === 'function') {
                const quality = this.videoElement.getVideoPlaybackQuality();
                const totalFrames = quality.totalVideoFrames;
                const droppedFrames = quality.droppedVideoFrames;
                
                const now = Date.now();
                const elapsed = (now - this.lastFpsUpdate) / 1000;
                const framesDelta = totalFrames - this.lastTotalFrames;
                
                this.fps = Math.round(framesDelta / elapsed);
                this.fpsEl.textContent = `${this.fps}`;
                
                this.lastTotalFrames = totalFrames;
                this.lastFpsUpdate = now;
                
                // Collect comprehensive diagnostics
                this.collectDiagnostics(quality);
            } else {
                this.fpsEl.textContent = '-';
            }
        }, 1000);
    }
    
    async collectDiagnostics(videoQuality) {
        // Client-side diagnostics
        const diagnostics = {
            client: {
                fps: this.fps,
                totalFrames: videoQuality.totalVideoFrames,
                droppedFrames: videoQuality.droppedVideoFrames,
                dropRate: videoQuality.totalVideoFrames > 0 
                    ? ((videoQuality.droppedVideoFrames / videoQuality.totalVideoFrames) * 100).toFixed(2) + '%'
                    : '0%',
                pendingChunks: this.pendingChunks.length,
                sourceBufferUpdating: this.sourceBuffer?.updating || false,
            }
        };
        
        // Get buffer info
        if (this.videoElement && this.sourceBuffer?.buffered?.length > 0) {
            const buffered = this.sourceBuffer.buffered;
            const currentTime = this.videoElement.currentTime;
            const bufferEnd = buffered.end(buffered.length - 1);
            diagnostics.client.bufferAhead = (bufferEnd - currentTime).toFixed(2) + 's';
            diagnostics.client.bufferHealth = bufferEnd - currentTime > 1 ? 'good' : 'low';
        }
        
        // Fetch server-side stats
        try {
            const response = await fetch('/stream-status');
            diagnostics.server = await response.json();
        } catch (e) {
            diagnostics.server = { error: e.message };
        }
        
        // Store for console access and log periodically
        this.lastDiagnostics = diagnostics;
        
        // Log warnings only for NEW dropped frames
        const newDrops = videoQuality.droppedVideoFrames - this.lastDroppedFrames;
        if (newDrops > 0) {
            console.warn(`⚠️ Dropped ${newDrops} frames (total: ${videoQuality.droppedVideoFrames})`);
        }
        this.lastDroppedFrames = videoQuality.droppedVideoFrames;
        
        if (this.pendingChunks.length > 10) {
            console.warn(`⚠️ Chunk queue backing up: ${this.pendingChunks.length} pending`);
        }
    }
    
    // Call viewer.showDiagnostics() in console to see full stats
    showDiagnostics() {
        console.table(this.lastDiagnostics?.client || {});
        console.table(this.lastDiagnostics?.server?.stats || {});
        console.log('Server queue:', this.lastDiagnostics?.server?.video_queue_size);
        console.log('Server FPS:', this.lastDiagnostics?.server?.server_fps);
        return this.lastDiagnostics;
    }
    
    // ==================== Mouse Handling ====================
    
    toggleMouse(enabled) {
        this.mouseEnabled = enabled;
        const target = this.videoElement || this.viewerContainer;
        
        if (enabled) {
            target.addEventListener('mousemove', this.boundMouseMove);
            target.addEventListener('mousedown', this.boundMouseDown);
            target.addEventListener('mouseup', this.boundMouseUp);
            target.addEventListener('contextmenu', this.boundContextMenu);
            target.addEventListener('wheel', this.boundWheel, { passive: false });
            this.viewerContainer.classList.add('mouse-capture');
            this.mouseBadge.classList.add('active');
            console.log('Mouse capture enabled');
        } else {
            target.removeEventListener('mousemove', this.boundMouseMove);
            target.removeEventListener('mousedown', this.boundMouseDown);
            target.removeEventListener('mouseup', this.boundMouseUp);
            target.removeEventListener('contextmenu', this.boundContextMenu);
            target.removeEventListener('wheel', this.boundWheel);
            this.viewerContainer.classList.remove('mouse-capture');
            this.mouseBadge.classList.remove('active');
            console.log('Mouse capture disabled');
        }
    }
    
    getMouseCoords(e) {
        const target = this.videoElement || e.target;
        const rect = target.getBoundingClientRect();
        // Use native video dimensions (1920x1080) for coordinate mapping
        const nativeWidth = this.videoElement?.videoWidth || 1920;
        const nativeHeight = this.videoElement?.videoHeight || 1080;
        const scaleX = nativeWidth / rect.width;
        const scaleY = nativeHeight / rect.height;
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
