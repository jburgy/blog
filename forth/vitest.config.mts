import { defineConfig } from 'vitest/config';

export default defineConfig({
    resolve: {
        alias: {
            // wasi-command.js imports uwasi from the esm.sh CDN rather than a
            // bare specifier (the blog serves plain ES modules, no import
            // map); redirect that back to the locally installed package.
            'https://esm.sh/uwasi@1.6.0': 'uwasi',
        },
    },
    test: {
        // wasi-command.js needs JSPI, still behind a flag in Node.
        execArgv: ['--experimental-wasm-jspi'],
        coverage: {
            reporter: ['text', 'lcov'],
        },
    },
});
