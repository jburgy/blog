// Tiny assertions, so the browser tests need nothing but mocha itself.

export function ok(value, message = 'expected a truthy value') {
    if (!value) throw new Error(message);
}

export function equal(actual, expected, message) {
    if (actual !== expected) {
        throw new Error(message ?? `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    }
}

export function deepEqual(actual, expected, message) {
    const a = JSON.stringify(actual);
    const b = JSON.stringify(expected);
    if (a !== b) throw new Error(message ?? `expected ${b}, got ${a}`);
}
