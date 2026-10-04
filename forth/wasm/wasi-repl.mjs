// Main-thread bootstrap for the no-pty wasi-worker.js browser demos
// (html/4th.html, html/5th.html, html/6th.html): mounts xterm.js, feeds the
// shared 4th.32.fs preamble to a Worker (see worker.js) over a uwasi
// SharedInputChannel, and uses xterm-readline for line editing -- the same
// addon main.js (jonesforth.wasm's published demo) already uses against this
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
 * @returns {{ term: Terminal, sendLine: (text: string) => void, getOutput: () => string }}
 *   `sendLine`/`getOutput` let a test drive the REPL deterministically
 *   (see wasi-repl-mocha.mjs). `sendLine` uses xterm.js's own `paste()` to
 *   feed Readline's pending `read()` -- still no simulated keystrokes. Two
 *   separate calls, not one `text + "\r"`: Readline's own paste handling
 *   (readline.js's readPaste) deliberately turns an Enter *inside* a
 *   multi-character paste into a literal "\n" (no accidental paste-and-run),
 *   so only a lone, single-character paste of "\r" takes the submit path.
 */
export function startRepl(wasmUrl) {
    const xterm = new Terminal();
    const rl = new Readline();
    xterm.loadAddon(rl);
    xterm.open(document.getElementById("terminal"));

    // Sized well past 4th.32.fs (~58 KiB), same margin as main.js's
    // jonesforth.f channel.
    const channel = new SharedInputChannel(128 * 1024);
    const worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });

    let output = "";
    // Mirrors main.js's resume heuristic: re-arm the next read() once a
    // chunk ends in '\n' (the REPL's own prompt line), or after a short
    // timeout if a chunk never does (e.g. an "OK " prompt with no newline).
    // `armed` guards both paths from ever firing twice for the same turn:
    // read() isn't idempotent -- calling it again while one is still
    // pending silently abandons the old promise and reprints the prompt,
    // which is exactly what produced an extra blank prompt line, since
    // libc's own stdout buffering decides -- unpredictably from here --
    // whether a reply arrives as one chunk or several.
    let armed = false;
    let timeout = -1;

    function readLine() {
        if (armed) return;
        armed = true;
        if (timeout >= 0) {
            clearTimeout(timeout);
            timeout = -1;
        }
        rl.read("").then((text) => {
            armed = false;
            processLine(text);
        });
    }

    function resume() {
        timeout = -1;
        readLine();
    }

    function processLine(text) {
        channel.push(new TextEncoder().encode(text + "\n"));
    }

    worker.addEventListener("message", async ({ data: { type, fd, data, code, message } }) => {
        switch (type) {
            case "ready": {
                const response = await fetch(new URL("./forth/4th.32.fs", import.meta.url));
                channel.push(new Uint8Array(await response.arrayBuffer()));
                readLine();
                break;
            }
            case "output":
                if (fd === 1 || fd === 2) {
                    output += data;
                    rl.write(data);
                    if (data.endsWith("\n")) readLine();
                    else if (timeout < 0) timeout = setTimeout(resume, 100);
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

    worker.postMessage({ sharedBuffer: channel.sharedBuffer, wasmUrl });

    return { term: xterm, sendLine, getOutput: () => output };
}

