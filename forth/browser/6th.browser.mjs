import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { checkWasiDemo } from "./wasi-demo.mjs";

const root = resolve(fileURLToPath(new URL("../..", import.meta.url)));

test("SEE QUIT works in the 6th browser demo", { timeout: 120_000 }, () =>
    checkWasiDemo({
        name: "6th",
        wasmFilePath: join(root, "forth", "zig-out", "web", "wasi", "6th.wasm"),
    }));
