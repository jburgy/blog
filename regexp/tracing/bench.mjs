// Time one full search (compile R + RE-SCAN) on the shipped, uninstrumented forth.wasm.
import fs from 'node:fs';
const BLOG = new URL('../../', import.meta.url);
const read = (path, enc = 'utf8') => fs.readFileSync(new URL(path, BLOG), enc);
const { Matcher } = await import(new URL('regexp/web/matcher.mjs', BLOG));
const m = await Matcher.fromSources({
  wasm: read('regexp/web/forth.wasm', null),
  preamble: read('forth/4th.32.fs'),
  regexp: read('regexp/regexp.f'),
  text: process.argv[2] ?? 'abccbcccd',
});
for (let i = 0; i < 200; i++) m.search('a(b|c)*d');
const N = 5000, t = performance.now();
for (let i = 0; i < N; i++) m.search('a(b|c)*d');
console.log(((performance.now() - t) / N * 1000).toFixed(1), 'us per search', JSON.stringify(m.search('a(b|c)*d')));
