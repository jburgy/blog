import { describe, expect, test } from 'vitest';
import {
    TERMINAL_X,
    TERMINAL_Y,
    PERCOLATION_THRESHOLD,
    nodeId,
    interiorNodeIds,
    createNetwork,
    eliminate,
    reduceGenerator,
    resistance,
} from '../lattice.mjs';

describe('PERCOLATION_THRESHOLD', () => {
    test('is the exact square-lattice bond threshold (self-duality: p_c = 1/2)', () => {
        expect(PERCOLATION_THRESHOLD).toBe(0.5);
    });
});

describe('nodeId', () => {
    test('leftmost column is TERMINAL_X, rightmost is TERMINAL_Y, elsewhere row-major', () => {
        const cols = 5;
        expect(nodeId(0, 2, cols)).toBe(TERMINAL_X);
        expect(nodeId(cols - 1, 2, cols)).toBe(TERMINAL_Y);
        expect(nodeId(2, 1, cols)).toBe(1 * cols + 2);
    });
});

describe('interiorNodeIds', () => {
    test('excludes both terminal columns, row-major', () => {
        expect(interiorNodeIds(4, 2)).toEqual([nodeId(1, 0, 4), nodeId(2, 0, 4), nodeId(1, 1, 4), nodeId(2, 1, 4)]);
    });

    test('is empty when there are no interior columns', () => {
        expect(interiorNodeIds(2, 3)).toEqual([]);
    });
});

describe('createNetwork', () => {
    test('every bond present when random() always returns 0', () => {
        const adjacency = createNetwork(3, 2, 0.5, () => 0);
        // 2 rows x 2 horizontal bonds + 1 interior column x 1 vertical bond
        expect(adjacency.get(TERMINAL_X).get(nodeId(1, 0, 3))).toBe(1);
        expect(adjacency.get(nodeId(1, 0, 3)).get(nodeId(1, 1, 3))).toBe(1);
        expect(adjacency.get(nodeId(1, 1, 3)).get(TERMINAL_Y)).toBe(1);
    });

    test('no bonds when random() always returns 1', () => {
        const adjacency = createNetwork(3, 2, 0.5, () => 1);
        expect(adjacency.size).toBe(0);
    });

    test('never generates a vertical bond within a terminal column', () => {
        // Every random() call must be for a genuine (non-self-loop) bond:
        // cols=2 has no interior columns, so only the 2 horizontal (X-Y)
        // bonds -- one per row -- should ever consult random().
        let calls = 0;
        createNetwork(2, 3, 1, () => {
            calls++;
            return 0;
        });
        expect(calls).toBe(3);
    });
});

describe('eliminate', () => {
    test('a degree-0 node vanishes with no new edges', () => {
        const adjacency = new Map([[0, new Map()]]);
        const change = eliminate(adjacency, 0);
        expect(adjacency.size).toBe(0);
        expect(change).toEqual({ removed: 0, removedNeighbors: [], changed: [] });
    });

    test('a degree-1 (dangling) node vanishes without touching its one neighbor', () => {
        const adjacency = new Map([
            ['a', new Map([['v', 1]])],
            ['v', new Map([['a', 1]])],
        ]);
        const change = eliminate(adjacency, 'v');
        expect(adjacency.has('v')).toBe(false);
        expect(adjacency.get('a').size).toBe(0);
        expect(change).toEqual({ removed: 'v', removedNeighbors: ['a'], changed: [] });
    });

    test('a degree-2 node reduces to the series formula g1*g2/(g1+g2)', () => {
        const adjacency = new Map([
            ['a', new Map([['v', 2]])],
            ['b', new Map([['v', 4]])],
            ['v', new Map([['a', 2], ['b', 4]])],
        ]);
        const change = eliminate(adjacency, 'v');
        expect(adjacency.has('v')).toBe(false);
        expect(adjacency.get('a').get('b')).toBeCloseTo((2 * 4) / (2 + 4), 12);
        expect(adjacency.get('b').get('a')).toBeCloseTo((2 * 4) / (2 + 4), 12);
        expect(change.removedNeighbors).toEqual(['a', 'b']);
        expect(change.changed).toHaveLength(1);
        const [[a, b, g]] = change.changed;
        expect([a, b]).toEqual(['a', 'b']);
        expect(g).toBeCloseTo((2 * 4) / (2 + 4), 12);
    });

    test('a degree-3 node performs a genuine Y-Delta (star-mesh) transform', () => {
        const adjacency = new Map([
            ['a', new Map([['v', 1]])],
            ['b', new Map([['v', 1]])],
            ['c', new Map([['v', 1]])],
            ['v', new Map([['a', 1], ['b', 1], ['c', 1]])],
        ]);
        const change = eliminate(adjacency, 'v');
        for (const [p, q] of [['a', 'b'], ['a', 'c'], ['b', 'c']]) {
            expect(adjacency.get(p).get(q)).toBeCloseTo(1 / 3, 12);
        }
        expect(change.changed).toHaveLength(3);
        for (const [, , g] of change.changed) expect(g).toBeCloseTo(1 / 3, 12);
    });

    test('a new mesh edge adds to (not replaces) any conductance already there, and reports the new total', () => {
        const adjacency = new Map([
            ['a', new Map([['v', 1], ['b', 0.25]])],
            ['b', new Map([['v', 1], ['a', 0.25]])],
            ['v', new Map([['a', 1], ['b', 1]])],
        ]);
        const change = eliminate(adjacency, 'v');
        const expected = 0.25 + (1 * 1) / (1 + 1);
        expect(adjacency.get('a').get('b')).toBeCloseTo(expected, 12);
        const [[, , g]] = change.changed;
        expect(g).toBeCloseTo(expected, 12);
    });
});

