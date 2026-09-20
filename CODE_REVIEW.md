# Python review — aoc2024, aoc2025, foo/bar

Four independent senior-DS reviews, 2026-09-20. 44 files. Priority order was
readability > correctness > performance. **No patches were requested or written** — this is
lessons + a package design.

**How to use this in a fresh session:** say *"do suggestion #S4"* (or `#S4`, `#L7`).
Every S-item below is self-contained: what to build, why, which files it fixes, the design
decisions already settled, and how to know it worked. Facts here were measured, not guessed.

---

## Scoreboard

| Slice | Files | Both parts printed | Verified defects | Worst runtime |
|---|---|---|---|---|
| aoc2024 d1–12 | 12 | 8 | day11 prints **wrong** part 1; day6 computes part 2 then `pass` | day6 **>600 s**, day7 160 s |
| aoc2024 d13–25 | 13 | 8 | day24 part 2 is a hand-derived constant; day23 uses an approximation algo for an exact question | day22 **46.9 s**, day18 29.1 s |
| aoc2025 | 13 | 6 | day12 is an area heuristic, not a tiling test | day10 10.8 s |
| foo/bar | 6 | n/a | **bunnies_escape is broken** (below) | guard_fight 10.3 s; `import` runs 14.5 s of asserts |

Nothing is tested: `aoc2024`, `aoc2025`, `foo` are all in `collect_ignore` in
[conftest.py](conftest.py). Zero known-answer assertions exist in any of the four directories.

### Verified defects (measured, not inferred)

- **foo/bar/bunnies_escape.py** — `paint()` is DFS (`stack.pop()` + visited, no relaxation) where
  shortest-path was required: wrong on **312/2271** solvable random grids. Its `done=True` fast path
  is wrong **~75%** of the time; `solution([[0,0,0],[0,1,0],[0,0,0]])` returns 3, true answer 5
  (below the Manhattan lower bound). Also mutates the caller's grid. Both of its asserts pass.
- **aoc2024/day11.py** — prints 98208915 for part 1; correct is 183435. The correct 9-line
  `@functools.cache` version is sitting in the module docstring, unused. Root cause: `if all(counts)`
  as a presence test where `if None not in counts` was meant.
- **aoc2024/day22.py** — 46.9 s with NumPy; a plain-Python version (base-19 packed deltas, per-buyer
  `seen` set) gives identical answers in 14.4 s. NumPy made it 3.2× slower.
- **foo/bar/guard_fight.py** — float `abs()` comparisons; exact integer `x*x+y*y` is both correct
  *and* 1.5× faster (6.85 s vs 10.3 s).
- **aoc2025/day10.py** — `int(sum(sol.x))` truncates MILP output. Exact on this input by luck.

---

## Lessons

- **L1 — The dedup rule and the pop order are the algorithm; `while q:` doesn't tell you which one you wrote.**
  Four visually identical loops, four semantics: bunnies_escape `paint` (component-labelling variant,
  wrong), day12 (flood fill, correct), day20 (`pop()` + `if d[i] < k: continue` — that's SPFA, not BFS),
  day10 (*no* visited set, deliberately, because it counts paths). You have a `while q` habit, not a BFS habit.
- **L2 — Run-the-file-get-both-answers is your only regression test and you don't have it.**
  ~11 files: day6 `pass`, day3/day13/aoc2025-day3 need a source edit, day14 builds `counts` and never
  calls `math.prod`, day8/day18 never print part 1, aoc2025/day10 has part 1 commented out.
- **L3 — Input properties that make your code correct are invariants: derive or assert them.**
  day15 stride `100` (grid is exactly 50 wide), day16 computes start/goal from `len(lines)` instead of
  finding `S`/`E`, day12 `[-1] * len(areas)` indexed by *column* (works only because 613 > 140),
  aoc2025/day7 `new_beams[i-1]` wraps if a `^` hits column 0, day20 has no column bounds check.
  All silent wrong answers, not crashes. day20 derives its width correctly with `lines.index("\n")` —
  you already know the move.
- **L4 — A `cast` / `ignore` / defensive `assert isinstance` is a bug report about your data structure.**
  Six files in d1–12 alone. day9's `[free, (id,size), …]` positional heterogeneous list (3 casts,
  2 ignores), day24's dict holding both gates and bits, day8 leaking loop vars via `for/else`,
  day21's `float("inf")` forcing `int | float` through an integer DP table.
