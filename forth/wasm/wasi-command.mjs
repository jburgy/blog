// Runs a classic (blocking `read()`) WASI command on the main thread via JSPI
// (Chrome 137+, Firefox 139+): `fd_read` is a `WebAssembly.Suspending` import,
// so a guest that owns stdin simply suspends until the host has more input. No
// Worker, SharedArrayBuffer, or cross-origin isolation involved.
//
// Imported from the esm.sh CDN rather than a bare `'uwasi'` specifier because
// the blog serves plain ES modules with no import map; vitest resolves the
// same URL back to the local package (see vitest.config.mts), and Node needs
// `--experimental-wasm-jspi`.
import { WASI, WASIProcExit, useArgs, useClock, useEnviron, useProc, useRandom, useStdio } from 'https://esm.sh/uwasi@1.6.0';

// uwasi's useStdio doesn't implement fd_pread/fd_pwrite. Zig's std.fs.File
// reader/writer (6th.zig's wasm32-wasi build) try positioned I/O before
// falling back to fd_read/fd_write; the default ENOSYS trips a panic
// ("unexpected errno: 52") instead of that fallback. Answering ESPIPE (WASI
// errno 70) for stdio's character-device fds makes the fallback happen, the
// same as a real OS would for an unseekable fd. Scoped to fds 0-2: this
// module has no filesystem feature (no useFS/useMemoryFS) yet, but a future
// one would add real, seekable files on higher fds, which must keep seeing
// ENOSYS here rather than a blanket, wrong ESPIPE.
const ESPIPE = 70;
const ENOSYS = 52;
function noSeek() {
    return () => ({
        fd_pread: (fd) => (fd <= 2 ? ESPIPE : ENOSYS),
        fd_pwrite: (fd) => (fd <= 2 ? ESPIPE : ENOSYS),
    });
}

// uwasi's useStdio fd_read tries to completely fill the requested buffer,
// retrying until it can or hits EOF. That's wrong for a classic POSIX read():
// these guests rely on short reads (jonesforth's TIB refill, like 5th.c's
// key(), always requests 4096 bytes however little input is left), so a fill
// loop hangs on an interactive stream. Hand-roll fd_read instead: one stream
// chunk per call, leftover bytes kept for the next one.
function streamRead(stdin) {
    const reader = stdin.getReader();
    let pending = new Uint8Array(0);
    let lastYield = performance.now();
    return (options, abi, memoryView) => ({
        fd_read: new WebAssembly.Suspending(async (fd, iovs, iovsLen, nreadPtr) => {
            if (fd !== 0) return 8; // WASI_ERRNO_BADF
            let view = memoryView();
            let capacity = 0;
            for (let i = 0; i < iovsLen; i++) capacity += view.getUint32(iovs + i * 8 + 4, true);
            // A zero-length read is always satisfiable: don't block waiting for input nobody asked for.
            if (capacity === 0) {
                view.setUint32(nreadPtr, 0, true);
                return 0;
            }
            if (pending.length) {
                // A resolved promise only yields to microtasks; yield a task too or the
                // browser never repaints while buffered input (a preamble) is consumed.
                // Once per frame, not per read: byte-at-a-time guests (lisp's getchar)
                // would otherwise pay a timer tick (1-4ms) per byte.
                if (performance.now() - lastYield > 16) {
                    await new Promise((resolve) => setTimeout(resolve));
                    lastYield = performance.now();
                }
            } else {
                // `done` (EOF) leaves `pending` empty, which reads back as 0 bytes.
                const { value, done } = await reader.read();
                if (!done) pending = value;
            }
            view = memoryView(); // the guest's memory may have grown while suspended
            const bytes = pending.subarray(0, capacity);
            pending = pending.subarray(bytes.length);
            let totalRead = 0;
            for (let i = 0; i < iovsLen && totalRead < bytes.length; i++) {
                const bufPtr = view.getUint32(iovs + i * 8, true);
                const n = Math.min(view.getUint32(iovs + i * 8 + 4, true), bytes.length - totalRead);
                new Uint8Array(view.buffer, bufPtr, n).set(bytes.subarray(totalRead, totalRead + n));
                totalRead += n;
            }
            view.setUint32(nreadPtr, totalRead, true);
            return 0;
        }),
    });
}

/**
 * @param {Response | Promise<Response>} source compiled WASI command (`_start`),
 *   served as `application/wasm`: what `WebAssembly.instantiateStreaming` takes
 * @param {object} [options]
 * @param {ReadableStream<Uint8Array>} [options.stdin] the guest suspends while it
 *   waits for a chunk; closing the stream is EOF. Defaults to empty.
 * @param {(chunk: string) => void} [options.stdout] already UTF-8 decoded
 * @param {(chunk: string) => void} [options.stderr] already UTF-8 decoded
 * @returns {Promise<number>} the WASI exit code
 */
export async function runWasiCommand(source, { stdin = new Blob().stream(), stdout, stderr } = {}) {
    const wasi = new WASI({
        features: [
            // A libc/language-runtime startup sequence (6th.zig's wasm32-wasi
            // build, unlike jonesforth.wasm's hand-written imports) can probe
            // these before ever touching stdin — missing ones resolve to
            // ENOSYS, which several guests turn into an early, silent exit.
            useArgs(),
            useClock(),
            useEnviron(),
            useRandom(),
            useProc(),
            noSeek(),
            useStdio({ stdout, stderr }),
            // After useStdio, so this fd_read overrides its: useStdio's `stdin` is sync
            // (can't suspend) and its fd_read fills the whole buffer (no short reads).
            streamRead(stdin),
        ],
    });
    const { instance } = await WebAssembly.instantiateStreaming(source, { wasi_snapshot_preview1: wasi.wasiImport });
    // setInstance, not start(): start() calls `_start` synchronously, without awaiting its promise.
    wasi.setInstance(instance);
    try {
        await WebAssembly.promising(instance.exports._start)();
        return 0;
    } catch (error) {
        if (error instanceof WASIProcExit) return error.code;
        throw error;
    }
}
