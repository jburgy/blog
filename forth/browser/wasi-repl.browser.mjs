import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { checkWasiDemo } from "./wasi-demo.mjs";

const root = resolve(fileURLToPath(new URL("../..", import.meta.url)));

// One file instead of 4th.browser.mjs/5th.browser.mjs/6th.browser.mjs: each
// call below only ever differed in `name`/`wasmFilePath`, registered as its
// own node:test case so one interpreter failing still reports the other two
// individually rather than aborting the whole run.
for (const [name, wasmFilePath] of [
    ["4th", join(root, "forth", "4th.wasm")],
    ["5th", join(root, "forth", "5th.wasm")],
    ["6th", join(root, "forth", "zig-out", "web", "wasi", "6th.wasm")],
]) {
    test(`SEE QUIT works in the ${name} browser demo`, { timeout: 120_000 }, () =>
        checkWasiDemo({ name, wasmFilePath }));
}
