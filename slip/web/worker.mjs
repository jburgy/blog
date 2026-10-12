// Loads slip.wasm (see src/web.rs) and answers one message per statement.
const ready = WebAssembly.instantiateStreaming(fetch(new URL("slip.wasm", import.meta.url)))
	.then(({ instance }) => instance.exports);
const encoder = new TextEncoder();
const decoder = new TextDecoder();

// Registered synchronously: messages sent while the module loads would be lost after a top-level await.
self.addEventListener("message", async ({ data }) => {
	const { memory, alloc, say, reply_len } = await ready;
	const bytes = encoder.encode(data);
	const input = alloc(bytes.length);
	new Uint8Array(memory.buffer, input, bytes.length).set(bytes);
	const reply = say(input, bytes.length);
	self.postMessage(decoder.decode(new Uint8Array(memory.buffer, reply, reply_len())));
});