- **L5 — When you've already written the clean version, ship it.** day11, above.
- **L6 — NumPy pays only if the *hot* loop is vectorised.** day22, above. day14 is the counterexample
  done right (`ndimage.label` on a full array). Same family: importing numpy for `base_repr` in day7.
- **L7 — Don't recompute a maintainable invariant; don't linear-scan a monotone predicate.**
  aoc2025/day8 `sum(circuit != set() for …) == 1` per union = 999k comparisons + 1000 set allocations
  to recompute what `-= 1` maintains. day18 re-runs BFS ~2000× (29.1 s) where `bisect` is ~11 calls.
  day6 retries obstacles on all 16k cells instead of the 5k path cells it already computed.
- **L8 — Comment the inversion, not the operation.** Near-zero comment density is fine; the gap is
  that the places where correctness hinges on a backwards-guessable convention have *no* comment:
  aoc2025/day11 passes a **successor** map to `TopologicalSorter`, which reads it as **predecessors**
  (that inversion is why it works); aoc2025/day8 relies on `np.fromiter(combinations(...))` matching
  `pdist` condensed order; guard_fight's parity tables; day25's `< 8`.
- **L9 — No `sqrt` to compare lengths; no `int()` on solver output.** guard_fight, aoc2025/day10.
- **L10 — One value, one meaning.** day6 `mark() -> list | None` (grid *or* loop-detected), day10
  `complex(len(score), rating)`, day18's grid as wall map + visited set + 1-based distance array.
- **L11 — Density is not concision.** aoc2025/day6 `second_half` is a 10-line expression with two
  off-by-ones inside; aoc2025/day2's `int(end[: prefix + len(end) - len(start)])`; day15's
  `cast(tuple[int,int], x.__divmod__(100))` ×24. Test: *can you breakpoint the interesting sub-step?*
  Your two best files (day19, day20) are your two most boring-looking ones.
- **L12 — Complex numbers are for rotation. If you never multiply it, it's a tuple.** Earned: day6,
  day16 (`v * 1j` *is* "turn"), guard_fight. Not earned: bunnies_escape needs `_get`/`_set`/`inside`
  + six `int(x.real)` casts to undo the choice; day21 only subtracts. Also day16 is `real=row` while
  day21 is `real=x` — opposite conventions, same directory.
- **L13 — Your stdlib misses cluster at the end of the file.** `math.prod` (day14 — would have printed
  part 1), `bisect` (day18 — the 200× win), the second `print`. You use `graphlib`, `linprog(integrality=1)`,
  `pdist`, `shapely.prepare`, `sumprod`, `cmp_to_key`, `IntFlag` correctly. These aren't knowledge gaps,
  they're wrap-up-phase gaps.
- **L14 — Finish renames, and lint.** `li`/`lj` name a parameter `l` that no longer exists;
  `min_times_i` names an array called `dist`; `next` shadows the builtin in the same file; `random`
  shadows the module in day22; aoc2025/day1 has two dead locals in 22 lines; day24 has 25 lines of
  dead ripple-carry adder. `ruff` with `F` is already configured in [pyproject.toml](pyproject.toml)
  and catches most of it — these directories aren't being linted.

---

## Suggestions

A package `puzzlekit`, installed (not path-hacked) so imports work regardless of cwd — every file
in all four directories currently hardcodes a path relative to the repo root.

**Built: <https://github.com/jburgy/puzzlekit>.** Prior-art pass (2026-09-20, verified against the
blog `.venv`) killed three of the seven proposed modules outright, so the shipped package is:

```
src/puzzlekit/
    io.py      ints/sections/lines/text          → S1 (thin; aocd covers more)
    search.py  explore() + dijkstra()            → S3  ← the only substantial module
    grid.py    Grid, ray()                       → S4 (list[str] case only)
    vec.py     Vec NamedTuple                    → S5
    bits.py    bits()                            → S7 (reduced to one function)
```

