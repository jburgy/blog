// node stepper.test.mjs -- fails if a definition's PARSE ERROR is dropped from `output`,
// a number on the return stack breaks `label`, or a runaway loop is not cut off.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import wabtInit from 'wabt';
import { record, label } from './stepper.mjs';

const read = (p, enc) => fs.readFileSync(new URL(p, import.meta.url), enc);
const wasm = (await wabtInit())
    .parseWat('traced.wast', read('../tabulate.traced.wast', 'utf8'), { multi_memory: true }).toBinary({}).buffer;
const preamble = read('../../../jonesforth/jonesforth.f', 'utf8');

const ok = await record(wasm, preamble, ': FACT DUP 1 > IF DUP 1- RECURSE * THEN ;', '5 FACT .');
assert.match(ok.output, /^120 $/);

const bad = await record(wasm, preamble, ': FACT DUP 1 > IF DUP 1- FACT * THEN ;', '5 FACT .');
assert.match(bad.output, /PARSE ERROR: FACT/);

// `>R` parks a plain number on the return stack, which no word contains.
const parked = await record(wasm, preamble, ': PARK 7 >R R> . ;', 'PARK');
const cells = parked.steps.flatMap((s) => s.rs);
assert.ok(cells.includes(7));
assert.equal(label(parked.words, 7), '7');
assert.match(label(parked.words, parked.steps[0].ip), /^PARK\+\d+$/);

const runaway = await record(wasm, preamble, ': SPIN BEGIN 0 UNTIL ;', 'SPIN');
assert.ok(runaway.truncated);
assert.ok(runaway.steps.length > 0);
console.log('ok');
