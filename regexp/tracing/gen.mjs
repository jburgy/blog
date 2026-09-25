// Render the snapshot measured by snap.mjs as an SVG.
import fs from 'node:fs';

const o = JSON.parse(fs.readFileSync(new URL('./out.json', import.meta.url)));
const SNAP = 791;
const s = o.steps[SNAP];
const C = o.R.cfa;
const hex = (n) => '0x' + n.toString(16).toUpperCase().padStart(4, '0');
const rel = (a) => `R+${a - C}`;
const esc = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

// Sanity: the numbers drawn below are the ones measured.
const expect = (cond, what) => { if (!cond) throw new Error(`snapshot mismatch: ${what}`); };
expect(s.exec === 'RE-MEMBER?' && s.word === '(NNODE)+16', 'executing word');
expect(s.sp === 0x1ff8 && s.rsp === 0x3fec && s.ip === 0x8874 && s.cfa === 0x87f4, 'registers');
expect(JSON.stringify(s.ds.map(rel)) === '["R+228","R+228"]', 'data stack');
expect(JSON.stringify(s.rsSym) === '["QUIT+16","RE-SCAN+48","RE-TRY+24","R+24","R+236"]', 'return stack');
expect(s.n === 0 && s.ch === 98 && s.pos - o.RE_TXT === 5, 'matcher variables');
expect(o.steps.length === 1629 && o.total === 5102, 'step counts');

const W = 960;
const X0 = 160;           // content column
const MONO = 6.62;        // Menlo advance at 11px
const out = [];
const put = (x) => out.push(x);
const text = (x, y, t, cls = '', extra = '') => put(`<text x="${x}" y="${y}"${cls ? ` class="${cls}"` : ''}${extra ? ' ' + extra : ''}>${t}</text>`);
const rect = (x, y, w, h, cls, extra = '') => put(`<rect x="${x}" y="${y}" width="${w}" height="${h}" class="${cls}"${extra ? ' ' + extra : ''}/>`);
const panel = (y, h, title, sub) => {
    rect(20, y, 920, h, 'p', 'rx="8"');
    text(34, y + 24, title, 'h');
    for (const [i, line] of sub.entries()) text(34, y + 42 + 14 * i, line, 'm s');
};

// ---------------------------------------------------------------- title
text(20, 32, 'Inside one click: <tspan class="c">a(b|c)*d</tspan> against <tspan class="c">abccbcccd</tspan>', 'title');
text(20, 54, `One instant, NEXT #${SNAP} of ${o.steps.length.toLocaleString('en')} in the first call of R, measured end to end through every layer`, 'm');

// ---------------------------------------------------------------- timeline
{
    const x = (step) => 40 + (step * 880) / o.steps.length;
    const loads = o.steps.flatMap((t, i) => (t.exec === 'RE-LOAD' ? [i] : []));
    const bounds = [0, ...loads, o.steps.length];
    const labels = ['', ...o.text.split(''), '\\0'];
    text(40, 84, 'Forth NEXTs executed by R, one segment per character of the subject', 'm s');
    text(920, 84, `179 NEXTs per character inside the loop · ${o.total.toLocaleString('en')} for the whole click`, 'm s', 'text-anchor="end"');
    for (let i = 0; i + 1 < bounds.length; i++) {
        const [a, b] = [x(bounds[i]), x(bounds[i + 1])];
        const cur = bounds[i] <= SNAP && SNAP < bounds[i + 1];
        rect(a.toFixed(1), 92, (b - a).toFixed(1), 24, cur ? 'seg now' : i % 2 ? 'seg' : 'seg alt');
        if (labels[i]) text((cur ? a + 12 : (a + b) / 2).toFixed(1), 109, labels[i], 'c' + (labels[i].length > 1 ? ' s' : '') + (cur ? ' b' : ''), 'text-anchor="middle"');
        if (i > 0 && bounds[i] !== o.steps.length) text(a.toFixed(1), 130, bounds[i], 'm xs', 'text-anchor="middle"');
    }
    const sx = x(SNAP).toFixed(1);
    put(`<line x1="${sx}" y1="86" x2="${sx}" y2="122" class="now-line"/>`);
    text(sx, 146, `▲ #${SNAP}: fifth character, a ‘b’, taken by the (b|c)* loop`, 'acc s b', 'text-anchor="middle"');
    text(40, 146, 'setup', 'm xs');
    text(920, 146, 'accept', 'm xs', 'text-anchor="end"');
}

