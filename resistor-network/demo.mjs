// DOM wiring for the resistor-network demo: a random bond-percolation
// lattice (see lattice.mjs), continuously reduced one node elimination per
// tick to a single equivalent resistor, whose value then feeds a running
// histogram before the next random lattice starts. Kept out of index.html
// so it stays testable, same split as ising/demo.mjs.

import {
    TERMINAL_X,
    TERMINAL_Y,
    PERCOLATION_THRESHOLD,
    nodeId,
    interiorNodeIds,
    createNetwork,
    reduceGenerator,
    resistance,
} from './lattice.mjs';

const SVG_NS = 'http://www.w3.org/2000/svg';

const COLS = 10;
const ROWS = 6;
const P = 0.6;
const P_MIN = 0.3;
const P_MAX = 0.9;
const P_STEP = 0.01;
const INTERVAL_MS = 120;

const CELL_SIZE = 56;
const PADDING = 28;

// How many histogram bars span [0, R_MAX); anything at or above R_MAX,
// including an outright disconnected (infinite-resistance) sample, lands in
// one extra overflow bar instead of growing the range unboundedly.
const BIN_COUNT = 20;

// Canonical zig-zag glyph: just the "body" (4 peaks), centered on its own
// local origin and never stretched -- every edge draws it with a plain
// translate to the edge's midpoint (plus whatever rotation the edge needs),
// no scale. The stretchy part of a resistor is its leads, not its zig-zag,
// so those are drawn separately as plain <line>s sized to fill whatever gap
// is left between the fixed-size body and each endpoint; see createEdge().
const ZIGZAG_WIDTH = 30;
const ZIGZAG_POINTS = '-15,0 -9,-8 -3,8 3,-8 9,8 15,0';

const PERCOLATION_THRESHOLD_PERCENT = (100 * (PERCOLATION_THRESHOLD - P_MIN)) / (P_MAX - P_MIN);
const TICK_MARKUP = `<span class="critical-tick" style="left: ${PERCOLATION_THRESHOLD_PERCENT}%"></span>`;

const MARKUP = `
<p data-role="title"></p>
<svg data-role="network"><defs><polyline id="resistor" points="${ZIGZAG_POINTS}"></polyline></defs><g data-role="edges"></g><g data-role="nodes"></g></svg>
<div data-role="histogram" class="histogram">${Array.from({ length: BIN_COUNT + 1 }, () => '<div class="bin" data-role="bin"></div>').join('')}</div>
<form class="controls">
    <label><input type="checkbox" data-role="run"> Run</label>
    <label class="probability">
        p
        <span class="probability__track">
            <input type="range" data-role="probability" min="${P_MIN}" max="${P_MAX}" step="${P_STEP}" value="${P}" list="percolation-threshold">
            ${TICK_MARKUP}
        </span>
    </label>
    <datalist id="percolation-threshold"><option value="${PERCOLATION_THRESHOLD}"></option></datalist>
</form>
`;

/**
 * Build the (unattached) demo markup: a title, an SVG network, a histogram
 * strip, a run checkbox, and a p slider.
 *
 * @param {Document} document
 * @returns {HTMLElement}
 */
export function createPanel(document) {
    const panel = document.createElement('section');
    panel.innerHTML = MARKUP;
    return panel;
}

/**
 * Every node's fixed pixel position: interior nodes at their grid
 * position, TERMINAL_X/TERMINAL_Y each at a single point (vertically
 * centered) standing in for every node shorted onto that bus bar. Built
 * once per attach() -- positions never change, only which edges/nodes are
 * currently present does.
 *
 * @param {number} cols
 * @param {number} rows
 * @returns {Map<number, { cx: number, cy: number }>}
 */
function layout(cols, rows) {
    const colX = (x) => PADDING + x * CELL_SIZE;
    const rowY = (y) => PADDING + y * CELL_SIZE;
    const positions = new Map();
    for (let y = 0; y < rows; y++) {
        for (let x = 1; x < cols - 1; x++) positions.set(nodeId(x, y, cols), { cx: colX(x), cy: rowY(y) });
    }
    const centerY = rowY((rows - 1) / 2);
    positions.set(TERMINAL_X, { cx: colX(0), cy: centerY });
    positions.set(TERMINAL_Y, { cx: colX(cols - 1), cy: centerY });
    return positions;
}

/** A stable, order-independent key for the one DOM element representing
 * the undirected edge between `a` and `b`. */
function edgeKey(a, b) {
    return a < b ? `${a},${b}` : `${b},${a}`;
}

