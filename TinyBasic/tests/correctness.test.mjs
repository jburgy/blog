// Regression coverage for six bugs found in core.ts's manual C->AssemblyScript
// transliteration, none caught by wasi.test.mjs since it only ever exercised
// the error-reporting path, never a successful RUN. Each would silently corrupt
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
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { expect, test } from "vitest";
import { runSession } from "../../forth/wasm/wasi-command.test-helper.mjs";

const wasm = await readFile(join(import.meta.dirname, "../build/TinyBasic-wasi.wasm"));

test("PQ: quote-terminated string printing", async () => {
    expect(await runSession(wasm, 'PRINT "HELLO"')).toMatch(/HELLO\n/);
});

test("BV/BN: digits 1-9 parse as numbers, not stray variable reads", async () => {
    expect(await runSession(wasm, "PRINT 5")).toMatch(/:5\n/);
    expect(await runSession(wasm, "PRINT 12")).toMatch(/:12\n/);
});

test("Peek2: a pushed-then-popped value round-trips exactly", async () => {
    expect(await runSession(wasm, "LET A=5", "PRINT A")).toMatch(/:5\n/);
});

test("AD vs DV: no longer aliased to the same opcode", async () => {
    expect(await runSession(wasm, "PRINT 3+4")).toMatch(/:7\n/);
    expect(await runSession(wasm, "PRINT 10/2")).toMatch(/:5\n/);
});

// ColdStart/UserProg: a multi-line stored program no longer corrupts its
// own later lines when it executes PRINT (pushes onto the expression stack).
test("ColdStart/UserProg: a stored program survives PRINT", async () => {
    expect(await runSession(wasm, "10 PRINT 1", "20 PRINT 2", "RUN")).toMatch(/1\n2\n/);
});

test("CP: signed relational compare, both directions and with a negative operand", async () => {
    expect(await runSession(wasm, 'IF 3<5 PRINT "YES"')).toMatch(/YES/);
    expect(await runSession(wasm, 'IF 3>5 PRINT "NO"')).not.toMatch(/NO/);
    expect(await runSession(wasm, "LET T=-1", 'IF 0<T PRINT "BAD"')).not.toMatch(/BAD/);
});
