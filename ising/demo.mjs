// DOM wiring for the Ising model demo: a checkbox per update rule drives
// the same L x L lattice, drawn as a grid of SVG circles. Checking one
// unchecks the others and (re)starts the simulation with that rule;
// unchecking the active checkbox (leaving none checked) stops it. Kept out
// of index.html so it stays testable. Based on
// https://jsfiddle.net/jburgy/br0gk7s8/1/, itself a tribute to Jian-Sheng
// Wang's early PostScript Ising demo
// (https://www.physics.nus.edu.sg/~phywjs/lecture-notes/ising.ps).

import { createLattice, metropolisSweep, swendsenWangSweep, wolffStep } from './lattice.mjs';

const L = 32;
const T = 2.5;
const INTERVAL_MS = 150;

/** One entry per selectable update rule: its id/label and its
 * `(spins, L, T) -> number[]` step function (see lattice.mjs). */
const ALGORITHMS = [
    { id: 'metropolis', label: 'Naive Metropolis', step: metropolisSweep },
    { id: 'swendsen-wang', label: 'Swendsen\u2013Wang', step: swendsenWangSweep },
    { id: 'wolff', label: 'Wolff', step: wolffStep },
];

const MARKUP = `
<p data-role="title"></p>
<svg data-role="lattice" height="512" width="512"></svg>
<form class="controls">${ALGORITHMS.map(
    ({ id, label }) => `
    <label><input type="checkbox" data-role="algorithm" value="${id}"> ${label}</label>`,
).join('')}
</form>
`;

/**
 * Build the (unattached) demo markup: a title, an SVG lattice, and one
 * checkbox per entry in ALGORITHMS.
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
 * Wire `panel` up: fill its SVG with one circle per site, then let its
 * checkboxes start/stop the simulation.
 *
 * @param {HTMLElement} panel as returned by createPanel
 * @param {{ L?: number, T?: number, intervalMs?: number }} [options]
 * @returns {{ spins: Int8Array, stop: () => void }}
 */
export function attach(panel, { L: size = L, T: temperature = T, intervalMs = INTERVAL_MS } = {}) {
    const document = panel.ownerDocument;
    const spins = createLattice(size);
    const svg = panel.querySelector('[data-role="lattice"]');
    const scale = parseFloat(svg.getAttribute('width')) / size;
    const delta = scale / 2;

    panel.querySelector('[data-role="title"]').textContent = `Ising Model (${size}\u00d7${size}, T = ${temperature})`;

    const circles = Array.from(spins, (_, i) => {
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', (i % size) * scale + delta);
        circle.setAttribute('cy', Math.trunc(i / size) * scale + delta);
        circle.setAttribute('r', delta - 2);
        svg.appendChild(circle);
        return circle;
    });
    const paint = (i) => {
        circles[i].style.fill = spins[i] > 0 ? 'black' : 'yellow';
    };
    spins.forEach((_, i) => paint(i));

    let timer = null;
    const stop = () => {
        clearInterval(timer);
        timer = null;
    };
    const start = (id) => {
        stop();
        const { step } = ALGORITHMS.find((algorithm) => algorithm.id === id);
        timer = setInterval(() => {
            for (const i of step(spins, size, temperature)) paint(i);
        }, intervalMs);
    };

    const checkboxes = Array.from(panel.querySelectorAll('[data-role="algorithm"]'));
    for (const checkbox of checkboxes) {
        checkbox.addEventListener('change', () => {
            if (checkbox.checked) {
                for (const other of checkboxes) if (other !== checkbox) other.checked = false;
                start(checkbox.value);
            } else {
                stop();
            }
        });
    }

    return { spins, stop };
}
