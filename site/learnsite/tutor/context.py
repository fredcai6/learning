"""What the tutor may answer from: the lesson, and passages of its sources.

The tutor sees the lesson's text and the passages of its cited sources that
best match the question, ranked by BM25 over the archived text, one PDF page
per passage so citations can name a page. A cited source with no archived
text (a video, a paywalled book) contributes its record: notes and
timestamps, so the tutor can point to it without quoting it.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

from ..vault import Lesson, Vault

WORD = re.compile(r"[a-z0-9]+")
STOP = set("the a an of to and or in on is are be by for with as that this it its at from we our you your "
           "can will which what how why when then than so if not no do does any each".split())
PASSAGE_CHARS = 2400
LESSON_CHARS = 9000


def words(text: str) -> list[str]:
    return [w for w in WORD.findall(text.lower()) if w not in STOP and len(w) > 1]


@dataclass
class Passage:
    source: str
    page: int
    text: str


@dataclass
class LessonText:
    title: str
    text: str
    sources: list[str]         # data-source ids cited by the lesson, in order


class _LessonParser(HTMLParser):
    SKIP = {"script", "style", "nav", "head"}
    BLOCK = {"p", "div", "li", "h1", "h2", "h3", "tr", "section", "details", "summary"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.sources: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")
        if a.get("data-source") and a["data-source"] not in self.sources:
            self.sources.append(a["data-source"])
        if tag == "button" and "data-correct" in a:
            self.parts.append("[correct answer] ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def lesson_text(vault: Vault, lesson: Lesson) -> LessonText:
    parser = _LessonParser()
    parser.feed((vault.root / lesson.href).read_text(encoding="utf-8", errors="replace"))
    text = re.sub(r"[ \t]+", " ", "".join(parser.parts))
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return LessonText(lesson.title, text[:LESSON_CHARS], parser.sources)


@lru_cache(maxsize=16)
def _pages(path: Path, mtime: float) -> tuple[tuple[int, str, tuple[str, ...]], ...]:
    """(page number, text, words) per passage. pdftotext separates pages with form feeds."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    out = []
    for number, page in enumerate(raw.split("\f"), start=1):
        page = re.sub(r"[ \t]+", " ", page).strip()
        for start in range(0, len(page), PASSAGE_CHARS):
            chunk = page[start:start + PASSAGE_CHARS]
            if len(chunk) > 80:
                out.append((number, chunk, tuple(words(chunk))))
    return tuple(out)


def passages(archive: Path | None, source_id: str, record: dict, query: str, k: int) -> list[Passage]:
    if archive is None or not record.get("archive"):
        return []
    text_file = archive / f"{source_id}.txt"
    if not text_file.is_file():
        return []
    pages = _pages(text_file, text_file.stat().st_mtime)
    if not pages:
        return []
    q = set(words(query))
    n = len(pages)
    df = Counter(w for _, _, ws in pages for w in set(ws))
    avg = sum(len(ws) for _, _, ws in pages) / n
    scored = []
    for number, chunk, ws in pages:
        tf = Counter(ws)
        score = 0.0
        for w in q:
            if w in tf:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                score += idf * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(ws) / avg))
        if score > 0:
            scored.append((score, number, chunk))
    scored.sort(reverse=True)
    return [Passage(source_id, number, chunk) for _, number, chunk in scored[:k]]


def source_note(source_id: str, record: dict) -> str:
    lines = [f"[{source_id}] {record.get('title', source_id)} ({record.get('kind', 'source')})",
             f"Use for: {record.get('use_for', '')}"]
    for stamp in record.get("timestamps", []):
        lines.append(f"  at {stamp.get('at')}: {stamp.get('covers')}")
    if record.get("url"):
        lines.append(f"Link: {record['url']}")
    if record.get("body"):
        lines.append(record["body"][:800])
    return "\n".join(lines)


def build(vault: Vault, archive: Path | None, lesson: Lesson, question: str, k: int = 4) -> str:
    """The material block for the system prompt."""
    lt = lesson_text(vault, lesson)
    records = vault.sources()
    query = f"{question} {lt.title}"
    found: list[Passage] = []
    for sid in lt.sources:
        found.extend(passages(archive, sid, records.get(sid, {}), query, k))
    found.sort(key=lambda p: -len(set(words(query)) & set(words(p.text))))
    parts = [f"=== LESSON: {lt.title} [lesson] ===\n{lt.text}"]
    parts.append("=== SOURCES THE LESSON CITES ===\n" + "\n\n".join(
        source_note(sid, records[sid]) for sid in lt.sources if sid in records))
    for p in found[:k]:
        parts.append(f"=== PASSAGE [{p.source}, PDF p. {p.page}] ===\n{p.text}")
    return "\n\n".join(parts)
