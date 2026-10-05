// A periodic L x L Ising lattice and three ways to update it: naive
// single-spin-flip Metropolis, Swendsen-Wang, and Wolff. The latter two are
// cluster algorithms built on the same Fortuin-Kasteleyn bond probability
// (see bondProbability() below); they decorrelate much faster than
// Metropolis near the critical temperature, which is the whole point of
// comparing them.
//
// Spins are +-1, stored row-major (index i = y*L + x) in an Int8Array.
// Each algorithm below is a generator, not a plain function: calling e.g.
// metropolisGenerator(spins, neighbors, T) once builds whatever that
// algorithm needs (union-find scratch, cluster-membership tracking) as
// ordinary local variables, then yields `spins` forever, once per
// sweep/step, after mutating it in place. That setup work only ever has to
// happen once per generator, for free, just by being outside the
// `for (;;)` loop -- no module-level cache keyed by lattice size needed,
// since the generator's own locals already live exactly as long as the
// generator does.
//
// The one piece of per-generator setup worth hoisting out further still is
// the neighbor table: it depends only on L, not on which algorithm or how
// many generators use it, so callers build it once via neighbors(L) and
// pass the same table to every generator they create, rather than each
// generator rebuilding its own copy.

/** Ferromagnetic coupling constant. Kept symbolic (rather than folded into
 * T) so the energy/probability formulas below read the same as in any
 * statistical mechanics textbook. */
export const J = 1;

/** Onsager's exact critical temperature for the 2D square-lattice Ising
 * model (k_B = 1): k_B*T_c = 2*J / ln(1 + sqrt(2)). Below it the lattice
 * has a spontaneous net magnetization; above it, none. */
export const CRITICAL_TEMPERATURE = (2 * J) / Math.log(1 + Math.sqrt(2));

/**
 * Build an L*L lattice, every spin pointing up.
 *
 * Starting fully ordered (rather than random) makes the three algorithms
 * easy to tell apart: at T above the critical temperature, naive Metropolis
 * visibly takes many sweeps to "melt" into a disordered state, while
 * Swendsen-Wang and Wolff reach it in a step or two.
 *
 * @param {number} L lattice side length
 * @returns {Int8Array} length L*L, every entry +1
 */
export function createLattice(L) {
    return new Int8Array(L * L).fill(1);
}

/**
 * Flat table of every site's 4 neighbors on an L*L lattice with periodic
 * boundary conditions: site i's neighbors (down, up, right, left) are
 * table[4*i] through table[4*i+3]. Site positions, not spins, determine
 * this, so build it once per lattice size and pass the same table to every
 * generator below -- they each look up every visited site's neighbors on
 * every single step, so a fresh 4-element array per lookup (down/up/right/
 * left computed individually) would cost needless allocation in the
 * hottest loop in this file.
 *
 * @param {number} L lattice side length
 * @returns {Int32Array} length 4*L*L
 */
export function neighbors(L) {
    const n = L * L;
    const table = new Int32Array(4 * n);
    for (let i = 0; i < n; i++) {
        const right = i + 1;
        const left = i - 1;
        table[4 * i] = (i + L) % n; // down
        table[4 * i + 1] = (i - L + n) % n; // up
        table[4 * i + 2] = right % L ? right : right - L;
        table[4 * i + 3] = i % L ? left : left + L;
    }
    return table;
}

/**
 * Probability that Swendsen-Wang/Wolff "freeze" the bond between two
 * aligned neighboring spins into the same cluster, following Fortuin and
 * Kasteleyn: p = 1 - exp(-2J/T). Unaligned neighbors are never bonded.
 *
 * @param {number} T temperature (k_B = 1)
 * @returns {number} in [0, 1)
 */
function bondProbability(T) {
    return 1 - Math.exp((-2 * J) / T);
}

/**
 * Metropolis sweeps: each `.next()` visits every site once (in index order)
 * and flips it with the standard single-spin-flip acceptance rule.
 *
 * @param {Int8Array} spins length L*L, entries +-1; mutated in place
 * @param {Int32Array} neighbors flat neighbor table, see neighbors(L)
 * @param {number} T temperature (k_B = 1)
 * @param {() => number} [random] uniform [0, 1) generator, injectable for tests
 * @yields {Int8Array} `spins`, mutated in place by this sweep
 */
export function* metropolisGenerator(spins, neighbors, T, random = Math.random) {
    for (;;) {
        for (let i = 0; i < spins.length; i++) {
            const s = spins[i];
            const base = 4 * i;
            const alignedNeighbors =
                spins[neighbors[base]] +
                spins[neighbors[base + 1]] +
                spins[neighbors[base + 2]] +
                spins[neighbors[base + 3]];
            const deltaE = 2 * J * s * alignedNeighbors;
            if (deltaE <= 0 || random() < Math.exp(-deltaE / T)) {
                spins[i] = -s;
            }
        }
        yield spins;
    }
}

