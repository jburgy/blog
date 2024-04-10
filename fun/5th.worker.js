importScripts("https://cdn.jsdelivr.net/npm/xterm-pty@0.9.4/workerTools.js");

// https://developer.mozilla.org/en-US/docs/Web/API/WorkerGlobalScope/self
// self.addEventListener("message", ...) looks less magic than onmessage = ... to me
self.addEventListener("message", (msg) => {
    importScripts(location.origin + "/5th.js");

    emscriptenHack(new TtyClient(msg.data));
});