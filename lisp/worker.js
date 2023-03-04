importScripts("https://cdn.jsdelivr.net/npm/xterm-pty@0.9.4/workerTools.js");

// https://developer.mozilla.org/en-US/docs/Web/API/WorkerGlobalScope/self
// self.addEventListener("message", ...) looks less magic than onmessage = ... to me
self.addEventListener("message", (msg) => {
    const client = new TtyClient(msg.data);
    const buf = [];
    let firstByteRead = false;

    class EOF extends Error {};
    let getString;

    fetch(new URL("./build/release.wasm", location.origin))
        .then((response) => WebAssembly.instantiateStreaming(response, {
            index: {
                memory: new WebAssembly.Memory({ initial: 0o100000 }),
                getchar: () => {
                    if (buf.length == 0) {
                        if (firstByteRead)
                            return null;
                        buf.push(...client.onRead());
                    }
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
            env: {
                abort: (msg, file, line, column) => {
                    console.log("abort: " + getString(msg) + " at " + getString(file) + ":" + line + ":" + column);
                },
            },
        }))
        .then(({ instance }) => {
            const { exports: { main, memory } } = instance;

            getString = (ptr) => {
                if (!ptr) return "null";
                const U32 = new Uint32Array(exports.memory.buffer);
                const U16 = new Uint16Array(exports.memory.buffer);
                const len16 = U32[(ptr - 12) >>> 2] >>> 1; // TODO: old header
                const ptr16 = ptr >>> 1;
                return String.fromCharCode.apply(String, U16.subarray(ptr16, ptr16 + len16));
            }

            try {
                main(); 
            } catch (error) {
            };
        });
});