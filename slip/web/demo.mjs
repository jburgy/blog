// DOM wiring for the ELIZA demo: a form that sends each statement to a web
// worker running slip.wasm (see worker.mjs) and appends the statement and the
// reply as one <li> of an <ol>, so the browser numbers the turns [1], [2], ...
// Same createPanel/attach shape as ising/demo.mjs so assets/index.html can
// mount it lazily.

const MARKUP = `
<p>HOW DO YOU DO. PLEASE TELL ME YOUR PROBLEM</p>
<ol data-role="log" aria-label="Conversation" aria-live="polite"></ol>
<form>
    <input name="say" aria-label="Say something" placeholder="Say something&hellip;" autocomplete="off" required>
    <button>Send</button>
</form>
`;

const TURN = '<li><p class="you"></p><p class="eliza"></p></li>';

/**
 * Build the (unattached) demo markup: a greeting, an empty conversation and
 * the input form.
 *
 * @param {Document} document
 * @returns {HTMLElement}
 */
export function createPanel(document) {
    const panel = document.createElement('div');
    panel.className = 'slip';
    panel.innerHTML = MARKUP;
    return panel;
}

/**
 * Start the worker and wire the form to it.
 *
 * @param {HTMLElement} panel
 * @returns {{ worker: Worker }}
 */
export function attach(panel, { workerUrl = new URL('./worker.mjs', import.meta.url) } = {}) {
    const log = panel.querySelector('[data-role="log"]');
    const form = panel.querySelector('form');
    const worker = new Worker(workerUrl, { type: 'module' });
    const waiting = []; // replies arrive in the order statements were sent
    worker.addEventListener('message', ({ data }) => waiting.shift()(data));

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const say = new FormData(form).get('say').trim();
        if (!say) return;
        const reply = await new Promise((resolve) => {
            waiting.push(resolve);
            worker.postMessage(say);
        });
        log.insertAdjacentHTML('beforeend', TURN);
        log.lastElementChild.querySelector('.you').textContent = say;
        log.lastElementChild.querySelector('.eliza').textContent = reply;
        log.scrollTop = log.scrollHeight;
        form.reset();
    });
    return { worker };
}
