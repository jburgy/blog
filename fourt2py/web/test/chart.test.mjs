import { describe, expect, test, vi } from 'vitest';
import { ampToY, yToAmp, xForIndex, polylinePath, WIDTH, HEIGHT, createChart, renderChart, attachChart } from '../chart.mjs';

// createChart/renderChart/attachChart take `document` as a plain parameter
// rather than reading a global, specifically so a hand-rolled stand-in like
// this is enough to exercise them -- no jsdom or real browser needed.
class FakeElement {
    constructor(tagName) {
        this.tagName = tagName;
        this.dataset = {};
        this.children = [];
        this.listeners = new Map();
    }

    setAttribute(name, value) {
        this[name] = String(value);
    }

    append(...nodes) {
        this.children.push(...nodes);
    }

    addEventListener(type, handler) {
        if (!this.listeners.has(type)) this.listeners.set(type, []);
        this.listeners.get(type).push(handler);
    }

    dispatch(type, event) {
        for (const handler of this.listeners.get(type) ?? []) handler(event);
    }

    setPointerCapture() {}

    getBoundingClientRect() {
        return { top: 0, height: HEIGHT };
    }
}

const fakeDocument = { createElementNS: (_ns, tagName) => new FakeElement(tagName) };

// Mirrors chart.mjs's private MARGIN.top (not exported): translates between a
// knot's plot-local y (what ampToY returns) and the simulated pointer's
// canvas-local clientY (what attachChart's move() consumes).
const MARGIN_TOP = 16;

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

describe('createChart', () => {
    test('builds one knot/stem/text triple per label, positioned left-to-right', () => {
        const { svg, path, knots } = createChart(fakeDocument, ['a', 'b', 'c']);
        expect(svg.viewBox).toBe(`0 0 ${WIDTH} ${HEIGHT}`);
        expect(path.tagName).toBe('path');
        expect(knots).toHaveLength(3);

        const xs = knots.map(({ knot }) => Number(knot.cx));
        expect(xs).toEqual([...xs].sort((a, b) => a - b));
        expect(new Set(xs).size).toBe(3); // distinct, not overlapping

        expect(knots.map(({ text }) => text.textContent)).toEqual(['a', 'b', 'c']);
        expect(knots.map(({ knot }) => knot.dataset.index)).toEqual(['0', '1', '2']);
    });
});

describe('renderChart', () => {
    test('moves each knot/stem to match the amplitudes and redraws the path', () => {
        const chart = createChart(fakeDocument, ['a', 'b']);
        renderChart(chart, [1, -1]);

        expect(chart.path.d).toBe(polylinePath([1, -1]));
        expect(Number(chart.knots[0].knot.cy)).toBeCloseTo(ampToY(1));
        expect(Number(chart.knots[1].knot.cy)).toBeCloseTo(ampToY(-1));
        expect(chart.knots[0].stem.y2).toBe(chart.knots[0].knot.cy);
    });
});

describe('attachChart', () => {
    test('dragging a knot updates its amplitude and calls onChange, until pointerup', () => {
        const amplitudes = [0, 0];
        const chart = createChart(fakeDocument, ['a', 'b']);
        const onChange = vi.fn();
        attachChart(chart, amplitudes, onChange);

        const [{ knot }] = chart.knots;
        const targetAmp = 0.5;
        const clientY = ampToY(targetAmp) + MARGIN_TOP;

        knot.dispatch('pointerdown', { clientY, pointerId: 7 });
        expect(amplitudes[0]).toBeCloseTo(targetAmp);
        expect(onChange).toHaveBeenLastCalledWith(amplitudes);

        knot.dispatch('pointerup', {});
        onChange.mockClear();
        knot.dispatch('pointermove', { clientY: ampToY(-1) + MARGIN_TOP });
        expect(amplitudes[0]).toBeCloseTo(targetAmp); // pointerup stopped the drag
        expect(onChange).not.toHaveBeenCalled();
    });

    test('only the dragged knot moves; others are untouched', () => {
        const amplitudes = [0, 0];
        const chart = createChart(fakeDocument, ['a', 'b']);
        attachChart(chart, amplitudes, () => {});

        chart.knots[1].knot.dispatch('pointerdown', { clientY: ampToY(1) + MARGIN_TOP, pointerId: 1 });
        expect(amplitudes).toEqual([0, 1]);
    });
});
