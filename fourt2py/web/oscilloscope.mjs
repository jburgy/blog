// Oscilloscope-style rendering: one period of the waveform traced with a
// phosphor-green glow on a dark CRT-like background. Point computation is
// separated from the actual canvas calls so it can be unit tested without a
// real `<canvas>`.

/** `[x, y]` pixel pairs tracing `samples` (each expected in [-1, 1]) across `width`x`height`. */
export function tracePoints(samples, width, height) {
    const n = samples.length;
    if (n < 2) return [];
    return Array.from({ length: n }, (_, i) => [
        (i / (n - 1)) * width,
        ((1 - samples[i]) / 2) * height,
    ]);
}

/**
 * Draw one oscilloscope frame on a 2D rendering context (real or a test
 * double exposing the same method names).
 */
export function drawOscilloscope(ctx, samples, options = {}) {
    const {
        width,
        height,
        color = '#39ff6a',
        background = '#00140a',
        lineWidth = 2,
    } = options;

    // A previous call may have left a glow (shadowBlur) active on the context;
    // reset it before filling, or the fill itself would pick up a green halo.
    ctx.shadowBlur = 0;
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, width, height);

    const points = tracePoints(samples, width, height);
    if (points.length === 0) return;

    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.shadowColor = color;
    ctx.shadowBlur = 8;
    ctx.beginPath();
    points.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
    ctx.stroke();
}