Dropped: **S2 → `aocd`**, **S6 → `scipy.cluster.hierarchy.DisjointSet`**, **S8 → `sys.maxsize`**.
Ordered by leverage. S1 is justified by all 44 files; S3 by 2024 + foo/bar only (**aoc2025 contains
zero frontier loops** — that year pushed you to union-find, DAG path counting and integer
programming instead).

### Prior art — check before writing anything

| Want | Already exists |
|---|---|
| union-find | `scipy.cluster.hierarchy.DisjointSet` — `merge()` returns bool, `n_subsets` maintained, union-by-size. **Verified: exactly the S6 API.** |
| integer infinity | `sys.maxsize` |
| popcount / bit width | `int.bit_count()` (3.10), `int.bit_length()` |
| pack/unpack bit arrays | `np.packbits` / `np.unpackbits` |
| sentinel border | `np.pad(g, 1, constant_values="#")` |
| flood fill / regions | `scipy.ndimage.label` |
| neighbour *counting* | `scipy.ndimage.convolve` with a 3×3 kernel — no bounds test at all |
| fixed-window scans | `np.lib.stride_tricks.sliding_window_view` |
| iterate a grid | `np.ndenumerate`, `np.argwhere(g == ch)` |
| Dijkstra on an **explicit** graph | `scipy.sparse.csgraph.dijkstra(..., return_predecessors=True, min_only=, limit=)`; `networkx`; `rustworkx` |
| topological order | `graphlib.TopologicalSorter` |
| AoC input fetch + answer verification | `aocd` (advent-of-code-data) — `from aocd import data, numbers`, plus an `aoc` runner that checks every day against known answers |
| extract integers | `re.findall(r"-?\d+", s)` |
| monotone-predicate search | `bisect` |
| memoization | `functools.cache` |

The lesson, consistent with L13: **three of seven proposed modules already existed**, and the one
that matched most exactly (S6) lives in a package this repo already imports.

### S1 — `puzzlekit/io.py`

```python
def text(day: int) -> str            # Path(caller.__file__).parent / f"day{day}input.txt"
def lines(day: int) -> list[str]     # .splitlines()
def sections(text: str) -> list[list[str]]   # split on blank lines
def ints(s: str) -> list[int]        # re.findall(r"-?\d+")
```

`ints()` alone replaces parsing in day1, day2, day7, day13, day14, day18, aoc2025 days 2/5/8/9/10,
and removes every `[1:-1]` bracket-strip in the repo. `sections()` replaces day5's `if/elif` state
machine (and its pyright suppression) and the `None`-as-mode-flag in day15, day25, aoc2025/day12.
`splitlines()` is the quiet win — strip discipline is currently spelled four ways in 2024 and three
in 2025, and one of them (`.strip()` on column-aligned data, aoc2025/day6) is a live hazard.
Path must derive from the *caller's* `__file__`, not cwd.

*Prior art:* `ints()` is a one-line `re.findall`; **`aocd` supersedes `text`/`lines`** entirely
(per-day caching, `aocd.examples`). Kept anyway because the puzzle files are already on disk and
`aocd` needs a session token.

### S2 — a two-part runner — **don't build it, use `aocd`**

The shape wanted was `solve(parse, part1, part2, *, expect=(a, b))`: parse once, print both,
`assert` against known answers. `aocd`'s `aoc` runner already does exactly this, including the
`expect` mechanism, and is actively maintained — so this is a dependency decision, not a coding
task.

Whatever the mechanism, it mechanically catches every L2 case and kills the import-time side
effects that make every file unusable from a REPL. Pair with dropping `aoc2024`/`aoc2025`/`foo`
from `collect_ignore` —
`--doctest-modules` is already in `addopts`, so foo/bar's six blocks of module-level asserts become
live tests by turning `assert solution(x) == y` into `>>>`. Also removes 14.5 s from
`import guard_fight` and makes them survive `python -O`.

### S3 — `puzzlekit/search.py` — the one module with no prior art

