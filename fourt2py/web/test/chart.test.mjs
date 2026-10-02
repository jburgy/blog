import { describe, expect, test } from 'vitest';
import { ampToY, yToAmp, xForIndex, polylinePath } from '../chart.mjs';

describe('ampToY / yToAmp', () => {
    test('are inverses of each other', () => {
        for (const amp of [-1, -0.3, 0, 0.42, 1]) {
            expect(yToAmp(ampToY(amp, 200), 200)).toBeCloseTo(amp);
        }
    });

    test('amplitude 1 is the top of the plot, -1 is the bottom', () => {
        expect(ampToY(1, 200)).toBeCloseTo(0);
        expect(ampToY(-1, 200)).toBeCloseTo(200);
        expect(ampToY(0, 200)).toBeCloseTo(100);
    });

    test('clamp out-of-range amplitudes and Y positions', () => {
        expect(ampToY(5, 200)).toBeCloseTo(ampToY(1, 200));
        expect(yToAmp(-50, 200)).toBe(1);
        expect(yToAmp(250, 200)).toBe(-1);
    });
});

describe('xForIndex', () => {
    test('spaces knots evenly and keeps them off the plot edges', () => {
        const xs = [0, 1, 2, 3].map((i) => xForIndex(i, 4, 400));
        expect(xs).toEqual([50, 150, 250, 350]);
    });
});

describe('polylinePath', () => {
    test('starts with M and continues with L for each subsequent knot', () => {
        const d = polylinePath([1, 0, -1], 300, 200);
        const commands = d.split(' ');
        expect(commands).toHaveLength(3);
        expect(commands[0]).toMatch(/^M/);
        expect(commands[1]).toMatch(/^L/);
        expect(commands[2]).toMatch(/^L/);
    });
});
