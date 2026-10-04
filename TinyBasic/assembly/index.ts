// Entry point for the original build: pulls host.ts's ambient ScreenChar/
// KeyInChar/OutStr into the compiled module (asc's --use flag, see
// package.json, resolves core.ts's free identifiers of the same names to
// these) and re-exports core.ts's public API unchanged. See wasi.ts for the
// real-WASI counterpart built from the same core.ts.
import { ScreenChar, KeyInChar, OutStr } from "./host";

export { ColdGo, ILfront, BadOp, Poke2, ColdStart, Interp } from "./core";
