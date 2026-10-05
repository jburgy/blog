// A periodic L x L Ising lattice and three ways to update it: naive
// single-spin-flip Metropolis, Swendsen-Wang, and Wolff. The latter two are
// cluster algorithms built on the same Fortuin-Kasteleyn bond probability
// (see bondProbability() below); they decorrelate much faster than
// Metropolis near the critical temperature, which is the whole point of
// comparing them.
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
 * boundary conditions, in no particular order. A thin, allocating wrapper
 * around neighborTable(L) below, for tests and callers that just want a
 * plain array; the hot loops in this file read the table directly instead.
 *
 * @param {number} i site index
 * @param {number} L lattice side length
 * @returns {number[]} length 4
 */
export function neighbors(i, L) {
    const table = neighborTable(L);
    const base = 4 * i;
    return [table[base], table[base + 1], table[base + 2], table[base + 3]];
}

const neighborTableCache = new Map();

/**
 * Flat, cached-per-L table of every site's 4 neighbors: site i's neighbors
 * (down, up, right, left) are table[4*i], table[4*i+1], table[4*i+2],
 * table[4*i+3]. Site positions, not spins, determine this, so it only ever
 * needs computing once per L -- worth doing, since every algorithm below
 * looks up every visited site's neighbors on every single step, and without
 * this they'd each cost a fresh 4-element array allocation (what neighbors()
 * above returns) instead of 4 typed-array reads.
 *
 * @param {number} L lattice side length
 * @returns {Int32Array} length 4*L*L
 */
function neighborTable(L) {
    let table = neighborTableCache.get(L);
    if (table === undefined) {
        const n = L * L;
        table = new Int32Array(4 * n);
        for (let i = 0; i < n; i++) {
            table[4 * i] = down(i, L);
            table[4 * i + 1] = up(i, L);
            table[4 * i + 2] = right(i, L);
            table[4 * i + 3] = left(i, L);
        }
        neighborTableCache.set(L, table);
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
    const table = neighborTable(L);
    const flipped = [];
    for (let i = 0; i < spins.length; i++) {
        const s = spins[i];
        const base = 4 * i;
        const alignedNeighbors = spins[table[base]] + spins[table[base + 1]] + spins[table[base + 2]] + spins[table[base + 3]];
        const deltaE = 2 * J * s * alignedNeighbors;
        if (deltaE <= 0 || random() < Math.exp(-deltaE / T)) {
            spins[i] = -s;
            flipped.push(i);
        }
    }
    return flipped;
}

const swScratchCache = new Map();

/**
 * Per-L union-find scratch for swendsenWangSweep, reused across calls
 * (reset, not reallocated) since a fresh sweep needs every entry back at
 * its own-root/rank-0/undecided starting state anyway -- allocating new
 * typed arrays for that every single sweep would just be needless garbage.
 *
 * @param {number} n site count (L*L)
 * @returns {{ parent: Int32Array, rank: Uint8Array, flipRoot: Int8Array }}
 */
function swScratch(n) {
    let scratch = swScratchCache.get(n);
    if (scratch === undefined) {
        scratch = { parent: new Int32Array(n), rank: new Uint8Array(n), flipRoot: new Int8Array(n) };
        swScratchCache.set(n, scratch);
    }
    const { parent, rank, flipRoot } = scratch;
    for (let i = 0; i < n; i++) {
        parent[i] = i;
        rank[i] = 0;
        flipRoot[i] = -1; // undecided
    }
    return scratch;
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
    const table = neighborTable(L);

    // Union-find with path halving and union by rank, inlined: this sweep
    // runs every animation frame, so it's worth not allocating a class.
    const { parent, rank, flipRoot } = swScratch(n);
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
        const base = 4 * i;
        const d = table[base];
        const r = table[base + 2];
        if (spins[i] === spins[d] && random() < p) union(i, d);
        if (spins[i] === spins[r] && random() < p) union(i, r);
    }

    const flipped = [];
    for (let i = 0; i < n; i++) {
        const root = find(i);
        if (flipRoot[root] === -1) flipRoot[root] = random() < 0.5 ? 1 : 0;
        if (flipRoot[root]) {
            spins[i] = -spins[i];
            flipped.push(i);
        }
    }
    return flipped;
}

const wolffScratchCache = new Map();

/**
 * Per-L cluster-membership scratch for wolffStep, reused across calls via
 * an epoch counter instead of reallocating: a typical cluster only touches
 * a small fraction of the lattice (see lattice.test.mjs/the demo for sizes),
 * so re-zeroing (or reallocating) a full L*L array on every single call --
 * the obvious approach -- would cost more than growing the cluster itself.
 * Bumping the epoch and comparing against it is equivalent to "is this site
 * marked in the current call" without touching every entry.
 *
 * @param {number} n site count (L*L)
 * @returns {{ visitedAt: Int32Array, epoch: number }}
 */
function wolffScratch(n) {
    let scratch = wolffScratchCache.get(n);
    if (scratch === undefined) {
        scratch = { visitedAt: new Int32Array(n), epoch: 0 };
        wolffScratchCache.set(n, scratch);
    }
    scratch.epoch++;
    return scratch;
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
    const table = neighborTable(L);
    const seedSpin = spins[seed];
    const { visitedAt, epoch } = wolffScratch(spins.length);
    const cluster = [seed];
    visitedAt[seed] = epoch;

    for (let k = 0; k < cluster.length; k++) {
        const base = 4 * cluster[k];
        for (let d = base; d < base + 4; d++) {
            const j = table[d];
            if (visitedAt[j] !== epoch && spins[j] === seedSpin && random() < p) {
                visitedAt[j] = epoch;
                cluster.push(j);
            }
        }
    }

    for (const i of cluster) spins[i] = -spins[i];
    return cluster;
}
