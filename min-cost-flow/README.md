# Min-cost flow, the lazy way

Minimum-cost flow has a famous "almost-linear time" algorithm
([Chen, Kyng, Liu, Peng, Probst Gutenberg, Sachdeva, FOCS 2022](https://arxiv.org/abs/2203.00671);
refined by [van den Brand, Chen, Kyng, Liu, Meierhans, Probst Gutenberg,
Sachdeva, FOCS 2024](https://arxiv.org/abs/2407.10830)), built from an
interior-point method (IPM) whose Newton step is a Laplacian solve, wrapped
in a dynamic expander-decomposition data structure that answers each step in
amortized $`m^{o(1)}`$ time. That data structure alone is a multi-year
research-engineering project with no public implementation, so this crate
does not attempt it.

What it keeps from the real algorithm is the one-sentence idea that
survives contact with practicality: **min-cost flow is an LP, and an IPM
solves LPs by repeated Newton steps on a barrier function.** Rather than
writing that Newton loop by hand, this crate hands the whole LP to
[Clarabel](https://github.com/oxfordcontrol/Clarabel.rs), an Apache-2.0,
pure-Rust interior-point conic solver that already does it:

```math
\begin{array}{rl}
\text{minimize}   & \mathrm{cost}^{\mathsf T} x \\
\text{subject to} & N x = b \\
                   & 0 \le x \le \mathrm{cap}
\end{array}
```

where $`N`$ is the signed node-arc incidence matrix (one row per node, one
column per edge, $`+1`$/$`-1`$ where an edge leaves/enters a node) and $`b`$
is the supply/demand vector. $`N`$ is totally unimodular, so the LP optimum
is already an integral min-cost flow (modulo the usual IPM caveat below).

The capacity bounds are encoded as `[-I; I] x + s = [0; cap], s >= 0`
(Clarabel has no dedicated box cone in this version), and the whole program
is [`Network::min_cost_flow`](src/lib.rs) — about 60 lines once the matrix
bookkeeping is stripped out.

## Why no LAPACK/MKL/Accelerate?

Clarabel's default build needs none of them: its KKT solves (the IPM's
Newton/Laplacian-solve step) use its own pure-Rust sparse LDL + AMD
ordering. Those BLAS backends (`sdp-accelerate`, `sdp-mkl`,
`sdp-openblas` — see [`Cargo.toml`](Cargo.toml)) only matter for the dense
factorizations behind Clarabel's SDP cone, which a plain LP never touches.

## Caveat

An interior-point method converges to *a* point in the optimal face, not
necessarily an extreme point/vertex. For degenerate instances (multiple
optimal flows, e.g. several equal-cost paths) the returned flow can land
strictly inside that face and come out fractional even though an integral
optimum exists. [`tests/textbook_example.rs`](tests/textbook_example.rs)
is built around exactly this case: it only asserts the objective value and
feasibility, not specific edge flows. Recovering an exact integral vertex
would need a simplex-style crossover/rounding pass on top of this.

Relatedly, `flow`/`objective` are only meaningful when `status` is
`Solved`/`AlmostSolved` — see the `FlowResult` doc comment in
[`src/lib.rs`](src/lib.rs). For any other status Clarabel repurposes them as
an infeasibility/unboundedness certificate, not a flow.

## Testing

[`tests/random_cross_check.rs`](tests/random_cross_check.rs) cross-checks
Clarabel's objective against an independent, textbook successive-shortest-
augmenting-path reference (Bellman-Ford based) over 200 random small DAGs —
a different algorithm family entirely, so a shared bug would be a
surprise.

```sh
cargo test -p min-cost-flow
```
