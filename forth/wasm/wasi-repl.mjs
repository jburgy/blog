// Main-thread bootstrap for the no-pty WASI browser demos
// (html/4th.html, html/5th.html, html/6th.html, and bur.gy's how-many-roads
// post's tabbed jonesforth.wasm/4th/5th/6th switcher): mounts xterm.js, runs
// the guest with wasi-command.mjs's runWasiCommand (JSPI, so `read()` just
// suspends it -- no Worker), and uses xterm-readline for line editing rather
// than hand-rolling a weaker one. Still no real pty, unlike the old
// xterm-pty-based demos those posts used before migrating to this module (see
// forth/README.md's "Toolkits, briefly" section).
import { Terminal } from "https://esm.sh/@xterm/xterm@5.5.0";
import { Readline } from "https://esm.sh/xterm-readline@1.1.2";
import { runWasiCommand } from "./wasi-command.mjs";

/**
 * @param {URL} module the WASI command to run
 * @param {URL} preamble fed to the guest's stdin before handing the terminal
 *   to the user
 * @param {Element} container where to mount the terminal; one REPL per
 *   container, but any number of containers per page
 * @returns {{ sendLine: (text: string) => void, getOutput: () => string, dispose: () => void }}
 *   `sendLine`/`getOutput` let a test drive the REPL deterministically
 *   (see wasi-repl-mocha.mjs). `sendLine` uses xterm.js's own `paste()` to
 *   feed Readline's pending `read()` -- still no simulated keystrokes. Two
 *   separate calls, not one `text + "\r"`: Readline's own paste handling
 *   (readline.js's readPaste) deliberately turns an Enter *inside* a
 *   multi-character paste into a literal "\n" (no accidental paste-and-run),
 *   so only a lone, single-character paste of "\r" takes the submit path.
 *   `dispose` tears down the Terminal and parks the guest on stdin forever
 *   (not EOF: jonesforth's KEY spins on it), so a caller that wants to switch
 *   modules mid-page (e.g. a tabbed demo picking between interpreters) can
 *   cleanly `mountRepl(...)` again in the same container.
 */
export function mountRepl(module, preamble, container) {
    if (!(module instanceof URL)) throw new TypeError("module must be a URL");
    if (!(preamble instanceof URL)) throw new TypeError("preamble must be a URL");
    if (!(container instanceof Element)) throw new TypeError("container must be an Element");
    const xterm = new Terminal();
    // xterm-readline redraws a line as many tiny write() calls (erase, text, "\r", cursor move);
    // coalesce them per tick so xterm.js never renders the half-drawn "cursor at column 0" state.
    // FIXME: drop once strtok/xterm-readline emits each redraw as one write (no upstream issue yet).
    const write0 = xterm.write.bind(xterm);
    let pending = "";
    let callbacks = [];
    xterm.write = (data, callback) => {
        if (!pending) queueMicrotask(() => {
            const [text, cbs] = [pending, callbacks];
            pending = "";
            callbacks = [];
            write0(text, () => cbs.forEach((cb) => cb()));
        });
        pending += data;
        if (callback) callbacks.push(callback);
    };
    const rl = new Readline();
    xterm.loadAddon(rl);
    xterm.open(container);

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
            controller.enqueue(new Uint8Array(await (await fetch(preamble)).arrayBuffer()));
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

    runWasiCommand(fetch(module), { stdin, stdout: write, stderr: write }).then(
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

    return { sendLine, getOutput: () => output, dispose };
}


/**
 * @deprecated Use {@link mountRepl}. Legacy argument handling, kept until
 * jburgy.github.io migrates: `preamble` is `true` (jonesforth.f), `false`
 * (none) or a path relative to this module; `container` is an element or id.
 * @param {string} wasmUrl
 * @param {boolean | string} [preamble]
 * @param {string | Element} [container]
 */
export function startRepl(wasmUrl, preamble = true, container = "terminal") {
    return mountRepl(
        new URL(wasmUrl, document.baseURI),
        preamble ? new URL(typeof preamble === "string" ? preamble : "./jonesforth/jonesforth.f", import.meta.url) : new URL("data:,"),
        typeof container === "string" ? document.getElementById(container) : container,
    );
}
