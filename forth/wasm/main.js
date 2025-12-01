// Main thread script for jonesforth WebAssembly with xterm.js

import { Terminal } from 'https://esm.sh/xterm@5.3.0';
import { Readline } from 'https://esm.sh/xterm-readline@1.1.2';

// Create xterm.js terminal
const term = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4'
    }
});
const rl = new Readline();
term.loadAddon(rl);

// Mount terminal to DOM
term.open(document.getElementById('terminal'));

// Shared buffers for synchronous communication with worker
const BUFFER_SIZE = 4096;
const sharedDataBuffer = new SharedArrayBuffer(BUFFER_SIZE);
const sharedControlBuffer = new SharedArrayBuffer(12); // 3 x Int32
const sharedDataView = new Uint8Array(sharedDataBuffer);
const controlView = new Int32Array(sharedControlBuffer);

// Control buffer indices (must match worker.js)
const CTRL_STATE = 0;   // 0=idle, 1=read_request, 2=data_ready, 3=write_request
const CTRL_LENGTH = 1;  // Length of data
const CTRL_FD = 2;      // File descriptor

// Create and initialize worker
const worker = new Worker('/blog/worker.js');

// Send shared buffers to worker
worker.postMessage({
    type: 'init_buffers',
    sharedData: sharedDataBuffer,
    sharedControl: sharedControlBuffer
});

// Handle messages from worker
worker.addEventListener('message', async (event) => {
    const { type, fd, data, code, message, stack } = event.data;

    switch (type) {
        case 'ready':
            const response = await fetch('/blog/jonesforth.f');
            const buffer = await response.arrayBuffer();
            const bytes = new Uint8Array(buffer);

            for (let i = 0; i < bytes.length; i += BUFFER_SIZE) {
                const chunk = bytes.slice(i, i + BUFFER_SIZE);

                while (Atomics.load(controlView, CTRL_STATE) !== 1) {
                    const result = Atomics.waitAsync(controlView, CTRL_STATE, 0);
                    if (result.async) await result.value;
                }
                sharedDataView.set(chunk);

                // Signal to WASM that data is ready
                Atomics.store(controlView, CTRL_LENGTH, chunk.byteLength);
                Atomics.store(controlView, CTRL_STATE, 2); // data_ready
                Atomics.notify(controlView, CTRL_STATE);
            }
            readLine();
            break;

        case 'output':
            // Write output from fd_write to terminal
            if (fd === 1 || fd === 2) { // stdout or stderr
                const decoder = new TextDecoder();
                const text = decoder.decode(data);

                rl.write(`\x1b[0;${33 -fd}m${text}\x1b[0;37m`);
                if (text.endsWith('\n'))
                    readLine();
            }
            break;

        case 'exit':
            rl.println(`\r\n[Process exited with code ${code}]`);
            break;

        case 'error':
            rl.println(`\r\n[Error: ${message}]`);
            console.error('Worker error:', message, stack);
            break;
    }
});

function readLine() {
    rl.read("$ ").then(processLine);
}

function processLine(text) {
    // Check if worker is waiting for input
    const state = Atomics.load(controlView, CTRL_STATE);
    const fd = Atomics.load(controlView, CTRL_FD);

    if (state === 1 && fd === 0) { // read_request
        // Convert string to bytes and copy to shared buffer
        const encoder = new TextEncoder();
        const bytes = encoder.encode(text + '\n');
        sharedDataView.set(bytes);

        // Update control buffer
        Atomics.store(controlView, CTRL_LENGTH, bytes.byteLength);
        Atomics.store(controlView, CTRL_STATE, 2); // data_ready
        Atomics.notify(controlView, CTRL_STATE);
    }
}
