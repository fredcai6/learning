#!/usr/bin/env python3
"""Serve a vault's lessons on the local network until the website exists.

Usage: python3 serve_local.py VAULT [--host 0.0.0.0] [--port 8090]

Read only. Serves `topics/` and `assets/` and an index of lessons and
reference sheets; nothing under `learners/`, `sources/` or the vault root is
reachable, so missions, records and learner identities stay on the machine.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

SERVED = ("topics", "assets")


def title_of(page: Path) -> str:
    match = re.search(r"<title>(.*?)</title>", page.read_text(encoding="utf-8", errors="replace"), re.S)
    return match.group(1).strip() if match else page.stem


def index_page(vault: Path) -> bytes:
    parts = []
    for topic in sorted(p for p in (vault / "topics").glob("*") if p.is_dir()):
        parts.append(f"<h2>{html.escape(topic.name.replace('-', ' ').capitalize())}</h2>")
        for kind in ("lessons", "reference"):
            pages = sorted((topic / kind).glob("*.html"))
            if not pages:
                continue
            parts.append(f"<h3>{kind.capitalize()}</h3><ol class='sources'>")
            for page in pages:
                href = f"/topics/{topic.name}/{kind}/{page.name}"
                parts.append(f"<li><a href='{html.escape(href)}'>{html.escape(title_of(page))}</a></li>")
            parts.append("</ol>")
    body = "".join(parts) or "<p>No lessons yet.</p>"
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Learning</title><link rel='stylesheet' href='/assets/base/lesson.css'></head>"
        f"<body><main><p class='kicker'>Local preview</p><h1>Learning</h1>{body}</main></body></html>"
    ).encode("utf-8")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, vault: Path, **kwargs):
        self.vault = vault
        super().__init__(*args, directory=str(vault), **kwargs)

    def _allowed(self) -> bool:
        path = unquote(urlsplit(self.path).path)
        first = path.lstrip("/").split("/", 1)[0]
        if first not in SERVED:
            return False
        # Resolve through the assets/base symlink, but never above an allowed root.
        target = (self.vault / path.lstrip("/")).resolve()
        roots = [(self.vault / name).resolve() for name in SERVED]
        roots.append((self.vault / "assets" / "base").resolve())
        return any(target == r or r in target.parents for r in roots)

    def do_GET(self):
        if urlsplit(self.path).path in ("/", "/index.html"):
            data = index_page(self.vault)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        if not self._allowed() or self.path.endswith("/"):
            self.send_error(404)
            return
        super().do_GET()

    def do_HEAD(self):
        if not self._allowed():
            self.send_error(404)
            return
        super().do_HEAD()

    def end_headers(self):
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                         "font-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'")
        super().end_headers()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("vault")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    vault = Path(args.vault).expanduser().resolve()
    if not (vault / "vault.toml").is_file():
        raise SystemExit(f"{vault} is not a vault")
    server = ThreadingHTTPServer((args.host, args.port), partial(Handler, vault=vault))
    print(f"serving {vault} on http://{args.host}:{args.port}/", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
