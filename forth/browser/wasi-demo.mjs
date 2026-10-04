// Shared puppeteer helper for the wasi-worker.js browser demos (4th, 5th,
// 6th): boots html/<name>.html in a real headless Chromium behind a local
// server (COOP/COEP headers, see ../../assets/serve-e2e.mjs, which this
// shares its static-file-serving core with), types a command, and checks the
// rendered terminal. No `node:test` imports here on purpose -- same
// convention as ../wasm-test.ts: this module only exports the reusable
// check; each <name>.browser.mjs owns its own `test(...)` call (see
// 4th.browser.mjs/5th.browser.mjs/6th.browser.mjs), since the harness itself
// (server, terminal hook, worker.js/wasi-worker.js/4th.32.fs asset wiring) is
// identical across all three -- only the wasm binary and expected output
// differ.
import assert from "node:assert/strict";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer";
import { safeJoin, startServer } from "../../assets/serve-e2e.mjs";

const root = resolve(fileURLToPath(new URL("../..", import.meta.url)));
const assetRoot = "/assets/";

function terminalText(page) {
    return page.evaluate(() => {
        const term = window.__xterm;
        if (!term) return "";
        const lines = [];
        const active = term.buffer.active;
        for (let i = 0; i < active.length; i += 1) {
            const line = active.getLine(i);
            if (line) lines.push(line.translateToString(true));
        }
        return lines.join("\n").replaceAll("\u00a0", " ").replaceAll("\r", "");
    });
}

function installTerminalHook(page) {
    return page.evaluateOnNewDocument(() => {
        Object.defineProperty(window, "Terminal", {
            configurable: true,
            set(value) {
                const Wrapped = function (...args) {
                    const term = new value(...args);
                    window.__xterm = term;
                    return term;
                };
                Object.setPrototypeOf(Wrapped, value);
                Wrapped.prototype = value.prototype;
                Object.defineProperty(window, "Terminal", {
                    value: Wrapped,
                    writable: true,
                    configurable: true,
                });
            },
        });
    });
}

function waitForTerminalText(page, needle) {
    return page.waitForFunction(
        (text) => {
            const term = window.__xterm;
            if (!term) return false;
            const active = term.buffer.active;
            const lines = [];
            for (let i = 0; i < active.length; i += 1) {
                const line = active.getLine(i);
                if (line) lines.push(line.translateToString(true));
            }
            return lines.join("\n").includes(text);
        },
        { timeout: 90_000 },
        needle,
    );
}

function diagnostics(page) {
    return page.evaluate(() => ({
        crossOriginIsolated,
        hasSharedArrayBuffer: typeof SharedArrayBuffer === "function",
        hasTerminal: !!window.__xterm,
        text: document.body.innerText,
    }));
}

function resolvePath({ name, wasmFilePath, htmlPath }, pathname) {
    if (pathname === "/") pathname = htmlPath;
    if (pathname.startsWith(`${assetRoot}node_modules/`)) {
        return join(root, "forth", "node_modules", pathname.slice(`${assetRoot}node_modules/`.length));
    }
    if (pathname === `${assetRoot}${name}.wasm`) {
        return wasmFilePath;
    }
    if (pathname === `${assetRoot}worker.js` || pathname === `${assetRoot}wasi-worker.js` || pathname === `${assetRoot}wasi-repl.mjs`) {
        return join(root, "forth", "wasm", pathname.slice(assetRoot.length));
    }
    if (pathname === `${assetRoot}forth/4th.32.fs`) {
        return join(root, "forth", "4th.32.fs");
    }
    return safeJoin(root, pathname);
}

/**
 * Drives html/<name>.html in a real browser: types `command` and asserts
 * `expected` shows up in the rendered terminal. Call this from inside your
 * own `test(...)` (see node:test) -- it owns no test registration itself.
 *
 * @param {object} options
 * @param {string} options.name e.g. "6th" -- serves wasmFilePath at /assets/<name>.wasm and html/<name>.html
 * @param {string} options.wasmFilePath absolute path to the built .wasm
 * @param {string} [options.expected] text that must appear in the terminal after `command`;
 *   defaults to QUIT's decompile, since 4th.c/5th.c/6th.zig all share the same 4th.32.fs dictionary
 * @param {string} [options.command] defaults to "SEE QUIT"
 */
export async function checkWasiDemo({
    name,
    wasmFilePath,
    expected = ": QUIT R0 RSP! INTERPRET BRANCH ( -8 ) ;",
    command = "SEE QUIT",
}) {
    const htmlPath = `/forth/html/${name}.html`;
    const server = await startServer((pathname) => resolvePath({ name, wasmFilePath, htmlPath }, pathname));
    const browser = await puppeteer.launch({
        headless: true,
        args: process.platform === "linux"
            ? ["--no-sandbox", "--enable-features=SharedArrayBuffer"]
            : [],
    });
    try {
        const page = await browser.newPage();
        await installTerminalHook(page);
        page.on("console", (message) => {
            if (message.type() === "warning" || message.type() === "error") {
                console.error(`[browser:${message.type()}] ${message.text()}`);
            }
        });
        page.on("pageerror", (error) => {
            console.error(`[browser:pageerror] ${error.stack ?? error.message}`);
        });
        await page.goto(`${server.origin}${htmlPath}`, { waitUntil: "networkidle0" });
        await page.waitForFunction(
            () => document.querySelector("#terminal .xterm-screen, #terminal canvas") !== null,
        );
        try {
            await waitForTerminalText(page, "JONESFORTH VERSION");
        } catch (error) {
            assert.fail(`terminal never printed banner: ${JSON.stringify(await diagnostics(page))}\n${error}`);
        }

        await page.click("#terminal");
        await page.keyboard.type(command);
        await page.keyboard.press("Enter");

        try {
            await waitForTerminalText(page, expected);
        } catch (error) {
            assert.fail(`terminal never printed expected output: ${JSON.stringify(await diagnostics(page))}\n${error}`);
        }

        const text = await terminalText(page);
        assert.match(text, new RegExp(expected.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
        await page.close();
    } finally {
        await browser.close();
        await server.close();
    }
}

