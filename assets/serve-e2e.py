#!/usr/bin/env python3
"""Serve jburgy.github.io's built site and blog/assets under one origin, for
local end-to-end testing of the browser WASM demos under forth/wasm/.

THE PROBLEM THIS SOLVES: these demos only render in a real browser (jsdom/
Node can't do it -- see forth/wasm/wasi-worker.test.ts's own comment on
that). Checking one out therefore means standing up the exact split-origin,
cross-origin-isolated setup GitHub Pages provides in production:
  - bur.gy (jburgy.github.io) and jburgy/blog's Pages deployment share one
    origin there, with blog's assets reachable under /blog/ (see
    jburgy.github.io/docs/_includes/terminal.html) -- this script collapses
    that two-repo split onto one local origin/port.
  - A worker-side blocking read (SharedInputChannel + Atomics.wait) needs
    SharedArrayBuffer, which needs COOP/COEP headers on *every* response,
    not just the demo's own page. This script just sends them; production
    fakes them client-side via coi-serviceworker.js's install + reload
    dance, which a local server doesn't need to bother with.

WORKFLOW for an agent checking out a demo change:
    1. Make sure jburgy.github.io is checked out as a sibling directory of
       this blog checkout (clone it there if it isn't; override the
       location with --site-root otherwise).
    2. Build whichever assets/ target the demo you're testing needs, e.g.
       `make jonesforth.wasm` in assets/ (this script does *not* build
       anything itself).
    3. Run this script (`make serve-e2e` from assets/, or directly:
       `python3 serve-e2e.py`) and open the demo's post at
       http://localhost:8000/<post-path>, e.g.
       http://localhost:8000/2025/11/29/how-many-roads.html.
    4. Iterate: `make <target>` again, then just reload the page -- files
       under assets/ are served straight off disk, no server restart
       needed. Only re-run this script (with --skip-jekyll-build, since the
       Jekyll site itself didn't change) if you stopped it.

Usage:
    python3 serve-e2e.py                       # build the jekyll site, then serve
    python3 serve-e2e.py --skip-jekyll-build    # just (re)serve, e.g. after a
                                                 # `make` in assets/
    python3 serve-e2e.py --port 8001
"""
import argparse
import http.server
import subprocess
from pathlib import Path

ASSETS = Path(__file__).resolve().parent
BLOG_ROOT = ASSETS.parent


def build_jekyll_site(site_root: Path) -> None:
    docs = site_root / "docs"
    subprocess.run(
        ["bundle", "exec", "jekyll", "build", "--source", ".",
         "--destination", "../_site"],
        cwd=docs, check=True,
    )


def make_handler(
    assets_dir: Path, jekyll_site_dir: Path,
) -> type[http.server.SimpleHTTPRequestHandler]:
    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path: str) -> str:
            # Route /blog/* into assets/*, everything else into the built
            # Jekyll site -- the same split production serves across two
            # repos, collapsed onto one local origin/port.
            if path == "/blog" or path.startswith("/blog/"):
                self.directory = str(assets_dir)
                path = path[len("/blog"):] or "/"
            else:
                self.directory = str(jekyll_site_dir)
            return super().translate_path(path)

        def end_headers(self) -> None:
            # What coi-serviceworker.js fakes client-side in production
            # (GitHub Pages sends neither header); a real local server can
            # just send them, so SharedArrayBuffer/Atomics.wait work from
            # the first request, no service-worker install + reload needed.
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
            super().end_headers()

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--site-root", type=Path, default=BLOG_ROOT.parent / "jburgy.github.io",
        help="jburgy.github.io checkout (default: sibling of this blog checkout)",
    )
    parser.add_argument(
        "--skip-jekyll-build", action="store_true",
        help="reuse the site's existing _site/ instead of rebuilding it",
    )
    args = parser.parse_args()

    if not args.skip_jekyll_build:
        build_jekyll_site(args.site_root)

    handler = make_handler(ASSETS, args.site_root / "_site")
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"Serving jburgy.github.io at http://localhost:{args.port}/")
        print(f"Serving blog/assets at    http://localhost:{args.port}/blog/")
        print("Ctrl-C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
