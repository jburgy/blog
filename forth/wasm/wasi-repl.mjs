// Main-thread bootstrap for the no-pty wasi-worker.js browser demos
// (html/4th.html, html/5th.html, html/6th.html, and bur.gy's how-many-roads
// post's tabbed jonesforth.wasm/4th/5th/6th switcher): mounts xterm.js, feeds
// jonesforth.f's classic dictionary to a Worker (see worker.js) over a uwasi
// SharedInputChannel, and uses xterm-readline for line editing -- the same
// addon main.js (jonesforth.
// wasm's original, since-retired published demo) already used against this
// exact worker/channel protocol, rather than hand-rolling a second, weaker
// line editor. Still no real pty, unlike the old xterm-pty-based demos
// those posts used before migrating to this module (see
// forth/README.md's "Toolkits, briefly" section). Named to pair with
// wasi-worker.js: that's the Worker side, this is the main-thread side.
import { Terminal } from "https://esm.sh/@xterm/xterm@5.5.0";
import { Readline } from "https://esm.sh/xterm-readline@1.1.2";
import { SharedInputChannel } from "https://esm.sh/uwasi@1.6.0";

/**
 * @param {string} wasmUrl
 * @param {boolean} [preamble] feeds jonesforth.f's classic dictionary before
 *   handing the terminal to the user (default); pass `false` for a WASI
 *   command with no use for it (e.g. lisp-wasi.wasm/TinyBasic-wasi.wasm, see
 *   jburgy.github.io's lisp/TinyBasic posts). One file for every FORTH here
 *   (4th.c/5th.c/6th.zig and jonesforth.wasm alike): jonesforth.f's own
 *   ARGC/ARGV/ENVIRON read S0-relative, the original x86 stack layout, which
 *   compiles fine under WASI but answers wrong instead of real argv (see
 *   wasi-worker.test.ts) -- harmless, since nothing here ever calls them.
 * @param {string | HTMLElement} [container] defaults to `#terminal`, same as
 *   every existing caller (a single demo per page). Pass an element (or a
 *   different id) to mount more than one REPL on the same page at once --
 *   e.g. assets/index.html's landing page, where each interpreter gets its
 *   own `<details>` instead of sharing one div like the tabbed how-many-roads
 *   post does.
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
export function startRepl(wasmUrl, preamble = true, container = "terminal") {
    const preambleUrl = new URL("./jonesforth/jonesforth.f", import.meta.url);
    const xterm = new Terminal();
    const rl = new Readline();
    xterm.loadAddon(rl);
    xterm.open(typeof container === "string" ? document.getElementById(container) : container);

    // Cyan input vs. default-colored output, via xterm-readline's Highlighter hook.
    rl.setHighlighter({
        highlight: (line) => `\x1b[36m${line}\x1b[0m`,
        highlightPrompt: (prompt) => prompt,
        // Must be true, or xterm-readline skips highlight() on its fast per-keystroke path.
        highlightChar: () => true,
    });

    // Sized well past jonesforth.f (~58 KiB).
    const channel = new SharedInputChannel(128 * 1024);
    const worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });

    let output = "";
    let disposed = false;
    // Skip "ok" after the first idle: WELCOME's own one-time "OK " already covers it.
    let first = true;

    // Empty prompt always: "ok" (see 'idle' below) is output glued after the
    // interpreter's own text, not a read() prompt -- raw output written
    // after an armed prompt gets erased on that read's next refresh.
    function readLine() {
        if (disposed) return;
        rl.read("").then(processLine);
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
                if (preamble) {
                    const response = await fetch(preambleUrl);
                    channel.push(new Uint8Array(await response.arrayBuffer()));
                }
                // No readLine() here -- the guest's own first fd_read fires 'idle' below, which arms it.
                break;
            }
            case "output":
                if (fd === 1 || fd === 2) {
                    output += data;
                    rl.write(data);
                }
                break;
            case "idle":
                // Guest's first fd_read can fire this before any preamble has
                // been pushed/read (two independent fetches racing) -- not a
                // real prompt yet.
                if (preamble && !output) {
                    readLine();
                    break;
                }
                // This line is done printing -- append dim "ok" (no leading
                // space: jonesforth's own output usually ends in one), then
                // "\n" so the next read starts on a row with nothing to erase.
                if (!first) rl.write("\x1b[2mok\x1b[0m");
                first = false;
                rl.write("\n");
                readLine();
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

