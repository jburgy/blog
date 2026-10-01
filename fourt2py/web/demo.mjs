// DOM wiring for the FOURT.F demo: a draggable frequency-domain chart feeds
// FOURT's inverse transform, whose output drives an oscilloscope-style
// canvas and the Web Audio API. Kept out of index.html so it stays testable.

import { N, HARMONICS, DEFAULT_AMPLITUDES, buildSpectrum, normalizedWaveform } from './spectrum.mjs';
import { createChart, attachChart } from './chart.mjs';
import { drawOscilloscope } from './oscilloscope.mjs';
import { Fourt } from './fourt.mjs';

const NOMINAL_SAMPLE_RATE = 44100;
const frequencyLabel = (k, sampleRate = NOMINAL_SAMPLE_RATE) => `${Math.round((k * sampleRate) / N)} Hz`;

const MARKUP = `
<div class="scope-wrap">
	<canvas data-role="scope" width="640" height="220" aria-label="oscilloscope trace"></canvas>
</div>
<div class="chart-wrap" data-role="chart-slot"></div>
<div class="controls">
	<button type="button" data-role="play">Play</button>
	<span class="status" data-role="status"></span>
</div>
`;

export function createPanel(document) {
    const panel = document.createElement('section');
    panel.className = 'panel';
    panel.innerHTML = MARKUP;
    return panel;
}

/**
 * Wire `panel` up: drag knots -> FOURT inverse transform -> oscilloscope + audio.
 * Returns a controller so tests can drive it without synthesizing real pointer events.
 */
export async function attach(panel, { fourt = null } = {}) {
    const engine = fourt ?? (await Fourt.instantiate());
    const amplitudes = DEFAULT_AMPLITUDES.slice();

    const labels = HARMONICS.map((k) => frequencyLabel(k));
    const chart = createChart(panel.ownerDocument ?? document, labels);
    panel.querySelector('[data-role="chart-slot"]').append(chart.svg);

    const canvas = panel.querySelector('[data-role="scope"]');
    const ctx = canvas.getContext('2d');
    const playButton = panel.querySelector('[data-role="play"]');
    const status = panel.querySelector('[data-role="status"]');

    let samples = new Float64Array(N);
    let audioCtx = null;
    let source = null;

    // The waveform is periodic and only changes when a knot moves, so a real
    // oscilloscope locked to that period would look static too -- redraw once
    // per change rather than looping requestAnimationFrame over an unchanged
    // trace (which would also have to re-fade a persistence trail every frame
    // for no visual benefit).
    const draw = () => {
        drawOscilloscope(ctx, samples, { width: canvas.width, height: canvas.height, background: '#00140a' });
    };

    // Whether a looping AudioBuffer's data is re-read after `start()` if it's
    // mutated in place is implementation-defined, so a knot change restarts
    // playback on a fresh buffer instead of relying on that.
    const startSource = () => {
        const buffer = audioCtx.createBuffer(1, N, audioCtx.sampleRate);
        buffer.getChannelData(0).set(samples);
        source = audioCtx.createBufferSource();
        source.buffer = buffer;
        source.loop = true;
        source.connect(audioCtx.destination);
        source.start();
    };

    const recompute = () => {
        const spectrum = buildSpectrum(amplitudes, HARMONICS, N);
        samples = normalizedWaveform(engine.transform(spectrum, N));
        if (source) {
            source.stop();
            startSource();
        }
        draw();
    };
    recompute();

    attachChart(chart, amplitudes, recompute);

    const play = () => {
        if (!audioCtx) {
            const AudioContextClass = globalThis.AudioContext ?? globalThis.webkitAudioContext;
            audioCtx = new AudioContextClass();
            for (const [i, k] of HARMONICS.entries()) {
                chart.knots[i].text.textContent = frequencyLabel(k, audioCtx.sampleRate);
            }
        }
        startSource();
        playButton.textContent = 'Stop';
        status.textContent = `playing ${Math.round(audioCtx.sampleRate / N)} Hz fundamental`;
    };

    const stop = () => {
        source?.stop();
        source = null;
        playButton.textContent = 'Play';
        status.textContent = '';
    };

    playButton.addEventListener('click', () => (source ? stop() : play()));

    return { amplitudes, recompute, play, stop, get samples() { return samples; } };
}
