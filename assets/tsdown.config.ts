export default {
    entry: [
        "../xterm-pty/src/client-server/ttyClient.ts",
        "../xterm-pty/src/client-server/ttyServer.ts",
    ],
    minify: false,
    sourcemap: false,
    clean: true,
    outDir: "dist",
    dts: true,
    format: "esm",
    target: false,
};