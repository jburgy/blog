importScripts("https://cdn.jsdelivr.net/npm/xterm-pty@0.9.4/workerTools.js");

// https://developer.mozilla.org/en-US/docs/Web/API/WorkerGlobalScope/self
// self.addEventListener("message", ...) looks less magic than onmessage = ... to me
self.addEventListener("message", (msg) => {
    importScripts(new URL("./TinyBasic.js", location.origin));

    emscriptenHack(new TtyClient(msg.data));
});