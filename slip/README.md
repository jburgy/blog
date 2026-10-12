# SLIP, the lazy way

[SLIP](https://en.wikipedia.org/wiki/SLIP_(programming_language))
(Symmetric LIst Processor) is Joseph Weizenbaum's 1960s list-processing
library, best known as the substrate [ELIZA](https://en.wikipedia.org/wiki/ELIZA)
was written in. It was never a standalone language: it was a set of FORTRAN
"accessor" subroutines (later embedded in MAD and ALGOL) operating on
circular, doubly-linked lists of fixed-size cells. A sketch of what it
looked like in Lisp, a contemporaneous but very different approach to the
same problem, lives in [`../lisp/eliza.lisp`](../lisp/eliza.lisp).

This folder asks the opposite-of-historical question: what does SLIP look
like if you build it today, in Rust, reusing as much of `std` and the crate
ecosystem as possible instead of hand-rolling pointer-chasing subroutines?

## What maps onto `std` directly

| SLIP concept | Rust answer |
|---|---|
| Header with reference count | `Rc`/`Arc` (not used here -- see below) |
| Sublist indicator cell | an enum variant (`Payload::Sublist`), no crate needed |
| Reader (independent scan cursor) | an `Iterator` impl |

## What needed a crate, and why `intrusive-collections`

SLIP cells were fixed-size records sitting in a FORTRAN array, mutated in
place via pointer-chasing subroutines, with the NEXT/PREV fields baked
right into the record. That's the opposite of a persistent,
structural-sharing list like the [`im`](https://docs.rs/im) crate, which
allocates fresh nodes on every "mutation" and shares the rest. It's a close
match for [`intrusive-collections`](https://docs.rs/intrusive-collections),
which embeds the link fields directly in [`Cell`](src/lib.rs) and gives
O(1) push/pop/splice on existing storage via cursors -- see
[`src/lib.rs`](src/lib.rs).

### The reader is a history stack

Wikipedia's one-line description of SLIP's reader is the most interesting
detail: *"essentially a state history stack -- a good example of a memento
pattern -- where each cell pointed to the header of the list being read,
the current position within it, and the level ... of the history stack."*

[`Reader`](src/lib.rs) implements that literally: it holds one
`intrusive_collections::linked_list::Cursor` per nesting level. Descending
into a sublist pushes a new cursor (the parent's position is already saved,
since its own cursor remembers it); exhausting a level pops back to resume
the parent exactly where it left off. `Reader::depth` is the "level" from
the quote. Because each `Reader` only holds `&'a` borrows into the list,
several of them can scan the same list independently and concurrently --
the Rust borrow checker enforces, at compile time, the same "don't mutate
out from under an active reader" discipline SLIP's unchecked FORTRAN
pointers left to the programmer.

## What was cut

Real SLIP let several parent cells share one sublist header, using its
refcount to free it once the last reference dropped. This sketch's
`Payload::Sublist` is single-owner (embedded by value) -- see the
`ponytail:` comment in [`src/lib.rs`](src/lib.rs) for the upgrade path
(`Rc<RefCell<List>>`) if sharing is ever actually needed.

## Testing

[`tests/reader.rs`](tests/reader.rs) covers the history-stack mechanics
directly: two readers over the same list, one descending into a sublist
while the other is untouched.

[`tests/eliza.rs`](tests/eliza.rs) exercises the one ELIZA-relevant trick:
a decompose/reassemble rule (`"I NEED X"` -> `"WHAT WOULD IT MEAN TO YOU IF
YOU GOT X"`, from Weizenbaum's original DOCTOR script) where the captured
fragment `X` is spliced into the reply as a nested sublist, and `Reader`
auto-flattens it back into one sentence.

```sh
cd slip && cargo test
```

## Running ELIZA

[`src/eliza.rs`](src/eliza.rs) is a complete (if trimmed-down) DOCTOR on top
of these lists: keyword ranks, `0`-wildcard decomposition patterns, numbered
reassembly slots that splice the reflected capture in as a `Sublist`, cycling
templates, and a `NONE` fallback. Type `bye` to quit.

```sh
cd slip && cargo run
```

### In the browser

[`web/`](web) is a no-dependency HTML5 version of the same thing, styled like an IPython session. `src/web.rs` exports three C-ABI functions (no wasm-bindgen), [`web/worker.mjs`](web/worker.mjs) loads the module in a web worker, and [`web/index.html`](web/index.html) is a plain `<form>` that appends one `<li>` per turn (statement plus reply) to an `<ol>` whose markers are `[1]`, `[2]`, ...

```sh
cd assets && make slip && python3 -m http.server   # then open /slip/
```
