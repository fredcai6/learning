"""The checker against a vault built from the format docs' own examples.

The examples are what the skill copies when it writes a vault, so a vault made
of them must pass, and each rule the checker claims to enforce must fire when
that vault is broken in the matching way.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skill" / "teach"
SCRIPTS = SKILL / "scripts"


def example(doc: str, lang: str, index: int = 0) -> str:
    text = (SKILL / doc).read_text(encoding="utf-8")
    blocks = re.findall(rf"```{lang}\n(.*?)```", text, re.S)
    return blocks[index]


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                          capture_output=True, text=True)


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    archive = tmp_path / "archive"
    assert run("init_vault.py", str(root), "--archive-dir", str(archive)).returncode == 0

    source = example("SOURCE-FORMAT.md", "md")
    (root / "sources" / "hall-2015.md").write_text(source)
    (archive / "hall-2015.pdf").write_bytes(b"%PDF-1.4 stand-in")

    node = example("MAP-FORMAT.md", "md")
    (root / "map" / "matrix-exponential.md").write_text(
        node.replace('helps_with = ["one-parameter-subgroups", "lie-algebra-of-a-matrix-group"]',
                     'helps_with = ["lie-bracket"]'))
    (root / "map" / "lie-bracket.md").write_text(
        '+++\nid = "lie-bracket"\ntitle = "The Lie bracket"\nhelps_with = []\nsources = ["hall-2015"]\n+++\n\nThe commutator.\n')

    (root / "learners.toml").write_text('[learners.alex]\nname = "Alex"\n')
    topic = root / "learners" / "alex" / "lie-algebra"
    (topic / "records").mkdir(parents=True)
    (topic / "MISSION.md").write_text(example("MISSION-FORMAT.md", "md"))
    (topic / "route.toml").write_text(example("MAP-FORMAT.md", "toml"))
    (topic / "records" / "0003-exp-of-nilpotent.md").write_text(
        '+++\nnodes = ["matrix-exponential"]\n+++\n\n# exp of a nilpotent matrix\n\nComputed one.\n')

    lessons = root / "topics" / "lie-algebra" / "lessons"
    lessons.mkdir(parents=True)
    lesson = example("LESSON-FORMAT.md", "html")
    (lessons / "0001-what-a-commutator-measures.html").write_text(lesson)
    (lessons / "0002-the-matrix-exponential.html").write_text(
        lesson.replace("0001-what-a-commutator-measures", "0002-the-matrix-exponential")
              .replace('href="0002-the-matrix-exponential.html"', 'href="0001-what-a-commutator-measures.html"'))

    cards_dir = root / "topics" / "lie-algebra" / "cards"
    cards_dir.mkdir()
    cards = example("CARDS-FORMAT.md", "toml")
    (cards_dir / "0001-what-a-commutator-measures.toml").write_text(cards)
    (cards_dir / "0002-the-matrix-exponential.toml").write_text(
        cards.replace("0001-what-a-commutator-measures", "0002-the-matrix-exponential"))
    return root


def check(root: Path) -> subprocess.CompletedProcess:
    return run("check.py", str(root))


def test_vault_built_from_the_format_examples_passes(vault):
    result = check(vault)
    assert result.returncode == 0, result.stdout
    assert "vault ok" in result.stdout


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    assert old in text, f"{old!r} not in {path.name}"
    path.write_text(text.replace(old, new, 1))


LESSON = "topics/lie-algebra/lessons/0001-what-a-commutator-measures.html"
CARDS = "topics/lie-algebra/cards/0001-what-a-commutator-measures.toml"
ROUTE = "learners/alex/lie-algebra/route.toml"


@pytest.mark.parametrize("path, old, new, expected", [
    (LESSON, 'data-source="hall-2015"', 'data-source="nobody-2020"', "unknown source 'nobody-2020'"),
    (LESSON, '<li id="src-1"', '<li id="src-9"', "citation #src-1 has no matching li"),
    (LESSON, 'class="primary-source"', 'class="aside"', "needs a .primary-source block"),
    (LESSON, '<p class="goal-link">', "<p>", "needs two .goal-link paragraphs"),
    (LESSON, '<script defer src="../../../assets/base/lesson.js"></script>', "<script>alert(1)</script>", "inline <script>"),
    (LESSON, 'content="lie-bracket"', 'content="no-such-node"', "unknown node 'no-such-node'"),
    (LESSON, '<button class="option" data-correct>', '<button class="option">', "needs exactly 1"),
    (LESSON, '<div class="answer">', '<div class="solution">', "has no .answer"),
    (LESSON, 'href="0002-the-matrix-exponential.html"', 'href="0009-missing.html"', "broken link '0009-missing.html'"),
    (LESSON, 'data-id="bracket-2x2"', 'data-id="commuting-bracket"', "used twice"),
    (CARDS, 'source = "hall-2015"', 'source = "nobody-2020"', "unknown source 'nobody-2020'"),
    (CARDS, 'kind = "produce"', 'kind = "guess"', "kind must be one of"),
    (CARDS, 'loc = "Def. 3.1"', 'loc = ""', "missing loc"),
    (CARDS, 'id = "commutator-of-commuting"', 'id = "commutator-definition"', "id used twice"),
    (ROUTE, 'state = "shaky"', 'state = "mastered"', "state must be one of"),
    (ROUTE, 'kind = "knows"', 'kind = "loves"', "connection kind must be one of"),
    (ROUTE, 'evidence = ["0003-exp-of-nilpotent.md"]', 'evidence = ["0099-gone.md"]', "is not a record"),
    ("sources/hall-2015.md", 'trust = "', 'trusted = "', "missing trust"),
    ("sources/hall-2015.md", 'archive = "hall-2015.pdf"', 'archive = "other.pdf"', "is not in"),
    ("map/lie-bracket.md", "helps_with = []", 'helps_with = ["ghost"]', "unknown node 'ghost'"),
])
def test_each_rule_fires(vault, path, old, new, expected):
    edit(vault / path, old, new)
    result = check(vault)
    assert result.returncode == 1
    assert expected in result.stdout, result.stdout


def test_lesson_without_cards_is_reported(vault):
    (vault / CARDS).unlink()
    result = check(vault)
    assert "no cards file" in result.stdout


def test_learner_missing_from_learners_toml_is_reported(vault):
    (vault / "learners.toml").write_text("")
    assert "no entry in learners.toml" in check(vault).stdout


def test_archive_saves_copy_text_and_record(vault, tmp_path):
    record = vault / "sources" / "hall-2015.md"
    record.write_text(re.sub(r"^archive = .*\n", "", record.read_text(), flags=re.M))
    page = tmp_path / "notes.html"
    page.write_text("<html><head><script>x()</script></head><body><nav>menu</nav>"
                    "<h1>Lie brackets</h1><p>The commutator is XY - YX.</p></body></html>")
    result = run("archive.py", "hall-2015", str(page), "--vault", str(vault))
    assert result.returncode == 0, result.stderr
    archive = tmp_path / "archive"
    text = (archive / "hall-2015.txt").read_text()
    assert "The commutator is XY - YX." in text
    assert "x()" not in text and "menu" not in text
    assert 'archive = "hall-2015.html"' in record.read_text()
    # The key landed above the [[timestamps]] table, so it is still top-level.
    assert check(vault).returncode == 0


def test_init_vault_refuses_archive_inside_the_vault(tmp_path):
    result = run("init_vault.py", str(tmp_path / "v"), "--archive-dir", str(tmp_path / "v" / "archive"))
    assert result.returncode != 0
    assert "outside the vault" in result.stderr
