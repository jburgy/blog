// Main-thread bootstrap for the no-pty WASI browser demos
// (html/4th.html, html/5th.html, html/6th.html, and bur.gy's how-many-roads
// post's tabbed jonesforth.wasm/4th/5th/6th switcher): mounts xterm.js, runs
// the guest with wasi-command.js's runWasiCommand (JSPI, so `read()` just
// suspends it -- no Worker), and uses xterm-readline for line editing rather
// than hand-rolling a weaker one. Still no real pty, unlike the old
// xterm-pty-based demos those posts used before migrating to this module (see
// forth/README.md's "Toolkits, briefly" section).
import { Terminal } from "https://esm.sh/@xterm/xterm@5.5.0";
import { Readline } from "https://esm.sh/xterm-readline@1.1.2";
import { runWasiCommand } from "./wasi-command.js";

/**
 * @param {string} wasmUrl
 * @param {boolean | string} [preamble] feeds jonesforth.f's classic
 *   dictionary before handing the terminal to the user (default); pass
 *   `false` for a WASI command with no use for it (e.g. TinyBasic-wasi.wasm,
 *   see jburgy.github.io's TinyBasic post). One file for every FORTH here
 *   (4th.c/5th.c/6th.zig and jonesforth.wasm alike): jonesforth.f's own
 *   ARGC/ARGV/ENVIRON read S0-relative, the original x86 stack layout, which
 *   compiles fine under WASI but answers wrong instead of real argv (see
 *   wasi-command.test.ts) -- harmless, since nothing here ever calls them.
 *   Pass a string instead (resolved relative to this module, same as the
 *   jonesforth.f default) to feed a different command its own preamble --
 *   e.g. lisp-wasi.wasm's `"./lisp/eliza.lisp"`, a single self-recursive
 *   expression (no interpreter changes needed) that greets the user, then
 *   keeps `(READ)`ing plain sentences and replying to them forever instead
 *   of ever handing control back to a bare `*` prompt.
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
 *   `dispose` tears down the Terminal and parks the guest on stdin forever
 *   (not EOF: jonesforth's KEY spins on it), so a caller that wants to switch
 *   wasmUrl mid-page (e.g. a tabbed demo picking between interpreters) can
 *   cleanly start a fresh `startRepl(...)` in the same `#terminal` div.
 */
export function startRepl(wasmUrl, preamble = true, container = "terminal") {
    const preambleUrl = new URL(typeof preamble === "string" ? preamble : "./jonesforth/jonesforth.f", import.meta.url);
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

    let output = "";
    let disposed = false;
    // Skip "ok" after the first prompt: WELCOME's own one-time "OK " already covers it.
    let first = true;
    // Set once an output chunk is a lone ":" with nothing else -- see its
    // use below.
    let lastWasBarePrompt = false;

    // A pull-based stdin: `pull` only runs when the guest is genuinely blocked
    // in read() with nothing buffered, which is exactly when to prompt. Chunks
    // `start` enqueues (the preamble) are consumed first, so the guest never
    // reads before it exists.
    const stdin = new ReadableStream({
        async start(controller) {
            if (preamble) controller.enqueue(new Uint8Array(await (await fetch(preambleUrl)).arrayBuffer()));
        },
        async pull(controller) {
            if (disposed) return new Promise(() => { });
            // This line is done printing -- append dim "ok" (no leading
            // space: jonesforth's own output usually ends in one), then
            // "\n" so the next read starts on a row with nothing to erase.
            if (!first) rl.write("\x1b[2mok\x1b[0m");
            first = false;
            rl.write("\n");
            // Empty prompt always: "ok" above is output glued after the
            // interpreter's own text, not a read() prompt -- raw output written
            // after an armed prompt gets erased on that read's next refresh.
            controller.enqueue(new TextEncoder().encode(`${await rl.read("")}\n`));
        },
    }, { highWaterMark: 0 });

    function write(data) {
        if (disposed) return;
        output += data;
        // A multi-line preamble (e.g. TinyBasic/tictactoe.bas,
        // ~70 stored lines) echoes its own bare ":" command
        // prompt once per line while loading -- faithful to the
        // real interpreter (it does this for every line it
        // reads, not just direct commands), but a wall of
        // identical prompts is pure noise with nothing else
        // interleaved. Collapse consecutive repeats down to the
        // single one a human typing one line at a time would
        // actually see; `output` above still keeps the true,
        // uncollapsed stream for getOutput() callers.
        const isBarePrompt = data === ":";
        if (!(isBarePrompt && lastWasBarePrompt)) rl.write(data);
        lastWasBarePrompt = isBarePrompt;
    }

    runWasiCommand(fetch(wasmUrl), { stdin, stdout: write, stderr: write }).then(
        (code) => { if (!disposed) rl.println(`[Process exited with code ${code}]`); },
        (error) => { if (!disposed) rl.println(`[Error: ${error.message}]`); },
    );

    function sendLine(text) {
        xterm.paste(text);
        xterm.paste("\r");
    }

    function dispose() {
        if (disposed) return;
        disposed = true;
        xterm.dispose();
    }

    return { term: xterm, sendLine, getOutput: () => output, dispose };
}