describe('resistance', () => {
    test('is the reciprocal of the direct X-Y conductance once fully reduced', () => {
        const adjacency = new Map([
            [TERMINAL_X, new Map([[TERMINAL_Y, 0.25]])],
            [TERMINAL_Y, new Map([[TERMINAL_X, 0.25]])],
        ]);
        expect(resistance(adjacency)).toBe(4);
    });

    test('is Infinity when X and Y aren\u2019t connected', () => {
        expect(resistance(new Map())).toBe(Infinity);
    });
});

describe('reduceGenerator', () => {
    test('yields a change record once per interior node, then finishes', () => {
        const cols = 4;
        const adjacency = createNetwork(cols, 1, 1, () => 0); // fully connected single row
        const ids = interiorNodeIds(cols, 1);
        const generator = reduceGenerator(adjacency, ids);
        const eliminated = [];
        for (const change of generator) eliminated.push(change.removed);
        expect(eliminated.sort()).toEqual([...ids].sort());
        expect(adjacency.size).toBe(2); // only TERMINAL_X and TERMINAL_Y remain
    });

    test('a straight chain of 2 series resistors reduces to their sum', () => {
        const cols = 3; // 1 interior column => X -(1ohm)- v -(1ohm)- Y
        const adjacency = createNetwork(cols, 1, 1, () => 0);
        const ids = interiorNodeIds(cols, 1);
        [...reduceGenerator(adjacency, ids)];
        expect(resistance(adjacency)).toBeCloseTo(2, 12);
    });

    test('two parallel rows of 1 resistor each reduce to 0.5 ohm', () => {
        const cols = 2; // no interior nodes: X and Y bus bars shorted by 2 direct rows
        const adjacency = createNetwork(cols, 2, 1, () => 0);
        const ids = interiorNodeIds(cols, 2);
        expect(ids).toEqual([]);
        expect(resistance(adjacency)).toBeCloseTo(0.5, 12);
    });

    test('eliminates lower-degree nodes first', () => {
        // v (degree 1, dangling off `a`) must come before `a` itself
        // (degree 2: `v` and TERMINAL_Y), regardless of interiorIds order.
        const adjacency = new Map([
            [TERMINAL_X, new Map([['a', 1]])],
            ['a', new Map([[TERMINAL_X, 1], ['v', 1], [TERMINAL_Y, 1]])],
            ['v', new Map([['a', 1]])],
            [TERMINAL_Y, new Map([['a', 1]])],
        ]);
        const generator = reduceGenerator(adjacency, ['a', 'v']);
        expect(generator.next().value.removed).toBe('v');
        expect(generator.next().value.removed).toBe('a');
        expect(generator.next().done).toBe(true);
    });
});

