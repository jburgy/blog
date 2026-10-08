// A random bond-percolation sample on a finite square lattice, reduced to
// its single equivalent resistor by repeated node elimination -- the
// general technique Frank and Lobb's propagator transformation specialized
// for the square lattice (see jburgy's thesis, Appendix A: "it is more
// efficient to eliminate [nodes] in order of lowest connectivity").
//
// Every present bond is a 1-ohm resistor; absent bonds simply don't exist
// as edges. The network is stored as an adjacency map of conductances
// (Map<id, Map<neighborId, conductance>>) rather than a resistance matrix:
// conductances of parallel edges add directly (no separate "parallel
// reduction" rule needed -- it falls out of always updating the one Map
// entry for a pair instead of allowing duplicates), and eliminating a node
// of degree n is the single star-mesh formula below for every n at once:
// n=0 (isolated node) vanishes with no new edges, n=1 (dangling end)
// likewise, n=2 is the familiar series combination, n>=3 is a general
// Y-Delta (star-mesh) transform. No case analysis, no separate series vs.
// parallel vs. bridge logic.

/** Sentinel ids for the two bus bars (left/right electrodes): negative, so
 * they never collide with the nonnegative row-major ids given to interior
 * nodes by nodeId() below. */
export const TERMINAL_X = -1;
export const TERMINAL_Y = -2;

/** Exact bond-percolation threshold for the 2D square lattice, from
 * self-duality (Sykes & Essam 1964). Analogous to ising's
 * CRITICAL_TEMPERATURE: below it, almost every sample is disconnected
 * (infinite resistance); above it, almost every sample conducts. */
export const PERCOLATION_THRESHOLD = 0.5;

/**
 * Map a grid position to a node id: the leftmost column is the single X
 * terminal, the rightmost column is the single Y terminal (both bus bars,
 * shorted together across every row), and every other column gets its own
 * id, row-major.
 *
 * @param {number} x column, 0 <= x < cols
 * @param {number} y row
 * @param {number} cols lattice width (>= 2)
 * @returns {number} TERMINAL_X, TERMINAL_Y, or a nonnegative interior id
 */
export function nodeId(x, y, cols) {
    if (x === 0) return TERMINAL_X;
    if (x === cols - 1) return TERMINAL_Y;
    return y * cols + x;
}

/**
 * Every interior (non-terminal) node id, in row-major order.
 *
 * @param {number} cols lattice width (>= 2)
 * @param {number} rows lattice height (>= 1)
 * @returns {number[]}
 */
export function interiorNodeIds(cols, rows) {
    const ids = [];
    for (let y = 0; y < rows; y++) {
        for (let x = 1; x < cols - 1; x++) ids.push(nodeId(x, y, cols));
    }
    return ids;
}

/**
 * Add conductance `g` between `a` and `b`, combining with whatever
 * conductance (if any) already connects them -- the "parallel reduction"
 * rule, applied automatically every time an edge is created rather than as
 * a separate step.
 *
 * @param {Map<number, Map<number, number>>} adjacency
 * @param {number} a
 * @param {number} b
 * @param {number} g
 * @returns {number} the resulting total conductance between a and b
 */
function addEdge(adjacency, a, b, g) {
    let na = adjacency.get(a);
    if (!na) adjacency.set(a, (na = new Map()));
    const total = (na.get(b) ?? 0) + g;
    na.set(b, total);
    let nb = adjacency.get(b);
    if (!nb) adjacency.set(b, (nb = new Map()));
    nb.set(a, total);
    return total;
}

/**
 * Build a fresh random bond-percolation sample: every horizontal bond
 * (including the two end columns, which just connects a boundary node
 * directly to its bus bar) and every vertical bond between two interior
 * columns is independently present, with conductance 1, with probability
 * `p`. No vertical bonds are generated for the terminal columns themselves
 * (a "bond" from a bus bar to itself would be a meaningless self-loop,
 * since every node in that column already shares the single TERMINAL_X/
 * TERMINAL_Y id). Open boundaries top and bottom, unlike ising's periodic
 * ones: a finite conduction sample needs two genuinely distinct edges, not
 * a wraparound.
 *
 * @param {number} cols lattice width (>= 2)
 * @param {number} rows lattice height (>= 1)
 * @param {number} p bond probability, in [0, 1]
 * @param {() => number} [random] uniform [0, 1) generator, injectable for tests
 * @returns {Map<number, Map<number, number>>}
 */
