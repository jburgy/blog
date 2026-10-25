// Covers lisp/lisp.f: SectorLISP (core.ts) in FORTH with a mark-and-sweep GC,
// on the two jonesforth ports that ship as wasm (forth/wasm/jonesforth.wast
// and forth/wasm/tabulate.wast), both fed the same jonesforth/jonesforth.f
// preamble.  eliza.lisp is the conformance test: the transcript has to match
// the AssemblyScript build's, character for character.
import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import { afterAll, beforeAll, describe, expect, test } from "vitest";
import { runSession } from "../../forth/wasm/wasi-command.test-helper.mjs";

const execFileAsync = promisify(execFile);
const here = import.meta.dirname;
const read = (...path) => readFile(join(here, ...path));

const hosts = ["jonesforth", "tabulate"];
const wasm = {};
let dir;

beforeAll(async () => {
    dir = await mkdtemp(join(tmpdir(), "lisp-forth-"));
    await Promise.all(
        hosts.map(async (host) => {
            const out = join(dir, `${host}.wasm`);
            // wabt isn't an installed dependency; fetch it on demand.
            await execFileAsync("npx", ["-y", "--package", "wabt", "wat2wasm", "--enable-tail-call", "--enable-multi-memory", "-o", out, join(here, `../../forth/wasm/${host}.wast`)]);
            wasm[host] = await readFile(out);
        }),
    );
}, 120_000);
afterAll(() => rm(dir, { recursive: true, force: true }));

const jonesforthF = await read("../../jonesforth/jonesforth.f");
const lispF = await read("../lisp.f");
const eliza = await read("../eliza.lisp");

const conversation = [
    "(I AM FEELING SAD TODAY)",
    "(BECAUSE MY MOTHER NEVER LOVED ME)",
    "(I HAVE A ZEBRA IN MY GARAGE)",
    "(OK BYE)",
];

// Everything from the first "* " on, i.e. without the host's banner.
const fromPrompt = (out) => out.slice(out.indexOf("* "));

describe.each(hosts)("lisp.f on %s.wasm", (host) => {
    // Evaluates `forms` one per line at the REPL and returns what it printed.
    const repl = async (...forms) => fromPrompt(await runSession(wasm[host], jonesforthF, lispF, "LISP", ...forms));

    test("the SectorLISP primitives", async () => {
        const out = await repl(
            "(CONS (QUOTE A) (QUOTE (B C)))",
            "(CONS (QUOTE A) (QUOTE B))",
            "(CAR (QUOTE (A B)))",
            "(CDR (QUOTE (A B)))",
            "(ATOM (QUOTE (A)))",
            "(EQ (QUOTE A) (QUOTE A))",
            "(COND ((EQ (QUOTE A) (QUOTE B)) (QUOTE NO)) ((QUOTE T) (QUOTE YES)))",
            "UNBOUND",
            "(PRINT (QUOTE HELLO))",
            "(CONS (READ) (QUOTE (2)))",
            "(1)",
        );
        expect(out).toBe(
            ["* (A B C)", "* (A∙B)", "* A", "* (B)", "* NIL", "* T", "* YES", "* NIL", "* HELLONIL", "* ((1) 2)", "* "].join("\n"),
        );
    });

    test("LAMBDA has dynamic scope", async () => {
        const out = await repl(
            "((LAMBDA (F X) (F)) (QUOTE (LAMBDA () X)) (QUOTE SEEN-THROUGH-THE-CALLER))",
        );
        expect(out).toBe("* SEEN-THROUGH-THE-CALLER\n* ");
    });

    test("GC reclaims garbage and keeps what is live", async () => {
        // Quadratic reverse, three times over: far more than 4096 nodes of
        // allocation, while the evaluator's intermediate values live only on
        // the FORTH stacks.
        const n = 40;
        const list = Array.from({ length: n }, (_, i) => i + 1).join(" ");
        const prog = `((LAMBDA (APPEND NREV L) (NREV (NREV (NREV L))))
 (QUOTE (LAMBDA (A B) (COND ((EQ A NIL) B) ((QUOTE T) (CONS (CAR A) (APPEND (CDR A) B))))))
 (QUOTE (LAMBDA (L) (COND ((EQ L NIL) NIL) ((QUOTE T) (APPEND (NREV (CDR L)) (CONS (CAR L) NIL))))))
 (QUOTE (${list})))`;
        const out = await runSession(
            wasm[host],
            jonesforthF,
            lispF,
            ": RUN1 LREAD NIL LEVAL LPRINT CR ;",
            `RUN1 ${prog}`,
            "GCS @ . CR",
        );
        const reversed = Array.from({ length: n }, (_, i) => n - i).join(" ");
        expect(out).toContain(`(${reversed})\n`);
        expect(Number(out.trim().split(/\s+/).at(-1))).toBeGreaterThan(0);
    });

    test("eliza.lisp matches the AssemblyScript build", async () => {
        const reference = await runSession(await read("../build/lisp-wasi.wasm"), eliza, ...conversation);
        const out = await runSession(wasm[host], jonesforthF, lispF, "LISP", eliza, ...conversation);
        // The reference prompts around each top-level form too, so compare replies only.
        const replies = (s) => s.match(/\((?:[A-Z]+ ?)+\)/g);
        expect(replies(fromPrompt(out))).toEqual(replies(reference));
        expect(replies(reference)).toContain("(GOODBYE AND TAKE CARE)");
    });
});