// --- Independent cross-check -------------------------------------------
//
// eliminate()'s star-mesh formula is the one piece of genuinely novel math
// here, so beyond the hand-worked cases above, a batch of random small
// networks is also checked against a completely different method: solving
// Kirchhoff's current law directly as a linear system (the grounded graph
// Laplacian), via plain Gaussian elimination. Agreement between two
// unrelated techniques is much stronger evidence of correctness than either
// one's hand-picked examples alone.

/** Tiny seeded PRNG (mulberry32, public domain) so the cross-check below is
 * deterministic across runs. */
function mulberry32(seed) {
    return function () {
        seed |= 0;
        seed = (seed + 0x6d2b79f5) | 0;
        let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

function connectedComponent(adjacency, start) {
    const seen = new Set([start]);
    const stack = [start];
    while (stack.length) {
        const u = stack.pop();
        for (const v of adjacency.get(u)?.keys() ?? []) {
            if (!seen.has(v)) {
                seen.add(v);
                stack.push(v);
            }
        }
    }
    return seen;
}

function solveLinearSystem(A, b) {
    const n = b.length;
    const M = A.map((row, i) => [...row, b[i]]);
    for (let col = 0; col < n; col++) {
        let pivot = col;
        for (let r = col + 1; r < n; r++) if (Math.abs(M[r][col]) > Math.abs(M[pivot][col])) pivot = r;
        [M[col], M[pivot]] = [M[pivot], M[col]];
        for (let r = col + 1; r < n; r++) {
            const factor = M[r][col] / M[col][col];
            for (let c = col; c <= n; c++) M[r][c] -= factor * M[col][c];
        }
    }
    const x = new Array(n).fill(0);
    for (let r = n - 1; r >= 0; r--) {
        let sum = M[r][n];
        for (let c = r + 1; c < n; c++) sum -= M[r][c] * x[c];
        x[r] = sum / M[r][r];
    }
    return x;
}

/** Equivalent X-Y resistance via direct linear solve, restricted to the
 * connected component containing X (so the reduced Laplacian is always
 * nonsingular, regardless of unrelated floating islands elsewhere in the
 * sample). Independent of eliminate()/reduceGenerator() entirely. */
function resistanceViaLinearSolve(adjacency) {
    const component = connectedComponent(adjacency, TERMINAL_X);
    if (!component.has(TERMINAL_Y)) return Infinity;
    const ids = [...component];
    const index = new Map(ids.map((id, i) => [id, i]));
    const xi = index.get(TERMINAL_X);
    const yi = index.get(TERMINAL_Y);
    const free = ids.map((_, i) => i).filter((i) => i !== xi && i !== yi);

    const A = Array.from({ length: free.length }, () => new Array(free.length).fill(0));
    const b = new Array(free.length).fill(0);
    free.forEach((i, r) => {
        const id = ids[i];
        for (const [neighborId, g] of adjacency.get(id)) {
            const j = index.get(neighborId);
            A[r][r] += g;
            if (j === xi) b[r] += g * 1; // known potential V[X] = 1 moved to the RHS
            else if (j !== yi) A[r][free.indexOf(j)] -= g; // V[Y] = 0 contributes nothing
        }
    });
    const V = solveLinearSystem(A, b);
    const potential = new Array(ids.length);
    potential[xi] = 1;
    potential[yi] = 0;
    free.forEach((i, r) => (potential[i] = V[r]));

    let current = 0;
    for (const [neighborId, g] of adjacency.get(TERMINAL_X)) {
        current += g * (1 - potential[index.get(neighborId)]);
    }
    return current > 0 ? 1 / current : Infinity;
}

describe('star-mesh elimination vs. direct linear solve', () => {
    test('agree on 20 random small networks', () => {
        const random = mulberry32(42);
        for (let trial = 0; trial < 20; trial++) {
            const cols = 4;
            const rows = 3;
            const original = createNetwork(cols, rows, 0.7, random);
            const copy = new Map([...original].map(([k, v]) => [k, new Map(v)]));

            [...reduceGenerator(copy, interiorNodeIds(cols, rows))];
            const viaStarMesh = resistance(copy);
            const viaLinearSolve = resistanceViaLinearSolve(original);

            if (Number.isFinite(viaLinearSolve)) {
                expect(viaStarMesh).toBeCloseTo(viaLinearSolve, 9);
            } else {
                expect(viaStarMesh).toBe(Infinity);
            }
        }
    });
});