export function createNetwork(cols, rows, p, random = Math.random) {
    const adjacency = new Map();
    for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols - 1; x++) {
            if (random() < p) addEdge(adjacency, nodeId(x, y, cols), nodeId(x + 1, y, cols), 1);
        }
    }
    for (let x = 1; x < cols - 1; x++) {
        for (let y = 0; y < rows - 1; y++) {
            if (random() < p) addEdge(adjacency, nodeId(x, y, cols), nodeId(x, y + 1, cols), 1);
        }
    }
    return adjacency;
}

/**
 * Eliminate node `v`: remove it and its incident edges, then reconnect its
 * former neighbors directly with a mesh of new (or augmented) edges, per
 * the general star-mesh transform
 *   g(i, j) += g(v, i) * g(v, j) / sum_k g(v, k)
 * for every pair of v's former neighbors i, j. This is exact for any
 * degree: 0 or 1 neighbors means the double loop below never runs (v just
 * disappears, correctly contributing nothing), 2 neighbors is the familiar
 * series formula, 3+ is a genuine Y-Delta.
 *
 * Returns exactly what changed (rather than leaving a caller to diff the
 * whole adjacency against its previous state) so a renderer can patch only
 * the handful of DOM elements affected by this one elimination, not redraw
 * the entire network every step.
 *
 * @param {Map<number, Map<number, number>>} adjacency mutated in place
 * @param {number} v node to eliminate
 * @returns {{ removed: number, removedNeighbors: number[], changed: [number, number, number][] }}
 *   removedNeighbors: v's former neighbors, each now missing an edge to v.
 *   changed: [a, b, newTotalConductance] for every pair of those neighbors,
 *   whether that mesh edge is brand new or an existing one just augmented.
 */
export function eliminate(adjacency, v) {
    const edges = adjacency.get(v);
    const entries = edges ? [...edges] : [];
    const total = entries.reduce((sum, [, g]) => sum + g, 0);
    for (const [n] of entries) adjacency.get(n).delete(v);
    adjacency.delete(v);
    const changed = [];
    for (let i = 0; i < entries.length; i++) {
        const [a, ga] = entries[i];
        for (let j = i + 1; j < entries.length; j++) {
            const [b, gb] = entries[j];
            changed.push([a, b, addEdge(adjacency, a, b, (ga * gb) / total)]);
        }
    }
    return { removed: v, removedNeighbors: entries.map(([n]) => n), changed };
}

/**
 * Reduce `adjacency` to a single X-Y edge, one node elimination per
 * `.next()`. Nodes are eliminated lowest-degree first (ties broken by
 * `interiorIds` order): cheap dangling ends and series chains clear out
 * before any genuine Y-Delta is needed, which is both the efficient order
 * (fewer new edges created per step) and, incidentally, the clearest one
 * to animate.
 *
 * Picking the next node to eliminate rescans every remaining node (O(n) per
 * step, O(n^2) overall) rather than maintaining a degree-bucketed queue --
 * fine for the lattice sizes this demo actually uses (tens to low hundreds
 * of nodes); revisit with a real priority structure before exposing a much
 * larger `cols`/`rows` to users.
 *
 * @param {Map<number, Map<number, number>>} adjacency mutated in place
 * @param {number[]} interiorIds every node to eliminate, e.g. from interiorNodeIds()
 * @yields {{ removed: number, removedNeighbors: number[], changed: [number, number, number][] }} see eliminate()
 */
export function* reduceGenerator(adjacency, interiorIds) {
    const remaining = new Set(interiorIds);
    while (remaining.size > 0) {
        let next, minDegree = Infinity;
        for (const id of remaining) {
            const degree = adjacency.get(id)?.size ?? 0;
            if (degree < minDegree) {
                minDegree = degree;
                next = id;
            }
        }
        const change = eliminate(adjacency, next);
        remaining.delete(next);
        yield change;
    }
}

/**
 * The network's equivalent resistance between X and Y, once fully reduced
 * (or at any earlier point, though it's only physically meaningful after
 * every interior node is eliminated).
 *
 * @param {Map<number, Map<number, number>>} adjacency
 * @returns {number} Infinity if X and Y aren't connected
 */
export function resistance(adjacency) {
    const g = adjacency.get(TERMINAL_X)?.get(TERMINAL_Y) ?? 0;
    return g > 0 ? 1 / g : Infinity;
}
