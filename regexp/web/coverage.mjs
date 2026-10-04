#!/usr/bin/env node
// Wraps the mocha-headless-chrome suite with coverage. mocha-headless-chrome
// can capture `window.__coverage__` (-c flag), but that global only exists if
// the code it loaded was instrumented first, and matcher.mjs/forth.mjs/
// demo.mjs are plain ES modules served as-is, no bundler in the loop. nyc
// does the instrumenting; this script runs it against a disposable copy of
// the sources (so the originals stay untouched for the real demo), captures
// coverage from that copy, then points the result back at the real files so
// coverage/lcov.info (and Codecov's line annotations) match the repo.
//
// The copy lives as a sibling of this directory, *not* under /tmp: matcher.mjs
// resolves '../../forth/4th.32.fs' and '../regexp.f' relative to its own URL,
// so the copy needs the same depth under the repo root for those fetches to
// still resolve.
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const skip = ['node_modules', 'coverage', '.nyc_output'].map((name) => join(root, name));
const copy = mkdtempSync(join(root, '..', '.coverage-'));

try {
    cpSync(root, copy, { recursive: true, filter: (src) => !skip.some((dir) => src === dir || src.startsWith(`${dir}/`)) });
    symlinkSync(join(root, 'node_modules'), join(copy, 'node_modules'));

    // cwd: copy, so nyc resolves its project root (package.json) to the copy
    // itself -- it refuses to touch files outside whatever root it picks.
    execFileSync('npx', ['nyc', 'instrument', copy, copy, '--extension', '.mjs', '--in-place'], { cwd: copy, stdio: 'inherit' });

    const rawCoverage = join(copy, 'raw-coverage.json');
    execFileSync(
        'npx',
        [
            'mocha-headless-chrome',
            '-f', join(copy, 'test/index.html'),
            '-a', 'allow-file-access-from-files',
            '-c', rawCoverage,
            ...process.argv.slice(2),
        ],
        { stdio: 'inherit' },
    );

    const remapped = readFileSync(rawCoverage, 'utf8').replaceAll(copy, root);
    mkdirSync(join(root, '.nyc_output'), { recursive: true });
    writeFileSync(join(root, '.nyc_output', 'out.json'), remapped);

    execFileSync('npx', ['nyc', 'report', '--reporter', 'text', '--reporter', 'lcov', '--report-dir', 'coverage'], {
        cwd: root,
        stdio: 'inherit',
    });
} finally {
    rmSync(copy, { recursive: true, force: true });
}
