use min_cost_flow::Network;
use clarabel::solver::SolverStatus;

/// Classic three-parallel-path network where every source-to-sink path
/// costs exactly 3 per unit, so the optimal objective is pinned down
/// (30 for 10 units) even though the optimal *edge* flows are not unique.
///
///      ,--1--> (1) --2--.
///     /                  \
///  (0)---------1---------->(3)
///     \                  /
///      `--2--> (2) --1--'
///  plus a cross edge (1)->(2) with cost 1 (also keeps every path at cost 3)
#[test]
fn three_tied_paths_textbook_example() {
    let mut net = Network::new(4);
    net.add_edge(0, 1, 10.0, 1.0); // 0->1
    net.add_edge(0, 2, 10.0, 2.0); // 0->2
    net.add_edge(1, 3, 10.0, 2.0); // 1->3
    net.add_edge(2, 3, 10.0, 1.0); // 2->3
    net.add_edge(1, 2, 5.0, 1.0); // 1->2

    let b = vec![10.0, 0.0, 0.0, -10.0];
    let result = net.min_cost_flow(&b);

    assert_eq!(result.status, SolverStatus::Solved);
    assert!(
        (result.objective - 30.0).abs() < 1e-4,
        "expected objective 30, got {}",
        result.objective
    );

    // Flow conservation and capacity feasibility must hold regardless of
    // which optimal vertex the interior-point method lands on.
    assert_feasible(&net, &b, &result.flow);
}

#[test]
#[should_panic(expected = "self-loops are not supported")]
fn self_loop_rejected() {
    let mut net = Network::new(2);
    net.add_edge(0, 0, 1.0, -1.0);
}

/// Pins down the `FlowResult` contract documented on the struct: when the
/// requested demand exceeds every path's capacity, `status` must report
/// infeasibility rather than `Solved`, so callers who check `status` first
/// never mistake the accompanying certificate for a real flow.
#[test]
fn infeasible_demand_reports_infeasible_status() {
    let mut net = Network::new(2);
    net.add_edge(0, 1, 5.0, 1.0); // only 5 units of capacity available

    let b = vec![10.0, -10.0]; // but 10 units are demanded
    let result = net.min_cost_flow(&b);

    assert_ne!(result.status, SolverStatus::Solved);
}

fn assert_feasible(net: &Network, b: &[f64], flow: &[f64]) {
    let mut net_out = vec![0.0; net.num_nodes];
    for (edge, &x) in net.edges.iter().zip(flow) {
        assert!(x >= -1e-6 && x <= edge.capacity + 1e-6, "capacity violated");
        net_out[edge.from] += x;
        net_out[edge.to] -= x;
    }
    for (v, (&actual, &expected)) in net_out.iter().zip(b).enumerate() {
        assert!(
            (actual - expected).abs() < 1e-4,
            "conservation violated at node {v}: flow balance {actual}, expected {expected}"
        );
    }
}