/**
 * Swendsen-Wang sweeps: each `.next()` freezes a bond between every pair of
 * aligned neighbors with probability `bondProbability(T)`, union-finds the
 * resulting clusters, then flips each whole cluster with probability 1/2.
 *
 * @param {Int8Array} spins length L*L, entries +-1; mutated in place
 * @param {Int32Array} neighbors flat neighbor table, see neighbors(L)
 * @param {number} T temperature (k_B = 1)
 * @param {() => number} [random] uniform [0, 1) generator, injectable for tests
 * @yields {Int8Array} `spins`, mutated in place by this sweep
 */
export function* swendsenWangGenerator(spins, neighbors, T, random = Math.random) {
    const n = spins.length;
    const p = bondProbability(T);

    // Union-find with path halving and union by rank, inlined: this sweep
    // runs every animation frame, so it's worth not allocating a class.
    // Allocated once here, reset (not reallocated) at the top of every
    // sweep below -- a fresh sweep needs every entry back at its
    // own-root/rank-0/undecided starting state regardless, so reusing the
    // same typed arrays just avoids needless garbage.
    const parent = new Int32Array(n);
    const rank = new Uint8Array(n);
    const flipRoot = new Int8Array(n);
    const find = (x) => {
        while (parent[x] !== x) {
            parent[x] = parent[parent[x]];
            x = parent[x];
        }
        return x;
    };
    const union = (x, y) => {
        const rx = find(x);
        const ry = find(y);
        if (rx === ry) return;
        // The < and > cases are mirror images (whichever of rx/ry has the
        // lower rank gets attached under the other), not independently
        // meaningful: which one actually fires for a given pair of trees
        // depends only on which argument order union() happened to be
        // called with, not on anything about the trees themselves.
        if (rank[rx] < rank[ry]) parent[rx] = ry;
        else if (rank[rx] > rank[ry]) parent[ry] = rx;
        else {
            parent[ry] = rx;
            rank[rx]++;
        }
    };

    for (;;) {
        for (let i = 0; i < n; i++) {
            parent[i] = i;
            rank[i] = 0;
            flipRoot[i] = -1; // undecided
        }

        // Only the right/down bonds are visited, so each of the 2*L*L
        // bonds in the lattice is considered exactly once.
        for (let i = 0; i < n; i++) {
            const base = 4 * i;
            const d = neighbors[base];
            const r = neighbors[base + 2];
            if (spins[i] === spins[d] && random() < p) union(i, d);
            if (spins[i] === spins[r] && random() < p) union(i, r);
        }

        for (let i = 0; i < n; i++) {
            const root = find(i);
            if (flipRoot[root] === -1) flipRoot[root] = random() < 0.5 ? 1 : 0;
            if (flipRoot[root]) spins[i] = -spins[i];
        }
        yield spins;
    }
}

/**
 * Wolff steps: each `.next()` grows a single cluster from a seed site (see
 * `pickSeed`) by adding aligned neighbors with probability
 * `bondProbability(T)`, then flips that whole cluster (always, unlike
 * Swendsen-Wang's coin flip per cluster).
 *
 * @param {Int8Array} spins length L*L, entries +-1; mutated in place
 * @param {Int32Array} neighbors flat neighbor table, see neighbors(L)
 * @param {number} T temperature (k_B = 1)
 * @param {() => number} [random] uniform [0, 1) generator, injectable for tests
 * @param {() => number} [pickSeed] returns the site to grow the next cluster from, injectable for tests
 * @yields {Int8Array} `spins`, mutated in place by this step
 */
export function* wolffGenerator(
    spins,
    neighbors,
    T,
    random = Math.random,
    // Clamped, not just Math.floor(random() * spins.length): random() is
    // documented as uniform [0, 1), but a custom test double that slips and
    // returns exactly 1 would otherwise pick the one out-of-bounds index
    // (spins.length), silently degenerating into a cluster that never
    // grows (undefined isn't strictly equal to any real spin) instead of a
    // clear failure.
    pickSeed = () => Math.min(Math.floor(random() * spins.length), spins.length - 1),
) {
    const p = bondProbability(T);

    // Cluster membership, reused across steps via an epoch counter instead
    // of a fresh array: a typical cluster only touches a small fraction of
    // the lattice, so re-zeroing a full L*L array on every single step --
    // the obvious approach -- would cost more than growing the cluster
    // itself. Bumping the epoch and comparing against it is equivalent to
    // "is this site marked in the current step" without touching every
    // entry.
    const visitedAt = new Int32Array(spins.length);
    let epoch = 0;

    for (;;) {
        epoch++;
        const seed = pickSeed();
        const seedSpin = spins[seed];
        const cluster = [seed];
        visitedAt[seed] = epoch;

        for (let k = 0; k < cluster.length; k++) {
            const base = 4 * cluster[k];
            for (let d = base; d < base + 4; d++) {
                const j = neighbors[d];
                if (visitedAt[j] !== epoch && spins[j] === seedSpin && random() < p) {
                    visitedAt[j] = epoch;
                    cluster.push(j);
                }
            }
        }

        for (const i of cluster) spins[i] = -spins[i];
        yield spins;
    }
}
