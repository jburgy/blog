import { attach, createPanel } from '../demo.mjs';
import { Matcher } from '../matcher.mjs';
import { deepEqual, equal, ok } from './assert.mjs';

const SUBJECT = 'Lorem ipsum dolor sit amet, dolor dolor';

describe('demo panel', () => {
    let matcher;
    let panel;
    let ui;

    before(async function boot() {
        this.timeout(60000);
        matcher = await Matcher.create({ text: SUBJECT });
    });

    beforeEach(async () => {
        panel = createPanel(document);
        document.body.append(panel);
        ui = await attach(panel, { matcher });
    });

    afterEach(() => panel.remove());

    const marks = () => [...panel.querySelectorAll('mark')].map((mark) => mark.textContent);
    const submit = () => panel.querySelector('form').requestSubmit();

    it('shows the subject text before any query', () => {
        equal(ui.subject.textContent, SUBJECT);
        deepEqual(marks(), []);
    });

    it('highlights the matches when the form is submitted', () => {
        ui.input.value = 'dolor';
        submit();
        deepEqual(marks(), ['dolor', 'dolor', 'dolor']);
        equal(panel.dataset.state, 'match');
        ok(/^3 matches in /.test(ui.status.textContent), ui.status.textContent);
    });

    it('keeps the unmatched text intact', () => {
        ui.input.value = 'do(l|r)';
        submit();
        equal(ui.subject.textContent, SUBJECT);
        deepEqual(marks(), ['dol', 'dol', 'dol']);
    });

    it('says so when nothing matches', () => {
        ui.input.value = 'xyzzy';
        submit();
        deepEqual(marks(), []);
        equal(panel.dataset.state, 'empty');
        ok(ui.status.textContent.startsWith('no matches'), ui.status.textContent);
    });

    it('reports an unusable pattern without touching the text', () => {
        ui.input.value = '(a|b';
        submit();
        equal(panel.dataset.state, 'error');
        equal(ui.status.textContent, 'unbalanced parentheses');
        equal(ui.subject.textContent, SUBJECT);
    });

    it('clears the highlighting for an empty pattern', () => {
        ui.input.value = 'dolor';
        submit();
        ui.input.value = '   ';
        submit();
        deepEqual(marks(), []);
        equal(panel.dataset.state, 'idle');
        equal(ui.status.textContent, '');
    });
});