/**
 * An edge's length and angle (degrees), from `pa` to `pb`. Every bond in
 * the freshly generated lattice is axis-aligned by construction (see
 * lattice.mjs's createNetwork), so most calls hit the cheap dy===0/dx===0
 * branches below instead of Math.hypot/Math.atan2 -- the same "skip the
 * general case when the structure guarantees something simpler" idea as
 * ising's precomputed neighbor table. Only mesh edges genuinely newly
 * created by star-mesh elimination can land at an arbitrary angle.
 *
 * @param {{ cx: number, cy: number }} pa
 * @param {{ cx: number, cy: number }} pb
 * @returns {{ length: number, angle: number }}
 */
function edgeGeometry(pa, pb) {
    const dx = pb.cx - pa.cx;
    const dy = pb.cy - pa.cy;
    if (dy === 0) return { length: Math.abs(dx), angle: dx > 0 ? 0 : 180 };
    if (dx === 0) return { length: Math.abs(dy), angle: dy > 0 ? 90 : -90 };
    return { length: Math.hypot(dx, dy), angle: (Math.atan2(dy, dx) * 180) / Math.PI };
}

// At g=1 (a single untouched 1-ohm bond, the overwhelming majority of what's
// on screen at any time) this is a slim 2px -- thick enough to read as a
// wire, not so thick it overwhelms the zig-zag's own 16px amplitude or
// creates miter spikes at its sharp turns (see the round linejoin in the
// CSS alongside it).
const strokeWidthFor = (g) => Math.min(4, 1 + Math.sqrt(g));

/**
 * Wire `panel` up: lay out an SVG network and histogram, then let the run
 * checkbox start/stop a continuous Monte Carlo loop (generate a random
 * lattice, reduce it one node per tick, record its equivalent resistance,
 * repeat) and the p slider adjust the bond probability live, clearing the
 * histogram (a mix of two different p's would be meaningless) and starting
 * a fresh trial immediately.
 *
 * @param {HTMLElement} panel as returned by createPanel
 * @param {{ cols?: number, rows?: number, p?: number, intervalMs?: number }} [options]
 * @returns {{ stop: () => void }}
 */
