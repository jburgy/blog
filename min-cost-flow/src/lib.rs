//! Phase 2 min-cost flow prototype.
//!
//! Strategy: do as little as possible ourselves. Min-cost flow on a graph
//! with `n` nodes and `m` edges is just a linear program:
//!
//! ```text
//! minimize    cost^T x
//! subject to  N x = b        (flow conservation, N = signed node-arc
//!                             incidence matrix)
//!             0 <= x <= cap  (capacities)
//! ```
//!
//! and the node-arc incidence matrix of a directed graph is totally
//! unimodular, so (modulo degenerate optima) the LP optimum is already an
//! integral min-cost flow. Rather than hand-rolling a Newton/path-following
//! loop around a Laplacian solver, we hand the whole LP to Clarabel, a
//! mature Apache-2.0-licensed interior-point conic solver written in Rust.
//! Everything below this module is just "build the constraint matrices,
//! call the solver, read back `x`".
use clarabel::algebra::*;
use clarabel::solver::*;

/// A directed edge with a flow capacity and a per-unit cost.
#[derive(Debug, Clone, Copy)]
pub struct Edge {
    pub from: usize,
    pub to: usize,
    pub capacity: f64,
    pub cost: f64,
}

/// A directed network on which to solve min-cost flow.
#[derive(Debug, Clone, Default)]
pub struct Network {
    pub num_nodes: usize,
    pub edges: Vec<Edge>,
}

/// Result of solving min-cost flow.
///
/// `flow` and `objective` are only meaningful when `status` is
/// `SolverStatus::Solved` (or `AlmostSolved`). For any other status
/// (infeasible, unbounded, iteration/time limit, ...) Clarabel repurposes
/// `x`/`obj_val` as an infeasibility certificate, not a flow -- callers must
/// check `status` before trusting `flow`/`objective`.
#[derive(Debug, Clone)]
pub struct FlowResult {
    /// Flow value per edge, in the same order edges were added, each in `[0, capacity]`.
    /// Only valid when `status` is `Solved`/`AlmostSolved`; see struct docs.
    pub flow: Vec<f64>,
    /// Achieved objective value (total cost).
    /// Only valid when `status` is `Solved`/`AlmostSolved`; see struct docs.
    pub objective: f64,
    /// Solver termination status.
    pub status: SolverStatus,
    /// Number of interior-point iterations taken.
    pub iterations: u32,
}

impl Network {
    pub fn new(num_nodes: usize) -> Self {
        Self {
            num_nodes,
            edges: Vec::new(),
        }
    }

    /// Adds a directed edge `from -> to` with the given capacity and cost.
    /// Returns the edge's index (its position in `flow` on solve).
    pub fn add_edge(&mut self, from: usize, to: usize, capacity: f64, cost: f64) -> usize {
        assert!(from < self.num_nodes && to < self.num_nodes);
        assert!(capacity >= 0.0);
        assert!(
            from != to,
            "self-loops are not supported: both triplet entries would land in \
             the same incidence-matrix cell and cancel to 0, silently dropping \
             the edge's conservation constraint"
        );
        self.edges.push(Edge {
            from,
            to,
            capacity,
            cost,
        });
        self.edges.len() - 1
    }

    /// Solves min-cost flow for supply/demand vector `b`:
    /// `b[v] > 0` is supply at `v`, `b[v] < 0` is demand, and `sum(b)` must be 0.
    pub fn min_cost_flow(&self, b: &[f64]) -> FlowResult {
        assert_eq!(b.len(), self.num_nodes, "b must have one entry per node");
        let scale = b.iter().map(|v| v.abs()).sum::<f64>().max(1.0);
        assert!(
            b.iter().sum::<f64>().abs() < 1e-9 * scale,
            "supply/demand must balance (sum(b) == 0)"
        );

        let n = self.num_nodes;
        let m = self.edges.len();

        // No quadratic term: this is a plain LP.
        let p = CscMatrix::<f64>::zeros((m, m));
        let q: Vec<f64> = self.edges.iter().map(|e| e.cost).collect();

        // Flow conservation: N x = b, one row per node, N[v, e] = +1 if e
        // leaves v, -1 if e enters v.
        let mut rows = Vec::with_capacity(2 * m);
        let mut cols = Vec::with_capacity(2 * m);
        let mut vals = Vec::with_capacity(2 * m);
        for (j, e) in self.edges.iter().enumerate() {
            rows.push(e.from);
            cols.push(j);
            vals.push(1.0);
            rows.push(e.to);
            cols.push(j);
            vals.push(-1.0);
        }
        let incidence = CscMatrix::new_from_triplets(n, m, rows, cols, vals);

        // Capacities: 0 <= x <= cap, written as [-I; I] x + s = [0; cap], s >= 0.
        let mut neg_identity = CscMatrix::<f64>::identity(m);
        neg_identity.negate();
        let pos_identity = CscMatrix::<f64>::identity(m);
        let bounds = CscMatrix::vcat(&neg_identity, &pos_identity).unwrap();

        let a = CscMatrix::vcat(&incidence, &bounds).unwrap();
        let mut rhs = b.to_vec();
        rhs.extend(std::iter::repeat_n(0.0, m));
        rhs.extend(self.edges.iter().map(|e| e.capacity));

        let cones = [ZeroConeT(n), NonnegativeConeT(2 * m)];

        let settings = DefaultSettingsBuilder::default()
            .equilibrate_enable(true)
            .verbose(false)
            .build()
            .expect("valid solver settings");

        let mut solver =
            DefaultSolver::new(&p, &q, &a, &rhs, &cones, settings).expect("well-formed LP");
        solver.solve();

        FlowResult {
            flow: solver.solution.x.clone(),
            objective: solver.solution.obj_val,
            status: solver.solution.status,
            iterations: solver.solution.iterations,
        }
    }
}