Every library option (`scipy.sparse.csgraph`, `networkx`, `rustworkx`) needs a **materialised**
graph. For implicit state spaces — day16's `(pos, heading)`, day6's `(pos, dir)` — building a
`csr_matrix` first is more code than the loop. The lazy `succ` callable is the gap, and it is ~40
lines. (`python-pathfinding`, `simpleai`, `astar` exist on PyPI; unmaintained or grid-specific,
not worth the dependency.)

Two functions, not one (the reviewers split on the return shape; this is the resolution):

```python
def explore(starts, succ, *, order: Literal["fifo","lifo","priority"],  # NO DEFAULT
            key: Callable[[S], Hashable] | None = identity) -> Iterator[tuple[S, C]]

def dijkstra(starts, succ, *, goal=None) -> tuple[dict[S, C], dict[S, list[S]]]
```

Settled design decisions, each traceable to a failure:
- **`order` has no default.** The whole bunnies_escape bug is `lifo` where `fifo` was needed; any
  default reproduces it.
- **`key=None` disables dedup entirely.** That one parameter separates day10 (must *not* dedupe),
  day12 (dedupe by position) and day6 (dedupe by `(pos, direction)`). A hardcoded `seen: set[Pos]`
  breaks three of four callers.
- **`succ` yields `(state, cost)` and owns all domain logic** — bounds, walls, turn costs. It's the
  only thing differing between day16 (1 or 1001), day18, day20, `paint()`. Forces push-time
  filtering, which deletes day12's four-clause post-pop predicate and day20's missing column check.
- **`dijkstra` returns predecessors unconditionally.** day16 part 2 is currently a second hand-copied
  traversal with a differently-signed prune, materialising growing path tuples; with preds it's a
  backward walk. Same mechanism subsumes running_with_bunnies' Floyd–Warshall `next` matrix.
- **`explore` is a generator** so callers keep plain locals: day10 needs `score.add(y)` *and*
  `rating += 1` per visit; day12 needs `area += 1` *and* a label write. A callback returning one
  value can't express either without closure gymnastics.

Explicitly **out of scope**: aoc2024/day11's worklist. It looks like a graph search but is a
hand-rolled trampoline for recursive memoization → `functools.cache`. Rule worth writing down:
*use `@cache` unless you've measured depth exceeding the recursion limit.* Depth there was 75.

### S4 — `puzzlekit/grid.py`

```python
class Grid(Generic[T]):
    def __contains__(self, p) -> bool          # replaces `0 <= y.real < m and 0 <= y.imag < n` ×6
    def get(self, p, default="#") -> T         # bounds-check + fetch; the actual common case
    def cells(self) -> Iterator[tuple[Vec, T]] # replaces the nested enumerate in ~8 files
    def find(self, ch) -> Vec                  # day6's `^`; kills the `find(...) > 0` bug outright
    def neighbors(self, p, deltas=ORTHOGONAL) -> Iterator[tuple[Vec, Vec, T]]
```

Three non-obvious requirements, each from a real bug:
- **`pad` sentinel border** kills aoc2025/day4's per-cell bounds test and aoc2025/day7's
  negative-index wrap in one move.
- **`neighbors` yields the delta alongside the position** — that's what collapses day12's four `if`
  blocks (each pairing a direction with a named `Side` flag) into one loop + a `dict[Vec, Side]`.
- **`__getitem__` raises off-grid, never wraps.** Python's negative-index silence is the shared root
  of day20's row-wrap, day18's negative enqueues, aoc2025/day7's column-0 wrap.

Plus a separate primitive `ray(grid, start, delta)` walking until out of bounds: replaces both of
day8's `while True: … else: break` blocks and all four of day4's mutually inconsistent
word-extraction idioms (string slice / `itemgetter` / two hand-written loops — in one loop body).

