// Shared, Worker-side half of running a classic (blocking `read()`) WASI
// command in the browser. A program written assuming it owns stdin/stdout
// gets them wired to a `uwasi.SharedInputChannel`, so `fd_read` genuinely
// blocks (via `Atomics.wait`) until the host thread supplies more input,
// instead of returning EOF whenever nothing happens to be buffered yet.
//
// Must run on a thread that allows blocking `Atomics.wait` — a Worker, never
// a browser main thread (see the host side, `SharedInputChannel.push`/
// `close`, wired up directly from `uwasi` on whichever page embeds this).
// Node's single thread allows blocking waits too, which is what makes this
// module directly testable without actually spinning up a Worker.
//
// Imported from the esm.sh CDN rather than a bare `'uwasi'` specifier: this
// module is loaded inside a `type: "module"` Worker in production (see
// worker.js), and import maps are not reliably honored for worker module
// graphs the way they are for the document's own (see forth/web/index.html,
// which only ever imports on the main thread). vitest resolves the same URL
// back to the local package — see vitest.config.ts.
import { WASI, useArgs, useClock, useEnviron, useProc, useRandom, useStdio, SharedInputChannel } from 'https://esm.sh/uwasi@1.6.0';

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

/**
 * @param {BufferSource | WebAssembly.Module} wasm compiled WASI command (`_start`)
 * @param {SharedArrayBuffer} sharedBuffer a host-created `SharedInputChannel`'s buffer
 * @param {(fd: 1 | 2, chunk: string) => void} onOutput stdout (1) / stderr (2), already UTF-8 decoded
 * @returns {Promise<number>} the WASI exit code
 */
export async function runWasiCommand(wasm, sharedBuffer, onOutput) {
    const channel = new SharedInputChannel(sharedBuffer);
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
            useStdio({
                // Block for real rather than draining whatever is buffered:
                // these guests call plain read()/getchar(), never poll_oneoff.
                stdin: () => {
                    channel.waitForInput(null);
                    return channel.consume();
                },
                stdout: (chunk) => onOutput(1, chunk),
                stderr: (chunk) => onOutput(2, chunk),
            }),
        ],
    });

    // `instantiate(bytes, ...)` resolves to `{ module, instance }`;
    // `instantiate(module, ...)` resolves to the instance directly.
    const result = await WebAssembly.instantiate(wasm, { wasi_snapshot_preview1: wasi.wasiImport });
    const instance = result instanceof WebAssembly.Instance ? result : result.instance;
    return wasi.start(instance);
}
