/*
    A LISP in Node.js in preparation for a LOGO in browser

    This borrows heavily from https://github.com/jart/sectorlisp/blob/main/lisp.c
    except it leverages the v8 runtime for RegExp, Symbol, and classes (Cons)
*/

import { createInterface } from 'node:readline';
import { env, stdin as input, stdout as output } from 'node:process';

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
        NUMBER: /-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/,
        SYMBOL: /[a-zA-Z]\w*/,
    }
).map(([name, { source }]) => `(?<${name}>${source})`).join('|'), 'g');

const trace = env.DEBUG ? console.log : () => { };

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
        case 'NUMBER': return parseFloat(value);
        case 'SYMBOL': return Symbol.for(value);
    }
    throw new Error(`Unexpected token: ${type}`);
}

function Read(tokens) {
    const { done, value } = tokens.next();
    return done ? value : GetObject(value, tokens);
}


function PrintObject(x) {
    return Array.isArray(x)
        ? `(${x.map(PrintObject).join(' ')})`
        : typeof x === 'symbol'
            ? Symbol.keyFor(x)
            : String(null);
}

/*───────────────────────────────────────────────────────────────────────────│─╗
│ The LISP Challenge § Bootstrap John McCarthy's Metacircular Evaluator    ─╬─│┼
╚────────────────────────────────────────────────────────────────────────────│*/

function Car(x) {
    return x[0];
}

function Cdr(x) {
    return x.slice(1);
}

function Cons(x, y) {
    return Array.isArray(y) ? [x, ...y] : [x];
}

function Pairlis(x, y, a) {
    trace('Pairlis', x, y, a);
    const m = new Map(a.entries());
    console.log(x, y);
    x.forEach((key, i) => m.set(key, y[i]))
    return m;
}

function Assoc(x, y) {
    trace('Assoc', x, y);
    return y.has(x) ? y.get(x) : [];
}

function Evcon(c, a) {
    trace('Evcon', c, a);
    return Eval(Cdr(c.find(x => Eval(Car(x), a))), a);
}

function Apply(f, x, a) {
    trace('Apply', f, x, a)
    switch (f) {
        case null: return null;
        case kEq: return Car(x) === Car(Cdr(x)) ? kT : null;
        case kCons: return Cons(Car(x), Car(Cdr(x)));
        case kAtom: return Array.isArray(x) ? null : kT;
        case kCar: return Car(Car(x));
        case kCdr: return Cdr(Car(x));
        case kRead: return Read();  /* FIXME: needs token generator */
        case kPrint:
            console.log(PrintObject(x))
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
                : Apply(Car(e), Cdr(e).map(x => Eval(x, a)), a);
}

const rl = createInterface({ input, output });
rl.setPrompt('> ');
rl.on('line', (line) => {
    const result = Eval(Read(tokenize(line)), new Map());
    console.log(PrintObject(result));
    rl.prompt();
});
rl.prompt();
