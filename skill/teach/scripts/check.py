#!/usr/bin/env python3
"""Check a learning vault: sources, map, routes, records, lessons, cards.

Usage: python3 check.py [VAULT]      (default: current directory)

Prints one line per problem and exits 1 if there are any. Standard library
only, so it runs anywhere the vault is checked out.
"""

from __future__ import annotations

import re
import sys
import tomllib
from html.parser import HTMLParser
from pathlib import Path

ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NUMBERED = re.compile(r"^\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*$")
SOURCE_KINDS = {"book", "notes", "paper", "video", "web", "course", "community"}
NODE_STATES = {"unknown", "new", "shaky", "working", "solid"}
CARD_KINDS = {"produce", "predict", "explain", "recall"}


class Report:
    def __init__(self, root: Path):
        self.root = root
        self.problems: list[str] = []

    def add(self, path: Path, message: str) -> None:
        self.problems.append(f"{path.relative_to(self.root)}: {message}")


def frontmatter(path: Path, report: Report) -> dict | None:
    """Parse TOML frontmatter between `+++` lines at the top of a markdown file."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\+\+\+\n(.*?)\n\+\+\+\n", text, re.S)
    if not match:
        report.add(path, "no +++ TOML frontmatter")
        return None
    try:
        return tomllib.loads(match.group(1))
    except tomllib.TOMLDecodeError as exc:
        report.add(path, f"frontmatter is not valid TOML: {exc}")
        return None


def load_toml(path: Path, report: Report) -> dict | None:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        report.add(path, f"not valid TOML: {exc}")
        return None


def check_sources(root: Path, archive_dir: Path | None, report: Report) -> set[str]:
    ids = set()
    for path in sorted((root / "sources").glob("*.md")):
        meta = frontmatter(path, report)
        if meta is None:
            continue
        sid = meta.get("id")
        if sid != path.stem:
            report.add(path, f"id {sid!r} does not match the file name")
        ids.add(path.stem)
        for key in ("title", "kind", "trust", "use_for"):
            if not meta.get(key):
                report.add(path, f"missing {key}")
        if meta.get("kind") and meta["kind"] not in SOURCE_KINDS:
            report.add(path, f"kind {meta['kind']!r} is not one of {sorted(SOURCE_KINDS)}")
        if meta.get("kind") != "community" and not (meta.get("url") or meta.get("archive")):
            report.add(path, "needs a url or an archived copy")
        if meta.get("archive"):
            if archive_dir is None:
                report.add(path, "has an archive but vault.toml sets no archive_dir")
            elif not (archive_dir / meta["archive"]).is_file():
                report.add(path, f"archived copy {meta['archive']!r} is not in {archive_dir}")
        for stamp in meta.get("timestamps", []):
            if not stamp.get("at") or not stamp.get("covers"):
                report.add(path, "every timestamp needs `at` and `covers`")
    return ids


def check_map(root: Path, sources: set[str], report: Report) -> set[str]:
    paths = sorted((root / "map").glob("*.md"))
    ids = {p.stem for p in paths}
    for path in paths:
        meta = frontmatter(path, report)
        if meta is None:
            continue
        if meta.get("id") != path.stem:
            report.add(path, f"id {meta.get('id')!r} does not match the file name")
        if not ID.match(path.stem):
            report.add(path, "node ids are dash-case")
        if not meta.get("title"):
            report.add(path, "missing title")
        for other in meta.get("helps_with", []):
            if other not in ids:
                report.add(path, f"helps_with names unknown node {other!r}")
        for sid in meta.get("sources", []):
            if sid not in sources:
                report.add(path, f"cites unknown source {sid!r}")
    return ids


def check_learners(root: Path, nodes: set[str], report: Report) -> None:
    learners_file = root / "learners.toml"
    declared = set()
    if learners_file.is_file():
        data = load_toml(learners_file, report) or {}
        declared = set(data.get("learners", {}))
    for learner_dir in sorted(p for p in (root / "learners").glob("*") if p.is_dir()):
        if learner_dir.name not in declared:
            report.add(learner_dir, "learner has no entry in learners.toml")
        for topic_dir in sorted(p for p in learner_dir.iterdir() if p.is_dir()):
            records = topic_dir / "records"
            record_names = set()
            if records.is_dir():
                for path in sorted(records.glob("*.md")):
                    record_names.add(path.name)
                    if not NUMBERED.match(path.stem):
                        report.add(path, "records are named NNNN-dash-case.md")
                    meta = frontmatter(path, report)
                    if meta:
                        for node in meta.get("nodes", []):
                            if node not in nodes:
                                report.add(path, f"names unknown node {node!r}")
            route = topic_dir / "route.toml"
            if route.is_file():
                data = load_toml(route, report) or {}
                if not data.get("goal"):
                    report.add(route, "missing goal")
                for entry in data.get("node", []):
                    nid = entry.get("id")
                    if nid not in nodes:
                        report.add(route, f"unknown node {nid!r}")
                    if entry.get("state") not in NODE_STATES:
                        report.add(route, f"{nid}: state must be one of {sorted(NODE_STATES)}")
                    if not entry.get("why"):
                        report.add(route, f"{nid}: missing why")
                    for ev in entry.get("evidence", []):
                        if ev != "diagnostic" and ev not in record_names:
                            report.add(route, f"{nid}: evidence {ev!r} is not a record in {records.relative_to(root)}")
            if not (topic_dir / "MISSION.md").is_file() and (route.is_file() or records.is_dir()):
                report.add(topic_dir, "has a route or records but no MISSION.md")


class LessonParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta: dict[str, str] = {}
        self.classes: list[str] = []
        self.cite_targets: list[str] = []
        self.source_items: dict[str, str | None] = {}
        self.links: list[str] = []
        self.inline_scripts = 0
        self.quizzes: list[dict] = []
        self.exercises: list[dict] = []
        self._stack: list[tuple[str, dict | None]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        self.classes.extend(classes)
        if tag == "meta" and a.get("name"):
            self.meta[a["name"]] = a.get("content") or ""
        if tag == "script" and not a.get("src"):
            self.inline_scripts += 1
        for attr in ("href", "src"):
            if a.get(attr):
                self.links.append(a[attr])
        if tag == "a" and "cite" in classes:
            self.cite_targets.append((a.get("href") or "").lstrip("#"))
        if tag == "li" and a.get("id", "").startswith("src-"):
            self.source_items[a["id"]] = a.get("data-source")
        block = None
        if "quiz" in classes:
            block = {"kind": "quiz", "id": a.get("data-id"), "correct": 0, "options": 0}
            self.quizzes.append(block)
        elif "exercise" in classes:
            block = {"kind": "exercise", "id": a.get("data-id"), "answer": False}
            self.exercises.append(block)
        if tag in ("br", "img", "input", "meta", "link", "hr"):
            return
        self._stack.append((tag, block))
        current = next((b for _, b in reversed(self._stack) if b), None)
        if current and current["kind"] == "quiz" and "option" in classes:
            current["options"] += 1
            if "data-correct" in a:
                current["correct"] += 1
        if current and current["kind"] == "exercise" and "answer" in classes:
            current["answer"] = True

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                break


def check_page(path: Path, root: Path, topic: str, is_lesson: bool, sources: set[str], nodes: set[str], report: Report) -> None:
    parser = LessonParser()
    parser.feed(path.read_text(encoding="utf-8"))

    if is_lesson and not NUMBERED.match(path.stem):
        report.add(path, "lessons are named NNNN-dash-case.html")
    expected_id = f"{topic}/{path.stem}"
    if parser.meta.get("lesson-id") != expected_id:
        report.add(path, f'needs <meta name="lesson-id" content="{expected_id}">')
    page_nodes = [n.strip() for n in parser.meta.get("nodes", "").split(",") if n.strip()]
    if not page_nodes:
        report.add(path, 'needs <meta name="nodes"> naming at least one map node')
    for node in page_nodes:
        if node not in nodes:
            report.add(path, f"names unknown node {node!r}")
    if 'viewport' not in parser.meta:
        report.add(path, 'needs <meta name="viewport"> for phones')

    if not parser.cite_targets:
        report.add(path, "cites nothing")
    for target in parser.cite_targets:
        if target not in parser.source_items:
            report.add(path, f"citation #{target} has no matching li in ol.sources")
    for item_id, sid in parser.source_items.items():
        if not sid:
            report.add(path, f"{item_id} has no data-source")
        elif sid not in sources:
            report.add(path, f"{item_id} cites unknown source {sid!r}")

    if is_lesson:
        if "primary-source" not in parser.classes:
            report.add(path, "needs a .primary-source block")
        if parser.classes.count("goal-link") < 2:
            report.add(path, "needs two .goal-link paragraphs: where it sits, and what it unlocks")

    if parser.inline_scripts:
        report.add(path, f"{parser.inline_scripts} inline <script>; use a src file")

    for link in parser.links:
        if re.match(r"^[a-z][a-z0-9+.-]*:", link) or link.startswith(("#", "//")):
            continue
        target = (path.parent / link.split("#")[0].split("?")[0]).resolve()
        if not target.exists():
            report.add(path, f"broken link {link!r}")

    seen = set()
    for block in parser.quizzes + parser.exercises:
        if not block["id"]:
            report.add(path, f"a .{block['kind']} has no data-id")
        elif block["id"] in seen:
            report.add(path, f"data-id {block['id']!r} is used twice")
        seen.add(block["id"])
    for quiz in parser.quizzes:
        if quiz["correct"] != 1:
            report.add(path, f"quiz {quiz['id']!r} has {quiz['correct']} options marked data-correct; needs exactly 1")
        if quiz["options"] < 2:
            report.add(path, f"quiz {quiz['id']!r} needs at least two options")
    for ex in parser.exercises:
        if not ex["answer"]:
            report.add(path, f"exercise {ex['id']!r} has no .answer")

    cards = path.parent.parent / "cards" / f"{path.stem}.toml"
    if not cards.is_file():
        report.add(path, f"no cards file at {cards.relative_to(root)}")


def check_cards(path: Path, root: Path, sources: set[str], nodes: set[str], report: Report) -> None:
    data = load_toml(path, report)
    if data is None:
        return
    origin = data.get("from")
    if not origin or not (path.parent.parent / origin).is_file():
        report.add(path, f"`from` must name the lesson or reference sheet, relative to the topic (got {origin!r})")
    cards = data.get("card", [])
    if not cards:
        report.add(path, "has no cards")
    seen = set()
    for card in cards:
        cid = card.get("id")
        label = cid or "(card without id)"
        if not cid or not ID.match(cid):
            report.add(path, f"{label}: id must be dash-case")
        elif cid in seen:
            report.add(path, f"{cid}: id used twice")
        seen.add(cid)
        if card.get("kind") not in CARD_KINDS:
            report.add(path, f"{label}: kind must be one of {sorted(CARD_KINDS)}")
        for key in ("front", "back", "loc"):
            if not card.get(key):
                report.add(path, f"{label}: missing {key}")
        if card.get("source") not in sources:
            report.add(path, f"{label}: unknown source {card.get('source')!r}")
        card_nodes = card.get("nodes", [])
        if not card_nodes:
            report.add(path, f"{label}: names no nodes")
        for node in card_nodes:
            if node not in nodes:
                report.add(path, f"{label}: unknown node {node!r}")


def check_topics(root: Path, sources: set[str], nodes: set[str], report: Report) -> None:
    for topic_dir in sorted(p for p in (root / "topics").glob("*") if p.is_dir()):
        topic = topic_dir.name
        if not ID.match(topic):
            report.add(topic_dir, "topic names are dash-case")
        for path in sorted((topic_dir / "lessons").glob("*.html")):
            check_page(path, root, topic, True, sources, nodes, report)
        for path in sorted((topic_dir / "reference").glob("*.html")):
            check_page(path, root, topic, False, sources, nodes, report)
        for path in sorted((topic_dir / "cards").glob("*.toml")):
            check_cards(path, root, sources, nodes, report)


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    report = Report(root)
    vault_file = root / "vault.toml"
    if not vault_file.is_file():
        print(f"{root} is not a vault: no vault.toml", file=sys.stderr)
        return 2
    settings = load_toml(vault_file, report) or {}
    archive_dir = Path(settings["archive_dir"]).expanduser() if settings.get("archive_dir") else None
    if archive_dir and not archive_dir.is_dir():
        report.add(vault_file, f"archive_dir {archive_dir} does not exist")
    if not (root / "assets" / "base" / "lesson.css").is_file():
        report.add(root, "assets/base is missing; run init_vault.py to link it")

    sources = check_sources(root, archive_dir, report)
    nodes = check_map(root, sources, report)
    check_learners(root, nodes, report)
    check_topics(root, sources, nodes, report)

    for problem in report.problems:
        print(problem)
    if report.problems:
        print(f"\n{len(report.problems)} problem(s)")
        return 1
    print("vault ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