// ---------------------------------------------------------------- 1. JavaScript
{
    const Y = 162;
    panel(Y, 104, 'JavaScript', ['V8 main thread', 'call stack →']);
    const frames = [
        ['submit listener', 'demo.mjs:67'],
        ['run()', 'demo.mjs:49'],
        ['Matcher.search()', 'matcher.mjs:152'],
        ['Forth.eval()', 'forth.mjs:43'],
        ['_start', 'wasm-function[10]'],
    ];
    frames.forEach(([name, loc], i) => {
        const bx = X0 + i * 158;
        rect(bx, Y + 16, 146, 46, i === 4 ? 'cell edge-acc' : 'cell', 'rx="5"');
        text(bx + 73, Y + 36, esc(name), 'c b', 'text-anchor="middle"');
        text(bx + 73, Y + 52, loc, 'm xs', 'text-anchor="middle"');
        if (i < 4) put(`<path d="M ${bx + 148} ${Y + 39} h 8" class="arrow" marker-end="url(#rs-head)"/>`);
    });
    text(X0, Y + 82, `<tspan class="m">source handed to the interpreter: </tspan>${esc('REWIND : R RE" a(b|c)*d" ; LATEST @ >CFA RE-SCAN')}`, 'c s');
    text(X0, Y + 97, 'frames 3–5 from new Error().stack inside the trace hook; 1–2 are what the page adds on top of them', 'm xs');
}

// ---------------------------------------------------------------- 2. WebAssembly
{
    const Y = 278;
    panel(Y, 214, 'WebAssembly', ['_start is the whole', 'interpreter: one', 'function, one loop,', 'one 100-way br_table']);
    text(X0, Y + 24, 'Which tier runs _start (%IsTurboFanFunction)', 'b s');
    const tiers = [
        ['eval #1', '4th.32.fs', 'uncompiled → TurboFan'],
        ['eval #2–4', 'regexp.f + glue', 'TurboFan'],
        ['eval #5', 'this click', 'TurboFan'],
    ];
    tiers.forEach(([a, b, c], i) => {
        const y = Y + 42 + 15 * i;
        text(X0, y, a, 'c s');
        text(X0 + 70, y, b, 's');
        text(X0 + 175, y, c, 'c s' + (i === 2 ? ' acc b' : ''));
    });
    text(X0, Y + 94, 'arm64 code: Liftoff 10,600 B, TurboFan 9,280 B', 's');
    text(X0, Y + 110, '≈25 µs per click ⇒ ≈5 ns per NEXT', 's');

    rect(X0, Y + 124, 312, 80, 'cell', 'rx="5"');
    text(X0 + 10, Y + 141, 'Wasm locals of _start at this instant', 'b s');
    const locals = [
        ['$cfa', hex(s.cfa), 'RE-MEMBER?  (*$cfa = 0 → $_docol)'],
        ['$ip', hex(s.ip), '(NNODE)+20'],
        ['$sp', hex(s.sp), 'two cells deep'],
        ['$rsp', hex(s.rsp), 'five cells deep'],
    ];
    locals.forEach(([k, v, note], i) => {
        const y = Y + 158 + 14 * i;
        text(X0 + 10, y, k, 'c s');
        text(X0 + 50, y, v, 'c s b');
        text(X0 + 110, y, esc(note), 'm xs');
    });

    const CX = 500;
    text(CX, Y + 24, 'NEXT and dispatch, as TurboFan compiled them', 'b s');
    text(CX, Y + 39, 'x8 = linear-memory base · w12 = $ip · w13 = $cfa · w14 = codeword', 'm xs');
    const code = [
        ['54', 'mov   w13, w12', '$cfa ← $ip'],
        ['58', 'ldr   w13, [x8, x13]', '$cfa ← mem[$ip]'],
        ['5c', 'add   w12, w12, #4', '$ip += 4'],
        ['60', 'str   x12, [sp, #72]', 'spill $ip to the frame'],
        ['6c', 'ldur  x14, [x26, #-224]', 'stack limit …'],
        ['70', 'cmp   sp, x14 ; b.ls', '… checked every iteration'],
        ['78', 'ldr   w14, [x8, x13]', 'codeword ← mem[$cfa]'],
        ['7c', 'cmp   x14, #100 ; b.hs', 'br_table bounds check'],
        ['84', 'adr   x16, table', ''],
        ['94', 'ldrsw x17, [x16, x14, lsl #2]', 'jump-table entry'],
        ['98', 'add   x16, x16, x17', ''],
        ['9c', 'br    x16', '→ $_docol, $drop, $swap, …'],
    ];
    code.forEach(([off, ins, note], i) => {
        const y = Y + 58 + 13 * i;
        text(CX, y, '+0x' + off, 'm c xs');
        text(CX + 42, y, esc(ins), 'c xs' + (off === '9c' ? ' acc b' : ''));
        text(CX + 250, y, esc(note), 'm xs');
    });
}

