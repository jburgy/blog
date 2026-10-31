// DOM wiring for the Forth stepper panel on the landing page.  assets/Makefile
// publishes this folder next to regexp/web/ and jonesforth/, so the relative
// URLs below hold in the repo and in assets/.

import { record, locate, label, disassemble } from './stepper.mjs';

const MARKUP = `
<form class="stepper__form" data-role="form">
	<label>Definition
		<input data-role="definition" value=": FACT DUP 1 > IF DUP 1- RECURSE * THEN ;" spellcheck="false">
	</label>
	<label>Run
		<input data-role="expression" value="5 FACT ." spellcheck="false">
	</label>
	<button type="submit">Record</button>
</form>
<div class="stepper__controls">
	<button type="button" data-role="first" title="First step">⏮</button>
	<button type="button" data-role="prev" title="Previous step">◀</button>
	<button type="button" data-role="play" title="Play">▶</button>
	<button type="button" data-role="next" title="Next step">▶|</button>
	<input type="range" min="0" max="0" value="0" data-role="slider" aria-label="Step">
	<output data-role="position"></output>
</div>
<div class="stepper__grid">
	<section>
		<h3>Threaded code</h3>
		<p class="stepper__title" data-role="title"></p>
		<div class="stepper__cells" data-role="code"></div>
	</section>
	<section>
		<h3>Data stack</h3>
		<div class="stepper__stack" data-role="ds"></div>
	</section>
	<section>
		<h3>Return stack</h3>
		<div class="stepper__stack" data-role="rs"></div>
	</section>
</div>
<p class="status" data-role="status" role="status"></p>
`;

export function createPanel(document) {
    const panel = document.createElement('section');
    panel.className = 'panel';
    panel.innerHTML = MARKUP;
    return panel;
}

const cell = (text, cls = '') => {
    const el = document.createElement('span');
    el.className = `cell ${cls}`.trim();
    el.textContent = text;
    return el;
};

const fill = (el, children) => el.replaceChildren(...children);

/** Wire `panel` up to the recorder. */
export async function attach(panel) {
    const $ = (role) => panel.querySelector(`[data-role="${role}"]`);
    const [wasm, preamble] = await Promise.all([
        fetch(new URL('./traced.wasm', import.meta.url)).then((r) => r.arrayBuffer()),
        fetch(new URL('../../../jonesforth/jonesforth.f', import.meta.url)).then((r) => r.text()),
    ]);

    let rec;
    let index = 0;
    let timer = null;

    // Top of stack first; a cell is "new" unless the stack below it is unchanged.
    const stackCells = (now, before, format) => [...now].reverse().map((value, k) => {
        const depth = now.length - 1 - k;
        return cell(format(value), before?.length > depth && before[depth] === value ? '' : 'new');
    });

    function show(n) {
        if (!rec.steps.length) return;
        index = Math.max(0, Math.min(rec.steps.length - 1, n));
        const step = rec.steps[index];
        const { word } = locate(rec.words, step.ip);
        const ret = (a) => label(rec.words, a);

        $('slider').value = index;
        $('position').textContent = `${index + 1} / ${rec.steps.length}`;
        $('title').textContent = `: ${word.name} … ;`;
        fill($('code'), disassemble(rec, word).map((c) => cell(c.text, `${c.literal ? 'lit' : ''} ${c.addr === step.ip ? 'at' : ''}`.trim())));
        fill($('ds'), stackCells(step.ds, rec.steps[index - 1]?.ds, String));
        fill($('rs'), stackCells(step.rs, rec.steps[index - 1]?.rs, ret));
    }

    const stop = () => {
        clearInterval(timer);
        timer = null;
        $('play').textContent = '▶';
    };

    const play = () => {
        if (timer) return stop();
        if (index >= rec.steps.length - 1) show(0);
        $('play').textContent = '⏸';
        timer = setInterval(() => (index >= rec.steps.length - 1 ? stop() : show(index + 1)), 250);
    };

    const clear = () => { for (const role of ['code', 'ds', 'rs', 'title', 'position']) fill($(role), []); };

    async function run() {
        stop();
        try {
            rec = await record(wasm, preamble, $('definition').value, $('expression').value);
        } catch (error) {
            rec = { steps: [] };
            $('slider').max = 0;
            $('status').textContent = `Error: ${error.message ?? error}`;
            return clear();
        }
        $('slider').max = Math.max(0, rec.steps.length - 1);
        const output = rec.output.trim() || '(none)';
        const n = rec.steps.length;
        $('status').textContent = rec.truncated
            ? `Gave up after ${n} steps inside the new code: the run did not finish (infinite loop?)`
            : n
                ? `Output: ${output}  ·  ${n} steps inside the new code`
                : `No steps executed inside the new code. Output: ${output}`;
        if (n) show(0);
        else clear();
    }

    $('form').addEventListener('submit', (event) => {
        event.preventDefault();
        run();
    });
    $('slider').addEventListener('input', (event) => show(+event.target.value));
    $('first').addEventListener('click', () => show(0));
    $('prev').addEventListener('click', () => show(index - 1));
    $('next').addEventListener('click', () => show(index + 1));
    $('play').addEventListener('click', play);

    await run();
}
