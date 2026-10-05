import { describe, expect, test } from 'vitest';
import { createLattice, neighbors, metropolisSweep, swendsenWangSweep, wolffStep } from '../lattice.mjs';

describe('createLattice', () => {
    test('starts fully ordered (every spin +1)', () => {
        const spins = createLattice(4);
        expect(spins.length).toBe(16);
        expect([...spins]).toEqual(new Array(16).fill(1));
    });
});

describe('neighbors', () => {
    const L = 4;

    test('interior site has its 4 orthogonal neighbors', () => {
        // site (1, 1) -> index 1*4 + 1 = 5
        expect(new Set(neighbors(5, L))).toEqual(new Set([9, 1, 6, 4]));
    });

    test('wraps around every edge (corner site)', () => {
        // site (0, 0) -> index 0
        expect(new Set(neighbors(0, L))).toEqual(new Set([4, 12, 1, 3]));
    });

    test('wraps around the right edge', () => {
        // site (3, 0) -> index 3
        expect(new Set(neighbors(3, L))).toEqual(new Set([7, 15, 0, 2]));
    });
});

describe('metropolisSweep', () => {
    test('accepts every flip when random() always returns 0', () => {
        const spins = createLattice(4);
        const flipped = metropolisSweep(spins, 4, 2.5, () => 0);
        expect(flipped.length).toBe(16);
        expect([...spins]).toEqual(new Array(16).fill(-1));
    });

    test('rejects every unfavorable flip when random() always returns 1', () => {
        // Starting fully ordered, every single-spin flip raises the energy,
        // so with random() always 1 (never < an acceptance probability < 1)
        // nothing should move.
        const spins = createLattice(4);
        const flipped = metropolisSweep(spins, 4, 2.5, () => 1);
        expect(flipped).toEqual([]);
        expect([...spins]).toEqual(new Array(16).fill(1));
    });
});

describe('swendsenWangSweep', () => {
    test('bonds everything and flips the whole lattice when random() always returns 0', () => {
        const spins = createLattice(4);
        const flipped = swendsenWangSweep(spins, 4, 2.5, () => 0);
        expect(flipped.length).toBe(16);
        expect([...spins]).toEqual(new Array(16).fill(-1));
    });

    test('bonds nothing and flips nothing when random() always returns 1', () => {
        const spins = createLattice(4);
        const flipped = swendsenWangSweep(spins, 4, 2.5, () => 1);
        expect(flipped).toEqual([]);
        expect([...spins]).toEqual(new Array(16).fill(1));
    });
});

describe('wolffStep', () => {
    test('grows the cluster to the whole lattice and flips it when random() always returns 0', () => {
        const spins = createLattice(4);
        const flipped = wolffStep(spins, 4, 2.5, () => 0, 0);
        expect(new Set(flipped)).toEqual(new Set(Array.from({ length: 16 }, (_, i) => i)));
        expect([...spins]).toEqual(new Array(16).fill(-1));
    });

    test('flips only the seed when random() always returns a value >= every bond probability', () => {
        const spins = createLattice(4);
        const flipped = wolffStep(spins, 4, 2.5, () => 0.999999, 5);
        expect(flipped).toEqual([5]);
        expect(spins[5]).toBe(-1);
        expect([...spins].filter((_, i) => i !== 5)).toEqual(new Array(15).fill(1));
    });

    test('defaults to a random seed in range when none is given', () => {
        const spins = createLattice(4);
        const flipped = wolffStep(spins, 4, 2.5, () => 0.999999);
        expect(flipped.length).toBe(1);
        expect(flipped[0]).toBeGreaterThanOrEqual(0);
        expect(flipped[0]).toBeLessThan(16);
    });
});
