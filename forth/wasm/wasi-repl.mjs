// Main-thread bootstrap for the no-pty wasi-worker.js browser demos
// (html/4th.html, html/5th.html, html/6th.html): mounts xterm.js, feeds the
// shared 4th.32.fs preamble to a Worker (see worker.js) over a uwasi
// SharedInputChannel, and does its own minimal line editing -- no real pty,
// unlike the published posts' Emscripten + xterm-pty demos (see those posts'
// own hardcoded scripts and forth/README.md's "Toolkits, briefly" section).
// Named to pair with wasi-worker.js: that's the Worker side, this is the
// main-thread side.
import "/assets/node_modules/@xterm/xterm/lib/xterm.js";
import { SharedInputChannel } from "https://esm.sh/uwasi@1.6.0";

/**
 * @param {string} wasmUrl
 * @returns {{ term: Terminal, sendLine: (text: string) => void, getOutput: () => string }}
 *   `sendLine`/`getOutput` let a test drive the REPL deterministically
 *   (see wasi-repl.spec.mjs) without simulating real keystrokes through
 *   xterm -- the same channel a human's typing ends up pushing to anyway.
 */
export function startRepl(wasmUrl) {
    const xterm = new Terminal();
    xterm.open(document.getElementById("terminal"));

    // Sized well past 4th.32.fs (~58 KiB), same margin as main.js's
    // jonesforth.f channel.
    const channel = new SharedInputChannel(128 * 1024);
    const worker = new Worker("/assets/worker.js", { type: "module" });

    let line = "";
    let output = "";

    worker.addEventListener("message", async ({ data: { type, fd, data, code, message } }) => {
        switch (type) {
            case "ready": {
                const response = await fetch("/assets/forth/4th.32.fs");
                channel.push(new Uint8Array(await response.arrayBuffer()));
                break;
            }
            case "output":
                // Forth emits bare newlines; a terminal wants CR LF.
                if (fd === 1 || fd === 2) {
                    output += data;
                    xterm.write(data.replace(/\n/g, "\r\n"));
                }
                break;
            case "exit":
                xterm.write(`\r\n[Process exited with code ${code}]\r\n`);
                break;
            case "error":
                xterm.write(`\r\n[Error: ${message}]\r\n`);
                break;
        }
    });

    function sendLine(text) {
        channel.push(new TextEncoder().encode(text + "\n"));
    }

    xterm.onData((key) => {
        if (key === "\r") {
            xterm.write("\r\n");
            sendLine(line);
            line = "";
        } else if (key === "\x7f") {
            if (line) {
                line = line.slice(0, -1);
                xterm.write("\b \b");
            }
        } else if (key >= " ") {
            line += key;
            xterm.write(key);
        }
    });

    worker.postMessage({ sharedBuffer: channel.sharedBuffer, wasmUrl });

    return { term: xterm, sendLine, getOutput: () => output };
}

