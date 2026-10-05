//! Cross-checks `Network::min_cost_flow` against an independent, textbook
//! successive-shortest-augmenting-path reference implementation on random
//! small DAGs. This is deliberately a different algorithm (combinatorial,
//! not an LP/IPM) so a bug shared between the two would be surprising.
use min_cost_flow::Network;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

/// Bare-bones residual graph for successive shortest paths (Bellman-Ford
/// based, so it tolerates the negative-cost reverse edges SSP creates).
struct Residual {
    adj: Vec<Vec<usize>>,
    from: Vec<usize>,
    to: Vec<usize>,
    cap: Vec<f64>,
    cost: Vec<f64>,
}

impl Residual {
    fn new(n: usize) -> Self {
        Self {
            adj: vec![Vec::new(); n],
            from: Vec::new(),
            to: Vec::new(),
            cap: Vec::new(),
            cost: Vec::new(),
        }
    }

    /// Adds a forward/backward edge pair. Must always be called this way
    /// (never pushing a single edge directly into `to`/`cap`/`cost`):
    /// `successive_shortest_paths` finds a forward edge `e`'s reverse with
    /// `e ^ 1`, which only works because every pair lands at indices
    /// `(2k, 2k+1)`.
    fn add_edge(&mut self, u: usize, v: usize, cap: f64, cost: f64) {
        let fwd = self.to.len();
        self.from.push(u);
        self.to.push(v);
        self.cap.push(cap);
        self.cost.push(cost);
        self.adj[u].push(fwd);

        let bwd = self.to.len();
        self.from.push(v);
        self.to.push(u);
        self.cap.push(0.0);
        self.cost.push(-cost);
        self.adj[v].push(bwd);
    }

    /// Returns the total cost of a min-cost flow of value `expected_flow`
    /// from `s` to `t`. Panics if the network cannot actually route that
    /// much flow, so an infeasible instance fails loudly here instead of
    /// silently comparing a partial flow's cost against the LP's answer.
    fn successive_shortest_paths(&mut self, s: usize, t: usize, expected_flow: f64) -> f64 {
        let n = self.adj.len();
        let mut total_cost = 0.0;
        let mut total_flow = 0.0;
        loop {
            let mut dist = vec![f64::INFINITY; n];
            let mut prev_edge = vec![None; n];
            dist[s] = 0.0;
            // Bellman-Ford: n-1 relaxation rounds is enough since there are no
            // negative cycles (SSP invariant).
            for _ in 0..n {
                let mut changed = false;
                for e in 0..self.to.len() {
                    if self.cap[e] <= 1e-9 {
                        continue;
                    }
                    let u = self.from[e];
                    let v = self.to[e];
                    if dist[u].is_finite() && dist[u] + self.cost[e] < dist[v] - 1e-9 {
                        dist[v] = dist[u] + self.cost[e];
                        prev_edge[v] = Some(e);
                        changed = true;
                    }
                }
                if !changed {
                    break;
                }
            }
            if prev_edge[t].is_none() {
                break; // no more augmenting path: done
            }

            // Walk back from t to s, finding the bottleneck capacity.
            let mut bottleneck = f64::INFINITY;
            let mut v = t;
            while v != s {
                let e = prev_edge[v].unwrap();
                bottleneck = bottleneck.min(self.cap[e]);
                v = self.from[e];
            }

            let mut v = t;
            while v != s {
                let e = prev_edge[v].unwrap();
                self.cap[e] -= bottleneck;
                self.cap[e ^ 1] += bottleneck;
                v = self.from[e];
            }
            total_cost += bottleneck * dist[t];
            total_flow += bottleneck;
        }
        assert!(
            (total_flow - expected_flow).abs() < 1e-6,
            "reference SSP routed {total_flow}, expected {expected_flow}: instance is infeasible"
        );
        total_cost
    }
}

fn reference_min_cost(net: &Network, supply: f64) -> f64 {
    let s = net.num_nodes;
    let t = net.num_nodes + 1;
    let mut g = Residual::new(net.num_nodes + 2);
    for e in &net.edges {
        g.add_edge(e.from, e.to, e.capacity, e.cost);
    }
    g.add_edge(s, 0, supply, 0.0);
    g.add_edge(net.num_nodes - 1, t, supply, 0.0);
    g.successive_shortest_paths(s, t, supply)
}

#[test]
fn random_small_dags_match_reference_ssp() {
    let mut rng = StdRng::seed_from_u64(0xC0FFEE);

    for _ in 0..200 {
        let n = rng.gen_range(3..=7);
        let supply = rng.gen_range(1..=5) as f64;

        let mut net = Network::new(n);
        // Guarantee feasibility with a direct source->sink edge, then add
        // random alternative/competing routes.
        net.add_edge(0, n - 1, supply, rng.gen_range(0..=5) as f64);
        for u in 0..n {
            for v in (u + 1)..n {
                if rng.gen_bool(0.5) {
                    let cap = rng.gen_range(1..=(supply as i64).max(1)) as f64;
                    let cost = rng.gen_range(0..=5) as f64;
                    net.add_edge(u, v, cap, cost);
                }
            }
        }

        let mut b = vec![0.0; n];
        b[0] = supply;
        b[n - 1] = -supply;

        let expected = reference_min_cost(&net, supply);
        let result = net.min_cost_flow(&b);

        assert!(
            (result.objective - expected).abs() < 1e-3,
            "n={n} supply={supply}: clarabel={} reference={}",
            result.objective,
            expected
        );
    }
}
