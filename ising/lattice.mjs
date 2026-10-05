// A periodic L x L Ising lattice and three ways to update it: naive
// single-spin-flip Metropolis, Swendsen-Wang, and Wolff. The latter two are
// cluster algorithms built on the same Fortuin-Kasteleyn bond probability
// (see BOND_PROBABILITY below); they decorrelate much faster than Metropolis
// near the critical temperature, which is the whole point of comparing them.
//
// Spins are +-1, stored row-major (index i = y*L + x) in an Int8Array.
// Every update function mutates `spins` in place and returns the indices
// that flipped, so a caller only has to repaint those.

/** Ferromagnetic coupling constant. Kept symbolic (rather than folded into
 * T) so the energy/probability formulas below read the same as in any
 * statistical mechanics textbook. */
export const J = 1;

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

/** Index of the neighbor one row below `i` (wraps top-to-bottom). */
function down(i, L) {
    return (i + L) % (L * L);
}

/** Index of the neighbor one row above `i` (wraps bottom-to-top). */
function up(i, L) {
    return (i - L + L * L) % (L * L);
}

/** Index of the neighbor one column right of `i` (wraps right-to-left). */
function right(i, L) {
    const j = i + 1;
    return j % L ? j : j - L;
}

/** Index of the neighbor one column left of `i` (wraps left-to-right). */
function left(i, L) {
    const j = i - 1;
    return i % L ? j : j + L;
}

/**
 * The 4 nearest neighbors of site `i` on an L*L lattice with periodic
 * boundary conditions, in no particular order.
 *
 * @param {number} i site index
 * @param {number} L lattice side length
 * @returns {number[]} length 4
 */
export function neighbors(i, L) {
    return [down(i, L), up(i, L), right(i, L), left(i, L)];
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
 * One Metropolis sweep: visit every site once (in index order) and flip it
 * with the standard single-spin-flip acceptance rule.
 *
 * @param {Int8Array} spins length L*L, entries +-1; mutated in place
 * @param {number} L lattice side length
 * @param {number} T temperature (k_B = 1)
 * @param {() => number} [random] uniform [0, 1) generator, injectable for tests
 * @returns {number[]} indices that flipped
 */
export function metropolisSweep(spins, L, T, random = Math.random) {
    const flipped = [];
    for (let i = 0; i < spins.length; i++) {
        const s = spins[i];
        const alignedNeighbors = neighbors(i, L).reduce((sum, j) => sum + spins[j], 0);
        const deltaE = 2 * J * s * alignedNeighbors;
        if (deltaE <= 0 || random() < Math.exp(-deltaE / T)) {
            spins[i] = -s;
            flipped.push(i);
        }
    }
    return flipped;
}

/**
 * One Swendsen-Wang sweep: freeze a bond between every pair of aligned
 * neighbors with probability `bondProbability(T)`, union-find the resulting
 * clusters, then flip each whole cluster with probability 1/2.
 *
 * @param {Int8Array} spins length L*L, entries +-1; mutated in place
 * @param {number} L lattice side length
 * @param {number} T temperature (k_B = 1)
 * @param {() => number} [random] uniform [0, 1) generator, injectable for tests
 * @returns {number[]} indices that flipped
 */
export function swendsenWangSweep(spins, L, T, random = Math.random) {
    const n = spins.length;
    const p = bondProbability(T);

    // Union-find with path halving and union by rank, inlined: this sweep
    // runs every animation frame, so it's worth not allocating a class.
    const parent = Int32Array.from({ length: n }, (_, i) => i);
    const rank = new Uint8Array(n);
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
        if (rank[rx] < rank[ry]) parent[rx] = ry;
        else if (rank[rx] > rank[ry]) parent[ry] = rx;
        else {
            parent[ry] = rx;
            rank[rx]++;
        }
    };

    // Only the right/down bonds are visited, so each of the 2*L*L bonds in
    // the lattice is considered exactly once.
    for (let i = 0; i < n; i++) {
        for (const j of [right(i, L), down(i, L)]) {
            if (spins[i] === spins[j] && random() < p) union(i, j);
        }
    }

    const UNDECIDED = -1;
    const flipRoot = new Int8Array(n).fill(UNDECIDED);
    const flipped = [];
    for (let i = 0; i < n; i++) {
        const root = find(i);
        if (flipRoot[root] === UNDECIDED) flipRoot[root] = random() < 0.5 ? 1 : 0;
        if (flipRoot[root]) {
            spins[i] = -spins[i];
            flipped.push(i);
        }
    }
    return flipped;
}

/**
 * One Wolff step: grow a single cluster from a random seed site by adding
 * aligned neighbors with probability `bondProbability(T)`, then flip that
 * whole cluster (always, unlike Swendsen-Wang's coin flip per cluster).
 *
 * @param {Int8Array} spins length L*L, entries +-1; mutated in place
 * @param {number} L lattice side length
 * @param {number} T temperature (k_B = 1)
 * @param {() => number} [random] uniform [0, 1) generator, injectable for tests
 * @param {number} [seed] site to grow the cluster from, injectable for tests
 * @returns {number[]} indices that flipped (the grown cluster)
 */
export function wolffStep(spins, L, T, random = Math.random, seed = Math.floor(random() * spins.length)) {
    const p = bondProbability(T);
    const seedSpin = spins[seed];
    const inCluster = new Uint8Array(spins.length);
    const cluster = [seed];
    inCluster[seed] = 1;

    for (let k = 0; k < cluster.length; k++) {
        for (const j of neighbors(cluster[k], L)) {
            if (!inCluster[j] && spins[j] === seedSpin && random() < p) {
                inCluster[j] = 1;
                cluster.push(j);
            }
        }
    }

    for (const i of cluster) spins[i] = -spins[i];
    return cluster;
}