// ---------------------------------------------------------------- 3. Linear memory
{
    const Y = 504;
    panel(Y, 124, 'Linear memory', ['2 × 64 KiB pages,', `HERE = ${hex(o.R.end)}`]);
    const LO = 0, HI = 0xb000;
    const x = (a) => +(X0 + ((a - LO) * 780) / (HI - LO)).toFixed(1);
    const regions = [
        [0x0000, 0x2000, 'ds', 'data stack ↓'],
        [0x2000, 0x4000, 'rs', 'return stack ↓'],
        [0x4000, 0x5000, 'seg alt', 'TIB'],
        [0x5000, 0x56fc, 'seg', ''],
        [0x56fc, o.R.addr, 'seg alt', 'dictionary: 4th.32.fs, regexp.f, glue →'],
        [o.R.addr, o.R.end, 'seg now', ''],
        [o.R.end, HI, 'seg', ''],
    ];
    for (const [a, b, cls, label] of regions) {
        rect(x(a), Y + 34, (x(b) - x(a)).toFixed(1), 24, cls);
        if (label) text(((x(a) + x(b)) / 2).toFixed(1), Y + 28, label, 'm xs', 'text-anchor="middle"');
    }
    // the live part of each stack
    rect(x(s.sp), Y + 34, Math.max(2, x(0x2000) - x(s.sp)), 24, 'live-ds');
    rect(x(s.rsp), Y + 34, Math.max(2, x(0x4000) - x(s.rsp)), 24, 'live-rs');
    for (const a of [0x0000, 0x2000, 0x4000, 0x5000]) text(x(a) + 2, Y + 72, hex(a).replace('0x', '0x'), 'm c xxs');
    text(x(HI), Y + 72, hex(HI), 'm c xxs', 'text-anchor="end"');
    const ptrs = [
        [s.sp, 0, `sp ${hex(s.sp)}`, 'end'],
        [s.rsp, 0, `rsp ${hex(s.rsp)}`, 'end'],
        [o.V['RE-POS'], 0, `RE-POS … RE-NLIST ${hex(o.V['RE-POS'])}`, 'middle'],
        [o.RE_TXT, 1, `RE-TXT ${hex(o.RE_TXT)}`, 'middle'],
        [o.R.addr, 0, `R ${hex(o.R.addr)}–${hex(o.R.end)}`, 'end'],
    ];
    for (const [a, row, label, anchor] of ptrs) {
        const px = x(a);
        const ty = Y + 94 + 14 * row;
        put(`<line x1="${px}" y1="${Y + 58}" x2="${px}" y2="${ty - 10}" class="ptr"/>`);
        const tx = anchor === 'end' ? (label.startsWith('R ') ? 938 : px - 3) : px;
        text(tx, ty, label, 'c xs', `text-anchor="${anchor}"`);
    }
}

