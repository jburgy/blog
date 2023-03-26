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

const trace = env.DEBUG ? console.trace : () => { };

function* tokenize(line) {
    for (const { groups } of line.matchAll(syntax)) {
        // captures are mutually exclusive, return the first defined one
        yield Object.entries(groups).find(([_, v]) => v !== undefined);
    }
    return null;
}

function AddList(token, tokens) {
    return new Cons(token, GetList(tokens));
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


function PrintList(x) {
    const parts = [PrintObject(Car(x))];
    while (x = Cdr(x)) {
        parts.push(x instanceof Cons ? ` ${PrintObject(Car(x))}` : ` ∙ ${PrintObject(x)}`)
    }
    return `(${parts.join('')})`
}

function PrintObject(x) {
    return x instanceof Cons ? PrintList(x) : typeof x === 'symbol' ? Symbol.keyFor(x) : String(null);
}

/*───────────────────────────────────────────────────────────────────────────│─╗
│ The LISP Challenge § Bootstrap John McCarthy's Metacircular Evaluator    ─╬─│┼
╚────────────────────────────────────────────────────────────────────────────│*/

function Car({ car }) {
    return car;
}

function Cdr({ cdr }) {
    return cdr;
}

class Cons {
    constructor(car, cdr) {
        this.car = car;
        this.cdr = cdr;
    }
}

function Evlis(m, a) {
    trace('Evlis', m, a);
    return m === null ? m : new Cons(Eval(Car(m), a), Evlis(Cdr(m), a));
}

function Pairlis(x, y, a) {
    trace('Pairlis', x, y, a);
    return x === null ? a : new Cons(new Cons(Car(x), Car(y)), Pairlis(Cdr(x), Cdr(y), a));
}

function Assoc(x, y) {
    trace('Assoc', x, y)
    return y === null
        ? null
        : x == Car(Car(y))
            ? Cdr(Car(y))
            : Assoc(x, Cdr(y));
}

function Evcon(c, a) {
    trace('Evcon', c, a)
    return Eval(Car(Car(c)), a)
        ? Eval(Car(Cdr(Car(c))), a)
        : Evcon(Cdr(c), a);
}

function Apply(f, x, a) {
    trace('Apply', f, x, a)
    switch (f) {
        case null: return null;
        case kEq: return Car(x) === Car(Cdr(x)) ? kT : null;
        case kCons: return new Cons(Car(x), Car(Cdr(x)));
        case kAtom: return x instanceof Cons ? null : kT;
        case kCar: return Car(Car(x));
        case kCdr: return Cdr(Car(x));
        case kRead: return Read();
        case kPrint:
            console.log(x === null ? '\n' : Car(x).toString())
            return null;
    }
    return f instanceof Cons
        ? Eval(Car(Cdr(Cdr(f))), Pairlis(Car(Cdr(f)), x, a))
        : Apply(Eval(f, a), x, a);
}

function Eval(e, a) {
    trace('Eval', e, a)
    return !(e instanceof Cons)
        ? Assoc(e, a)
        : Car(e) === kQuote
            ? Car(Cdr(e))
            : Car(e) === kCond
                ? Evcon(Cdr(e))
                : Apply(Car(e), Evlis(Cdr(e), a), a);
}

const rl = createInterface({ input, output });
rl.setPrompt('> ');
rl.on('line', (line) => {
    const result = Eval(Read(tokenize(line)), null);
    console.log(PrintObject(result));
    rl.prompt();
});
rl.prompt();
