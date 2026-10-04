// Shared puppeteer harness for the wasi-worker.js browser demos (4th, 5th,
// 6th): boots html/<name>.html in a real headless Chromium behind a local
// server (COOP/COEP headers, same as GitHub Pages' sw.js workaround), types
// a command, and checks the rendered terminal. Parametrized per interpreter
// by its own <name>.browser.mjs -- see 4th.browser.mjs/5th.browser.mjs/
// 6th.browser.mjs -- since the harness itself (server, terminal hook,
// worker.js/wasi-worker.js/4th.32.fs asset wiring) is identical across all
// three; only the wasm binary and expected output differ.
import assert from "node:assert/strict";
import { once } from "node:events";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, test } from "node:test";
import puppeteer from "puppeteer";

const root = resolve(fileURLToPath(new URL("../..", import.meta.url)));
const assetRoot = "/assets/";
const sharedHeaders = {
    "cross-origin-embedder-policy": "require-corp",
    "cross-origin-opener-policy": "same-origin",
};

function contentType(pathname) {
    return ({
        ".css": "text/css; charset=utf-8",
        ".f": "text/plain; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8",
        ".wasm": "application/wasm",
    })[extname(pathname)] ?? "application/octet-stream";
}

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

/**
 * @param {object} options
 * @param {string} options.name e.g. "6th" -- serves wasmFilePath at /assets/<name>.wasm
 * @param {string} options.wasmFilePath absolute path to the built .wasm
 * @param {string} options.expected text that must appear in the terminal after `command`
 * @param {string} [options.command] defaults to "SEE QUIT"
 */
export function describeWasiDemo({ name, wasmFilePath, expected, command = "SEE QUIT" }) {
    const htmlPath = `/forth/html/${name}.html`;

    function assetPath(pathname) {
        if (pathname.startsWith(`${assetRoot}node_modules/`)) {
            return join(root, "forth", "node_modules", pathname.slice(`${assetRoot}node_modules/`.length));
        }
        if (pathname === `${assetRoot}${name}.wasm`) {
            return wasmFilePath;
        }
        if (pathname === `${assetRoot}worker.js` || pathname === `${assetRoot}wasi-worker.js`) {
            return join(root, "forth", "wasm", pathname.slice(assetRoot.length));
        }
        if (pathname === `${assetRoot}forth/4th.32.fs`) {
            return join(root, "forth", "4th.32.fs");
        }
        return null;
    }

    function filePath(pathname) {
        const asset = assetPath(pathname);
        if (asset) return asset;
        const relative = normalize(pathname).replace(/^\/+/, "");
        if (relative.startsWith("..")) return null;
        return join(root, relative);
    }

    async function startServer() {
        const server = createServer(async (req, res) => {
            try {
                const url = new URL(req.url ?? "/", "http://127.0.0.1");
                const pathname = url.pathname === "/" ? htmlPath : url.pathname;
                const path = filePath(pathname);
                if (!path) {
                    res.writeHead(404).end("not found");
                    return;
                }
                const body = await readFile(path);
                res.writeHead(200, { ...sharedHeaders, "content-type": contentType(pathname) });
                res.end(body);
            } catch {
                res.writeHead(404, sharedHeaders).end("not found");
            }
        });
        server.listen(0, "localhost");
        await once(server, "listening");
        const { port } = server.address();
        return {
            origin: `http://localhost:${port}`,
            async close() {
                server.closeAllConnections();
                server.close();
                await once(server, "close");
            },
        };
    }

    let browser;
    let server;

    before(async () => {
        server = await startServer();
        browser = await puppeteer.launch({
            headless: true,
            args: process.platform === "linux"
                ? ["--no-sandbox", "--enable-features=SharedArrayBuffer"]
                : [],
        });
    });

    after(async () => {
        await browser?.close();
        await server?.close();
    });

    test(`${command} works in the ${name} browser demo`, { timeout: 120_000 }, async () => {
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
    });
}