// ---------------------------------------------------------------- 4. Forth
{
    const Y = 640;
    panel(Y, 300, 'Forth', ['jonesforth dialect,', 'threaded code in', 'linear memory']);

    // data stack
    text(X0, Y + 24, 'Data stack', 'b s');
    text(X0, Y + 38, '0x0000–0x1FFF, grows down', 'm xs');
    const cellH = 36;
    const dcell = (y, addr, tag, sym, num, cls) => {
        rect(X0, y, 170, cellH, 'cell');
        rect(X0, y, 4, cellH, cls);
        text(X0 + 10, y + 15, `${addr}${tag ? ` <tspan class="acc b">${tag}</tspan>` : ''}`, 'm c xs');
        text(X0 + 162, y + 16, sym, 'c b', 'text-anchor="end"');
        text(X0 + 162, y + 29, num, 'm c xxs', 'text-anchor="end"');
    };
    dcell(Y + 50, hex(s.sp), 'sp', rel(s.ds[1]), hex(s.ds[1]), 'k-ds');
    dcell(Y + 50 + cellH, hex(s.sp + 4), '', rel(s.ds[0]), hex(s.ds[0]), 'k-ds');
    [
        'R> just popped R+168: the',
        '“return address” of the call to',
        '(NNODE) at R+164 is the state',
        'that follows ‘b’. RE-RESOLVE',
        'chased its BRANCH to R+228;',
        'DUP kept a copy for RE-MEMBER?',
        'which is being entered now.',
    ].forEach((line, i) => text(X0, Y + 142 + 14 * i, esc(line), 'm xs'));

    // return stack
    const RX = 344, RW = 272;
    text(RX, Y + 24, 'Return stack', 'b s');
    text(RX, Y + 38, '0x2000–0x3FFF, grows down', 'm xs');
    const rcell = (y, addr, tag, sym, num, note, cls, dashed = false) => {
            rect(RX, y, RW, cellH, dashed ? 'cell ghost' : 'cell');
        rect(RX, y, 4, cellH, cls);
        text(RX + 10, y + 15, `${addr}${tag ? ` <tspan class="acc b">${tag}</tspan>` : ''}`, 'm c xs');
        text(RX + 84, y + 15, esc(sym), 'c b');
        text(RX + RW - 8, y + 15, num, 'm c xxs', 'text-anchor="end"');
        text(RX + 84, y + 29, esc(note), 'm xs');
    };
    rcell(Y + 50, 'next', '', '(NNODE)+20', hex(s.ip), 'DOCOL pushes it into RE-MEMBER?', 'k-now', true);
    const notes = [
        ['R+236', 'pending thread: exit loop, try d', 'k-th'],
        ['R+24', 'sentinel: go read the next char', 'k-sen'],
        ['RE-TRY+24', 'R’s caller; RE-RSP unwinds here', 'k-fc'],
        ['RE-SCAN+48', 'RE-SCAN called RE-TRY', 'k-fc'],
        ['QUIT+16', 'INTERPRET dispatched RE-SCAN', 'k-fc'],
    ];
    const rsTop = [...s.rs].reverse();
    notes.forEach(([sym, note, cls], i) => {
        expect(s.rsSym[s.rs.length - 1 - i] === sym, `rs ${i}`);
        rcell(Y + 90 + cellH * i, hex(s.rsp + 4 * i), i === 0 ? 'rsp' : '', sym, hex(rsTop[i]), note, cls);
    });

    // Thompson's machine
    const TX = 632;
    text(TX, Y + 24, 'Thompson’s machine', 'b s');
    text(TX, Y + 38, 'regexp.f variables', 'm xs');
    const subject = [...o.text, '\\0'];
    subject.forEach((c, i) => {
        const bx = TX + i * 30;
        const cls = i === 4 ? 'cell now-cell' : 'cell';
        rect(bx, Y + 50, 30, 30, cls);
        text(bx + 15, Y + 70, c, 'c' + (i < 4 ? ' m' : '') + (c.length > 1 ? ' xs' : ''), 'text-anchor="middle"');
    });
    text(TX, Y + 94, `RE-TXT ${hex(o.RE_TXT)}`, 'm c xxs');
    text(TX + 5 * 30 + 15, Y + 94, '▲ RE-POS', 'm xs', 'text-anchor="middle"');
    const vars = [
        ['RE-CH', '\'b\'', 'the character every thread tests'],
        ['RE-POS', hex(s.pos), 'where RE-LOAD reads next'],
        ['RE-N', String(s.n), 'threads queued for the next char'],
        ['RE-RSP', '0x3FF4', 'return stack mark for RE-ACCEPT'],
    ];
    vars.forEach(([k, v, note], i) => {
        const y = Y + 116 + 15 * i;
        text(TX, y, k, 'c xs');
        text(TX + 52, y, esc(v), 'c xs b');
        text(TX + 104, y, esc(note), 'm xs');
    });
    text(TX, Y + 188, `RE-NLIST ${hex(o.RE_NLIST)}: Thompson’s NLIST`, 'b s');
    for (let i = 0; i < 4; i++) {
        rect(TX + i * 62, Y + 196, 60, 28, i === 0 ? 'cell ghost-th' : 'cell');
    }
    text(TX + 30, Y + 214, 'R+228', 'c xs th', 'text-anchor="middle"');
    text(TX + 4 * 62 + 4, Y + 214, '…', 'm');
    text(TX, Y + 242, '↑ (NNODE) stores R+228 here 26 NEXTs from now', 'm xs');
    text(TX, Y + 262, 'CLIST is the return stack above the sentinel:', 'xs');
    text(TX, Y + 276, 'R+60 moves RE-NLIST onto it with >R, then', 'xs');
    text(TX, Y + 290, 'each thread’s EXIT “returns” into the next one.', 'xs');
}

