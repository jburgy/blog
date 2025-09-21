import { defineConfig } from 'rolldown';

export default defineConfig([
    {
        input: '../xterm-pty/src/client-server/ttyClient.ts',
        output: { format: 'esm' },
    },
    {
        input: '../xterm-pty/src/client-server/ttyServer.ts',
        output: { format: 'esm' },
    },
]);