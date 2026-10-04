import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describeWasiDemo } from "./wasi-demo.mjs";

const root = resolve(fileURLToPath(new URL("../..", import.meta.url)));

describeWasiDemo({
    name: "4th",
    wasmFilePath: join(root, "forth", "4th.wasm"),
    expected: ": QUIT R0 RSP! INTERPRET BRANCH ( -8 ) ;",
});
