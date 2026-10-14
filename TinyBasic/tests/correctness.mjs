// Regression coverage for six bugs found in core.ts's manual C->AssemblyScript
// transliteration, none caught by wasi.mjs since it only ever exercised the
// error-reporting path, never a successful RUN. Each would silently corrupt
// or misevaluate any real Tiny BASIC program (e.g. tic-tac-toe.bas), not
// just an edge case:
//   - PQ (case 0x21) compared the string terminator against ' ' (0x20)
//     instead of '"' (0x22), so PRINT "..." never stopped on the closing
//     quote.
//   - BV (case 0x05) accepted ch > 0x30 as a letter instead of ch > 0x40,
//     so every digit 1-9 was misread as a variable reference.
//   - Peek2's bswap<T>() result escaped unmasked past 16 bits when returned
//     directly, so e.g. PRINT 5 printed 327685.
//   - AD (case 0x18, Add) was mistyped as case 0x1B, colliding with DV
//     (Divide)'s real case 0x1B: addition silently did nothing and division
//     performed addition instead.
//   - ColdStart's UserProg placement masked with 0xF0 instead of 0xFF00, so
//     the BASIC program text area started almost on top of the expression
//     stack instead of safely past the IL interpreter.
//   - CP (case 0x1C, signed compare) stored the comparison delta in a T
//     (u16) local, so an unsigned "< 0" check could never be true and every
//     IF with a true "less than" result was skipped instead of taken.
// Runs each scripted session in a child process, killed once it has
// produced the expected output -- see wasi-fixture.mjs for why.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const loader = pathToFileURL(join(import.meta.dirname, "../../forth/wasm/uwasi-cdn.loader.mjs")).href;
const registerLoader = `data:text/javascript,
    import { register } from "node:module";
    register(${JSON.stringify(loader)});
`;

const fixture = join(import.meta.dirname, "wasi-fixture.mjs");
const wasmPath = join(import.meta.dirname, "../build/TinyBasic-wasi.wasm");

async function run(lines) {
    const child = spawn(process.execPath, ["--experimental-wasm-jspi", "--import", registerLoader, fixture, wasmPath, ...lines]);
    let out = "";
    await new Promise((resolve) => {
        child.stdout.on("data", (chunk) => { out += chunk; });
        setTimeout(resolve, 2000);
    }).finally(() => child.kill("SIGKILL"));
    return out;
}

// PQ: quote-terminated string printing.
assert.match(await run(['PRINT "HELLO"']), /HELLO\n/);

// BV/BN: digits 1-9 parse as numbers, not stray variable reads.
assert.match(await run(["PRINT 5"]), /:5\n/);
assert.match(await run(["PRINT 12"]), /:12\n/);

// Peek2: a pushed-then-popped value round-trips exactly.
assert.match(await run(["LET A=5", "PRINT A"]), /:5\n/);

// AD vs DV: no longer aliased to the same opcode.
assert.match(await run(["PRINT 3+4"]), /:7\n/);
assert.match(await run(["PRINT 10/2"]), /:5\n/);

// ColdStart/UserProg: a multi-line stored program no longer corrupts its
// own later lines when it executes PRINT (pushes onto the expression stack).
assert.match(await run(["10 PRINT 1", "20 PRINT 2", "RUN"]), /1\n2\n/);

// CP: signed relational compare, both directions and with a negative operand.
assert.match(await run(["IF 3<5 PRINT \"YES\""]), /YES/);
assert.doesNotMatch(await run(["IF 3>5 PRINT \"NO\""]), /NO/);
assert.doesNotMatch(await run(["LET T=-1", "IF 0<T PRINT \"BAD\""]), /BAD/);

console.log("ok");
