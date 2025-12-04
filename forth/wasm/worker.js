// Web Worker for running jonesforth.wasm
// Handles WASI imports and communication with main thread using SharedArrayBuffer

let memory = null;

// Shared buffers for synchronous communication
let sharedDataBuffer = null;      // SharedArrayBuffer for actual data
let sharedControlBuffer = null;   // Int32Array for control/synchronization
let sharedDataView = null;        // Uint8Array view of data buffer

// Control buffer indices
const CTRL_STATE = 0;        // 0=idle, 1=read_request, 2=data_ready, 3=write_request
const CTRL_LENGTH = 1;       // Length of data
const CTRL_FD = 2;           // File descriptor

// Message handler for communication with main thread
self.addEventListener('message', (event) => {
    const { type, sharedData, sharedControl } = event.data;

    if (type === 'init_buffers') {
        // Initialize shared buffers sent from main thread
        sharedDataBuffer = sharedData;
        sharedControlBuffer = new Int32Array(sharedControl);
        sharedDataView = new Uint8Array(sharedData);

        // Start initialization
        initWasm();
    }
});

// WASI import object
const importObject = {
    wasi_snapshot_preview1: {
        // fd_read(fd: i32, iovs: i32, iovs_len: i32, nread: i32) -> i32
        fd_read: (fd, iovs, iovs_len, nread) => {
            if (fd !== 0) {
                // Only stdin (fd=0) is supported
                return 8; // EBADF
            }

            const memoryView = new Uint8Array(memory.buffer);
            const dataView = new DataView(memory.buffer);

            // Signal main thread that we need input
            Atomics.store(sharedControlBuffer, CTRL_FD, fd);
            Atomics.store(sharedControlBuffer, CTRL_STATE, 1); // read_request
            Atomics.notify(sharedControlBuffer, CTRL_STATE);

            // Wait for main thread to provide data
            while (Atomics.load(sharedControlBuffer, CTRL_STATE) !== 2) {
                Atomics.wait(sharedControlBuffer, CTRL_STATE, 1);
            }

            // Read data length from control buffer
            const dataLength = Atomics.load(sharedControlBuffer, CTRL_LENGTH);

            // Copy data from shared buffer to WebAssembly memory
            let totalRead = 0;
            for (let i = 0; i < iovs_len && totalRead < dataLength; i++) {
                const iovecPtr = iovs + i * 8;
                const bufPtr = dataView.getUint32(iovecPtr, true);
                const bufLen = dataView.getUint32(iovecPtr + 4, true);

                const bytesToCopy = Math.min(bufLen, dataLength - totalRead);
                memoryView.set(sharedDataView.slice(totalRead, totalRead + bytesToCopy), bufPtr);
                totalRead += bytesToCopy;
            }

            // Write the number of bytes read
            if (nread !== 0) {
                dataView.setUint32(nread, totalRead, true);
            }

            // Reset state
            Atomics.store(sharedControlBuffer, CTRL_STATE, 0); // idle
            Atomics.notify(sharedControlBuffer, CTRL_STATE);

            return 0; // Success
        },

        // fd_write(fd: i32, iovs: i32, iovs_len: i32, nwritten: i32) -> i32
        fd_write: (fd, iovs, iovs_len, nwritten) => {
            let totalWritten = 0;
            const memoryView = new Uint8Array(memory.buffer);
            const dataView = new DataView(memory.buffer);

            // Read all iovecs and concatenate the data
            for (let i = 0; i < iovs_len; i++) {
                const iovecPtr = iovs + i * 8;
                const bufPtr = dataView.getUint32(iovecPtr, true);
                const bufLen = dataView.getUint32(iovecPtr + 4, true);

                // Send to main thread
                self.postMessage({
                    type: 'output',
                    fd: fd,
                    data: memoryView.slice(bufPtr, bufPtr + bufLen),
                });

                totalWritten += bufLen;
            }

            // Write the number of bytes written
            if (nwritten !== 0) {
                dataView.setUint32(nwritten, totalWritten, true);
            }

            return 0; // Success
        },

        // proc_exit(code: i32)
        proc_exit: (code) => {
            self.postMessage({
                type: 'exit',
                code: code
            });

            // Terminate the worker
            self.close();
        }
    }
};

// Initialize and load the WebAssembly module
async function initWasm() {
    try {
        const response = await fetch('/blog/jonesforth.wasm');
        const { instance: { exports } } = await WebAssembly.instantiateStreaming(response, importObject);

        memory = exports.memory;
        // Notify main thread that initialization is complete
        self.postMessage({ type: 'ready' });
        exports._start();
    } catch (error) {
        self.postMessage({
            type: 'error',
            message: error.message,
            stack: error.stack
        });
    }
}

