#!/usr/bin/env node
// Serves jburgy.github.io's built site and blog/assets under one origin, for
// local end-to-end testing of the browser WASM demos under forth/wasm/, and
// doubles as the shared static-file-serving core forth/browser/wasi-demo.mjs
// uses for its own automated (puppeteer/mocha-headless-chrome) test server --
// both need the exact same COOP/COEP-header dance, just different routing.
//
// THE PROBLEM THIS SOLVES: these demos only render in a real browser (jsdom/
// Node can't do it -- see forth/wasm/wasi-worker.test.ts's own comment on
// that). Checking one out therefore means standing up the exact split-origin,
// cross-origin-isolated setup GitHub Pages provides in production:
//   - bur.gy (jburgy.github.io) and jburgy/blog's Pages deployment share one
//     origin there, with blog's assets reachable under /blog/ (see
//     jburgy.github.io/docs/_includes/terminal.html) -- this script collapses
//     that two-repo split onto one local origin/port.
//   - A worker-side blocking read (SharedInputChannel + Atomics.wait) needs
//     SharedArrayBuffer, which needs COOP/COEP headers on *every* response,
//     not just the demo's own page. This script just sends them; production
//     fakes them client-side via coi-serviceworker.js's install + reload
//     dance, which a local server doesn't need to bother with.
//
// WORKFLOW for an agent checking out a demo change:
//     1. Make sure jburgy.github.io is checked out as a sibling directory of
//        this blog checkout (clone it there if it isn't; override the
//        location with --site-root otherwise).
//     2. Build whichever assets/ target the demo you're testing needs, e.g.
//        `make jonesforth.wasm` in assets/ (this script does *not* build
//        anything itself).
//     3. Run this script (`make serve-e2e` from assets/, or directly:
//        `node serve-e2e.mjs`) and open the demo's post at
//        http://localhost:8000/<post-path>, e.g.
//        http://localhost:8000/2025/11/29/how-many-roads.html.
//     4. Iterate: `make <target>` again, then just reload the page -- files
//        under assets/ are served straight off disk, no server restart
//        needed. Only re-run this script (with --skip-jekyll-build, since the
//        Jekyll site itself didn't change) if you stopped it.
//
// Usage:
//     node serve-e2e.mjs                       # build the jekyll site, then serve
//     node serve-e2e.mjs --skip-jekyll-build    # just (re)serve, e.g. after a
//                                                # `make` in assets/
//     node serve-e2e.mjs --port 8001
import { execFileSync } from "node:child_process";
import { once } from "node:events";
import { createServer } from "node:http";
import { createReadStream } from "node:fs";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ASSETS = resolve(fileURLToPath(new URL(".", import.meta.url)));
const BLOG_ROOT = resolve(ASSETS, "..");

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

/**
 * Joins `base` with the URL path `pathname`, refusing to escape `base` via
 * `..` segments. Returns null for an attempted traversal.
 */
export function safeJoin(base, pathname) {
    const relative = normalize(pathname).replace(/^\/+/, "");
    if (relative.startsWith("..")) return null;
    return join(base, relative);
}

/**
 * Generic static-file HTTP server with the COOP/COEP headers
 * SharedArrayBuffer/Atomics.wait needs on every response (what
 * coi-serviceworker.js fakes client-side in production; GitHub Pages sends
 * neither header itself). `resolvePath(pathname)` maps a request path to an
 * absolute file path (or a falsy value for 404) -- the caller owns all
 * routing, this function only owns headers/content-type/error handling.
 * Streams the file (no buffering the whole thing into memory first): a
 * response only starts once the file is confirmed openable, so a missing
 * file still gets a clean 404 rather than a 200 that aborts mid-stream.
 *
 * @param {(pathname: string) => string | null | undefined} resolvePath
 * @param {number} [port] defaults to 0 (OS-assigned)
 */
export async function startServer(resolvePath, port = 0) {
    const server = createServer((req, res) => {
        const url = new URL(req.url ?? "/", "http://127.0.0.1");
        const path = resolvePath(url.pathname);
        if (!path) {
            res.writeHead(404, sharedHeaders).end("not found");
            return;
        }
        const stream = createReadStream(path);
        stream.on("error", () => res.writeHead(404, sharedHeaders).end("not found"));
        stream.once("open", () => {
            res.writeHead(200, { ...sharedHeaders, "content-type": contentType(path) });
            stream.pipe(res);
        });
    });
    server.listen(port, "localhost");
    await once(server, "listening");
    const { port: boundPort } = server.address();
    return {
        origin: `http://localhost:${boundPort}`,
        async close() {
            server.closeAllConnections();
            server.close();
            await once(server, "close");
        },
    };
}

function resolveBlogOrSitePath(pathname, assetsDir, siteDir) {
    const isBlog = pathname === "/blog" || pathname.startsWith("/blog/");
    const base = isBlog ? assetsDir : siteDir;
    let rel = isBlog ? pathname.slice("/blog".length) || "/" : pathname;
    if (rel.endsWith("/")) rel += "index.html";
    return safeJoin(base, rel);
}

function buildJekyllSite(siteRoot) {
    execFileSync(
        "bundle",
        ["exec", "jekyll", "build", "--source", ".", "--destination", "../_site"],
        { cwd: join(siteRoot, "docs"), stdio: "inherit" },
    );
}

function parseArgs(argv) {
    const options = {
        port: 8000,
        siteRoot: resolve(BLOG_ROOT, "..", "jburgy.github.io"),
        skipJekyllBuild: false,
    };
    for (let i = 0; i < argv.length; i++) {
        const arg = argv[i];
        if (arg === "--port") options.port = Number(argv[++i]);
        else if (arg === "--site-root") options.siteRoot = resolve(argv[++i]);
        else if (arg === "--skip-jekyll-build") options.skipJekyllBuild = true;
    }
    return options;
}

async function main() {
    const options = parseArgs(process.argv.slice(2));
    if (!options.skipJekyllBuild) buildJekyllSite(options.siteRoot);

    const siteDir = join(options.siteRoot, "_site");
    const { origin, close } = await startServer(
        (pathname) => resolveBlogOrSitePath(pathname, ASSETS, siteDir),
        options.port,
    );
    console.log(`Serving jburgy.github.io at ${origin}/`);
    console.log(`Serving blog/assets at    ${origin}/blog/`);
    console.log("Ctrl-C to stop.");
    process.on("SIGINT", async () => {
        await close();
        process.exit(0);
    });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
    main();
}
