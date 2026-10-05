import { describe, expect, test } from 'vitest';
import {
    createLattice,
    neighbors,
    metropolisGenerator,
    swendsenWangGenerator,
    wolffGenerator,
    CRITICAL_TEMPERATURE,
} from '../lattice.mjs';

describe('createLattice', () => {
    test('starts fully ordered (every spin +1)', () => {
        const spins = createLattice(4);
        expect(spins.length).toBe(16);
        expect([...spins]).toEqual(new Array(16).fill(1));
    });
});

describe('CRITICAL_TEMPERATURE', () => {
    test("matches Onsager's exact value (k_B*T_c = 2J / ln(1 + sqrt(2)))", () => {
        expect(CRITICAL_TEMPERATURE).toBeCloseTo(2.269185314213022, 12);
    });
});

describe('neighbors', () => {
    const L = 4;
    const table = neighbors(L);
    const neighborsOf = (i) => [table[4 * i], table[4 * i + 1], table[4 * i + 2], table[4 * i + 3]];

    test('interior site has its 4 orthogonal neighbors', () => {
        // site (1, 1) -> index 1*4 + 1 = 5
        expect(new Set(neighborsOf(5))).toEqual(new Set([9, 1, 6, 4]));
    });

    test('wraps around every edge (corner site)', () => {
        // site (0, 0) -> index 0
        expect(new Set(neighborsOf(0))).toEqual(new Set([4, 12, 1, 3]));
    });

    test('wraps around the right edge', () => {
        // site (3, 0) -> index 3
        expect(new Set(neighborsOf(3))).toEqual(new Set([7, 15, 0, 2]));
    });
});

describe('metropolisGenerator', () => {
    test('accepts every flip when random() always returns 0', () => {
        const spins = createLattice(4);
        const { value } = metropolisGenerator(spins, neighbors(4), 2.5, () => 0).next();
        expect(value).toBe(spins);
        expect([...spins]).toEqual(new Array(16).fill(-1));
    });

    test('rejects every unfavorable flip when random() always returns 1', () => {
        // Starting fully ordered, every single-spin flip raises the energy,
        // so with random() always 1 (never < an acceptance probability < 1)
        // nothing should move.
        const spins = createLattice(4);
        metropolisGenerator(spins, neighbors(4), 2.5, () => 1).next();
        expect([...spins]).toEqual(new Array(16).fill(1));
    });

    test('keeps sweeping on repeated next() calls', () => {
        const spins = createLattice(4);
        const generator = metropolisGenerator(spins, neighbors(4), 2.5, () => 0);
        generator.next(); // all +1 -> all -1
        generator.next(); // all -1 -> all +1
        expect([...spins]).toEqual(new Array(16).fill(1));
    });
});

describe('swendsenWangGenerator', () => {
    test('bonds everything and flips the whole lattice when random() always returns 0', () => {
        const spins = createLattice(4);
        swendsenWangGenerator(spins, neighbors(4), 2.5, () => 0).next();
        expect([...spins]).toEqual(new Array(16).fill(-1));
    });

    test('bonds nothing and flips nothing when random() always returns 1', () => {
        const spins = createLattice(4);
        swendsenWangGenerator(spins, neighbors(4), 2.5, () => 1).next();
        expect([...spins]).toEqual(new Array(16).fill(1));
    });

    test('keeps sweeping on repeated next() calls', () => {
        const spins = createLattice(4);
        const generator = swendsenWangGenerator(spins, neighbors(4), 2.5, () => 0);
        generator.next(); // all +1 -> all -1
        generator.next(); // all -1 -> all +1
        expect([...spins]).toEqual(new Array(16).fill(1));
    });
});

describe('wolffGenerator', () => {
    test('grows the cluster to the whole lattice and flips it when random() always returns 0', () => {
        const spins = createLattice(4);
        wolffGenerator(spins, neighbors(4), 2.5, () => 0, () => 0).next();
        expect([...spins]).toEqual(new Array(16).fill(-1));
    });

    test('flips only the seed when random() always returns a value >= every bond probability', () => {
        const spins = createLattice(4);
        wolffGenerator(spins, neighbors(4), 2.5, () => 0.999999, () => 5).next();
        expect(spins[5]).toBe(-1);
        expect([...spins].filter((_, i) => i !== 5)).toEqual(new Array(15).fill(1));
    });

    test('defaults to a random seed in range when none is given', () => {
        const spins = createLattice(4);
        const before = [...spins];
        wolffGenerator(spins, neighbors(4), 2.5, () => 0.999999).next();
        const changed = before.reduce((count, v, i) => count + (v !== spins[i] ? 1 : 0), 0);
        expect(changed).toBe(1);
    });

    test('a fixed pickSeed can drive successive steps deterministically', () => {
        const spins = createLattice(4);
        const seeds = [5, 2];
        let call = 0;
        const generator = wolffGenerator(spins, neighbors(4), 2.5, () => 0.999999, () => seeds[call++]);
        generator.next();
        expect(spins[5]).toBe(-1);
        expect(spins[2]).toBe(1); // not yet flipped
        generator.next();
        expect(spins[2]).toBe(-1);
    });
});
