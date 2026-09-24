import { LOREM, Matcher, highlight, validate } from '../matcher.mjs';
import { deepEqual, equal, ok } from './assert.mjs';

const SUBJECT = 'Lorem ipsum dolor sit amet, dolor dolor';

describe('validate', () => {
    it('accepts the syntax from the paper', () => {
        for (const pattern of ['a', 'abcdefg', '(a|b)*a', 'a(b|c)*d', 'a*', '(a*b*)*c', 'a\\*b']) {
            equal(validate(pattern), null, `${pattern} should be valid`);
        }
    });

    it('rejects patterns regexp.f cannot compile', () => {
        ok(validate(''));
        ok(validate('(a'));
        ok(validate('a)'));
        ok(validate('*a'));
        ok(validate('(|a)'));
        ok(validate('a|'));
        ok(validate('a\\'));
        ok(validate('a"b'));
        ok(validate('a'.repeat(200)));
    });
});

describe('highlight', () => {
    it('wraps the given ranges and leaves the rest alone', () => {
        equal(highlight('abcd', [[1, 3]]), 'a<mark>bc</mark>d');
        equal(highlight('abcd', []), 'abcd');
        equal(highlight('abcd', [[0, 1], [3, 4]]), '<mark>a</mark>bc<mark>d</mark>');
    });

    it('escapes markup in both the matched and unmatched text', () => {
        equal(highlight('<a&b>', [[0, 2]]), '<mark>&lt;a</mark>&amp;b&gt;');
    });
});

describe('Matcher', () => {
    let matcher;
    let lorem;

    before(async function boot() {
        this.timeout(60000);
        matcher = await Matcher.create({ text: SUBJECT });
        lorem = await Matcher.create();
    });

    it('serves the text it was given', () => {
        equal(matcher.text, SUBJECT);
        equal(lorem.text, LOREM);
    });

    it('finds every occurrence of a literal', () => {
        deepEqual(matcher.search('dolor').ranges, [[12, 17], [28, 33], [34, 39]]);
    });

    it('compiles alternation and grouping', () => {
        deepEqual(matcher.search('do(l|r)').ranges, [[12, 15], [28, 31], [34, 37]]);
        deepEqual(matcher.search('l(a|o)r').ranges, [[14, 17], [30, 33], [36, 39]]);
    });

    it('compiles closure', () => {
        deepEqual(matcher.search('do*l').ranges, [[12, 15], [28, 31], [34, 37]]);
    });

    it('reports no ranges when nothing matches', () => {
        deepEqual(matcher.search('xyzzy').ranges, []);
    });

    it('agrees with the platform RegExp on unambiguous patterns', () => {
        for (const pattern of ['dolor', 'ut', 'ex', 'qq', 'do(l|r)', 'e(x|s)']) {
            const mine = lorem.search(pattern).ranges;
            const native = [...LOREM.matchAll(new RegExp(pattern, 'g'))].map((m) => [m.index, m.index + m[0].length]);
            deepEqual(mine, native, `${pattern}: ${JSON.stringify(mine)} vs ${JSON.stringify(native)}`);
        }
    });

    it('returns non-overlapping ranges in order', () => {
        let previous = 0;
        for (const [start, end] of lorem.search('(a|e|i|o|u)(a|e|i|o|u)').ranges) {
            ok(start >= previous, `${start} overlaps the previous match`);
            ok(end > start, 'ranges must be non-empty');
            previous = end;
        }
    });

    it('surfaces validation errors instead of compiling them', () => {
        const { ranges, error } = matcher.search('(a');
        deepEqual(ranges, []);
        equal(error, 'unbalanced parentheses');
    });

    it('stays usable after an error, because REWIND undoes the query', () => {
        matcher.search('(a');
        deepEqual(matcher.search('dolor').ranges, [[12, 17], [28, 33], [34, 39]]);
    });

    it('does not leak dictionary space across queries', () => {
        const first = matcher.search('ipsum').ranges;
        for (let i = 0; i < 40; i++) matcher.search('(a|b|c|d|e)*dolor');
        deepEqual(matcher.search('ipsum').ranges, first);
    });
});
