import { defineConfig } from 'vitest/config';

export default defineConfig({
    resolve: {
        alias: {
            // wasi-worker.js imports uwasi from the esm.sh CDN rather than a
            // bare specifier (see its own comment for why); redirect that
            // back to the locally installed package for tests.
            'https://esm.sh/uwasi@1.6.0': 'uwasi',
        },
    },
});
