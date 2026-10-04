// Node has no import maps: resolves the `https://esm.sh/uwasi@1.6.0`
// specifier wasi-worker.js uses (see its own comment for why) back to the
// locally installed package, the same way vitest.config.ts's alias does for
// the in-process tests. Registered via `--import` (see wasi-worker.test.ts)
// for the child-process fixture, which runs as plain `node`, not vitest.
export async function resolve(specifier, context, nextResolve) {
    if (specifier === 'https://esm.sh/uwasi@1.6.0') {
        return nextResolve('uwasi', context);
    }
    return nextResolve(specifier, context);
}
