// Ambient host I/O for the original (custom ScreenChar/KeyInChar/OutStr)
// build. @external pins each wasm import's module/name to "index"/<name> no
// matter which file declares it, so TinyBasic.worker.js's existing
// `{ index: { ScreenChar, KeyInChar, OutStr } }` import object keeps working
// unchanged even though index.ts itself no longer declares these directly
// (see core.ts and package.json's --use flags for why).
type T = u16;

@external("index", "ScreenChar")
export declare function ScreenChar(ch: T): void;

@external("index", "KeyInChar")
export declare function KeyInChar(): T;

@external("index", "OutStr")
export declare function OutStr(theMsg: u8): void;
