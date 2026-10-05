// DOM wiring for the Ising model demo: a checkbox per update rule drives
// the same L x L lattice, drawn as a grid of SVG circles. Checking one
// unchecks the others and (re)starts the simulation with that rule;
// unchecking the active checkbox (leaving none checked) stops it. Kept out
// of index.html so it stays testable. Based on
// https://jsfiddle.net/jburgy/br0gk7s8/1/, itself a tribute to Jian-Sheng
// Wang's early PostScript Ising demo
// (https://www.physics.nus.edu.sg/~phywjs/lecture-notes/ising.ps).

import { createLattice, metropolisGenerator, swendsenWangGenerator, wolffGenerator } from './lattice.mjs';

const L = 32;
const T = 2.5;
const INTERVAL_MS = 150;

// Not pure #0000ff: pure blue is too dark to read on a dark background (its
// WCAG relative luminance is only ~0.07), so plain red/blue fails exactly
// the "regardless of dark mode" requirement these are picked for. Both
// colors below sit at a luminance (~0.18-0.20) chosen to contrast >=4:1
// against *both* white and black -- see index.html's transparent lattice
// background, which relies on that. Being red vs. blue (not red vs. green)
// also keeps them apart on the one color-vision axis (red-green) most
// color blindness affects.
const SPIN_UP_COLOR = '#457b9d'; // steel blue
const SPIN_DOWN_COLOR = '#e63946'; // imperial red

/** One entry per selectable update rule: its id/label and the generator
 * function that drives it (see lattice.mjs). */
const ALGORITHMS = [
    { id: 'metropolis', label: 'Naive Metropolis', createGenerator: metropolisGenerator },
    { id: 'swendsen-wang', label: 'Swendsen\u2013Wang', createGenerator: swendsenWangGenerator },
    { id: 'wolff', label: 'Wolff', createGenerator: wolffGenerator },
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
        circles[i].style.fill = spins[i] > 0 ? SPIN_UP_COLOR : SPIN_DOWN_COLOR;
    };
    spins.forEach((_, i) => paint(i));

    let timer = null;
    const stop = () => {
        clearInterval(timer);
        timer = null;
    };
    const start = (id) => {
        stop();
        const { createGenerator } = ALGORITHMS.find((algorithm) => algorithm.id === id);
        const generator = createGenerator(spins, size, temperature);
        timer = setInterval(() => {
            for (const i of generator.next().value) paint(i);
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
