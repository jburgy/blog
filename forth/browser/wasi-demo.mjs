// Shared mocha-headless-chrome helper for the wasi-worker.js browser demos
// (4th, 5th, 6th): serves html/<name>.html behind a local server (COOP/COEP
// headers, see ../../assets/serve-e2e.mjs, which this shares its
// static-file-serving core with), then drives it headless. The actual
// assertion lives in the page itself (wasm/wasi-repl-mocha.mjs's in-browser
// mocha spec, loaded by every html/<name>.html -- a human visiting the page
// sees the same pass/fail report), so this only needs to launch a headless
// browser against the page and surface mocha's result; no second
// browser-automation library to keep in sync with regexp/web's existing
// mocha-headless-chrome setup (see regexp/web/coverage.mjs). No `node:test`
// imports here on purpose -- same convention as ../wasm-test.ts: this module
// only exports the reusable check; wasi-repl.browser.mjs owns the
// `test(...)` calls, one per interpreter.
import { execFile } from "node:child_process";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { safeJoin, startServer } from "../../assets/serve-e2e.mjs";

const execFileAsync = promisify(execFile);
const root = resolve(fileURLToPath(new URL("../..", import.meta.url)));
const assetRoot = "/assets/";

function resolvePath({ name, wasmFilePath, htmlPath }, pathname) {
    if (pathname === "/") pathname = htmlPath;
    if (pathname === `${assetRoot}${name}-wasi.wasm`) {
        return wasmFilePath;
    }
    if (
        pathname === `${assetRoot}worker.js`
        || pathname === `${assetRoot}wasi-worker.js`
        || pathname === `${assetRoot}wasi-repl.mjs`
        || pathname === `${assetRoot}wasi-repl-mocha.mjs`
    ) {
        return join(root, "forth", "wasm", pathname.slice(assetRoot.length));
    }
    if (pathname === `${assetRoot}forth/4th.32.fs`) {
        return join(root, "forth", "4th.32.fs");
    }
    return safeJoin(root, pathname);
}

/**
 * Drives html/<name>.html headless and asserts mocha's own in-page spec
 * passed. Call this from inside your own `test(...)` (see node:test) -- it
 * owns no test registration itself.
 *
 * @param {object} options
 * @param {string} options.name e.g. "6th" -- serves wasmFilePath at /assets/<name>-wasi.wasm and html/<name>.html
 * @param {string} options.wasmFilePath absolute path to the built .wasm
 */
export async function checkWasiDemo({ name, wasmFilePath }) {
    const htmlPath = `/forth/html/${name}.html`;
    const server = await startServer((pathname) => resolvePath({ name, wasmFilePath, htmlPath }, pathname));
    try {
        const args = [
            "mocha-headless-chrome",
            "-f", `${server.origin}${htmlPath}`,
            "-t", "90000",
            ...(process.platform === "linux" ? ["-a", "no-sandbox", "-a", "enable-features=SharedArrayBuffer"] : []),
        ];
        // Nonzero exit (execFileAsync throws) is the failure signal; its own
        // stdout/stderr (surfaced via the thrown error) already has mocha's
        // pass/fail report, so there's nothing to parse here.
        await execFileAsync("npx", args);
    } finally {
        await server.close();
    }
}
