import { describe, expect, test } from 'vitest';
import { tracePoints, drawOscilloscope } from '../oscilloscope.mjs';

describe('tracePoints', () => {
    test('spans the full width and maps amplitude 1/-1 to the top/bottom', () => {
        const points = tracePoints([1, 0, -1, 0], 300, 200);
        expect(points[0]).toEqual([0, 0]);
        expect(points[2][1]).toBeCloseTo(200);
        expect(points.at(-1)[0]).toBeCloseTo(300);
    });

    test('returns nothing for fewer than two samples', () => {
        expect(tracePoints([1], 300, 200)).toEqual([]);
        expect(tracePoints([], 300, 200)).toEqual([]);
    });
});

function fakeContext() {
    return {
        calls: [],
        shadowBlur: 0,
        fillRectShadowBlur: [],
        fillRect(...args) {
            this.fillRectShadowBlur.push(this.shadowBlur);
            this.calls.push(['fillRect', ...args]);
        },
        beginPath() { this.calls.push(['beginPath']); },
        moveTo(...args) { this.calls.push(['moveTo', ...args]); },
        lineTo(...args) { this.calls.push(['lineTo', ...args]); },
        stroke() { this.calls.push(['stroke']); },
    };
}

describe('drawOscilloscope', () => {
    test('fills the background then traces one moveTo and n-1 lineTo calls', () => {
        const ctx = fakeContext();
        drawOscilloscope(ctx, [0, 1, 0, -1], { width: 100, height: 50 });
        expect(ctx.calls[0][0]).toBe('fillRect');
        expect(ctx.calls.filter(([name]) => name === 'moveTo')).toHaveLength(1);
        expect(ctx.calls.filter(([name]) => name === 'lineTo')).toHaveLength(3);
        expect(ctx.calls.at(-1)).toEqual(['stroke']);
    });

    test('does not stroke an empty trace', () => {
        const ctx = fakeContext();
        drawOscilloscope(ctx, [1], { width: 100, height: 50 });
        expect(ctx.calls.some(([name]) => name === 'stroke')).toBe(false);
    });

    test('resets shadowBlur before filling, so a previous glow does not bleed into the next frame', () => {
        const ctx = fakeContext();
        ctx.shadowBlur = 8; // leftover from a hypothetical previous stroke
        drawOscilloscope(ctx, [0, 1, 0, -1], { width: 100, height: 50 });
        expect(ctx.fillRectShadowBlur).toEqual([0]);
    });
});
