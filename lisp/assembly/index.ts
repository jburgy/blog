// Entry point for the original build: pulls host.ts's ambient getchar/
// putchar into the compiled module (asc's --use flag, see package.json,
// resolves core.ts's free getchar/putchar identifiers to these) and
// re-exports core.ts's main unchanged. See wasi.ts for the real-WASI
// counterpart built from the same core.ts.
import { getchar, putchar } from "./host";

export { main } from "./core";
