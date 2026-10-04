// Ambient host I/O for the original (custom getchar/putchar) build. @external
// pins the wasm import's module/name to "index"/"getchar"/"putchar" no
// matter which file declares it, so lisp.worker.js's existing
// `{ index: { getchar, putchar } }` import object keeps working unchanged
// even though index.ts itself no longer declares these directly (see
// core.ts and package.json's --use flags for why).
@external("index", "getchar")
export declare function getchar(): i32;

@external("index", "putchar")
export declare function putchar(c: i32): void;