*Prior art, and it reframes the problem:* numpy/scipy already cover the **vectorisable** cases —
`np.pad` is the sentinel border, `ndimage.label` is flood fill, `ndimage.convolve` with a 3×3 kernel
is 8-neighbour counting with no bounds test whatsoever (the Game-of-Life trick — that's
aoc2025/day4), `sliding_window_view` is day4's word search and day22's windows. Several of these
aren't "write a better `Grid`", they're **stop looping**. `Grid` is scoped to the per-cell walk
(day6's guard, ray casting) where numpy doesn't help.

### S5 — `puzzlekit/vec.py`

`Vec(NamedTuple)` with `rot(quarter_turns)` and `norm2() -> int`. `norm2` returning `int` makes
guard_fight's float bug unrepresentable; a NamedTuple is ~2× cheaper as a dict key than `complex`.
Fix **one** axis convention repo-wide and state it in the module docstring — you currently have both.

*Prior art:* none. `complex` is the stdlib answer and carries L12's float/cast problems;
`pygame.math.Vector2` is float; `shapely`/`sympy` are heavy. ~15 lines, justified.

### S6 — union-find — **obsolete, use `scipy.cluster.hierarchy.DisjointSet`**

Verified in the blog `.venv`: `merge(a, b)` returns `True`/`False` and `n_subsets` is a maintained
attribute — i.e. exactly the two things aoc2025/day8's hand-rolled version lacked, and the entire
fix for its 999k-comparison scan (L7). Union-by-size and path halving come free. scipy is already a
dev dependency. (`networkx.utils.UnionFind` also exists but is weaker: `union` returns `None`, no
component count.) **Do not write this module.**

### S7 — `puzzlekit/bits.py` — reduced to one function

`int.bit_count()` (3.10) is popcount, `int.bit_length()` is width, `np.packbits`/`unpackbits` are
pack/unpack. Only `bits(n)` — iterate set-bit indices — has no equivalent, and it is three lines.
It still earns its place: aoc2025/day10 has **three** spellings of bitmask construction in one file
including `bin(word)[:1:-1]`, and expanding_nebula currently has no way to *print* a DP state while
debugging.

### S8 — one integer sentinel: **`sys.maxsize`**, never `float("inf")`

Four spellings today: `len(grid)` (day20), `float("inf")` leaking into an int DP table (day21),
`.get() is None` (day16), and day18's in-band overload where 0 means unvisited so distances are
1-based. The in-band ones are where the bugs live — and day18's distances end up unused anyway,
since the only question ever asked is `grid[-1][-1] == 0`.

### S9 — Grids never double as distance maps

day18, same file as S8: three meanings in one array.

### S10 — Turn on the linter for these directories

`ruff` with `F` is already configured in [pyproject.toml](pyproject.toml). Adding the `ARG`/`B`
families catches aoc2025/day1's dead locals, day5's builtin shadow, day10's dead code, and L14's
rename fossils — no judgement calls needed.

### S11 — Migrate one directory as a pilot

Don't retrofit 44 files. aoc2025 is the smallest and has no frontier loops, so it exercises S1/S2/S10
cleanly without blocking on S3. Alternative pilot if the goal is to prove S3: aoc2024 days 10, 12,
16, 18, 20 — the five files whose search loops span all the axes.

### S12 — Fuzz against a dumb reference when one is cheap

The nine-line BFS reference that found the bunnies_escape bug took under a minute to write. Two
examples from a problem statement are not a test suite — bunnies_escape passes both of its asserts
and is wrong on roughly half of all solvable grids.

---

<!-- breadcrumb for a future session:
     Source reviews were four parallel subagents (senior-DS persona) over aoc2024 d1-12, aoc2024
     d13-25, aoc2025, foo/bar. They were instructed NOT to propose patches — only lessons + a shared
     package design. Timings above are wall-clock on jburgy's machine via .venv/bin/python from the
     repo root. If asked to "do suggestion #SN", the S-item is self-contained; re-read the cited
     files before writing code.

     STATUS 2026-09-20: puzzlekit HAS BEEN BUILT -> github.com/jburgy/puzzlekit (local clone at
     ~/puzzlekit, uv + src layout). S1/S3/S4/S5/S7 are implemented there with tests derived from
     the verified defects above and examples derived from the review's use cases. S2/S6/S8 were
     deliberately NOT built (aocd / scipy DisjointSet / sys.maxsize). Nothing in aoc2024, aoc2025 or
     foo/bar has been touched — S9-S12 are still open, and S11 (pilot migration) is the next step. -->
