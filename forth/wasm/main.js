// Main thread script for jonesforth WebAssembly with xterm.js

import { Terminal } from 'https://esm.sh/xterm@5.3.0';
import { Readline } from 'https://esm.sh/xterm-readline@1.1.2';
import { SharedInputChannel } from 'https://esm.sh/uwasi@1.6.0';

let timeout = -1;

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

// Synchronous handoff to the worker's blocking stdin (see wasi-worker.js):
// `channel.push`/`close` are the entire host-side protocol, uwasi's
// `SharedInputChannel` does the rest (backpressure, Atomics wake-ups, ...).
// Sized well past jonesforth.f (~59 KiB): `push()` falls back to a busy-spin
// on this main thread if the ring is ever full (real `Atomics.wait` isn't
// allowed here), so the preamble must fit in one push with margin to spare.
const channel = new SharedInputChannel(128 * 1024);

// Create and initialize worker
const worker = new Worker('/blog/worker.js', { type: 'module' });
worker.postMessage({ sharedBuffer: channel.sharedBuffer });

// Handle messages from worker
worker.addEventListener('message', async (event) => {
    const { type, fd, data, code, message, stack } = event.data;

    switch (type) {
        case 'ready': {
            const response = await fetch('/blog/jonesforth.f');
            channel.push(new Uint8Array(await response.arrayBuffer()));
            readLine();
            break;
        }

        case 'output':
            // `data` is already UTF-8 decoded text (see wasi-worker.js).
            if (fd === 1 || fd === 2) { // stdout or stderr
                rl.write(`\x1b[0;${33 - fd}m${data}\x1b[0;37m`);
                if (data.endsWith('\n'))
                    readLine();
                else if (timeout < 0)
                    timeout = setTimeout(resume, 100);
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

function resume() {
    timeout = -1;
    rl.println('');
    readLine();
}

function processLine(text) {
    channel.push(new TextEncoder().encode(text + '\n'));
}
