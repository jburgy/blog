// Snapshot the whole regexp.f demo mid-match: run the real Matcher/Forth JS
// against tabulate.traced.wast (see instrument.mjs), recording every NEXT
// during the first call of the compiled matcher.  INSTRUMENT=0 runs the
// shipped regexp/web/forth.wasm instead, for tiers and --print-wasm-code.
import fs from 'node:fs';
import wabtInit from 'wabt';

const BLOG = new URL('../../', import.meta.url);
const read = (path, enc = 'utf8') => fs.readFileSync(new URL(path, BLOG), enc);
const PATTERN = process.argv[2] ?? 'a(b|c)*d';
const TEXT = process.argv[3] ?? 'abccbcccd';
const INSTRUMENT = process.env.INSTRUMENT !== '0';

const src = read('regexp/tracing/tabulate.traced.wast');
const brTable = src.slice(src.indexOf('(br_table') + 9, src.indexOf('(i32.load (local.get $cfa)))', src.indexOf('(br_table')))
    .trim().split(/\s+/);
const wasm = INSTRUMENT
    ? (await wabtInit()).parseWat('tabulate.traced.wast', src, { multi_memory: true }).toBinary({}).buffer
    : read('regexp/web/forth.wasm', null);

let hook = () => {};
let instance;
const instantiate = WebAssembly.instantiate;
WebAssembly.instantiate = async (bytes, imports) => {
    const result = await instantiate(bytes, { ...imports, trace: { step: (...a) => hook(...a) } });
    instance = result.instance;
    return result;
};

const tierOf = new Function('f', 'return %IsTurboFanFunction(f) ? "TurboFan" : %IsLiftoffFunction(f) ? "Liftoff" : "uncompiled"');

const { Matcher } = await import(new URL('regexp/web/matcher.mjs', BLOG));
const { Forth } = await import(new URL('regexp/web/forth.mjs', BLOG));
const evals = [];
const evalOrig = Forth.prototype.eval;
Forth.prototype.eval = function (source) {
    const before = tierOf(instance.exports._start);
    const t = performance.now();
    const out = evalOrig.call(this, source);
    evals.push({ source: source.slice(0, 40).replace(/\s+/g, ' '), before, after: tierOf(instance.exports._start), ms: +(performance.now() - t).toFixed(2) });
    return out;
};
const preamble = read('forth/4th.32.fs');
const regexp = read('regexp/regexp.f');

const matcher = await Matcher.fromSources({ wasm, preamble, regexp, text: TEXT });
const start = instance.exports._start;
const tierBefore = tierOf(start);

const mem = () => new DataView(instance.exports.memory.buffer);
const u32 = (a) => mem().getUint32(a, true);
const i32 = (a) => mem().getInt32(a, true);

// Walk the dictionary.
function dictionary() {
    const words = [];
    for (let w = u32(0x5008); w; w = u32(w)) {
        const flags = mem().getUint8(w + 4);
        const len = flags & 0x1f;
        const name = new TextDecoder().decode(new Uint8Array(instance.exports.memory.buffer, w + 5, len));
        const cfa = (w + 5 + len + 3) & ~3;
        words.push({ addr: w, name, cfa, code: u32(cfa), hidden: !!(flags & 0x20) });
    }
    return words.sort((a, b) => a.addr - b.addr);
}
const varAddr = (words, name) => u32(words.findLast((w) => w.name === name).cfa + 8);

let words = dictionary();
const H0 = u32(varAddr(words, 'H0'));
const V = Object.fromEntries(['RE-POS', 'RE-CH', 'RE-N', 'RE-RSP', 'RE-P', 'RE-E'].map((n) => [n, varAddr(words, n)]));
const RE_NLIST = u32(words.findLast((w) => w.name === 'RE-NLIST').cfa + 8);
const RE_TXT = u32(words.findLast((w) => w.name === 'RE-TXT').cfa + 8);

let steps = [];
let run = 0;
let inR = false;
let jsStack = null;
let tierDuring = null;
let total = 0;
const rEnd = () => u32(0x5004);
const within = (a) => a >= H0 && a < rEnd();
const stack = (lo, hi) => { const out = []; for (let a = hi - 4; a >= lo; a -= 4) out.push(u32(a)); return out; }; // bottom first

hook = (cfa, ip, sp, rsp) => {
    total++;
    const rs = stack(rsp, 0x4000);
    const active = within(ip - 4) || rs.some(within);
    if (active && !inR) run++;
    inR = active;
    if (!active || run !== 1) return;
    if (!jsStack) {
        const limit = Error.stackTraceLimit; Error.stackTraceLimit = 50;
        jsStack = new Error().stack; Error.stackTraceLimit = limit;
        tierDuring = tierOf(start);
    }
    steps.push({
        cfa, ip, sp, rsp, ds: stack(sp, 0x2000), rs,
        pos: u32(V['RE-POS']), ch: u32(V['RE-CH']), n: u32(V['RE-N']),
        nlist: Array.from({ length: u32(V['RE-N']) }, (_, i) => u32(RE_NLIST + 4 * i)),
    });
};

const result = matcher.search(PATTERN);
hook = () => {};
const tierAfter = tierOf(start);
words = dictionary();
const R = words.findLast((w) => w.name === 'R');

const name = (a) => {
    const w = words.findLast((w) => w.addr <= a);
    if (!w) return `0x${a.toString(16)}`;
    return w === R ? `R+${a - R.cfa}` : `${w.name}+${a - w.cfa}`;
};

const body = [];
for (let a = R.cfa + 4; a < rEnd(); a += 4) {
    const v = i32(a);
    const w = words.find((w) => w.cfa === v);
    body.push({ off: a - R.cfa, addr: a, val: v, sym: w ? w.name : String(v) });
}

fs.writeFileSync(process.env.OUT ?? new URL('./out.json', import.meta.url), JSON.stringify({
    pattern: PATTERN, text: TEXT, result, instrumented: INSTRUMENT,
    tiers: { tierBefore, tierDuring, tierAfter }, evals, v8: process.versions.v8, node: process.version, arch: process.arch,
    total, stepsRun1: steps.length, H0, RE_TXT, RE_NLIST, V, R: { addr: R.addr, cfa: R.cfa, end: rEnd() },
    jsStack,
    body,
    steps: steps.map((s) => ({
        ...s,
        word: name(s.ip - 4),
        exec: (words.find((w) => w.cfa === s.cfa) ?? { name: `?${s.cfa}` }).name,
        prim: brTable[u32(s.cfa)],
        rsSym: s.rs.map(name),
    })),
}, null, 1));
