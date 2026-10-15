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
 * One REPL per container, but any number of containers per page. These are
 * interactive demos, so a guest that exits (e.g. BYE) or traps after the user
 * typed something is respawned with a fresh preamble. One that dies before
 * reading any user input is not, so a broken preamble can't loop forever.
 * `sendLine` and `output` let a test drive it deterministically (see
 * wasi-repl-mocha.mjs). `dispose` tears down the Terminal and parks the guest
 * on stdin forever (not EOF: jonesforth's KEY spins on it), so a caller that
 * wants to switch modules mid-page (e.g. a tabbed demo picking between
 * interpreters) can cleanly `new REPL(...)` again in the same container.
 */
export class REPL {
    /** @readonly */
    #xterm = new Terminal();
    /** @readonly */
    #rl = new Readline();
    /** @readonly @type {URL} */
    #module;
    #disposed = false;

    /** Everything the guest has written so far, uncollapsed. */
    output = "";

    /**
     * @param {URL} module the WASI command to run
     * @param {URL} preamble fed to the guest's stdin before handing the terminal
     *   to the user
     * @param {Element} container where to mount the terminal
     */
    constructor(module, preamble, container) {
        if (!(module instanceof URL)) throw new TypeError("module must be a URL");
        if (!(preamble instanceof URL)) throw new TypeError("preamble must be a URL");
        if (!(container instanceof Element)) throw new TypeError("container must be an Element");
        this.#module = module;
        const xterm = this.#xterm;
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
        xterm.loadAddon(this.#rl);
        xterm.open(container);

        // Cyan input vs. default-colored output, via xterm-readline's Highlighter hook.
        this.#rl.setHighlighter({
            highlight: (line) => `\x1b[36m${line}\x1b[0m`,
            highlightPrompt: (prompt) => prompt,
            // Must be true, or xterm-readline skips highlight() on its fast per-keystroke path.
            highlightChar: () => true,
        });

        this.#run(preamble).catch((error) => this.#rl.println(`[Error: ${error.message}]`));
    }

    /** @param {URL} preambleUrl */
    async #run(preambleUrl) {
        const preamble = new Uint8Array(await (await fetch(preambleUrl)).arrayBuffer());
        const rl = this.#rl;
        while (!this.#disposed) {
            // Skip "ok" after the first prompt: WELCOME's own one-time "OK " already covers it.
            let first = true;
            // Set once an output chunk is a lone ":" with nothing else -- see its
            // use below.
            let lastWasBarePrompt = false;
            let lines = 0;

            // A pull-based stdin: `pull` only runs when the guest is genuinely blocked
            // in read() with nothing buffered, which is exactly when to prompt. Chunks
            // `start` enqueues (the preamble) are consumed first, so the guest never
            // reads before it exists.
            const stdin = new ReadableStream({
                start: (controller) => controller.enqueue(preamble),
                pull: async (controller) => {
                    if (this.#disposed) return new Promise(() => { });
                    // This line is done printing -- append dim "ok" (no leading
                    // space: jonesforth's own output usually ends in one), then
                    // "\n" so the next read starts on a row with nothing to erase.
                    if (!first) rl.write("\x1b[2mok\x1b[0m");
                    first = false;
                    rl.write("\n");
                    // Empty prompt always: "ok" above is output glued after the
                    // interpreter's own text, not a read() prompt -- raw output written
                    // after an armed prompt gets erased on that read's next refresh.
                    const line = await rl.read("");
                    lines++;
                    controller.enqueue(new TextEncoder().encode(`${line}\n`));
                },
            }, { highWaterMark: 0 });

            const write = (data) => {
                if (this.#disposed) return;
                this.output += data;
                // Collapse repeated bare ":" prompts a multi-line preamble echoes; output keeps the raw stream.
                const isBarePrompt = data === ":";
                if (!(isBarePrompt && lastWasBarePrompt)) rl.write(data);
                lastWasBarePrompt = isBarePrompt;
            };

            let status;
            try {
                const code = await runWasiCommand(fetch(this.#module), { stdin, stdout: write, stderr: write });
                status = `[Process exited with code ${code}`;
            } catch (error) {
                status = `[Error: ${error.message}`;
            }
            if (this.#disposed) return;
            // Respawn only once the user got to type something, so a guest that dies
            // during its own preamble can't loop forever.
            const respawn = lines > 0;
            rl.println(`${status}${respawn ? ", restarting" : ""}]`);
            if (!respawn) return;
            rl.write("\x1b[3J\x1b[2J\x1b[H");
        }
    }

    /**
     * Feeds Readline's pending `read()` through xterm.js's own `paste()` --
     * still no simulated keystrokes. Two separate calls, not one
     * `text + "\r"`: Readline's own paste handling (readline.js's readPaste)
     * deliberately turns an Enter *inside* a multi-character paste into a
     * literal "\n" (no accidental paste-and-run), so only a lone,
     * single-character paste of "\r" takes the submit path.
     * @param {string} text
     */
    sendLine(text) {
        this.#xterm.paste(text);
        this.#xterm.paste("\r");
    }

    dispose() {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#xterm.dispose();
    }
}
