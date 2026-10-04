// Web Worker for any blocking-stdin WASI command (jonesforth.wasm, 6th.wasm,
// ...): fetches the module and drives it through the shared `runWasiCommand`
// (see wasi-worker.js), which blocks stdin on a `uwasi.SharedInputChannel`
// that the main thread feeds from the terminal. The hand-rolled WASI imports
// this file used to carry (fd_read/fd_write over a bespoke SharedArrayBuffer
// protocol) are gone — `runWasiCommand` and `uwasi` cover the same ground for
// every wasi command, not just jonesforth.wasm. `wasmUrl` defaults to
// jonesforth.wasm's published path so bur.gy/2025/11/29/how-many-roads.html,
// which loads this worker with no `wasmUrl` in its message, keeps working
// unchanged; other consumers (e.g. html/6th.html) pass their own.
import { runWasiCommand } from './wasi-worker.js';

self.addEventListener('message', async ({ data: { sharedBuffer, wasmUrl = '/blog/jonesforth.wasm' } }) => {
    try {
        const bytes = await fetch(wasmUrl).then((response) => response.arrayBuffer());
        self.postMessage({ type: 'ready' });
        const code = await runWasiCommand(bytes, sharedBuffer, (fd, chunk) => {
            self.postMessage({ type: 'output', fd, data: chunk });
        });
        self.postMessage({ type: 'exit', code });
    } catch (error) {
        self.postMessage({ type: 'error', message: error.message, stack: error.stack });
    }
});
