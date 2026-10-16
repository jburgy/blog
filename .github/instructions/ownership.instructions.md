---
description: Design principles — give per-run state its own class, and hand collaborators the owner rather than closures over its private state
applyTo: '**/*.{mjs,js,ts}'
---

# Extract per-run state into a class

When a function accumulates several `let` locals plus closures that mutate them (a stream source, a
write sink, counters, flags), and that state is recreated on every restart/retry, make it a small class
instead. `GuestIO` in `forth/wasm/wasi-repl.mjs` replaced ~35 lines of locals and closures inside
`REPL.#run`.

- The locals become documented fields (`first`, `lines`, `lastWasBarePrompt`, `output`); a fresh
  instance per run resets them all at once, so no manual re-initialisation.
- Callback objects the platform already accepts can be the class itself: `new ReadableStream(io, ...)`
  takes `start`/`pull` as methods, and a sink is `io.write.bind(io)`.
- The owner keeps only a reference to the current instance and exposes per-run values as getters that
  delegate (`REPL.output` -> `#io?.output ?? ""`), so state is never copied or re-synced.
- Per-run results the owner needs afterwards (e.g. `io.lines` to decide respawn vs. stop) are read off
  the instance, not tracked in outer variables.
- Per-run comments move onto the field or method they explain, so the loop body shrinks to control flow.

# Pass the owner, not callbacks into its internals

When a helper needs to know something about the object that created it, give it a reference to that
owner (typed as a minimal `{ readonly x: T }` view) and expose the state as a public getter. Don't hand
it closures like `() => this.#x`, and don't copy state into it that has to be kept in sync.

- Keep private fields private and the getter read-only: encapsulation without callback plumbing.
- Prefer a getter over a public field when writes from outside would bypass teardown (`dispose()`).
- Don't reach for `WeakRef` to express "is the owner gone": it reports GC, not disposal, and is nondeterministic.

Example: `GuestIO` checks `this.repl.disposed`; `REPL` exposes `get disposed()`.
