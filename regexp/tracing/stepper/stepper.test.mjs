// node stepper.test.mjs -- fails if a definition's PARSE ERROR is dropped from `output`.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import wabtInit from 'wabt';
import { record } from './stepper.mjs';

const read = (p, enc) => fs.readFileSync(new URL(p, import.meta.url), enc);
const wasm = (await wabtInit())
    .parseWat('traced.wast', read('../tabulate.traced.wast', 'utf8'), { multi_memory: true }).toBinary({}).buffer;
const preamble = read('../../../jonesforth/jonesforth.f', 'utf8');

const ok = await record(wasm, preamble, ': FACT DUP 1 > IF DUP 1- RECURSE * THEN ;', '5 FACT .');
assert.match(ok.output, /^120 $/);

const bad = await record(wasm, preamble, ': FACT DUP 1 > IF DUP 1- FACT * THEN ;', '5 FACT .');
assert.match(bad.output, /PARSE ERROR: FACT/);
console.log('ok');
