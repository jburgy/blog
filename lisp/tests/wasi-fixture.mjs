// Fixture spawned by wasi.mjs: runs lisp-wasi.wasm against a scripted
// session. getchar() never treats EOF as a stop here (see wasiHost.ts: a
// closed, exhausted channel wraps to 255, which core.ts's GetToken loop
// reads as "still inside a token" forever) -- the caller always kills this
// process once it has read enough, so stdin is deliberately left open
// rather than closed.
import { writeSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { runWasiCommand } from "../../forth/wasm/wasi-command.js";

try {
    const [, , wasmPath, ...lines] = process.argv;
    const stdin = new ReadableStream({
        start(controller) {
            for (const line of lines) controller.enqueue(new TextEncoder().encode(line + "\n"));
        },
    });
    const source = new Response(await readFile(wasmPath), { headers: { "content-type": "application/wasm" } });
    const write = (chunk) => writeSync(1, chunk);
    await runWasiCommand(source, { stdin, stdout: write, stderr: write });
} catch (error) {
    writeSync(1, `FIXTURE ERROR: ${error.stack ?? error}\n`);
    process.exitCode = 1;
}