export function attach(panel, { cols = COLS, rows = ROWS, p: initialP = P, intervalMs = INTERVAL_MS } = {}) {
    const document = panel.ownerDocument;
    const positions = layout(cols, rows);
    // Heuristic histogram ceiling: cols - 1 is the resistance of the single
    // straight-line path across the lattice (one bond per column gap), so
    // 2x that comfortably covers ordinary connected samples without
    // devoting most of the chart to the long tail near the percolation
    // threshold, where resistance diverges.
    const rMax = 2 * (cols - 1);

    const svg = panel.querySelector('[data-role="network"]');
    const width = positions.get(TERMINAL_Y).cx + PADDING;
    const height = (rows - 1) * CELL_SIZE + 2 * PADDING;
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    const edgesGroup = svg.querySelector('[data-role="edges"]');
    const nodesGroup = svg.querySelector('[data-role="nodes"]');

    const bins = Array.from(panel.querySelectorAll('[data-role="bin"]'));
    const counts = new Array(BIN_COUNT + 1).fill(0);
    let trials = 0;
    let disconnected = 0;

    let p = initialP;
    const updateTitle = () => {
        panel.querySelector('[data-role="title"]').textContent =
            `Resistor Network (${cols}\u00d7${rows}, p = ${p.toFixed(2)}, ${trials} trials, ${disconnected} disconnected)`;
    };

    const createNodeCircle = (id) => {
        const { cx, cy } = positions.get(id);
        const circle = document.createElementNS(SVG_NS, 'circle');
        circle.setAttribute('cx', cx);
        circle.setAttribute('cy', cy);
        circle.setAttribute('r', id === TERMINAL_X || id === TERMINAL_Y ? 6 : 3);
        circle.dataset.role = id === TERMINAL_X || id === TERMINAL_Y ? 'terminal' : 'interior';
        nodesGroup.appendChild(circle);
        return circle;
    };

    // One <g> per edge: a plain <line> lead on either side (the only part
    // that stretches to fit) around a fixed-size, never-scaled zig-zag
    // centered at the midpoint -- see ZIGZAG_WIDTH's docstring above.
    const createEdgeGroup = (a, b, g) => {
        const { length, angle } = edgeGeometry(positions.get(a), positions.get(b));
        const half = length / 2;
        // Only the leads are clamped to >= 0 here; the zig-zag itself (fixed
        // at ZIGZAG_WIDTH, translated to `half`) is never shrunk to match a
        // short edge. That's safe only because every edge is >= CELL_SIZE
        // (56px, comfortably more than ZIGZAG_WIDTH's 30px): original bonds
        // span exactly one CELL_SIZE, and star-mesh elimination only ever
        // connects two distinct real grid positions, never closer together
        // than that. If either constant changed without the other, a short
        // enough edge would overshoot past its own endpoints.
        const legEnd = Math.max(0, half - ZIGZAG_WIDTH / 2);

        const group = document.createElementNS(SVG_NS, 'g');
        group.dataset.role = 'edge';
        group.setAttribute('transform', `translate(${positions.get(a).cx},${positions.get(a).cy}) rotate(${angle})`);

        const lead1 = document.createElementNS(SVG_NS, 'line');
        lead1.setAttribute('x2', legEnd);
        group.appendChild(lead1);

        const zigzag = document.createElementNS(SVG_NS, 'use');
        zigzag.setAttribute('href', '#resistor');
        zigzag.setAttribute('transform', `translate(${half},0)`);
        group.appendChild(zigzag);

        const lead2 = document.createElementNS(SVG_NS, 'line');
        lead2.setAttribute('x1', length - legEnd);
        lead2.setAttribute('x2', length);
        group.appendChild(lead2);

        group.style.strokeWidth = strokeWidthFor(g);
        edgesGroup.appendChild(group);
        return group;
    };

    const recordSample = (r) => {
        trials++;
        const bin = Number.isFinite(r) && r < rMax ? Math.floor((r / rMax) * BIN_COUNT) : BIN_COUNT;
        // Deliberately separate from `bin`: a finite-but-huge resistance
        // (r >= rMax, common enough near the percolation threshold) also
        // lands in the overflow bin for charting purposes, but it's not
        // actually disconnected the way Infinity is, and the UI promises
        // this count means "never connected at all".
        if (!Number.isFinite(r)) disconnected++;
        counts[bin]++;
        const max = Math.max(...counts);
        bins.forEach((bar, i) => {
            bar.style.height = `${(counts[i] / max) * 100}%`;
        });
        updateTitle();
    };

    // DOM elements currently on screen, one per living node/edge -- kept
    // around across ticks so a single node elimination only ever touches
    // the handful of elements it actually changes (removed node,
    // its former edges, the mesh edges replacing them) instead of tearing
    // down and rebuilding the whole network every animation frame.
    const nodeElements = new Map();
    const edgeElements = new Map();

    let adjacency, generator;
    const newTrial = () => {
        adjacency = createNetwork(cols, rows, p, Math.random);
        const interiorIds = interiorNodeIds(cols, rows);
        generator = reduceGenerator(adjacency, interiorIds);

        edgesGroup.replaceChildren();
        nodesGroup.replaceChildren();
        nodeElements.clear();
        edgeElements.clear();
        for (const id of [...interiorIds, TERMINAL_X, TERMINAL_Y]) {
            nodeElements.set(id, createNodeCircle(id));
        }
        const seen = new Set();
        for (const [a, neighbors] of adjacency) {
            for (const [b, g] of neighbors) {
                const key = edgeKey(a, b);
                if (seen.has(key)) continue; // each undirected edge stored both ways; create it once
                seen.add(key);
                edgeElements.set(key, createEdgeGroup(a, b, g));
            }
        }
    };
    newTrial();
    updateTitle();

    let frameId = null;
    const stop = () => {
        if (frameId !== null) cancelAnimationFrame(frameId);
        frameId = null;
    };
    const start = () => {
        stop();
        let lastStep = 0;
        const tick = (now) => {
            if (now - lastStep >= intervalMs) {
                lastStep = now;
                const { value: change, done } = generator.next();
                if (done) {
                    recordSample(resistance(adjacency));
                    newTrial();
                } else {
                    nodeElements.get(change.removed)?.remove();
                    nodeElements.delete(change.removed);
                    for (const n of change.removedNeighbors) {
                        const key = edgeKey(change.removed, n);
                        edgeElements.get(key)?.remove();
                        edgeElements.delete(key);
                    }
                    for (const [a, b, g] of change.changed) {
                        const key = edgeKey(a, b);
                        const existing = edgeElements.get(key);
                        if (existing) existing.style.strokeWidth = strokeWidthFor(g);
                        else edgeElements.set(key, createEdgeGroup(a, b, g));
                    }
                }
            }
            frameId = requestAnimationFrame(tick);
        };
        frameId = requestAnimationFrame(tick);
    };

    panel.querySelector('[data-role="run"]').addEventListener('change', (event) => {
        if (event.target.checked) start();
        else stop();
    });

    panel.querySelector('[data-role="probability"]').addEventListener('input', (event) => {
        p = parseFloat(event.target.value);
        counts.fill(0);
        trials = 0;
        disconnected = 0;
        bins.forEach((bar) => (bar.style.height = '0%'));
        newTrial();
        updateTitle();
    });

    return { stop };
}
