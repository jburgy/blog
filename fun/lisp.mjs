/*
    A LISP in Node.js in preparation for a LOGO in browser

    This borrows heavily from https://github.com/jart/sectorlisp/blob/main/lisp.c
    except it leverages the v8 runtime for RegExp, Symbol, and classes (Cons)
*/

import { readSync, writeSync } from 'node:fs';

const kT = Symbol.for('T');
const kQuote = Symbol.for('QUOTE');
const kCond = Symbol.for('COND');
const kRead = Symbol.for('READ');
const kPrint = Symbol.for('PRINT');
const kAtom = Symbol.for('ATOM');
const kCar = Symbol.for('CAR');
const kCdr = Symbol.for('CDR');
const kCons = Symbol.for('CONS');
const kEq = Symbol.for('EQ');

const syntax = new RegExp(Object.entries(
    {
        LEFT_PAREN: /\(/,
        RIGHT_PARENT: /\)/,
        SYMBOL: /[^\s()]+/,
    }
).map(([name, { source }]) => `(?<${name}>${source})`).join('|'), 'g');

const trace = process.env.DEBUG ? console.log : () => { };

function* tokenize(line) {
    for (const { groups } of line.matchAll(syntax)) {
        // captures are mutually exclusive, return the first defined one
        yield Object.entries(groups).find(([_, v]) => v !== undefined);
    }
    return null;
}

function AddList(token, tokens) {
    return Cons(token, GetList(tokens));
}

function GetList(tokens) {
    const { done, value } = tokens.next();
    return done
        ? value
        : value[0] == 'RIGHT_PARENT'
            ? null
            : AddList(GetObject(value, tokens), tokens);
}

function GetObject([type, value], tokens) {
    switch (type) {
        case 'LEFT_PAREN': return GetList(tokens);
        case 'SYMBOL': return value === 'NIL' ? null : Symbol.for(value);
    }
    throw new Error(`Unexpected token: ${type}`);
}

function Read(tokens) {
    const { done, value } = tokens.next();
    return done ? process.exit() : GetObject(value, tokens);
}


function PrintObject(x) {
    return x === null
        ? 'NIL'
        : Array.isArray(x)
            ? `(${x.map(PrintObject).join(' ')})`
            : Symbol.keyFor(x);
}

/*───────────────────────────────────────────────────────────────────────────│─╗
│ The LISP Challenge § Bootstrap John McCarthy's Metacircular Evaluator    ─╬─│┼
╚────────────────────────────────────────────────────────────────────────────│*/

function Car(x) {
    return x?.[0] ?? null;
}

function Cdr(x) {
    return x?.length > 1 ? x.slice(1) : null;
}

function Cons(x, y) {
    return Array.isArray(y) ? [x, ...y] : [x];
}

function Pairlis(x, y, a) {
    trace('Pairlis', x, y, a);
    const m = new Map(a.entries());
    x?.forEach((key, i) => m.set(key, y?.[i] ?? null))
    return m;
}

function Assoc(x, y) {
    trace('Assoc', x, y);
    return y.has(x) ? y.get(x) : null;
}

function Evcon(c, a) {
    trace('Evcon', c, a);
    return Eval(Car(Cdr(c.find(x => Eval(Car(x), a)))), a);
}

function Apply(f, x, a) {
    trace('Apply', f, x, a)
    switch (f) {
        case null: return null;
        case kEq: return Car(x) === Car(Cdr(x)) ? kT : null;
        case kCons: return Cons(Car(x), Car(Cdr(x)));
        case kAtom: return Array.isArray(Car(x)) ? null : kT;
        case kCar: return Car(Car(x));
        case kCdr: return Cdr(Car(x));
        case kRead: return Read(tokens);
        case kPrint:
            writeSync(1, x ? PrintObject(Car(x)) : '\n');
            return null;
    }
    return Array.isArray(f)
        ? Eval(Car(Cdr(Cdr(f))), Pairlis(Car(Cdr(f)), x, a))
        : Apply(Eval(f, a), x, a);
}

function Eval(e, a) {
    trace('Eval', e, a)
    return !Array.isArray(e)
        ? Assoc(e, a)
        : Car(e) === kQuote
            ? Car(Cdr(e))
            : Car(e) === kCond
                ? Evcon(Cdr(e), a)
                : Apply(Car(e), Cdr(e)?.map(x => Eval(x, a)) ?? null, a);
}

// Like core.ts, a stream of expressions: they may span lines and (READ) takes the next one. Blocking
// reads rather than process.stdin keep Eval synchronous; on a TTY each Enter delivers one line.
// Output goes through writeSync too, and `process` is the global, not `import ... from 'node:process'`:
// either one constructs process.stdin/stdout, which makes a shared TTY non-blocking so readSync fails with EAGAIN.
function* readTokens() {
    const buf = Buffer.alloc(4096);
    const decoder = new TextDecoder();
    let pending = '';
    for (let n; (n = readSync(0, buf)) > 0;) {
        pending += decoder.decode(buf.subarray(0, n), { stream: true });
        const lines = pending.split('\n');
        pending = lines.pop();
        for (const line of lines) yield* tokenize(line);
    }
    yield* tokenize(pending);
}

const tokens = readTokens();
for (let t; writeSync(1, '* '), !(t = tokens.next()).done;) {
    writeSync(1, `${PrintObject(Eval(GetObject(t.value, tokens), new Map()))}\n`);
}
