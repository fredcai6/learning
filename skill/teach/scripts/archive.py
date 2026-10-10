#!/usr/bin/env python3
"""Archive a copy of a source, extract its text, and record it.

Usage: python3 archive.py SOURCE_ID URL_OR_FILE [--vault DIR]

Saves the copy as <archive_dir>/<id>.<ext>, writes the extracted text to
<archive_dir>/<id>.txt (what the tutor reads), and sets `archive` in
sources/<id>.md. The record must already exist. The copy never enters the
vault repo: archive_dir lives outside it, set in vault.toml.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) learning-archive/1"


class TextExtractor(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "noscript", "svg"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "pre", "section", "article"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)

    def text(self) -> str:
        joined = "".join(self.parts)
        joined = re.sub(r"[ \t]+", " ", joined)
        return re.sub(r"\n\s*\n+", "\n\n", joined).strip() + "\n"


def fetch(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read(), response.headers.get_content_type()


def kind_of(name: str, content_type: str, data: bytes) -> str:
    if data[:5] == b"%PDF-" or content_type == "application/pdf" or name.lower().endswith(".pdf"):
        return "pdf"
    if content_type in ("text/html", "application/xhtml+xml") or name.lower().endswith((".html", ".htm")):
        return "html"
    if content_type.startswith("text/") or name.lower().endswith((".txt", ".md", ".tex")):
        return "txt"
    raise SystemExit(f"cannot tell what kind of file this is (content type {content_type!r}); "
                     "archive PDFs, web pages, or text")


def set_archive_field(record: Path, filename: str) -> None:
    text = record.read_text(encoding="utf-8")
    match = re.match(r"(\+\+\+\n)(.*?)(\n\+\+\+\n)", text, re.S)
    if not match:
        raise SystemExit(f"{record} has no +++ frontmatter")
    body = match.group(2)
    line = f'archive = "{filename}"'
    if re.search(r"^archive\s*=", body, re.M):
        body = re.sub(r"^archive\s*=.*$", line, body, count=1, flags=re.M)
    else:
        # Before the first [[table]], so the key stays top-level.
        table = re.search(r"^\[", body, re.M)
        body = body[: table.start()] + line + "\n" + body[table.start():] if table else body + "\n" + line
    record.write_text(match.group(1) + body + match.group(3) + text[match.end():], encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source_id")
    parser.add_argument("location", help="a URL or a local file")
    parser.add_argument("--vault", default=".")
    args = parser.parse_args()

    vault = Path(args.vault).resolve()
    settings = tomllib.loads((vault / "vault.toml").read_text(encoding="utf-8"))
    archive_dir = Path(settings["archive_dir"]).expanduser()
    archive_dir.mkdir(parents=True, exist_ok=True)
    record = vault / "sources" / f"{args.source_id}.md"
    if not record.is_file():
        raise SystemExit(f"write the record first: {record} does not exist")

    if re.match(r"^https?://", args.location):
        data, content_type = fetch(args.location)
        name = args.location.split("?")[0]
    else:
        path = Path(args.location).expanduser()
        data, content_type, name = path.read_bytes(), "", path.name

    kind = kind_of(name, content_type, data)
    copy = archive_dir / f"{args.source_id}.{kind}"
    copy.write_bytes(data)
    text_path = archive_dir / f"{args.source_id}.txt"

    if kind == "pdf":
        if not shutil.which("pdftotext"):
            raise SystemExit("pdftotext not found (install poppler-utils)")
        subprocess.run(["pdftotext", "-layout", str(copy), str(text_path)], check=True)
    elif kind == "html":
        extractor = TextExtractor()
        extractor.feed(data.decode("utf-8", errors="replace"))
        text_path.write_text(extractor.text(), encoding="utf-8")
    # A .txt copy is already its own text.

    set_archive_field(record, copy.name)
    words = len(text_path.read_text(encoding="utf-8", errors="replace").split())
    print(f"archived {copy} ({len(data):,} bytes), text {text_path} ({words:,} words)")
    if words < 200:
        print("warning: very little text extracted — a scanned PDF or a script-rendered page? "
              "Check the copy before teaching from it.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