// ---------------------------------------------------------------- 5. compiled R + NFA
{
    const Y = 952;
    panel(Y, 300, 'Compiled word R', ['what RE" left in the', `dictionary: 76 cells`, `at ${hex(o.R.addr)}`]);
    text(X0, Y + 24, 'Threaded code, one row per block (→ marks resolved branch targets)', 'b s');
    const T = (t, cls = '') => ({ t, cls });
    const rows = [
        ['R+4', 'hdr', [T('RSP@'), T('LIT'), T('RE-RSP'), T('!'), T('RE-START')]],
        ['R+24', 'loop', [T('RE-DONE?', 'sen'), T('0BRANCH→R+48'), T('LIT'), T('0'), T('EXIT')]],
        ['R+48', '', [T('LIT'), T('R+24'), T('>R'), T('RE-THREAD'), T('DUP'), T('0BRANCH→R+88'), T('>R'), T('BRANCH→R+60')]],
        ['R+88', '', [T('DROP'), T('RE-LOAD')]],
        ['R+96', 'a', [T('BRANCH→R+104'), T('│', 'm'), T('LIT'), T("'a'"), T('RE-CHAR?'), T('0BRANCH→R+128'), T('EXIT'), T('(NNODE)')]],
        ['R+132', 'b', [T('BRANCH→R+244'), T('│', 'm'), T('LIT'), T("'b'"), T('RE-CHAR?'), T('0BRANCH→R+164'), T('EXIT'), T('(NNODE)', 'now')]],
        ['R+168', 'c', [T('BRANCH→R+228'), T('│', 'm'), T('LIT'), T("'c'"), T('RE-CHAR?'), T('0BRANCH→R+200'), T('EXIT'), T('(NNODE)')]],
        ['R+204', '|', [T('BRANCH→R+228'), T('│', 'm'), T('XCALL'), T('R+176'), T('BRANCH→R+140')]],
        ['R+228', '*', [T('XCALL', 'th'), T('R+212', 'th'), T('BRANCH→R+260', 'pend'), T('│', 'm'), T('XCALL'), T('R+212'), T('BRANCH→R+260')]],
        ['R+260', 'd', [T('BRANCH→R+268'), T('│', 'm'), T('LIT'), T("'d'"), T('RE-CHAR?'), T('0BRANCH→R+292'), T('EXIT'), T('(NNODE)')]],
        ['R+296', '', [T('RE-ACCEPT'), T('EXIT')]],
    ];
    rows.forEach(([off, tag, toks], r) => {
        const y = Y + 46 + 21 * r;
        text(X0, y, off, 'm c xs');
        if (tag) text(X0 + 44, y, esc(tag), 'c b s');
        let x = X0 + 82;
        for (const { t, cls } of toks) {
            const w = t.length * MONO * (10.5 / 11);
            if (cls === 'now') rect(x - 2, y - 12, w + 4, 16, 'hl-now', 'rx="3"');
            if (cls === 'th') rect(x - 2, y - 12, w + 4, 16, 'hl-th', 'rx="3"');
            if (cls === 'pend') rect(x - 2, y - 12, w + 4, 16, 'hl-pend', 'rx="3"');
            if (cls === 'sen') rect(x - 2, y - 12, w + 4, 16, 'hl-sen', 'rx="3"');
            text(x.toFixed(1), y, esc(t), 'c xs' + (cls === 'm' ? ' m' : ''));
            x += w + 5.5;
        }
    });
    text(X0, Y + 290, 'highlighted: R+24 sentinel · R+228 thread popped from RE-NLIST · R+236 pending · R+164 executing', 'm xs');

    // NFA
    const NX = 740;
    text(660, Y + 24, 'The NFA those cells encode', 'b s');
    const node = (y, label, cls, accept = false) => {
        put(`<circle cx="${NX}" cy="${y}" r="22" class="${cls}"/>`);
        if (accept) put(`<circle cx="${NX}" cy="${y}" r="18" class="${cls}"/>`);
        text(NX, y + 4, label, 'c xxs b', 'text-anchor="middle"');
    };
    const [y0, y1, y2, y3] = [Y + 62, Y + 132, Y + 202, Y + 268];
    put(`<path d="M ${NX} ${Y + 32} V ${y0 - 24}" class="arrow" marker-end="url(#rs-head)"/>`);
    put(`<path d="M ${NX} ${y0 + 22} V ${y1 - 24}" class="arrow" marker-end="url(#rs-head)"/>`);
    text(NX + 8, (y0 + y1) / 2 + 4, 'a', 'c s');
    put(`<path d="M ${NX} ${y1 + 22} V ${y2 - 24}" class="arrow" marker-end="url(#rs-head)"/>`);
    text(NX + 8, (y1 + y2) / 2 + 4, 'b | c', 'c s');
    put(`<path d="M ${NX + 20} ${y2 - 10} C ${NX + 78} ${y2 - 44}, ${NX + 78} ${y2 + 44}, ${NX + 22} ${y2 + 8}" class="arrow now-edge" marker-end="url(#rs-head-acc)"/>`);
    text(NX + 70, y2 + 4, 'b | c', 'c s acc b');
    put(`<path d="M ${NX - 20} ${y1 + 10} C ${NX - 110} ${y1 + 50}, ${NX - 110} ${y3 - 40}, ${NX - 22} ${y3 - 6}" class="arrow" marker-end="url(#rs-head)"/>`);
    text(NX - 94, (y1 + y3) / 2 + 4, 'd', 'c s', 'text-anchor="end"');
    put(`<path d="M ${NX} ${y2 + 22} V ${y3 - 24}" class="arrow pend-edge" marker-end="url(#rs-head)"/>`);
    text(NX + 8, (y2 + y3) / 2 + 4, 'd', 'c s th');
    node(y0, 'R+96', 'n');
    node(y1, 'R+244', 'n');
    node(y2, 'R+228', 'n n-th');
    node(y3, 'R+296', 'n', true);
    text(NX + 30, y0 + 4, 'tried at every char', 'm xxs');
    text(NX + 30, y1 + 4, 'after a', 'm xxs');
    text(NX - 28, y2 + 4, 'running', 'th xxs b', 'text-anchor="end"');
    text(NX + 30, y3 + 4, 'accept', 'm xxs');
}

