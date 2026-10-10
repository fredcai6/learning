"""A small vault shared by the site and tutor tests."""

from __future__ import annotations

from pathlib import Path

import pytest

LESSON = """<!doctype html><html><head><meta charset="utf-8">
<meta name="lesson-id" content="lie-algebra/0001-rotations"><meta name="nodes" content="so3">
<title>Rotations</title></head><body><main><p>Hi</p></main></body></html>"""

CARDS = """from = "lessons/0001-rotations.html"
[[card]]
id = "orthogonal"
kind = "produce"
front = "What is $R^T R$ for a rotation?"
back = "$I$"
source = "lp"
loc = "§3.2"
nodes = ["so3"]

[[card]]
id = "det"
kind = "recall"
front = "What is $\\\\det R$?"
back = "$1$"
source = "lp"
loc = "§3.2"
nodes = ["so3"]
"""


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "topics/lie-algebra/lessons").mkdir(parents=True)
    (root / "topics/lie-algebra/cards").mkdir(parents=True)
    (root / "topics/lie-algebra/lessons/0001-rotations.html").write_text(LESSON)
    (root / "topics/lie-algebra/cards/0001-rotations.toml").write_text(CARDS)
    (root / "sources").mkdir()
    (root / "sources/lp.md").write_text('+++\nid = "lp"\ntitle = "Modern Robotics"\nkind = "book"\n'
                                        'archive = "lp.pdf"\ntrust = "t"\nuse_for = "u"\n+++\n')
    (root / "map").mkdir()
    (root / "map/so3.md").write_text('+++\nid = "so3"\ntitle = "Rotation matrices"\n+++\n')
    (root / "learners/ann/lie-algebra/records").mkdir(parents=True)
    (root / "learners/ann/lie-algebra/route.toml").write_text(
        'goal = "Read SE(3)"\n[[node]]\nid = "so3"\nstate = "shaky"\nevidence = []\nwhy = "Everything sits on it."\n')
    (root / "learners/ann/lie-algebra/records/0001-knows-matrices.md").write_text(
        '+++\nnodes = ["so3"]\n+++\n\n# Knows matrices\n\nFrom aerospace.\n')
    (root / "learners.toml").write_text('[learners.ann]\nname = "Ann"\nemail = "ann@example.com"\n'
                                        '[learners.bo]\nname = "Bo"\nemail = "bo@example.com"\n')
    (root / "vault.toml").write_text("")
    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "lp.pdf").write_bytes(b"%PDF-1.4 copy")
    (tmp_path / "secret.txt").write_text("outside")
    return root


