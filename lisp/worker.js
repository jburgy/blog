importScripts("https://cdn.jsdelivr.net/npm/xterm-pty@0.9.4/workerTools.js");

// https://developer.mozilla.org/en-US/docs/Web/API/WorkerGlobalScope/self
// self.addEventListener("message", ...) looks less magic than onmessage = ... to me
self.addEventListener("message", (msg) => {
    const client = new TtyClient(msg.data);
    const buf = [];

    class EOF extends Error {};

    fetch(new URL("./build/debug.wasm", location.origin))
        .then((response) => WebAssembly.instantiateStreaming(response, {
            index: {
                getchar: () => {
                    if (buf.length == 0)
                        buf.push(...client.onRead());
                    const c = buf.shift();
                    if (c < 0)
                        throw new EOF();
                    firstByteRead = true;
                    return c < 128 ? c : c - 256;
                },
                putchar: (val) => {
                    client.onWrite([(val + 256) % 256])
                },
            },
        }))
        .then(({ instance }) => {
            const { exports: { main, memory } } = instance;

            memory.grow(1);

            const M = new DataView(memory.buffer);
            Array.from("NIL\0T\0QUOTE\0COND\0READ\0PRINT\0ATOM\0CAR\0CDR\0CONS\0EQ")
                .forEach((s, i) => M.setUint8(0x8000 | i, s.codePointAt(0)));

            try {
                main(); 
            } catch (error) {
                console.error(error);
            };
        });
});