// ---------------------------------------------------------------- legend + method
{
    const Y = 1276;
    const keys = [['k-now', 'executing now'], ['k-th', 'a thread (CLIST / NLIST)'], ['k-sen', 'sentinel'], ['k-fc', 'Forth call chain'], ['k-ds', 'data stack']];
    let x = 20;
    for (const [cls, label] of keys) {
        rect(x, Y - 9, 12, 12, cls, 'rx="2"');
        text(x + 18, Y + 1, label, 's');
        x += 30 + label.length * 6.4;
    }
    text(20, Y + 22, 'Measured, not drawn from memory: the demo’s own matcher.mjs, forth.mjs and regexp.f, driven in Node 24.18 (V8 13.6, arm64) against a copy of forth/wasm/tabulate.wast', 'm xs');
    text(20, Y + 36, 'whose $next loop calls an imported trace(cfa, ip, sp, rsp). Tiers from %IsTurboFanFunction; machine code from --print-wasm-code on the unmodified forth.wasm.', 'm xs');
}

const H = 1324;
// XML comments may not contain "--", so no command-line flags in here.
const svg = `<!--
  Provenance: generated by https://github.com/jburgy/blog/tree/main/regexp/tracing
  gen.mjs drew NEXT #${SNAP} of out.json, which snap.mjs recorded while the regexp.f demo's own
  matcher.mjs / forth.mjs / regexp.f matched ${o.pattern} against "${o.text}" on tabulate.traced.wast
  (Node ${o.node}, V8 ${o.v8}, ${o.arch}). Rebuild with: cd regexp/tracing; npm install; npm run publish
-->
<svg id="rs" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-labelledby="rs-title">
<title id="rs-title">Every layer of the regexp.f demo, frozen halfway through matching a(b|c)*d against abccbcccd: JavaScript call stack, WebAssembly tier and machine code, linear memory, Forth data and return stacks, and the compiled threaded code with its NFA.</title>
<style>
#rs{--bg:#fff;--fg:#1f2328;--muted:#6e7781;--line:#d0d7de;--panel:#f6f8fa;--cell:#fff;--acc:#b58900;--th:#859900;--sen:#d33682;--fc:#268bd2;--ds:#2aa198;
font:12px -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;fill:var(--fg)}
@media (prefers-color-scheme:dark){#rs{--bg:#0d1117;--fg:#e6edf3;--muted:#8d96a0;--line:#3d444d;--panel:#161b22;--cell:#0d1117}}
#rs text{fill:var(--fg)}
#rs .bg{fill:var(--bg)}
#rs .title{font-size:21px;font-weight:600}
#rs .h{font-size:14px;font-weight:600}
#rs .b{font-weight:600}
#rs .s{font-size:11.5px}
#rs .xs{font-size:10.5px}
#rs .xxs{font-size:9.5px}
#rs .c{font-family:Menlo,Consolas,"DejaVu Sans Mono",monospace}
#rs text.m,#rs .m{fill:var(--muted)}
#rs text.acc,#rs .acc{fill:var(--acc)}
#rs text.th,#rs .th{fill:var(--th)}
#rs .p{fill:var(--panel);stroke:var(--line)}
#rs .cell{fill:var(--cell);stroke:var(--line)}
#rs .edge-acc{stroke:var(--acc);stroke-width:2}
#rs .ghost{stroke:var(--acc);stroke-dasharray:4 3}
#rs .ghost-th{stroke:var(--th);stroke-dasharray:4 3}
#rs .now-cell{fill:var(--acc);fill-opacity:.3;stroke:var(--acc)}
#rs .seg{fill:var(--cell);stroke:var(--line)}
#rs .seg.alt{fill:var(--panel)}
#rs .seg.now{fill:var(--acc);fill-opacity:.3;stroke:var(--acc)}
#rs .ds{fill:var(--ds);fill-opacity:.15;stroke:var(--line)}
#rs .rs{fill:var(--fc);fill-opacity:.15;stroke:var(--line)}
#rs .live-ds{fill:var(--ds)}
#rs .live-rs{fill:var(--fc)}
#rs .now-line{stroke:var(--acc);stroke-width:2}
#rs .ptr{stroke:var(--muted);stroke-width:1}
#rs .arrow{fill:none;stroke:var(--muted);stroke-width:1.3}
#rs .now-edge{stroke:var(--acc);stroke-width:2.2}
#rs .pend-edge{stroke:var(--th);stroke-dasharray:5 3;stroke-width:1.8}
#rs .k-now{fill:var(--acc)}
#rs .k-th{fill:var(--th)}
#rs .k-sen{fill:var(--sen)}
#rs .k-fc{fill:var(--fc)}
#rs .k-ds{fill:var(--ds)}
#rs .hl-now{fill:var(--acc);fill-opacity:.35}
#rs .hl-th{fill:var(--th);fill-opacity:.3}
#rs .hl-pend{fill:none;stroke:var(--th);stroke-dasharray:3 2}
#rs .hl-sen{fill:var(--sen);fill-opacity:.25}
#rs .n{fill:var(--cell);stroke:var(--muted);stroke-width:1.3}
#rs .n-th{fill:var(--th);fill-opacity:.25;stroke:var(--acc);stroke-width:2.2}
#rs .head{fill:var(--muted)}
#rs .head-acc{fill:var(--acc)}
</style>
<defs>
<marker id="rs-head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="head"/></marker>
<marker id="rs-head-acc" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="head-acc"/></marker>
</defs>
<rect width="${W}" height="${H}" rx="10" class="bg"/>
${out.join('\n')}
</svg>
`;
fs.writeFileSync(process.argv[2] ?? new URL('./snapshot.svg', import.meta.url), svg);
console.log('wrote', svg.length, 'bytes');
