// Drives regexp/regexp.f from JavaScript.
//
// regexp.f compiles `RE" ..."` into a Forth word with the stack effect
// ( c-addr -- a ): a is the end of the leftmost match starting at c-addr, or
// 0.  SCAN (below) turns that into a sweep over the whole subject and prints
// one `start end` pair per match, which is all this module has to parse.

import { Forth } from './forth.mjs';

export const LOREM = [
    'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod',
    'tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim',
    'veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea',
    'commodo consequat. Duis aute irure dolor in reprehenderit in voluptate',
    'velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat',
    'cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id',
    'est laborum.',
].join(' ');

const SETUP = `
( Glue between regexp.f and the browser demo. )
2048 ALLOT CONSTANT RE-TXT

VARIABLE RE-XT
VARIABLE RE-P
VARIABLE RE-E

( The compiled matcher searches -- it answers where the leftmost match ENDS, )
( or 0 -- so RE-TRY at successive positions is also how we find where it began. )
: RE-TRY	( -- end )  RE-P @ RE-XT @ EXECUTE ;

(
	RE-SCAN prints the start and end offset of every match in RE-TXT.
	Advancing the start while the reported end stays put walks RE-P up to the
	first position that still reaches that end, which is the match itself.
	RE-P only ever moves forward, so the whole sweep costs O(n) matcher runs.
)
: RE-SCAN	( xt -- )
	RE-XT !
	RE-TXT RE-P !
	BEGIN RE-P @ C@ WHILE
		RE-TRY DUP RE-E ! 0= IF EXIT THEN	( nothing matches from here on )
		RE-E @ RE-P @ = IF
			1 RE-P +!			( empty match: step over it )
		ELSE
			BEGIN  1 RE-P +!  RE-TRY RE-E @ <>  UNTIL
			-1 RE-P +!
			RE-P @ RE-TXT - .
			RE-E @ RE-TXT - .
			RE-E @ RE-P !
		THEN
	REPEAT
;

( REWIND drops everything compiled after itself, so each query starts clean. )
VARIABLE H0
VARIABLE L0
: REWIND	( -- )  H0 @ HERE !  L0 @ LATEST ! ;
HERE @ H0 !  LATEST @ L0 !
`;

const MAX_PATTERN = 48;

/** @returns {string|null} why `pattern` is unusable, or null when it is fine. */
export function validate(pattern) {
    if (!pattern) return 'empty pattern';
    if (pattern.length > MAX_PATTERN) return `pattern longer than ${MAX_PATTERN} characters`;
    if (!/^[\x20-\x7e]*$/.test(pattern)) return 'only printable ASCII is supported';
    if (pattern.includes('"')) return 'a double quote would end the RE" literal';

    let depth = 0;
    let previous = '|';
    for (let i = 0; i < pattern.length; i++) {
        const c = pattern[i];
        if (c === '\\') {
            if (i + 1 === pattern.length) return 'trailing backslash';
            i++;
            previous = 'a';
            continue;
        }
        if (c === '(') depth++;
        else if (c === ')') {
            if (--depth < 0) return 'unbalanced parentheses';
            if (previous === '(' || previous === '|') return 'empty group';
        } else if (c === '*' && (previous === '(' || previous === '|' || previous === '*')) {
            return 'nothing for * to repeat';
        } else if (c === '|' && (previous === '(' || previous === '|')) {
            return 'empty alternative';
        }
        previous = c;
    }
    if (depth !== 0) return 'unbalanced parentheses';
    if (previous === '|') return 'empty alternative';
    return null;
}

/** Wrap `text` ranges in <mark>, escaping everything else. */
export function highlight(text, ranges) {
    const escape = (s) => s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]);
    let html = '';
    let at = 0;
    for (const [start, end] of ranges) {
        html += escape(text.slice(at, start));
        html += `<mark>${escape(text.slice(start, end))}</mark>`;
        at = end;
    }
    return html + escape(text.slice(at));
}

export class Matcher {
    #forth;
    #address;

    constructor(forth, address, text) {
        this.#forth = forth;
        this.#address = address;
        this.text = text;
    }

    static async create({ text = LOREM, base = import.meta.url } = {}) {
        const url = (path) => new URL(path, base);
        const [wasm, preamble, regexp] = await Promise.all([
            fetch(url('./forth.wasm')).then((r) => r.arrayBuffer()),
            fetch(url('../../forth/4th.32.fs')).then((r) => r.text()),
            fetch(url('../regexp.f')).then((r) => r.text()),
        ]);
        return Matcher.fromSources({ wasm, preamble, regexp, text });
    }

    static async fromSources({ wasm, preamble, regexp, text = LOREM }) {
        const forth = await Forth.instantiate(wasm);
        forth.eval(preamble);
        forth.eval(regexp);
        forth.eval(SETUP);

        const address = Number.parseInt(forth.eval('RE-TXT .').trim(), 10);
        if (!Number.isInteger(address)) throw new Error('could not locate the subject buffer');

        const bytes = new TextEncoder().encode(text);
        if (bytes.some((b) => b > 0x7f)) throw new Error('subject text must be ASCII');
        forth.poke(address, bytes);
        return new Matcher(forth, address, text);
    }

    /**
     * @returns {{ranges: [number, number][], error: string|null}}
     */
    search(pattern) {
        const error = validate(pattern);
        if (error) return { ranges: [], error };

        const output = this.#forth.eval(`REWIND : R RE" ${pattern}" ; LATEST @ >CFA RE-SCAN`);
        if (!/^[\s\d]*$/.test(output)) return { ranges: [], error: output.trim() };

        const numbers = (output.match(/\d+/g) ?? []).map(Number);
        const ranges = [];
        for (let i = 0; i + 1 < numbers.length; i += 2) ranges.push([numbers[i], numbers[i + 1]]);
        return { ranges, error: null };
    }
}
