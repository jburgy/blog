import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { checkWasiDemo } from "./wasi-demo.mjs";

const root = resolve(fileURLToPath(new URL("../..", import.meta.url)));

test("SEE QUIT works in the 4th browser demo", { timeout: 120_000 }, () =>
    checkWasiDemo({
        name: "4th",
        wasmFilePath: join(root, "forth", "4th.wasm"),
    }));
