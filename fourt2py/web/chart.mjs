// A draggable-knot XY chart: predefined frequencies (X) are fixed, only a
// knot's amplitude (Y) moves. Coordinate math is kept separate from the DOM
// so it can be unit tested without a browser.

export const WIDTH = 640;
export const HEIGHT = 220;
const MARGIN = { top: 16, right: 16, bottom: 28, left: 16 };
const PLOT_WIDTH = WIDTH - MARGIN.left - MARGIN.right;
const PLOT_HEIGHT = HEIGHT - MARGIN.top - MARGIN.bottom;

const SVG_NS = 'http://www.w3.org/2000/svg';
const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));

/** Amplitude in [-1, 1] -> Y pixel offset from the plot's top edge. */
export function ampToY(amp, plotHeight = PLOT_HEIGHT) {
    return ((1 - clamp(amp, -1, 1)) / 2) * plotHeight;
}

/** Y pixel offset from the plot's top edge -> amplitude in [-1, 1]. */
export function yToAmp(y, plotHeight = PLOT_HEIGHT) {
    return clamp(1 - (2 * y) / plotHeight, -1, 1);
}

/** Knot index (0-based, among `count` knots) -> X pixel offset from the plot's left edge. */
export function xForIndex(i, count, plotWidth = PLOT_WIDTH) {
    return ((i + 0.5) / count) * plotWidth;
}

/** SVG path `d` for the polyline joining the knots, in plot-local coordinates. */
export function polylinePath(amplitudes, plotWidth = PLOT_WIDTH, plotHeight = PLOT_HEIGHT) {
    return amplitudes
        .map((a, i) => `${i === 0 ? 'M' : 'L'}${xForIndex(i, amplitudes.length, plotWidth)},${ampToY(a, plotHeight)}`)
        .join(' ');
}

/**
 * Build the chart's DOM. `labels[i]` is shown under knot `i` (e.g. its frequency).
 * Returns the `<svg>` element; call {@link attachChart} to make its knots draggable.
 */
export function createChart(document, labels) {
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${WIDTH} ${HEIGHT}`);
    svg.setAttribute('class', 'chart');
    svg.setAttribute('touch-action', 'none');

    const plot = document.createElementNS(SVG_NS, 'g');
    plot.setAttribute('transform', `translate(${MARGIN.left},${MARGIN.top})`);
    svg.append(plot);

    const zero = document.createElementNS(SVG_NS, 'line');
    zero.setAttribute('class', 'chart__zero');
    zero.setAttribute('x1', '0');
    zero.setAttribute('x2', String(PLOT_WIDTH));
    zero.setAttribute('y1', String(ampToY(0)));
    zero.setAttribute('y2', String(ampToY(0)));
    plot.append(zero);

    const path = document.createElementNS(SVG_NS, 'path');
    path.setAttribute('class', 'chart__line');
    path.setAttribute('fill', 'none');
    plot.append(path);

    const knots = labels.map((label, i) => {
        const x = xForIndex(i, labels.length);

        const stem = document.createElementNS(SVG_NS, 'line');
        stem.setAttribute('class', 'chart__stem');
        stem.setAttribute('x1', String(x));
        stem.setAttribute('x2', String(x));
        stem.setAttribute('y1', String(ampToY(0)));
        plot.append(stem);

        const knot = document.createElementNS(SVG_NS, 'circle');
        knot.setAttribute('class', 'chart__knot');
        knot.setAttribute('r', '7');
        knot.setAttribute('cx', String(x));
        knot.dataset.index = String(i);
        plot.append(knot);

        const text = document.createElementNS(SVG_NS, 'text');
        text.setAttribute('class', 'chart__label');
        text.setAttribute('x', String(x));
        text.setAttribute('y', String(PLOT_HEIGHT + 18));
        text.textContent = label;
        plot.append(text);

        return { knot, stem, text };
    });

    return { svg, path, knots };
}

/**
 * Render `amplitudes` into a chart built by {@link createChart} (moves knots,
 * stems and the connecting path; does not touch labels).
 */
export function renderChart({ path, knots }, amplitudes) {
    path.setAttribute('d', polylinePath(amplitudes));
    knots.forEach(({ knot, stem }, i) => {
        const y = ampToY(amplitudes[i]);
        knot.setAttribute('cy', String(y));
        stem.setAttribute('y2', String(y));
    });
}

/**
 * Make a chart's knots draggable. `amplitudes` is mutated in place as the
 * user drags; `onChange(amplitudes)` fires after every move.
 */
export function attachChart(chart, amplitudes, onChange) {
    renderChart(chart, amplitudes);
    let dragging = -1;

    const move = (event) => {
        if (dragging < 0) return;
        const rect = chart.svg.getBoundingClientRect();
        const svgY = ((event.clientY - rect.top) / rect.height) * HEIGHT;
        amplitudes[dragging] = yToAmp(svgY - MARGIN.top);
        renderChart(chart, amplitudes);
        onChange(amplitudes);
    };

    for (const { knot } of chart.knots) {
        knot.addEventListener('pointerdown', (event) => {
            dragging = Number(knot.dataset.index);
            knot.setPointerCapture(event.pointerId);
            move(event);
        });
        knot.addEventListener('pointermove', move);
        knot.addEventListener('pointerup', () => {
            dragging = -1;
        });
    }
}
