"""Read-only view of a learning vault.

Everything is re-read on each call: the vault is small, the skill edits it
between sessions, and a cache would be one more thing to invalidate.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

FRONTMATTER = re.compile(r"\+\+\+\n(.*?)\n\+\+\+\n?(.*)", re.S)


def split_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER.match(text)
    if not match:
        return {}, text
    return tomllib.loads(match.group(1)), match.group(2)


@dataclass
class Learner:
    id: str
    name: str
    email: str | None
    telegram_chat_id: int | None


@dataclass
class Lesson:
    id: str                  # <topic>/<stem>
    topic: str
    kind: str                # lessons | reference
    stem: str
    title: str
    nodes: list[str]
    href: str                # relative to the site root


@dataclass
class Card:
    id: str                  # <topic>/<cards stem>/<card id>
    lesson_id: str           # <topic>/<cards stem>, same as the page it comes from
    kind: str
    front: str
    back: str
    source: str
    loc: str
    nodes: list[str] = field(default_factory=list)


@dataclass
class Record:
    learner: str
    topic: str
    name: str
    nodes: list[str]
    body: str


class Vault:
    def __init__(self, root: Path):
        self.root = root

    # --- people ---------------------------------------------------------------

    def learners(self) -> dict[str, Learner]:
        path = self.root / "learners.toml"
        data = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        out = {}
        for lid, entry in data.get("learners", {}).items():
            out[lid] = Learner(lid, entry.get("name", lid), entry.get("email"), entry.get("telegram_chat_id"))
        return out

    def learner_by_email(self, email: str) -> Learner | None:
        email = email.strip().lower()
        for learner in self.learners().values():
            if learner.email and learner.email.strip().lower() == email:
                return learner
        return None

    # --- teaching content -----------------------------------------------------

    def topics(self) -> list[str]:
        return sorted(p.name for p in (self.root / "topics").glob("*") if p.is_dir())

    def lessons(self, topic: str | None = None) -> list[Lesson]:
        out = []
        for t in [topic] if topic else self.topics():
            for kind in ("lessons", "reference"):
                for page in sorted((self.root / "topics" / t / kind).glob("*.html")):
                    text = page.read_text(encoding="utf-8", errors="replace")
                    title = re.search(r"<title>(.*?)</title>", text, re.S)
                    nodes = re.search(r'<meta name="nodes" content="([^"]*)"', text)
                    out.append(Lesson(
                        id=f"{t}/{page.stem}", topic=t, kind=kind, stem=page.stem,
                        title=title.group(1).strip() if title else page.stem,
                        nodes=[n.strip() for n in nodes.group(1).split(",")] if nodes else [],
                        href=f"topics/{t}/{kind}/{page.name}",
                    ))
        return out

    def cards(self) -> dict[str, Card]:
        out = {}
        for t in self.topics():
            for path in sorted((self.root / "topics" / t / "cards").glob("*.toml")):
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                for c in data.get("card", []):
                    cid = f"{t}/{path.stem}/{c['id']}"
                    out[cid] = Card(cid, f"{t}/{path.stem}", c.get("kind", "recall"), c.get("front", ""),
                                    c.get("back", ""), c.get("source", ""), c.get("loc", ""), c.get("nodes", []))
        return out

    def map_nodes(self) -> dict[str, dict]:
        out = {}
        for path in sorted((self.root / "map").glob("*.md")):
            meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
            meta["body"] = body.strip()
            out[path.stem] = meta
        return out

    def sources(self) -> dict[str, dict]:
        out = {}
        for path in sorted((self.root / "sources").glob("*.md")):
            meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
            meta["body"] = body.strip()
            out[path.stem] = meta
        return out

    # --- per learner ----------------------------------------------------------

    def route(self, learner: str, topic: str) -> dict | None:
        path = self.root / "learners" / learner / topic / "route.toml"
        return tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def mission(self, learner: str, topic: str) -> str | None:
        path = self.root / "learners" / learner / topic / "MISSION.md"
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def learner_topics(self, learner: str) -> list[str]:
        base = self.root / "learners" / learner
        return sorted(p.name for p in base.glob("*") if p.is_dir()) if base.is_dir() else []

    def records(self, learner: str) -> list[Record]:
        out = []
        for topic in self.learner_topics(learner):
            for path in sorted((self.root / "learners" / learner / topic / "records").glob("*.md")):
                meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
                out.append(Record(learner, topic, path.name, meta.get("nodes", []), body.strip()))
        return out
