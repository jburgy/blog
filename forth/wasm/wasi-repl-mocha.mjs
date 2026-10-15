// Shared in-browser mocha spec for the wasi-command.mjs REPL demos
// (html/4th.html, html/5th.html, html/6th.html): drives mountRepl()
// (wasi-repl.mjs) directly -- no simulated keystrokes -- and asserts on its
// accumulated output, the same assertion every demo needs, parametrized by
// which interpreter's page is loading it. The page itself owns mocha.setup()
// and mocha.run() (see any of the three html files); this only registers the
// describe/it. Named *-mocha.mjs, not *.spec.mjs/*.test.mjs: this only runs
// inside a browser (mocha, loaded from a CDN by the page) -- vitest's
// default test-file glob would otherwise pick this up and try to execute it
// directly in Node, where wasi-repl.mjs's own browser-only imports (xterm.js,
// a Worker, ...) can't resolve/run.
//
// `waitFor` is exported too: index.html's own lazy, per-<details> smoke
// tests need the same polling helper but (unlike registerWasiReplSpec) don't
// send a command into the live terminal, so they can't reuse the spec itself.
import { mountRepl } from "./wasi-repl.mjs";

export function waitFor(predicate, timeout = 60000, interval = 100) {
    return new Promise((resolve, reject) => {
        const start = Date.now();
        (function check() {
            if (predicate()) return resolve();
            if (Date.now() - start > timeout) return reject(new Error("timed out waiting for condition"));
            setTimeout(check, interval);
        })();
    });
}

/**
 * @param {object} options
 * @param {string} options.name e.g. "6th" -- used for the suite's own description
 * @param {URL} options.module e.g. new URL("/assets/6th-wasi.wasm", location.href)
 * @param {URL} options.preamble e.g. new URL("/assets/forth/4th.32.fs", location.href)
 * @param {Element} options.container where to mount the terminal
 * @param {string} [options.expected] text that must appear in the output after `command`;
 *   defaults to QUIT's decompile, since 4th.c/5th.c/6th.zig all share the same 4th.32.fs dictionary
 * @param {string} [options.command] defaults to "SEE QUIT"
 */
export function registerWasiReplSpec({
    name,
    module,
    preamble,
    container,
    expected = ": QUIT R0 RSP! INTERPRET BRANCH ( -8 ) ;",
    command = "SEE QUIT",
}) {
    describe(`${name} REPL`, function () {
        this.timeout(60000);
        let repl;

        before(async () => {
            repl = mountRepl(module, preamble, container);
            await waitFor(() => repl.getOutput().includes("JONESFORTH VERSION"));
        });

        it(`${command} works`, async () => {
            repl.sendLine(command);
            await waitFor(() => repl.getOutput().includes(expected));
        });
    });
}
