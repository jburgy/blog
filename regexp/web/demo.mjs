// DOM wiring for the regexp.f demo, kept out of index.html so the browser
// tests can mount the same panel and drive it.

import { Matcher, highlight } from './matcher.mjs';

const MARKUP = `
<form class="query" data-role="query">
	<label class="query__label">
		<span>Regular expression</span>
		<input type="text" data-role="pattern" autocomplete="off" autocapitalize="off"
			spellcheck="false" placeholder="(a|b)*ab" aria-describedby="re-status">
	</label>
	<button type="submit">Match</button>
</form>
<p class="status" id="re-status" data-role="status" role="status"></p>
<div class="subject" data-role="subject"></div>
`;

export function createPanel(document) {
    const panel = document.createElement('section');
    panel.className = 'panel';
    panel.innerHTML = MARKUP;
    return panel;
}

/**
 * Wire `panel` up to a Matcher.  Returns the panel's controller so tests can
 * call `run()` directly instead of synthesising key events.
 */
export async function attach(panel, { matcher = null } = {}) {
    const engine = matcher ?? (await Matcher.create());
    const form = panel.querySelector('[data-role="query"]');
    const input = panel.querySelector('[data-role="pattern"]');
    const status = panel.querySelector('[data-role="status"]');
    const subject = panel.querySelector('[data-role="subject"]');

    subject.textContent = engine.text;

    const run = () => {
        const pattern = input.value.trim();
        if (!pattern) {
            panel.dataset.state = 'idle';
            status.textContent = '';
            subject.textContent = engine.text;
            return { ranges: [], error: null };
        }

        const started = performance.now();
        const result = engine.search(pattern);
        const elapsed = performance.now() - started;

        if (result.error) {
            panel.dataset.state = 'error';
            status.textContent = result.error;
            subject.textContent = engine.text;
        } else {
            panel.dataset.state = result.ranges.length ? 'match' : 'empty';
            const n = result.ranges.length;
            status.textContent = `${n === 0 ? 'no' : n} match${n === 1 ? '' : 'es'} in ${elapsed.toFixed(1)} ms`;
            subject.innerHTML = highlight(engine.text, result.ranges);
        }
        return result;
    };

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        run();
    });

    return { matcher: engine, run, input, status, subject };
}
