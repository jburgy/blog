// Main-thread bootstrap for the no-pty wasi-worker.js browser demos
// (html/4th.html, html/5th.html, html/6th.html, and bur.gy's how-many-roads
// post's tabbed jonesforth.wasm/4th/5th/6th switcher): mounts xterm.js, feeds
// a preamble (4th.32.fs by default, or jonesforth.f for jonesforth.wasm) to a
// Worker (see worker.js) over a uwasi SharedInputChannel, and uses
// xterm-readline for line editing -- the same addon main.js (jonesforth.
// wasm's original, since-retired published demo) already used against this
// exact worker/channel protocol, rather than hand-rolling a second, weaker
// line editor. Still no real pty, unlike the published posts' Emscripten +
// xterm-pty demos (see those posts' own hardcoded scripts and
// forth/README.md's "Toolkits, briefly" section). Named to pair with
// wasi-worker.js: that's the Worker side, this is the main-thread side.
import { Terminal } from "https://esm.sh/@xterm/xterm@5.5.0";
import { Readline } from "https://esm.sh/xterm-readline@1.1.2";
import { SharedInputChannel } from "https://esm.sh/uwasi@1.6.0";

/**
 * @param {string} wasmUrl
 * @param {string | URL | null} [preambleUrl] defaults to the shared 4th.32.fs
 *   dictionary (4th.c/5th.c/6th.zig); pass jonesforth.wasm's own
 *   `jonesforth.f` (a different address width, not a different protocol)
 *   to drive that interpreter instead, or explicit `null` for a WASI
 *   command with no use for either (e.g. lisp-wasi.wasm/TinyBasic-wasi.wasm,
 *   see jburgy.github.io's lisp/TinyBasic posts) -- omitting the argument
 *   still gets the 4th.32.fs default, so every existing caller is
 *   unaffected; only `null` explicitly opts all the way out. Verified
 *   against real builds of both: feeding either the FORTH preamble as
 *   typed input produces thousands of lines of garbage (parse errors /
 *   IL-dump spam) before the interpreter ever reaches its own prompt.
 * @returns {{ term: Terminal, sendLine: (text: string) => void, getOutput: () => string, dispose: () => void }}
 *   `sendLine`/`getOutput` let a test drive the REPL deterministically
 *   (see wasi-repl-mocha.mjs). `sendLine` uses xterm.js's own `paste()` to
 *   feed Readline's pending `read()` -- still no simulated keystrokes. Two
 *   separate calls, not one `text + "\r"`: Readline's own paste handling
 *   (readline.js's readPaste) deliberately turns an Enter *inside* a
 *   multi-character paste into a literal "\n" (no accidental paste-and-run),
 *   so only a lone, single-character paste of "\r" takes the submit path.
 *   `dispose` terminates the Worker and tears down the Terminal so a caller
 *   that wants to switch wasmUrl mid-page (e.g. a tabbed demo picking
 *   between interpreters) can cleanly start a fresh `startRepl(...)` in the
 *   same `#terminal` div without the old Worker's `fd_read` wait loop or its
 *   stray `postMessage`s outliving it.
 */
export function startRepl(wasmUrl, preambleUrl = new URL("./forth/4th.32.fs", import.meta.url)) {
    const xterm = new Terminal();
    const rl = new Readline();
    xterm.loadAddon(rl);
    xterm.open(document.getElementById("terminal"));

    // Sized well past 4th.32.fs (~58 KiB), same margin as main.js's
    // jonesforth.f channel.
    const channel = new SharedInputChannel(128 * 1024);
    const worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });

    let output = "";
    let disposed = false;

    // Re-arms by calling itself from its own `rl.read().then()`, not
    // reactively from 'output' messages (the previous design: re-arm once a
    // chunk ends in '\n', or after a 100ms fallback timeout for one that
    // doesn't). That heuristic assumed every submitted line eventually
    // produces *some* output to react to, which is false: jonesforth.f's
    // "OK " prompt (WELCOME) is a one-time startup banner, not reprinted
    // per line (see jonesforth.f), so a blank/no-op input line can -- and
    // does -- yield zero bytes back from the guest. With nothing to react
    // to, the old code never called rl.read() again, and xterm-readline
    // silently drops all further keystrokes while no read is pending --
    // the terminal looked dead after the first no-op line (confirmed live
    // with instrumented logging: readLine() simply never fired again).
    // Calling itself unconditionally after every resolved read guarantees
    // exactly one pending read at a time with no output-shaped guesswork:
    // the next read only ever starts once the current one resolves.
    function readLine() {
        if (disposed) return;
        rl.read("").then((text) => {
            processLine(text);
            readLine();
        });
    }

    function processLine(text) {
        channel.push(new TextEncoder().encode(text + "\n"));
    }

    worker.addEventListener("message", async ({ data: { type, fd, data, code, message } }) => {
        // A disposed REPL's Worker is terminate()d below, but a message it
        // already posted before that lands here can still race the
        // termination (same microtask queue) -- never touch `rl`/`xterm`
        // past dispose(), both are themselves torn down by then.
        if (disposed) return;
        switch (type) {
            case "ready": {
                if (preambleUrl) {
                    const response = await fetch(preambleUrl);
                    channel.push(new Uint8Array(await response.arrayBuffer()));
                }
                readLine();
                break;
            }
            case "output":
                if (fd === 1 || fd === 2) {
                    output += data;
                    rl.write(data);
                }
                break;
            case "exit":
                rl.println(`[Process exited with code ${code}]`);
                break;
            case "error":
                rl.println(`[Error: ${message}]`);
                break;
        }
    });

    function sendLine(text) {
        xterm.paste(text);
        xterm.paste("\r");
    }

    function dispose() {
        if (disposed) return;
        disposed = true;
        worker.terminate();
        xterm.dispose();
    }

    worker.postMessage({ sharedBuffer: channel.sharedBuffer, wasmUrl });

    return { term: xterm, sendLine, getOutput: () => output, dispose };
}

