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
const htmlPath = "/forth/html/6th.html";
const expected = ": QUIT R0 RSP! INTERPRET BRANCH ( -8 ) ;";
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

function assetPath(pathname) {
    if (pathname.startsWith(`${assetRoot}node_modules/`)) {
        return join(root, "forth", "node_modules", pathname.slice(`${assetRoot}node_modules/`.length));
    }
    if (pathname === `${assetRoot}6th.mjs` || pathname === `${assetRoot}6th.wasm`) {
        return join(root, "forth", "zig-out", "web", pathname.slice(assetRoot.length));
    }
    if (pathname === `${assetRoot}jonesforth.f`) {
        return join(root, "jonesforth", "jonesforth.f");
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
    server.listen(0, "127.0.0.1");
    await once(server, "listening");
    const { port } = server.address();
    return {
        origin: `http://127.0.0.1:${port}`,
        async close() {
            server.closeAllConnections();
            server.close();
            await once(server, "close");
        },
    };
}

function terminalText(page) {
    return page.$eval("#terminal", (node) =>
        (node.innerText || node.textContent || "")
            .replaceAll("\u00a0", " ")
            .replaceAll("\r", ""),
    );
}

let browser;
let server;

before(async () => {
    server = await startServer();
    browser = await puppeteer.launch({
        headless: true,
        args: process.platform === "linux" ? ["--no-sandbox"] : [],
    });
});

after(async () => {
    await browser?.close();
    await server?.close();
});

test("SEE QUIT decompiles QUIT in the browser demo", { timeout: 120_000 }, async () => {
    const page = await browser.newPage();
    await page.goto(`${server.origin}${htmlPath}`, { waitUntil: "networkidle0" });
    await page.waitForFunction(
        () => document.querySelector("#terminal .xterm-screen, #terminal canvas") !== null,
    );
    await page.waitForFunction(async () => {
        const terminal = document.querySelector("#terminal");
        const text = (terminal?.textContent ?? "").replaceAll("\u00a0", " ");
        return text.includes("JONESFORTH VERSION");
    });

    await page.click("#terminal");
    await page.keyboard.type("SEE QUIT");
    await page.keyboard.press("Enter");

    await page.waitForFunction(
        (needle) => {
            const terminal = document.querySelector("#terminal");
            const text = (terminal?.innerText ?? terminal?.textContent ?? "")
                .replaceAll("\u00a0", " ")
                .replaceAll("\r", "");
            return text.includes(needle);
        },
        {},
        expected,
    );

    const text = await terminalText(page);
    assert.match(text, new RegExp(expected.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    await page.close();
});
