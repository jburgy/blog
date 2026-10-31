// Record every NEXT of a Forth expression on the instrumented interpreter
// (../tabulate.traced.wast), so a UI can scrub back and forth through it.
import { Forth } from '../../web/forth.mjs';

const LATEST = 0x5008;
const HERE = 0x5004;
const DSTACK_TOP = 0x2000;
const RSTACK_TOP = 0x4000;
// Runaway loops (`BEGIN 0 UNTIL`) would otherwise record forever.
const MAX_NEXTS = 200_000;
const LIMIT = Symbol('step limit');

/** Dictionary entries, oldest first: { addr, name, cfa }. */
function dictionary(dv, bytes) {
    const words = [];
    for (let w = dv.getUint32(LATEST, true); w; w = dv.getUint32(w, true)) {
        const len = dv.getUint8(w + 4) & 0x1f;
        const name = new TextDecoder().decode(bytes.subarray(w + 5, w + 5 + len));
        words.push({ addr: w, name, cfa: (w + 5 + len + 3) & ~3 });
    }
    return words.reverse();
}

/**
 * Compile `definition`, then run `expression` and record each NEXT that executes
 * inside the code `definition` compiled. Gives up after MAX_NEXTS NEXTs of any
 * kind and flags `truncated`; `output` is then only what `definition` printed.
 * @returns {{ steps, words, output, truncated, lo, hi, dv }}
 */
export async function record(wasm, preamble, definition, expression) {
    let hook = () => {};
    const forth = await Forth.instantiate(wasm, { trace: { step: (...a) => hook(...a) } });
    const dv = () => new DataView(forth.memory.buffer);
    const bytes = () => new Uint8Array(forth.memory.buffer);
    const u32 = (a) => dv().getUint32(a, true);
    const stack = (lo, top) => Array.from({ length: (top - lo) / 4 }, (_, i) => dv().getInt32(top - 4 * (i + 1), true));

    forth.eval(preamble);
    const lo = u32(HERE);
    const compiled = forth.eval(definition); // carries PARSE ERROR lines
    const hi = u32(HERE);
    const words = dictionary(dv(), bytes());

    const within = (a) => a >= lo && a < hi;
    const steps = [];
    let nexts = 0;
    hook = (cfa, ip, sp, rsp) => {
        if (++nexts > MAX_NEXTS) throw LIMIT;
        const rs = stack(rsp, RSTACK_TOP);
        if (within(ip - 4) || rs.some(within)) steps.push({ cfa, ip: ip - 4, ds: stack(sp, DSTACK_TOP), rs });
    };
    let output = compiled;
    let truncated = false;
    try {
        output += forth.eval(expression);
    } catch (error) {
        if (error !== LIMIT) throw error;
        truncated = true;
    }
    hook = () => {};

    return { steps, words, output, truncated, lo, hi, dv: dv() };
}

/** The word whose body contains `addr`, with the offset in cells. */
export function locate(words, addr) {
    const w = words.findLast((w) => w.addr <= addr);
    return w ? { word: w, cell: (addr - w.cfa) / 4 } : null;
}

/** `locate` as text; return-stack cells hold plain numbers too (`>R`), shown as is. */
export function label(words, addr) {
    const l = locate(words, addr);
    return l ? `${l.word.name}+${l.cell}` : String(addr);
}

/** Body of `word` decoded cell by cell: { addr, text, literal }. */
export function disassemble(rec, word) {
    const next = rec.words.find((w) => w.addr > word.addr)?.addr ?? rec.hi;
    const byCfa = new Map(rec.words.map((w) => [w.cfa, w.name]));
    const out = [];
    let operand = false;
    for (let a = word.cfa + 4; a < next; a += 4) {
        const v = rec.dv.getInt32(a, true);
        const name = byCfa.get(v);
        out.push({ addr: a, text: operand || !name ? String(v) : name, literal: operand || !name });
        operand = !operand && (name === 'LIT' || name === 'BRANCH' || name === '0BRANCH');
    }
    return out;
}
