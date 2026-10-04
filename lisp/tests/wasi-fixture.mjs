// Fixture spawned by wasi.mjs: runs lisp-wasi.wasm against a scripted
// session exactly like forth/wasm/wasi-worker.test-fixture.mjs does for
// jonesforth.wasm. getchar() never treats EOF as a stop here either (see
// wasiHost.ts: a closed, exhausted channel wraps to 255, which core.ts's
// GetToken loop reads as "still inside a token" forever) -- the caller
// always kills this process once it has read enough, so the channel is
// deliberately left open rather than closed.
import { writeSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { SharedInputChannel } from "uwasi";
import { runWasiCommand } from "../../forth/wasm/wasi-worker.js";

try {
    const [, , wasmPath, ...lines] = process.argv;
    const channel = new SharedInputChannel();
    for (const line of lines) channel.push(new TextEncoder().encode(line + "\n"));

    const bytes = await readFile(wasmPath);
    await runWasiCommand(bytes, channel.sharedBuffer, (_fd, chunk) => writeSync(1, chunk));
} catch (error) {
    writeSync(1, `FIXTURE ERROR: ${error.stack ?? error}\n`);
    process.exitCode = 1;
}
