// Derive tabulate.traced.wast from forth/wasm/tabulate.wast: the $next loop
// calls an imported trace.step(cfa, ip, sp, rsp) before every dispatch.
// `node instrument.mjs --check` fails if the committed copy is stale.
import fs from 'node:fs';

const source = new URL('../../forth/wasm/tabulate.wast', import.meta.url);
const target = new URL('./tabulate.traced.wast', import.meta.url);

const NEXT = '(local.set $ip (i32.add (local.get $ip) (i32.const 4))) ;; ip += 4';
const IMPORT = /(\(func \$proc_exit .*\n)/;

const src = fs.readFileSync(source, 'utf8');
if (!src.includes(NEXT) || !IMPORT.test(src)) throw new Error('tabulate.wast no longer has the expected $next loop');
const traced = src
    .replace(IMPORT, '$1    (func $trace (import "trace" "step") (param i32 i32 i32 i32))\n')
    .replace(NEXT, `${NEXT}\n            (call $trace (local.get $cfa) (local.get $ip) (local.get $sp) (local.get $rsp))`);

if (process.argv.includes('--check')) {
    if (!fs.existsSync(target) || fs.readFileSync(target, 'utf8') !== traced) {
        console.error('tabulate.traced.wast is stale: run npm run instrument');
        process.exit(1);
    }
} else {
    fs.writeFileSync(target, traced);
    console.log('wrote', target.pathname);
}
