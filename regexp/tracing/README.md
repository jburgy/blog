# tracing

This folder stops the [regexp.f browser demo](../web) halfway through matching
`a(b|c)*d` against `abccbcccd` and draws everything that is live at that moment:

- the JavaScript call stack
- the V8 tier running `_start` and the arm64 code V8 generated for it
- linear memory
- the Forth data and return stacks
- Thompson's list of pending states
- the threaded code that `RE"` compiled

The output is [assets/regexp-snapshot.svg](../../assets/regexp-snapshot.svg), which
the Pages deploy serves at `/blog/regexp-snapshot.svg`.

## Usage

You need Node ≥ 24. The scripts use V8 intrinsics (`--allow-natives-syntax`), so
they don't run in a plain browser.

```sh
npm install
npm run all        # check + snap + svg  ->  out.json, snapshot.svg
npm run disasm     # machine code V8 emitted for the shipped forth.wasm -> code.txt
npm run bench      # µs per search on the shipped forth.wasm
npm run publish    # snap, then write ../../assets/regexp-snapshot.svg
```

After you change [tabulate.wast](../../forth/wasm/tabulate.wast), run
`npm run instrument` to regenerate `tabulate.traced.wast`. `npm run check` fails
until you do.

`snap.mjs` takes an optional pattern and subject:
`node --allow-natives-syntax snap.mjs 'l(a|o)b' 'labor'`. `gen.mjs` only draws
the default `a(b|c)*d` / `abccbcccd` snapshot.

## Files

| file | role |
| --- | --- |
| `instrument.mjs` | Derives `tabulate.traced.wast`: imports `trace.step` and calls it with `$cfa $ip $sp $rsp` at the top of `$next` |
| `tabulate.traced.wast` | The instrumented interpreter. It is committed so you can diff it against `tabulate.wast` |
| `snap.mjs` | Runs the demo's own `Matcher`/`Forth` classes and records every NEXT of the first call of `R` (stacks, `RE-NLIST`, subject cursor) plus the JS stack and tiers, into `out.json` |
| `gen.mjs` | Draws step 791 of `out.json` as an SVG with light and dark modes. Asserts on the measured values stop it from drawing a snapshot that no longer matches |
| `bench.mjs` | Times `Matcher.search` on the uninstrumented `forth.wasm` |

`INSTRUMENT=0` makes `snap.mjs` load the shipped `../web/forth.wasm` instead of
the traced build. `disasm` uses that mode, because the trace call would change
the code TurboFan generates.

## Caveats

- Node is used as a stand-in for Chrome, since both use V8. The top two JS frames
  in the SVG (the submit listener and `run()`) come from reading
  [demo.mjs](../web/demo.mjs), not from a trace.
- The arm64 listing in `gen.mjs` is copied by hand from `code.txt` (Node 24.18,
  V8 13.6, Apple silicon). Offsets and registers change with the V8 version and
  the CPU.
- Step 791, the addresses, and the cell offsets in `R` all depend on
  `4th.32.fs`, `regexp.f`, and the glue in `matcher.mjs`. If you edit any of
  these, `gen.mjs` stops with `snapshot mismatch` and its hard-coded labels need
  updating.
- Timings depend on the machine. `bench` reported 20–27 µs per search.
