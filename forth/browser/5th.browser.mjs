import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describeWasiDemo } from "./wasi-demo.mjs";

const root = resolve(fileURLToPath(new URL("../..", import.meta.url)));

describeWasiDemo({
    name: "5th",
    wasmFilePath: join(root, "forth", "5th.wasm"),
    expected: ": QUIT R0 RSP! INTERPRET BRANCH ( -8 ) ;",
});
